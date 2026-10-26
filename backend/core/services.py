import logging
import uuid
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import Account, Order, Outbox, Preview, RecipientState, PaymentAttempt, MessageDelivery, FinancialEvent
from .privacy import digest, encrypt, mask, normalize_phone

logger = logging.getLogger(__name__)
PAYMENT_WINDOW = timedelta(minutes=15)


class APIError(Exception):
    def __init__(self, code, message, status=400, fields=None):
        self.code, self.message, self.status, self.fields = code, message, status, fields


def is_product_authenticated(user):
    return user.is_authenticated and hasattr(user, "account")


def api(methods, authenticated=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return error_response(APIError("method_not_allowed", "روش درخواست مجاز نیست.", 405))
            if authenticated and not is_product_authenticated(request.user):
                return error_response(APIError("authentication_required", "ابتدا شماره خود را تأیید کنید.", 401))
            try:
                result = view(request, *args, **kwargs)
                if isinstance(result, dict):
                    result = JsonResponse(result, json_dumps_params={"ensure_ascii": False})
                result["Cache-Control"] = "no-store"
                return result
            except APIError as exc:
                return error_response(exc)
            except ValueError as exc:
                return error_response(APIError("invalid_input", str(exc)))
        return wrapped
    return decorate


def error_response(exc):
    from .status_reasons import REQUEST_UNAVAILABLE
    error = {"code": exc.code, "message": REQUEST_UNAVAILABLE if exc.status >= 500 else exc.message}
    if exc.fields and exc.status < 500:
        error["fields"] = exc.fields
    response = JsonResponse({"error": error}, status=exc.status, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response


def limited(scope, identity, limit, seconds):
    key = "rate:" + scope + ":" + digest(identity)
    try:
        count = 1 if cache.add(key, 1, timeout=seconds) else cache.incr(key)
    except Exception as exc:
        logger.warning("Rate limiter unavailable")
        raise APIError("service_unavailable", "سرویس موقتاً در دسترس نیست؛ کمی بعد تلاش کنید.", 503) from exc
    if count > limit:
        raise APIError("rate_limited", "تعداد درخواست‌ها زیاد است؛ کمی بعد تلاش کنید.", 429)


def recipient_unavailable():
    # Do not reveal whether a recipient is registered, opted out or in cooldown.
    from .status_reasons import RECIPIENT_LIMIT
    return APIError("recipient_unavailable", RECIPIENT_LIMIT, 409)


def get_owned_order(user, order_id):
    try:
        return Order.objects.get(id=order_id, owner=user)
    except Order.DoesNotExist:
        raise APIError("not_found", "درخواست پیدا نشد.", 404)


def serialize_order(order):
    payment = order.payment_attempts.filter(applied_to_order=True).first() or order.payment_attempts.order_by("-created_at").first()
    delivery = MessageDelivery.objects.filter(order=order).first()
    from .models import Refund
    open_refund = Refund.objects.filter(payment__order=order).exclude(status="refunded").exists()
    from .status_reasons import order_status_reason
    event = Outbox.objects.filter(order=order).first()
    return {"financial_status": ("free_credit_returned" if order.free_credit_released_at else "free") if order.is_free else "refunded" if payment and payment.refunds.filter(status="refunded").exists() else "refund_pending" if open_refund else payment.status if payment else "legacy_demo_paid" if order.paid_at else "unpaid",
        "status_reason": order_status_reason(order, delivery, event),
        "delivery_status": delivery.status if delivery else "not_ready","id": str(order.id), "status": order.status, "amount_toman": order.amount_toman,
        "payment_mode": order.payment_mode, "recipient_masked": order.recipient_masked, "is_free": order.is_free,
        "text": order.full_sms or order.text, "category": order.category, "paid_at": order.paid_at.isoformat() if order.paid_at else None,
        "created_at": order.created_at.isoformat(), "payment_expires_at": (order.created_at + PAYMENT_WINDOW).isoformat()}


def create_order(user, session_key, data, idempotency_key):
    try:
        key = uuid.UUID(idempotency_key)
        preview_id = uuid.UUID(str(data.get("preview_id", "")))
    except (ValueError, TypeError, AttributeError):
        raise APIError("invalid_input", "شناسه پیش‌نمایش و کلید یکتای درخواست معتبر نیست.")
    phone = normalize_phone(data.get("recipient_phone"))
    phone_hash = digest(phone)
    now = timezone.now()
    with transaction.atomic():
        # Serializes quota/idempotency checks for a sender across all workers.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        previous = Order.objects.filter(owner=user, idempotency_key=key).first()
        if previous:
            if previous.preview_id != preview_id or previous.recipient_hash != phone_hash:
                raise APIError("idempotency_conflict", "این کلید برای درخواست دیگری استفاده شده است.", 409)
            return previous
        from .safety import ensure_open
        ensure_open()
        if user.account.suspended or user.account.deletion_requested_at:
            raise APIError("account_unavailable", "این حساب فعلاً اجازه ارسال ندارد.", 403)
        from .demo_limits import unlimited_demo_sends
        unlimited = unlimited_demo_sends(user)
        if not unlimited:
            limited("orders", str(user.pk), 10, 60)
        if user.account.phone_hash == phone_hash:
            raise APIError("self_recipient", "شمارهٔ گیرنده باید با شمارهٔ خودت متفاوت باشد.", 409)
        try:
            preview = Preview.objects.select_for_update().get(id=preview_id)
        except Preview.DoesNotExist:
            raise APIError("preview_expired", "پیش‌نمایش معتبر نیست؛ دوباره متن را آماده کنید.", 409)
        if preview.owner_id != user.pk and not (preview.owner_id is None and preview.session_key == session_key):
            raise APIError("not_found", "پیش‌نمایش پیدا نشد.", 404)
        if preview.recipient_hash and preview.recipient_hash != phone_hash:
            raise APIError("quote_recipient_changed", "شماره عوض شده؛ پیش‌نمایش تازه بساز.", 409)
        if preview.moderation_mode == 'gapgpt':
            from .freeform import validate_preview
            from .moderation import ModerationRejected
            try:
                validate_preview(preview, recipient_hash=phone_hash)
            except ModerationRejected:
                raise APIError('preview_expired', 'متن نهایی معتبر نیست؛ دوباره آماده‌اش کن.', 409) from None
        consent = data.get("consent") is True and data.get("terms_version") == preview.terms_version
        if settings.PROVIDER_NETWORK_MODE == "external" and preview.terms_version != settings.TERMS_VERSION:
            raise APIError("preview_expired", "شرایط ارسال تغییر کرده؛ متن نهایی را دوباره آماده کن.", 409)
        if settings.PROVIDER_NETWORK_MODE == "external" and not consent:
            raise APIError("consent_required", "نسخه شرایط و رضایت ارسال را پیش از خرید تأیید کن.", 422)
        if preview.expires_at <= now or Order.objects.filter(preview=preview).exists():
            raise APIError("preview_expired", "پیش‌نمایش منقضی یا استفاده شده است؛ دوباره متن را آماده کنید.", 409)
        if not preview.is_free and not settings.DEMO_MODE and settings.PAYMENT_BACKEND != "zarinpal":
            raise APIError("payment_disabled", "۳ ارسال هدیه تمام شده؛ ارسال پولی فعلاً بسته است.", 409)
        from .demo_limits import quota_start, recipient_in_cooldown
        sender_start = quota_start(now, hours=24, sender=user)
        sender_orders = Order.objects.filter(owner=user, created_at__gte=sender_start)
        if not settings.DEMO_MODE:
            sender_orders = sender_orders.exclude(status=Order.Status.DELIVERED_DEMO)
        if not unlimited and sender_orders.count() >= settings.SENDER_DAILY_LIMIT:
            raise APIError("daily_limit", f"سقف {settings.SENDER_DAILY_LIMIT} درخواست در ۲۴ ساعت شما تکمیل شده است؛ بعد از گذشت این بازه دوباره تلاش کن.", 429)
        RecipientState.objects.get_or_create(phone_hash=phone_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=phone_hash)
        busy = Order.objects.filter(recipient_hash=phone_hash).filter(
            models_busy_query(now)
        ).exists()
        from .models import InvitationSend
        busy = busy or InvitationSend.objects.filter(invitation__phone_hash=phone_hash,
            status__in=['pending', 'submitting', 'unknown']).exists()
        pair_start = quota_start(now, hours=settings.SENDER_RECIPIENT_COOLDOWN_HOURS, sender=user, recipient_hash=phone_hash)
        sent_statuses = [Order.Status.ACCEPTED, Order.Status.DELIVERED, Order.Status.UNKNOWN]
        if settings.DEMO_MODE:
            sent_statuses.append(Order.Status.DELIVERED_DEMO)
        if not unlimited and Order.objects.filter(owner=user, recipient_hash=phone_hash, status__in=sent_statuses,
                updated_at__gte=pair_start).exists():
            raise APIError("pair_cooldown", f"بین ارسال‌های شما به همین شماره باید {settings.SENDER_RECIPIENT_COOLDOWN_HOURS} ساعت فاصله باشد؛ بعد از گذشت این زمان دوباره تلاش کن.", 409)
        if state.blocked or busy or recipient_in_cooldown(state, now, sender=user):
            raise recipient_unavailable()
        if preview.is_free:
            from django.db.models import F
            if not Account.objects.filter(user=user, free_sends_remaining__gt=0).update(free_sends_remaining=F("free_sends_remaining")-1):
                raise APIError("free_quota_changed", "سهمیهٔ رایگان تغییر کرده؛ متن نهایی و هزینه را دوباره آماده کن.", 409)
        return Order.objects.create(owner=user, preview=preview, idempotency_key=key,
            consent_at=now if consent else None, terms_version=preview.terms_version if consent else "",
            recipient_hash=phone_hash, recipient_cipher=encrypt(phone), recipient_masked=mask(phone),
            text=preview.text, full_sms=preview.full_sms, category=preview.category, amount_toman=preview.price_toman,
            is_free=preview.is_free, payment_mode="free" if preview.is_free else "demo" if settings.DEMO_MODE else "disabled")


def models_busy_query(now):
    from django.db.models import Q
    return Q(status__in=[Order.Status.QUEUED, Order.Status.ACCEPTED, Order.Status.UNKNOWN]) | Q(status=Order.Status.AWAITING_PAYMENT, created_at__gt=now - PAYMENT_WINDOW)


def pay_order(user, order_id):
    if not settings.DEMO_MODE or settings.PAYMENT_BACKEND != "demo":
        raise APIError("payment_disabled", "پرداخت واقعی هنوز فعال نشده است.", 503)
    from .safety import ensure_open
    ensure_open()
    now = timezone.now()
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(id=order_id, owner=user)
        except Order.DoesNotExist:
            raise APIError("not_found", "درخواست پیدا نشد.", 404)
        if order.is_free:
            return confirm_free_order(user, order_id)
        if order.paid_at:
            return order
        if order.status != Order.Status.AWAITING_PAYMENT or order.created_at + PAYMENT_WINDOW <= now:
            raise APIError("payment_expired", "زمان پرداخت آزمایشی تمام شده است؛ دوباره درخواست بسازید.", 409)
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        from .demo_limits import recipient_in_cooldown
        if state.blocked or recipient_in_cooldown(state, now, sender=user):
            raise recipient_unavailable()
        order.status = Order.Status.QUEUED
        order.paid_at = now
        order.save(update_fields=["status", "paid_at", "updated_at"])
        payment, _ = PaymentAttempt.objects.get_or_create(order=order, applied_to_order=True,
            defaults={"amount_toman": order.amount_toman, "status": "verified", "provider_reference": f"demo-payment-{order.id}"})
        FinancialEvent.objects.get_or_create(payment=payment, kind="payment",
            defaults={"amount_toman": payment.amount_toman})
        MessageDelivery.objects.get_or_create(order=order, defaults={"status": "queued"})
        event, _ = Outbox.objects.get_or_create(order=order, defaults={"available_at": now})
        transaction.on_commit(lambda: dispatch(event.pk))
    order.refresh_from_db()
    return order


def dispatch(event_id):
    from .tasks import deliver_message
    try:
        deliver_message.delay(event_id)
    except Exception:
        # The committed outbox remains pending. Beat/management command retries it.
        logger.warning("Outbox publish deferred event=%s", event_id)


def record_demo_refund(order, reason):
    """Called inside the worker transaction; repeated tasks never refund twice."""
    from .models import PaymentAttempt, Refund, FinancialEvent
    if order.is_free:
        release_free_credit(order)
        return
    payment = PaymentAttempt.objects.filter(order=order, applied_to_order=True).first()
    if payment:
        if payment.provider != "demo":
            from .provider_services import request_refund
            request_refund(payment, reason)
            return
        refund, _ = Refund.objects.get_or_create(payment=payment,
            defaults={"reason_code": reason, "amount_toman": payment.amount_toman, "status": "refunded"})
        if refund.status != "refunded":
            refund.status = "refunded"
            refund.save(update_fields=["status", "updated_at"])
        FinancialEvent.objects.get_or_create(refund=refund,
            defaults={"payment": payment, "kind": "refund", "amount_toman": refund.amount_toman})


def release_free_credit(order):
    """Caller holds the order lock in a transaction; a definitive failure returns once."""
    from django.db.models import F
    if order.is_free and not order.free_credit_released_at:
        order.free_credit_released_at = timezone.now()
        order.save(update_fields=["free_credit_released_at"])
        Account.objects.filter(user_id=order.owner_id).update(free_sends_remaining=F("free_sends_remaining")+1)


def confirm_free_order(user, order_id):
    from .safety import ensure_open
    from .demo_limits import recipient_in_cooldown
    ensure_open()
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id, owner=user).first()
        if not order:
            raise APIError("not_found", "درخواست پیدا نشد.", 404)
        if not order.is_free or order.amount_toman != 0:
            raise APIError("free_order_required", "این سفارش از سهمیهٔ رایگان نیست.", 409)
        if order.paid_at:
            return order
        if order.status != Order.Status.AWAITING_PAYMENT or order.created_at + PAYMENT_WINDOW <= timezone.now():
            raise APIError("order_expired", "مهلت سفارش تمام شده؛ متن نهایی را دوباره آماده کن.", 409)
        if user.account.suspended or user.account.deletion_requested_at:
            raise APIError("account_unavailable", "این حساب فعلاً اجازه ارسال ندارد.", 403)
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        if state.blocked or recipient_in_cooldown(state, timezone.now(), sender=user):
            raise recipient_unavailable()
        demo = settings.DEMO_MODE and settings.SMS_BACKEND == "console"
        live = (not settings.DEMO_MODE and settings.SMS_BACKEND == "kavenegar"
                and settings.PROVIDER_NETWORK_MODE == "external" and settings.LIVE_PROVIDERS_ENABLED)
        if not demo and not live:
            raise APIError("sms_disabled", "ارسال پیام فعلاً فعال نیست.", 503)
        if live and (not order.consent_at or order.terms_version != settings.TERMS_VERSION):
            raise APIError("preview_expired", "شرایط ارسال تغییر کرده؛ متن نهایی را دوباره آماده کن.", 409)
        # paid_at is the existing dispatch authorization timestamp; there is no payment.
        order.paid_at, order.status = timezone.now(), Order.Status.QUEUED
        order.save(update_fields=["paid_at", "status", "updated_at"])
        defaults = {"status": "queued"}
        if live:
            defaults.update(provider="kavenegar", environment=settings.PROVIDER_ENVIRONMENT,
                            local_id=(uuid.uuid4().int % (2**63-1)) or 1)
        MessageDelivery.objects.get_or_create(order=order, defaults=defaults)
        event, _ = Outbox.objects.get_or_create(order=order, defaults={"available_at": timezone.now()})
        transaction.on_commit(lambda: dispatch(event.pk))
    return order
