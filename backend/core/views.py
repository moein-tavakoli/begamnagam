import hmac
import json
import logging
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.contrib.auth import get_user_model, login, logout
from django.core.cache import cache
from django.db import connection, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from . import services
from .models import Account, ModerationAudit, OTPChallenge, Order, Preview, RecipientState
from .moderation import ModerationRejected, RewriteUnavailable, rewrite
from .message_examples import public_catalog, is_current_suggestion
from .privacy import DIGITS, decrypt, digest, encrypt, mask, normalize_phone
from .services import APIError, api, is_product_authenticated, limited
from .sms import (MAX_REWRITE_BODY_UNITS, MESSAGE_SLOT, REPLY_SLOT, compose_freeform_sms, compose_recipient_sms,
                  sender_sms, sms_origin, sms_segments)
from .otp import OTP_LENGTH, valid_otp
from .input_digits import canonical_input
from .message_attempts import capture_preview_attempt, record_attempt

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
    except RequestDataTooBig:
        raise APIError("request_too_large", "حجم درخواست بیش از حد مجاز است.", 413) from None
    except (ValueError, UnicodeDecodeError):
        raise APIError("invalid_input", "ساختار درخواست معتبر نیست.")
    if not isinstance(data, dict):
        raise APIError("invalid_input", "ساختار درخواست معتبر نیست.")
    return canonical_input(data, json_numbers=True)


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
    from .payment_options import options as payment_options
    authenticated = is_product_authenticated(request.user)
    from .freeform import available as freeform_available
    from .ai_config import current as ai_configuration
    from .identity_settings import identity_requests_enabled
    from .limits import policy
    ai = ai_configuration()
    from .message_tones import choices as tone_choices, resolve as resolve_tone
    from .packages import balance_field, checkout_enabled
    from .conversion_experiments import assignment, catalog
    data = {"demo_mode": settings.DEMO_MODE, "authenticated": authenticated,
        "identity_requests_enabled": identity_requests_enabled(),
        "price_toman": 0, **public_catalog(freeform=freeform_available(ai)), "rewrite_mode": ai.provider if freeform_available(ai) else 'template', "payment_backend": settings.PAYMENT_BACKEND, "support_contact": settings.SUPPORT_CONTACT,
        "otp_is_real": otp_is_real()}
    data['payment_options'] = payment_options()
    data['package_checkout_enabled'] = checkout_enabled(data['payment_options'])
    data['conversion_experiment'] = assignment(request.user.account if authenticated else None, data['payment_options'])
    data['message_packages'] = catalog(data['conversion_experiment'])
    data['message_tones'] = tone_choices(ai)
    data['default_message_tone'] = resolve_tone(None, ai)
    if authenticated:
        from .wallet import balance_field as wallet_balance_field
        data['wallet_balance_toman'] = str(getattr(request.user.account, wallet_balance_field()))
        data["unlimited_free_sends"] = request.user.account.unlimited_free_sends
        data["free_sends_remaining"] = request.user.account.free_sends_remaining
        data['purchased_sends_remaining'] = getattr(request.user.account, balance_field())
        data["free_sends_total"] = 3 + request.user.account.free_sends_earned_total
        data["free_sends_earned_total"] = request.user.account.free_sends_earned_total
        data["recent_auth"] = timezone.now().timestamp() - request.session.get("phone_verified_at", 0) <= 300
        data["session_identity"] = digest("session-identity:" + request.session.session_key)
        data['message_visibility_revision'] = services.message_visibility_revision(request.user)
        data["phone_masked"] = request.user.account.phone_masked
        data["phone"] = decrypt(request.user.account.phone_cipher) if request.user.account.phone_cipher else ''
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
    from .limits import policy, request_limit
    limits, phone_rule = policy(), request_limit("otp-phone")
    if phone_rule.enabled and OTPChallenge.objects.filter(phone_hash=phone_hash,
            created_at__gt=now - timedelta(seconds=phone_rule.window_seconds)).count() >= phone_rule.maximum:
        raise APIError("rate_limited", "کمی بعد دوباره برای کد تأیید تلاش کنید.", 429)
    demo_otp = settings.DEMO_MODE and settings.OTP_BACKEND == "demo" and settings.SMS_BACKEND == "console"
    if not demo_otp and settings.OTP_BACKEND != "kavenegar":
        raise APIError("sms_disabled", "ارسال کد فعلاً فعال نیست.", 503)
    code = f"{secrets.randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"
    challenge_id = uuid.uuid4()
    OTPChallenge.objects.create(id=challenge_id, phone_hash=phone_hash, phone_cipher=encrypt(phone),
        code_digest=digest(f"otp:{challenge_id}:{code}"), session_key=session_key(request),
        expires_at=now + timedelta(seconds=limits.otp_validity_seconds))
    if demo_otp:
        return {"challenge_id": str(challenge_id), "debug_code": code, "demo_mode": True, "expires_in": limits.otp_validity_seconds}
    from .providers import Kavenegar, ProviderDisabled, ProviderUnknown, ProviderRejected
    from .budget import lock_dispatch_control, observe_cost, reserve_cost
    delivery_status = 'accepted'
    try:
        if hasattr(request, 'bot_conversation'):
            # The bot session transaction holds the day lock until this
            # response commits. Follow the overrun lock order before reserving.
            lock_dispatch_control()
        reserve_cost('otp:' + str(challenge_id), 'otp', limits.otp_max_cost_rial)
        result = Kavenegar().otp(phone=phone, code=code)
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
    return {"challenge_id": str(challenge_id), "demo_mode": False, "expires_in": limits.otp_validity_seconds, "delivery_status": delivery_status}


@api(["POST"])
def verify_otp(request, *, signup_source=Account.SignupSource.WEB):
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
    from .limits import policy
    max_attempts = policy().otp_max_attempts
    invalid = False
    with transaction.atomic():
        try:
            challenge = OTPChallenge.objects.select_for_update().get(id=challenge_id)
        except OTPChallenge.DoesNotExist:
            raise APIError("invalid_otp", "کد تأیید معتبر نیست.")
        if challenge.session_key != request.session.session_key or challenge.consumed_at or challenge.expires_at <= timezone.now() or challenge.attempts >= max_attempts:
            raise APIError("invalid_otp", "کد تأیید معتبر نیست یا منقضی شده است.")
        challenge.attempts += 1
        if not valid_otp(code) or not hmac.compare_digest(challenge.code_digest, digest(f"otp:{challenge.id}:{code}")):
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
                "phone_cipher": challenge.phone_cipher, "phone_masked": mask(phone), "signup_source": signup_source})
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
    verified_at = timezone.now()
    request.session["phone_verified_at"] = verified_at.timestamp()
    # Absolute expiry survives browser restarts and is not renewed by session writes.
    request.session.set_expiry(verified_at + timedelta(seconds=settings.PRODUCT_SESSION_AGE))
    Preview.objects.filter(session_key=old_session, owner__isnull=True).update(owner=user, session_key=new_session)
    return {"authenticated": True, "phone_masked": user.account.phone_masked,
        "phone": decrypt(user.account.phone_cipher) if user.account.phone_cipher else '', "recent_auth": True}


@api(["POST"], authenticated=True)
def logout_view(request):
    logout(request)
    return {"authenticated": False}


@api(["POST"])
def preview(request):
    return prepare_preview(request, body(request))


@api(["POST"], authenticated=True)
def text_trial(request):
    data = body(request)
    if set(data) != {'text'} or not isinstance(data['text'], str):
        raise APIError('invalid_input', 'فقط متن پیام را وارد کن.', 422)
    return prepare_preview(request, {**data, 'source_mode': 'freeform'}, text_trial=True)


def limit_preview_origin(request, unlimited):
    if not unlimited:
        limited("preview-session", session_key(request), 20, 600)
    limited("preview-ip-flood", request.META.get("REMOTE_ADDR", "unknown"), 10000, 600)


@capture_preview_attempt
def prepare_preview(request, data, *, text_trial=False):
    request._message_attempt_data = data
    if set(data) - {'text', 'category', 'recipient_phone', 'reply_token', 'source_mode', 'payment_method', 'message_tone', 'alternative_token', 'share_token'}:
        raise APIError('invalid_input', 'فقط متن اولیه و شمارهٔ گیرنده را بفرست؛ نتیجهٔ بررسی در سرور تعیین می‌شود.', 422)
    owner = request.user if is_product_authenticated(request.user) else None
    has_share = 'share_token' in data
    if has_share:
        if not owner:
            raise APIError('authentication_required', 'ابتدا شمارهٔ خودت را تأیید کن.', 401)
        if {'recipient_phone', 'reply_token'} & data.keys():
            raise APIError('invalid_input', 'مقصد این پیام از لینک شخصی انتخاب می‌شود.', 422)
    from .demo_limits import unlimited_demo_sends
    unlimited = unlimited_demo_sends(owner)
    limit_preview_origin(request, unlimited)
    category = data.get("category", 'custom')
    text = data.get("text", "")
    payment_method = data.get('payment_method', 'credit')
    if not isinstance(payment_method, str) or payment_method not in {'credit', 'wallet', 'gateway'}:
        raise APIError('invalid_input', 'روش پرداخت معتبر نیست.', 422)
    if payment_method != 'credit':
        raise APIError('package_required', 'ارسال تازه فقط از هدیه یا اعتبار بسته انجام می‌شود؛ ابتدا بستهٔ پیام بخر.', 409)
    if not isinstance(category, str):
        raise APIError("invalid_input", "دسته‌بندی معتبر را انتخاب کنید.")
    category = category or 'custom'
    from .freeform import available as freeform_available, prepare, signature
    from .ai_config import current as ai_configuration
    ai = ai_configuration()
    from .message_tones import resolve as resolve_tone
    tone = resolve_tone(data.get('message_tone'), ai)
    request._message_attempt_tone = tone
    use_freeform = freeform_available(ai)
    source_mode = data.get('source_mode')
    if source_mode is not None and (not isinstance(source_mode, str) or source_mode not in {'suggestion', 'freeform', 'reviewed_alternative'}):
        raise APIError('invalid_input', 'روش آماده‌سازی متن معتبر نیست.')
    choosing_alternative = source_mode == 'reviewed_alternative'
    is_reply = 'reply_token' in data
    if is_reply:
        if not owner:
            raise APIError('authentication_required', 'ابتدا شماره‌ای را که پیامک را دریافت کرده تأیید کن.', 401)
        if 'recipient_phone' in data or source_mode != 'freeform':
            raise APIError('invalid_input', 'پاسخ ناشناس با بازبینی متن و بدون وارد کردن شمارهٔ مقصد آماده می‌شود.', 422)
        if not use_freeform:
            raise APIError('freeform_unavailable', 'بازبینی پاسخ فعلاً در دسترس نیست؛ کمی بعد دوباره تلاش کن.', 409)
    if 'alternative_token' in data and not choosing_alternative:
        raise APIError('invalid_input', 'روش انتخاب پیشنهاد معتبر نیست.', 422)
    if choosing_alternative:
        if set(data) & {'text', 'category'}:
            raise APIError('server_snapshot_required', 'متن پیشنهاد جایگزین فقط از سرور خوانده می‌شود.', 422)
        use_freeform = False
    if source_mode == 'freeform' and not use_freeform:
        raise APIError('freeform_unavailable', 'بازنویسی متن دلخواه فعلاً فعال نیست؛ از پیشنهاد آماده استفاده کن.', 409)
    if source_mode == 'suggestion' and not use_freeform:
        if not is_current_suggestion(category, text):
            raise APIError('freeform_unavailable', 'متن عوض شده است؛ برای بازنویسی دلخواه باید این قابلیت فعال باشد.', 409)
    if not use_freeform and category == 'custom' and not choosing_alternative:
        raise APIError('freeform_unavailable', 'بازنویسی متن دلخواه فعلاً فعال نیست؛ از پیشنهاد آماده استفاده کن.', 409)
    if settings.PILOT_POSITIVE_ONLY and not choosing_alternative and (use_freeform or category not in {"appreciation", "encouragement", "congratulations"}):
        raise APIError("category_unavailable", "این موضوع فعلاً فعال نیست.", 422)
    if owner and not unlimited:
        limited("preview-user", str(owner.pk), 20, 600)
    recipient_hash, parent, with_reply = '', None, True
    share_token_id = None
    if is_reply:
        from .anonymous_replies import MAX_REPLIES, check_turn, counterpart_phone, parent_for_token
        parent = parent_for_token(owner, data['reply_token'])
        with_reply = check_turn(parent, owner) < MAX_REPLIES
        target_phone = counterpart_phone(parent, owner)
        recipient_hash = digest(target_phone)
        request._message_attempt_recipient_phone = target_phone
    elif has_share:
        from .personal_share import parse_token, target_phone
        share_token_id = parse_token(data['share_token'])
        phone = target_phone(owner, share_token_id)
        recipient_hash = digest(phone)
        request._message_attempt_recipient_phone = phone
    elif data.get('recipient_phone'):
        if not owner:
            raise APIError('authentication_required', 'ابتدا شماره خودت را تأیید کن.', 401)
        recipient_hash = digest(normalize_phone(data['recipient_phone']))
        if recipient_hash == owner.account.phone_hash:
            raise APIError('self_recipient', 'شمارهٔ گیرنده باید با شمارهٔ خودت متفاوت باشد.', 422)
    if (use_freeform or choosing_alternative) and not text_trial and (not owner or not recipient_hash):
        raise APIError('authentication_required' if not owner else 'recipient_required',
            'برای آماده‌سازی متن، ابتدا وارد شو و شمارهٔ گیرنده را وارد کن.', 401 if not owner else 422)
    from .sms_template_settings import current_sms_layout, sample_recipient_code
    layout, variables = current_sms_layout()
    if text_trial and MESSAGE_SLOT not in layout:
        raise APIError('sms_template_unavailable', 'قالب فعلی پیامک متن شخصی را نمایش نمی‌دهد.', 503)
    origin = sms_origin()
    request._message_attempt_admitted = True
    alternative_body = None
    if choosing_alternative:
        from .message_alternatives import resolve as resolve_alternative
        category, alternative_body = resolve_alternative(data.get('alternative_token'), owner=owner,
            session=session_key(request), recipient_hash=recipient_hash, tone=tone)
        text = alternative_body
    direct = tone != 'polite'
    try:
        if choosing_alternative:
            from .moderation import moderate
            moderate(alternative_body)
            rewritten, mode = alternative_body, 'template'
        elif use_freeform:
            rewritten, mode = prepare(owner, text, max_units=MAX_REWRITE_BODY_UNITS, message_tone=tone, config=ai), ai.provider
            category = 'custom'
        else:
            rewritten, mode = rewrite(category, text, message_tone=tone, provider_mode='template')
        from .limits import policy
        expires_at = timezone.now() + timedelta(seconds=policy().preview_validity_seconds)
        is_free = bool(owner and (owner.account.unlimited_free_sends or owner.account.free_sends_remaining > 0))
        with transaction.atomic():
            item = Preview.objects.create(owner=owner, session_key=session_key(request), category=category,
                from_text_trial=text_trial,
                message_tone=tone, payment_method='credit', wallet_policy_version='', original_text=text,
                text='' if use_freeform else rewritten, generated_body=rewritten if use_freeform else '',
                recipient_hash=recipient_hash, reply_to=parent, is_shared_destination=has_share,
                personal_share_token=share_token_id,
                terms_version=settings.TERMS_VERSION, moderation_mode=mode,
                expires_at=expires_at, is_free=is_free, price_toman=0)
            from .recipient import issue_grant
            token = (sample_recipient_code(layout) if text_trial else
                     issue_grant(item, recipient_hash, with_reply=with_reply and REPLY_SLOT in layout))
            if use_freeform:
                full_sms = compose_freeform_sms(rewritten, origin, token, layout=layout, variables=variables)
            else:
                item.text, full_sms = compose_recipient_sms(category, rewritten, origin, token, message_tone=tone,
                    layout=layout, variables=variables, exact=choosing_alternative)
            item.full_sms = full_sms
            item.review_signature = signature(item) if use_freeform else ''
            item.save(update_fields=['text', 'full_sms', 'review_signature'])
            event = ModerationAudit.objects.create(owner=owner, category=category, outcome='accepted',
                reason_code=mode + ('_' + tone if direct else ''), content_digest=digest(json.dumps(text, ensure_ascii=True)))
            request._message_attempt_moderation_event = event.event_id
            record_attempt(request, preview=item)
    except ModerationRejected as exc:
        reason = str(exc)
        event = ModerationAudit.objects.create(owner=owner, category=category[:32], outcome='rejected',
            reason_code=reason, content_digest=digest(json.dumps(text, ensure_ascii=True)))
        request._message_attempt_moderation_event = event.event_id
        from .message_alternatives import feedback, offers
        code, message = feedback(text, reason)
        alternatives = []
        if not choosing_alternative and not is_reply and owner and recipient_hash:
            alternatives = offers(owner, session_key(request), recipient_hash, tone, text, reason)
        raise APIError(code, message, 422, details={'alternatives': alternatives})
    except RewriteUnavailable:
        raise APIError("rewrite_unavailable", "آماده‌سازی متن موقتاً در دسترس نیست؛ کمی بعد تلاش کنید.", 503)
    if text_trial:
        return {'trial_id': str(item.pk), 'full_sms': item.full_sms, 'expires_at': item.expires_at.isoformat()}
    return preview_data(item)


def preview_data(item):
    is_reply = item.reply_to_id is not None
    return {"preview_id": str(item.id), "payment_method": item.payment_method, "wallet_terms_version": item.wallet_policy_version,
        "rewritten_text": item.generated_body if item.moderation_mode in {'gapgpt', 'ollama'} else item.text,
        "price_toman": item.price_toman, "is_free": item.is_free, "is_reply": is_reply, "message_tone": item.message_tone,
        "expires_at": item.expires_at.isoformat(), "moderation_mode": item.moderation_mode, "terms_version": item.terms_version,
        "full_sms": sender_sms(item.full_sms, hide_recipient_links=is_reply or item.is_shared_destination),
        "sms_segments": sms_segments(item.full_sms)}


@api(['GET'], authenticated=True)
def resume_preview(request, preview_id):
    from .purchase_resume import resolve
    preview, direct_phone = resolve(request.user, request.session.session_key, preview_id)
    return {**preview_data(preview), 'recipient_masked': mask(direct_phone) if direct_phone else '',
            'is_shared_destination': preview.is_shared_destination}


@api(["POST"], authenticated=True)
def create_order(request):
    order = services.create_order(request.user, request.session.session_key, body(request), request.headers.get("Idempotency-Key", ""),
                                  allow_purchase_resume=request.path == '/api/v1/orders')
    return services.serialize_order(order)


@api(["POST"], authenticated=True)
def pay_demo(request, order_id):
    if body(request):
        raise APIError('server_snapshot_required', 'متن ارسال فقط از سفارش بررسی‌شدهٔ سرور خوانده می‌شود.', 422)
    return services.serialize_order(services.pay_order(request.user, order_id))


@api(["POST"], authenticated=True)
def confirm_free(request, order_id):
    if body(request):
        raise APIError('server_snapshot_required', 'متن ارسال فقط از سفارش بررسی‌شدهٔ سرور خوانده می‌شود.', 422)
    return services.serialize_order(services.confirm_free_order(request.user, order_id))


@api(["GET"], authenticated=True)
def order_detail(request, order_id):
    return services.serialize_order(services.get_owned_order(request.user, order_id))


@api(["GET"], authenticated=True)
def messages(request):
    orders = list(services.visible_orders(request.user).order_by('-created_at')[:100])
    return {'results': services.serialize_orders(orders)}


@api(["DELETE"], authenticated=True)
def hide_message(request, order_id):
    return services.hide_owned_order(request.user, order_id)


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
    attempt = PaymentAttempt.objects.filter(provider='zarinpal', environment=settings.PROVIDER_ENVIRONMENT, authority=authority).exclude(authority='').first()
    if not settings.DEMO_MODE and settings.PROVIDER_ENVIRONMENT != 'live':
        attempt = None
    if attempt:
        limited('callback', str(attempt.pk), 10, 60)
        try:
            verify_provider_payment.delay(str(attempt.pk))
        except Exception:
            pass  # Independent reconciler will verify the durable attempt.
    target = '/wallet?topup=' + str(attempt.wallet_topup_id) if attempt and attempt.wallet_topup_id else '/credits?purchase=' + str(attempt.purchase_id) if attempt and attempt.purchase_id else '/history?payment_return=1'
    return HttpResponseRedirect(settings.APP_BASE_URL + target)


@api(["POST"])
def recipient_action(request, action):
    from . import recipient
    from .recipient_codes import is_short_code
    data = body(request)
    token = data.get('token')
    if action == 'identity':
        from .identity_consent import request_identity
        return request_identity(request, data)
    # Token is in JSON only, never request paths/query/access logs.
    limited('recipient-action-session', session_key(request), 30, 600)
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    limited('recipient-action-ip', ip, 120, 600)
    if is_short_code(token):
        limited('recipient-action-short-ip', ip, 30, 600)
    limited('recipient-action-token', digest(str(token)[:100]), 30, 600)
    if action == 'reply':
        if not is_product_authenticated(request.user):
            raise APIError('authentication_required', 'ابتدا شماره‌ای را که پیامک را دریافت کرده تأیید کن.', 401)
        from .anonymous_replies import check_turn, parent_for_token
        check_turn(parent_for_token(request.user, token), request.user)
        return {'active': True}
    if action == 'inspect': return recipient.inspect(token)
    if action == 'stop': return recipient.stop(token, phone=data.get('phone'))
    if action == 'report': return recipient.report(token, data.get('reason'), data.get('details', ''), phone=data.get('phone'))
    raise APIError('not_found', 'درخواست پیدا نشد.', 404)


@api(["POST"], authenticated=True)
def request_deletion(request):
    body(request)
    if timezone.now().timestamp() - request.session.get('phone_verified_at', 0) > 300:
        raise APIError('reauthentication_required', 'برای درخواست حذف، شماره خودت را مجدداً تأیید کن.', 403)
    from .models import IdentityConsent, IdentityReceipt, OperatorAudit, PersonalShareLink
    from django.db.models import F, Q
    with transaction.atomic():
        account = Account.objects.select_for_update().get(user=request.user)
        if not account.deletion_requested_at:
            account.deletion_requested_at = timezone.now()
            account.suspended = True
            account.save(update_fields=['deletion_requested_at', 'suspended'])
            PersonalShareLink.objects.filter(account=account).delete()
            IdentityConsent.objects.filter(Q(subject=account) | Q(requester=account)).update(
                status=IdentityConsent.Status.REVOKED, revision=F('revision')+1, updated_at=timezone.now(), source_order=None,
            )
            IdentityReceipt.objects.filter(Q(consent__subject=account) | Q(consent__requester=account)).update(
                status=IdentityConsent.Status.REVOKED, source_order=None,
            )
            OperatorAudit.objects.create(actor=request.user, action='account_delete_requested', object_id=str(account.pk), reason='verified_owner_request')
    return {'requested': True, 'redaction_within_days': 30}


@api(["GET"])
def operations_status(request):
    if not request.user.is_active or not request.user.is_staff or not request.user.has_perm('core.view_operations'):
        raise APIError('forbidden', 'مجوز مشاهده عملیات را ندارید.', 403)
    from .safety import snapshot
    return snapshot()
