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

from .models import Order, Outbox, Preview, RecipientState, PaymentAttempt, MessageDelivery, FinancialEvent
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
    error = {"code": exc.code, "message": exc.message}
    if exc.fields:
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
    return APIError("recipient_unavailable", "در حال حاضر امکان ارسال به این شماره وجود ندارد. هزینه‌ای دریافت نشده است.", 409)


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
    return {"financial_status": "refunded" if payment and payment.refunds.filter(status="refunded").exists() else "refund_pending" if open_refund else payment.status if payment else "legacy_demo_paid" if order.paid_at else "unpaid",
        "delivery_status": delivery.status if delivery else "not_ready","id": str(order.id), "status": order.status, "amount_toman": order.amount_toman,
        "payment_mode": order.payment_mode, "recipient_masked": order.recipient_masked,
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
        limited("orders", str(user.pk), 10, 60)
        if user.account.phone_hash == phone_hash:
            raise recipient_unavailable()
        try:
            preview = Preview.objects.select_for_update().get(id=preview_id)
        except Preview.DoesNotExist:
            raise APIError("preview_expired", "پیش‌نمایش معتبر نیست؛ دوباره متن را آماده کنید.", 409)
        if preview.owner_id != user.pk and not (preview.owner_id is None and preview.session_key == session_key):
            raise APIError("not_found", "پیش‌نمایش پیدا نشد.", 404)
        if preview.recipient_hash and preview.recipient_hash != phone_hash:
            raise APIError("quote_recipient_changed", "شماره عوض شده؛ پیش‌نمایش تازه بساز.", 409)
        consent = data.get("consent") is True and data.get("terms_version") == preview.terms_version
        if settings.PROVIDER_NETWORK_MODE == "external" and not consent:
            raise APIError("consent_required", "نسخه شرایط و رضایت ارسال را پیش از خرید تأیید کن.", 422)
        if preview.expires_at <= now or Order.objects.filter(preview=preview).exists():
            raise APIError("preview_expired", "پیش‌نمایش منقضی یا استفاده شده است؛ دوباره متن را آماده کنید.", 409)
        if Order.objects.filter(owner=user, created_at__gte=now - timedelta(hours=24)).count() >= settings.SENDER_DAILY_LIMIT:
            raise APIError("daily_limit", "سقف درخواست‌های روزانه شما تکمیل شده است.", 429)
        RecipientState.objects.get_or_create(phone_hash=phone_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=phone_hash)
        busy = Order.objects.filter(recipient_hash=phone_hash).filter(
            models_busy_query(now)
        ).exists()
        if Order.objects.filter(owner=user, recipient_hash=phone_hash, status__in=[Order.Status.DELIVERED_DEMO, Order.Status.ACCEPTED, Order.Status.DELIVERED, Order.Status.UNKNOWN],
                updated_at__gte=now - timedelta(days=30)).exists():
            raise recipient_unavailable()
        if state.blocked or busy or (state.last_sent_at and state.last_sent_at > now - timedelta(hours=settings.RECIPIENT_COOLDOWN_HOURS)):
            raise recipient_unavailable()
        return Order.objects.create(owner=user, preview=preview, idempotency_key=key,
            consent_at=now if consent else None, terms_version=preview.terms_version if consent else "",
            recipient_hash=phone_hash, recipient_cipher=encrypt(phone), recipient_masked=mask(phone),
            text=preview.text, full_sms=preview.full_sms, category=preview.category, amount_toman=preview.price_toman,
            payment_mode="demo" if settings.DEMO_MODE else "disabled")


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
        if order.paid_at:
            return order
        if order.status != Order.Status.AWAITING_PAYMENT or order.created_at + PAYMENT_WINDOW <= now:
            raise APIError("payment_expired", "زمان پرداخت آزمایشی تمام شده است؛ دوباره درخواست بسازید.", 409)
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        if state.blocked or (state.last_sent_at and state.last_sent_at > now - timedelta(hours=settings.RECIPIENT_COOLDOWN_HOURS)):
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
