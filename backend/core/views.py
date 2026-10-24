import hmac
import json
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
    return {"status": "ok", "demo_mode": settings.DEMO_MODE}


@ensure_csrf_cookie
@api(["GET"])
def bootstrap(request):
    session_key(request)
    authenticated = is_product_authenticated(request.user)
    data = {"demo_mode": settings.DEMO_MODE, "authenticated": authenticated,
        "price_toman": settings.PRICE_TOMAN, "categories": CATEGORIES, "rewrite_mode": settings.AI_MODE}
    if authenticated:
        data["phone_masked"] = request.user.account.phone_masked
        data["recipient_blocked"] = RecipientState.objects.filter(phone_hash=request.user.account.phone_hash, blocked=True).exists()
    return data


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
    if not settings.DEMO_MODE or settings.SMS_BACKEND != "console":
        raise APIError("sms_disabled", "ارسال کد واقعی هنوز فعال نشده است.", 503)
    code = f"{secrets.randbelow(1000000):06}"
    challenge_id = uuid.uuid4()
    OTPChallenge.objects.create(id=challenge_id, phone_hash=phone_hash, phone_cipher=encrypt(phone),
        code_digest=digest(f"otp:{challenge_id}:{code}"), session_key=session_key(request),
        expires_at=now + timedelta(minutes=5))
    return {"challenge_id": str(challenge_id), "debug_code": code, "demo_mode": True, "expires_in": 300}


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
            user, created = get_user_model().objects.get_or_create(username="phone_" + challenge.phone_hash)
            if created:
                user.set_unusable_password()
                user.save(update_fields=["password"])
            Account.objects.get_or_create(user=user, defaults={"phone_hash": challenge.phone_hash,
                "phone_cipher": challenge.phone_cipher, "phone_masked": mask(phone)})
            if not user.is_active:
                invalid = True
    if invalid:
        raise APIError("invalid_otp", "کد تأیید معتبر نیست.")
    old_session = request.session.session_key
    login(request, user)
    # Switching from a different authenticated account flushes the old session.
    # Create the new key now rather than waiting for SessionMiddleware.save().
    new_session = session_key(request)
    Preview.objects.filter(session_key=old_session, owner__isnull=True).update(owner=user, session_key=new_session)
    return {"authenticated": True, "phone_masked": user.account.phone_masked}


@api(["POST"], authenticated=True)
def logout_view(request):
    logout(request)
    return {"authenticated": False}


@api(["POST"])
def preview(request):
    data = body(request)
    limited("preview-session", session_key(request), 20, 600)
    limited("preview-ip-flood", request.META.get("REMOTE_ADDR", "unknown"), 10000, 600)
    category = data.get("category")
    text = data.get("text", "")
    if not isinstance(category, str):
        raise APIError("invalid_input", "دسته‌بندی معتبر را انتخاب کنید.")
    owner = request.user if is_product_authenticated(request.user) else None
    if owner:
        limited("preview-user", str(owner.pk), 20, 600)
    try:
        rewritten, mode = rewrite(category, text)
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
            raise APIError("recipient_unavailable", "ارسال به این شماره اکنون ممکن نیست.", 422)
    full_sms = rewritten + "\nبگم نگم | لغو: " + settings.APP_BASE_URL + "/preferences"
    if len(full_sms.encode("utf-16-le")) // 2 > 201:
        raise APIError("message_too_long", "متن نهایی بیش از سه بخش پیامک است؛ موضوع دیگری انتخاب کن.", 422)
    expires_at = timezone.now() + timedelta(minutes=15)
    item = Preview.objects.create(owner=owner, session_key=session_key(request), category=category,
        text=rewritten, full_sms=full_sms, recipient_hash=recipient_hash, moderation_mode=mode, expires_at=expires_at, price_toman=settings.PRICE_TOMAN)
    ModerationAudit.objects.create(owner=owner, category=category, outcome="accepted", reason_code=mode, content_digest=digest(str(text)))
    return {"preview_id": str(item.id), "rewritten_text": item.text, "price_toman": item.price_toman,
        "expires_at": expires_at.isoformat(), "moderation_mode": mode, "full_sms": item.full_sms, "sms_segments": 1 if len(full_sms.encode("utf-16-le")) // 2 <= 70 else (len(full_sms.encode("utf-16-le")) // 2 + 66) // 67}


@api(["POST"], authenticated=True)
def create_order(request):
    order = services.create_order(request.user, request.session.session_key, body(request), request.headers.get("Idempotency-Key", ""))
    return services.serialize_order(order)


@api(["POST"], authenticated=True)
def pay_demo(request, order_id):
    return services.serialize_order(services.pay_order(request.user, order_id))


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
