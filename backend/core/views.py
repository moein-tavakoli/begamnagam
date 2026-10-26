import hmac
import json
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.core.cache import cache
from django.db import connection, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import services
from .models import Account, ModerationAudit, OTPChallenge, Order, Preview, RecipientState
from .moderation import CATEGORIES, ModerationRejected, RewriteUnavailable, rewrite
from .privacy import DIGITS, decrypt, digest, encrypt, mask, normalize_phone
from .services import APIError, api, is_product_authenticated, limited
from .sms import compose_recipient_sms, SMSTooLong

logger = logging.getLogger(__name__)


def otp_failure_reason(error):
    reason = str(error)
    known = {'tls_certificate_verification_failed', 'provider_connection_failed',
        'daily_budget_exhausted', 'provider_cost_halt', 'cost_ceiling_missing',
        'missing_sms_key', 'invalid_otp_configuration', 'outside_pilot_allowlist',
        'provider_network_disabled', 'local_real_otp_scope_violation',
        'http_uncertain', 'transport_or_format', 'sms_unknown_response',
        'sms_ambiguous_entries', 'sms_unbound_response', 'sms_delivery_failed', 'sms_delivery_unknown'}
    if reason in known or (reason.startswith('sms_rejected_') and len(reason) == 16 and reason[-3:].isdigit()):
        return reason
    return 'provider_failure'


def body(request):
    if request.content_type != "application/json":
        raise APIError("invalid_input", "بدنه درخواست باید JSON باشد.", 415)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise APIError("invalid_input", "ساختار درخواست معتبر نیست.")
    if not isinstance(data, dict):
        raise APIError("invalid_input", "ساختار درخواست معتبر نیست.")
    return data


def session_key(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


@api(["GET"])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        cache.set("healthcheck", "ok", 5)
        if cache.get("healthcheck") != "ok":
            raise RuntimeError()
    except Exception:
        raise APIError("not_ready", "سرویس آماده نیست.", 503)
    value = {"status": "ok", "demo_mode": settings.DEMO_MODE, "otp_is_real": otp_is_real()}
    if settings.BENCHMARK_RUN_ID: value["benchmark_run_id"] = settings.BENCHMARK_RUN_ID
    return value


@ensure_csrf_cookie
@api(["GET"])
def bootstrap(request):
    session_key(request)
    authenticated = is_product_authenticated(request.user)
    data = {"demo_mode": settings.DEMO_MODE, "authenticated": authenticated,
        "price_toman": settings.PRICE_TOMAN, "categories": [c for c in CATEGORIES if not settings.PILOT_POSITIVE_ONLY or c["id"] in {"appreciation", "encouragement", "congratulations"}], "rewrite_mode": settings.AI_MODE, "payment_backend": settings.PAYMENT_BACKEND, "support_contact": settings.SUPPORT_CONTACT,
        "otp_is_real": otp_is_real()}
    if authenticated:
        data["free_sends_remaining"] = request.user.account.free_sends_remaining
        data["free_sends_total"] = 3 + request.user.account.free_sends_earned_total
        data["free_sends_earned_total"] = request.user.account.free_sends_earned_total
        data["recent_auth"] = timezone.now().timestamp() - request.session.get("phone_verified_at", 0) <= 300
        data["session_identity"] = digest("session-identity:" + request.session.session_key)
        data["phone_masked"] = request.user.account.phone_masked
        data["recipient_blocked"] = RecipientState.objects.filter(phone_hash=request.user.account.phone_hash, blocked=True).exists()
    return data


def otp_is_real():
    return settings.OTP_BACKEND == 'kavenegar' and (settings.LOCAL_REAL_OTP_ENABLED or settings.PROVIDER_NETWORK_MODE == 'external')


@api(["POST"])
def request_otp(request):
    data = body(request)
    phone = normalize_phone(data.get("phone"))
    phone_hash = digest(phone)
    limited("otp-ip-flood", request.META.get("REMOTE_ADDR", "unknown"), 1000, 600)
    limited("otp-session", session_key(request), 6, 600)
    limited("otp-phone", phone_hash, 3, 600)
    now = timezone.now()
    if OTPChallenge.objects.filter(phone_hash=phone_hash, created_at__gt=now - timedelta(minutes=10)).count() >= 3:
        raise APIError("rate_limited", "کمی بعد دوباره برای کد تأیید تلاش کنید.", 429)
    demo_otp = settings.DEMO_MODE and settings.OTP_BACKEND == "demo" and settings.SMS_BACKEND == "console"
    if not demo_otp and settings.OTP_BACKEND != "kavenegar":
        raise APIError("sms_disabled", "ارسال کد فعلاً فعال نیست.", 503)
    code = f"{secrets.randbelow(1000000):06}"
    challenge_id = uuid.uuid4()
    OTPChallenge.objects.create(id=challenge_id, phone_hash=phone_hash, phone_cipher=encrypt(phone),
        code_digest=digest(f"otp:{challenge_id}:{code}"), session_key=session_key(request),
        expires_at=now + timedelta(minutes=5))
    if demo_otp:
        return {"challenge_id": str(challenge_id), "debug_code": code, "demo_mode": True, "expires_in": 300}
    from .providers import Kavenegar, ProviderDisabled, ProviderUnknown, ProviderRejected
    from .budget import reserve_cost
    delivery_status = 'accepted'
    try:
        reserve_cost('otp:' + str(challenge_id), 'otp', settings.OTP_MAX_COST_RIAL)
        result = Kavenegar().otp(phone=phone, code=code)
        from .budget import observe_cost
        observe_cost("otp:" + str(challenge_id), result.cost_rial)
        if result.status == 'failed':
            raise ProviderRejected('sms_delivery_failed')
        if result.status not in {'accepted', 'delivered'}:
            raise ProviderUnknown('sms_delivery_unknown')
    except (ProviderRejected, ProviderDisabled) as error:
        reason = otp_failure_reason(error)
        logger.warning('OTP unavailable request_id=%s reason=%s', request.public_request_id, reason)
        OTPChallenge.objects.filter(pk=challenge_id).update(consumed_at=timezone.now())
        message = ('ارتباط امن با سرویس پیامک برقرار نشد؛ تنظیمات اتصال سرور باید بررسی شود.'
            if reason == 'tls_certificate_verification_failed' else 'ارسال کد فعلاً ممکن نیست؛ کمی بعد تلاش کن.')
        raise APIError('otp_unavailable', message, 503) from None
    except ProviderUnknown as error:
        # The OTP may arrive; retain this challenge and never expose its code.
        delivery_status = 'unknown'
        logger.warning('OTP outcome unknown request_id=%s reason=%s', request.public_request_id, otp_failure_reason(error))
    else:
        logger.info('OTP provider accepted request_id=%s reference=%s', request.public_request_id, result.reference)
    return {"challenge_id": str(challenge_id), "demo_mode": False, "expires_in": 300, "delivery_status": delivery_status}


@api(["POST"])
def verify_otp(request):
    data = body(request)
    try:
        challenge_id = uuid.UUID(str(data.get("challenge_id", "")))
    except (ValueError, AttributeError):
        raise APIError("invalid_otp", "کد تأیید معتبر نیست.", 400)
    code = data.get("code", "")
    if not isinstance(code, str):
        raise APIError("invalid_otp", "کد تأیید معتبر نیست.")
    code = code.translate(DIGITS).strip()
    limited("otp-verify-session", session_key(request), 30, 600)
    invalid = False
    with transaction.atomic():
        try:
            challenge = OTPChallenge.objects.select_for_update().get(id=challenge_id)
        except OTPChallenge.DoesNotExist:
            raise APIError("invalid_otp", "کد تأیید معتبر نیست.")
        if challenge.session_key != request.session.session_key or challenge.consumed_at or challenge.expires_at <= timezone.now() or challenge.attempts >= 5:
            raise APIError("invalid_otp", "کد تأیید معتبر نیست یا منقضی شده است.")
        challenge.attempts += 1
        if len(code) != 6 or not hmac.compare_digest(challenge.code_digest, digest(f"otp:{challenge.id}:{code}")):
            challenge.save(update_fields=["attempts"])
            invalid = True
        else:
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=["attempts", "consumed_at"])
            phone = decrypt(challenge.phone_cipher)
            from .invitations import lock_phone, record_registration
            lock_phone(challenge.phone_hash)
            user, created = get_user_model().objects.get_or_create(username="phone_" + challenge.phone_hash)
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            account, account_created = Account.objects.get_or_create(user=user, defaults={"phone_hash": challenge.phone_hash,
                "phone_cipher": challenge.phone_cipher, "phone_masked": mask(phone)})
            if account_created and user.is_active:
                record_registration(account)
            challenge.phone_cipher = ""
            challenge.code_digest = ""
            challenge.save(update_fields=["phone_cipher", "code_digest"])
            if not user.is_active:
                invalid = True
    if invalid:
        raise APIError("invalid_otp", "کد تأیید معتبر نیست.")
    old_session = request.session.session_key
    login(request, user)
    # Switching from a different authenticated account flushes the old session.
    # Create the new key now rather than waiting for SessionMiddleware.save().
    new_session = session_key(request)
    request.session["phone_verified_at"] = timezone.now().timestamp()
    Preview.objects.filter(session_key=old_session, owner__isnull=True).update(owner=user, session_key=new_session)
    return {"authenticated": True, "phone_masked": user.account.phone_masked, "recent_auth": True}


@api(["POST"], authenticated=True)
def logout_view(request):
    logout(request)
    return {"authenticated": False}


@api(["POST"])
def preview(request):
    data = body(request)
    owner = request.user if is_product_authenticated(request.user) else None
    from .demo_limits import unlimited_demo_sends
    unlimited = unlimited_demo_sends(owner)
    if not unlimited:
        limited("preview-session", session_key(request), 20, 600)
    limited("preview-ip-flood", request.META.get("REMOTE_ADDR", "unknown"), 10000, 600)
    category = data.get("category")
    text = data.get("text", "")
    if not isinstance(category, str):
        raise APIError("invalid_input", "دسته‌بندی معتبر را انتخاب کنید.")
    if settings.PILOT_POSITIVE_ONLY and category not in {"appreciation", "encouragement", "congratulations"}:
        raise APIError("category_unavailable", "این موضوع فعلاً فعال نیست.", 422)
    if owner and not unlimited:
        limited("preview-user", str(owner.pk), 20, 600)
    direct = bool(owner and owner.account.direct_message_tone)
    try:
        rewritten, mode = rewrite(category, text, direct=direct)
    except ModerationRejected as exc:
        ModerationAudit.objects.create(owner=owner, category=category[:32], outcome="rejected", reason_code=str(exc), content_digest=digest(str(text)))
        raise APIError("moderation_rejected", "این متن قابل ارسال نیست. لطفاً موضوعی محترمانه و بدون توهین، تهدید یا اطلاعات شخصی انتخاب کنید.", 422)
    except RewriteUnavailable:
        raise APIError("rewrite_unavailable", "آماده‌سازی متن موقتاً در دسترس نیست؛ کمی بعد تلاش کنید.", 503)
    recipient_hash = ""
    if data.get("recipient_phone"):
        if not owner:
            raise APIError("authentication_required", "ابتدا شماره خودت را تأیید کن.", 401)
        recipient_hash = digest(normalize_phone(data["recipient_phone"]))
        if recipient_hash == owner.account.phone_hash:
            raise APIError("self_recipient", "شمارهٔ گیرنده باید با شمارهٔ خودت متفاوت باشد.", 422)
    expires_at = timezone.now() + timedelta(minutes=15)
    is_free = bool(owner and owner.account.free_sends_remaining > 0)
    with transaction.atomic():
        item = Preview.objects.create(owner=owner, session_key=session_key(request), category=category,
            text=rewritten, recipient_hash=recipient_hash, terms_version=settings.TERMS_VERSION, moderation_mode=mode, expires_at=expires_at, is_free=is_free, price_toman=0 if is_free else settings.PRICE_TOMAN)
        token = ""
        if recipient_hash:
            from .recipient import issue_grant
            token = issue_grant(item, recipient_hash)
        sms_origin = settings.APP_BASE_URL.removeprefix("https://").removeprefix("http://")
        try:
            item.text, full_sms = compose_recipient_sms(category, rewritten, sms_origin, token, direct=direct)
        except SMSTooLong:
            raise APIError("message_too_long", "متن نهایی بیش از سه بخش پیامک است؛ موضوع دیگری انتخاب کن.", 422)
        item.full_sms = full_sms
        item.save(update_fields=["text", "full_sms"])
    ModerationAudit.objects.create(owner=owner, category=category, outcome="accepted", reason_code=mode + ("_direct" if direct else ""), content_digest=digest(str(text)))
    return {"preview_id": str(item.id), "rewritten_text": item.text, "price_toman": item.price_toman, "is_free": item.is_free,
        "message_tone": "direct" if direct else "gentle",
        "expires_at": expires_at.isoformat(), "moderation_mode": mode, "terms_version": item.terms_version, "full_sms": item.full_sms, "sms_segments": 1 if len(full_sms.encode("utf-16-le")) // 2 <= 70 else (len(full_sms.encode("utf-16-le")) // 2 + 66) // 67}


@api(["POST"], authenticated=True)
def create_order(request):
    order = services.create_order(request.user, request.session.session_key, body(request), request.headers.get("Idempotency-Key", ""))
    return services.serialize_order(order)


@api(["POST"], authenticated=True)
def pay_demo(request, order_id):
    return services.serialize_order(services.pay_order(request.user, order_id))


@api(["POST"], authenticated=True)
def confirm_free(request, order_id):
    return services.serialize_order(services.confirm_free_order(request.user, order_id))


@api(["GET"], authenticated=True)
def order_detail(request, order_id):
    return services.serialize_order(services.get_owned_order(request.user, order_id))


@api(["GET"], authenticated=True)
def messages(request):
    return {"results": [services.serialize_order(order) for order in Order.objects.filter(owner=request.user).order_by("-created_at")[:100]]}


@api(["GET", "POST"], authenticated=True)
def preferences(request):
    if not hasattr(request.user, "account"):
        raise APIError("authentication_required", "ابتدا شماره خود را تأیید کنید.", 401)
    phone_hash = request.user.account.phone_hash
    if request.method == "POST":
        value = body(request).get("blocked")
        if type(value) is not bool:
            raise APIError("invalid_input", "وضعیت دریافت پیام باید بله یا خیر باشد.")
        if value is False and timezone.now().timestamp() - request.session.get("phone_verified_at", 0) > 300:
            raise APIError("reauthentication_required", "برای فعال‌سازی دوباره، شماره خودت را مجدداً تأیید کن.", 403)
        with transaction.atomic():
            RecipientState.objects.get_or_create(phone_hash=phone_hash)
            state = RecipientState.objects.select_for_update().get(phone_hash=phone_hash)
            state.blocked = value
            state.save(update_fields=["blocked", "updated_at"])
        return {"blocked": value}
    return {"blocked": RecipientState.objects.filter(phone_hash=phone_hash, blocked=True).exists()}


def csrf_failure(request, reason=""):
    return services.error_response(APIError("csrf_failed", "نشست معتبر نیست؛ صفحه را تازه کنید و دوباره تلاش کنید.", 403))


def not_found(request, exception=None):
    return services.error_response(APIError("not_found", "درخواست پیدا نشد.", 404))


def server_error(request):
    return services.error_response(APIError("service_unavailable", "سرویس موقتاً در دسترس نیست؛ کمی بعد تلاش کنید.", 500))


@api(["POST"], authenticated=True)
def begin_payment(request, order_id):
    from .provider_services import begin_payment as begin
    body(request)
    return begin(request.user, order_id, request.headers.get('Idempotency-Key', ''))


@api(["GET"])
def payment_return(request):
    from .models import PaymentAttempt
    from .tasks import verify_provider_payment
    from django.http import HttpResponseRedirect
    authority = request.GET.get('Authority', '')
    if len(authority) > 128:
        authority = ''
    # Status/query parameters never prove payment, and no session is trusted here.
    attempt = PaymentAttempt.objects.filter(provider='zarinpal', authority=authority).exclude(authority='').first()
    if attempt:
        limited('callback', str(attempt.pk), 10, 60)
        try:
            verify_provider_payment.delay(str(attempt.pk))
        except Exception:
            pass  # Independent reconciler will verify the durable attempt.
    return HttpResponseRedirect(settings.APP_BASE_URL + '/history?payment_return=1')


@api(["POST"])
def recipient_action(request, action):
    from . import recipient
    data = body(request)
    token = data.get('token')
    # Token is in JSON only, never request paths/query/access logs.
    limited('recipient-action-session', session_key(request), 30, 600)
    limited('recipient-action-ip', request.META.get('REMOTE_ADDR', 'unknown'), 120, 600)
    limited('recipient-action-token', digest(str(token)[:100]), 30, 600)
    if action == 'inspect': return recipient.inspect(token)
    if action == 'stop': return recipient.stop(token)
    if action == 'report': return recipient.report(token, data.get('reason'), data.get('details', ''))
    raise APIError('not_found', 'درخواست پیدا نشد.', 404)


@api(["POST"], authenticated=True)
def request_deletion(request):
    body(request)
    if timezone.now().timestamp() - request.session.get('phone_verified_at', 0) > 300:
        raise APIError('reauthentication_required', 'برای درخواست حذف، شماره خودت را مجدداً تأیید کن.', 403)
    from .models import OperatorAudit
    with transaction.atomic():
        account = Account.objects.select_for_update().get(user=request.user)
        if not account.deletion_requested_at:
            account.deletion_requested_at = timezone.now()
            account.suspended = True
            account.save(update_fields=['deletion_requested_at', 'suspended'])
            OperatorAudit.objects.create(actor=request.user, action='account_delete_requested', object_id=str(account.pk), reason='verified_owner_request')
    return {'requested': True, 'redaction_within_days': 30}


@api(["GET"])
def operations_status(request):
    if not request.user.is_active or not request.user.is_staff or not request.user.has_perm('core.view_operations'):
        raise APIError('forbidden', 'مجوز مشاهده عملیات را ندارید.', 403)
    from .safety import snapshot
    return snapshot()
