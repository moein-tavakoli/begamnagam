"""Explicit opt-in alternatives from reviewed templates, never repaired harm.

An offer is encrypted, signed, short-lived and bound to its account, session,
recipient, tone and exact template. Choosing it creates a normal server preview;
it does not authorize dispatch, consume AI quota or replace the rejected intent.
"""
from datetime import timedelta
from django.conf import settings
from django.core import signing
from django.utils import timezone
from .privacy import decrypt, digest, encrypt
from .services import APIError

SALT = 'reviewed-message-alternative-v1'
MAX_AGE = 300


def offers(owner, session, recipient_hash, tone):
    from .message_tones import templates
    from .sms import compose_recipient_sms, SMSTooLong
    from .moderation import ModerationRejected
    categories = [('conversation', 'گفت‌وگوی محترمانه'), ('good_wishes', 'آرزوی حال خوب')]
    if settings.PILOT_POSITIVE_ONLY:
        categories = [('appreciation', 'قدردانی'), ('encouragement', 'دلگرمی')]
    origin = settings.APP_BASE_URL.removeprefix('https://').removeprefix('http://')
    result = []
    for category, label in categories:
        try:
            text, _ = compose_recipient_sms(category, templates(category, tone)[0], origin, 'Ab12Cd34', message_tone=tone)
        except (ModerationRejected, SMSTooLong):
            continue
        payload = {'owner': owner.pk, 'session': digest(session), 'recipient': recipient_hash,
                   'category': category, 'tone': tone, 'body': digest(text)}
        result.append({'id': category, 'label': label, 'text': text, 'message_tone': tone,
                       'expires_at': (timezone.now()+timedelta(seconds=MAX_AGE)).isoformat(),
                       'token': encrypt(signing.dumps(payload, salt=SALT, compress=True))})
    return result


def resolve(token, *, owner, session, recipient_hash, tone):
    from .message_tones import templates
    from .sms import compose_recipient_sms
    try:
        if not isinstance(token, str) or not 1 <= len(token) <= 4096 or not owner or not recipient_hash:
            raise ValueError
        payload = signing.loads(decrypt(token), salt=SALT, max_age=MAX_AGE)
        if (not isinstance(payload, dict) or payload.get('owner') != owner.pk
                or payload.get('session') != digest(session) or payload.get('recipient') != recipient_hash
                or payload.get('tone') != tone or payload.get('category') not in {'conversation', 'good_wishes', 'appreciation', 'encouragement'}):
            raise ValueError
        category = payload['category']
        if settings.PILOT_POSITIVE_ONLY and category not in {'appreciation', 'encouragement'}:
            raise ValueError
        origin = settings.APP_BASE_URL.removeprefix('https://').removeprefix('http://')
        text, _ = compose_recipient_sms(category, templates(category, tone)[0], origin, 'Ab12Cd34', message_tone=tone)
        if payload.get('body') != digest(text):
            raise ValueError
    except Exception:
        # Never echo cryptographic errors, tokens, payloads or private input.
        raise APIError('alternative_expired', 'پیشنهاد جایگزین معتبر نیست یا منقضی شده؛ متن را دوباره بررسی کن.', 409) from None
    return category, text


def feedback(text, reason):
    from .moderation import rejection_feedback
    from .draft_guard import _normal, _UNSAFE_WORDS, _UNSAFE_PHRASES, _INSULTS, _MASKED_INSULTS
    code, message = rejection_feedback(reason)
    specific = {
        'draft_instructions': 'متن شامل دستور به سامانه یا قالب فنی است؛ فقط پیامی را که برای مخاطب داری بنویس.',
        'draft_without_intent': 'پس از حذف واژه‌های توهین‌آمیز، درخواست یا احساس مشخصی باقی نماند؛ منظورت را روشن‌تر بنویس.',
        'invalid_draft': 'متن باید خوانا، غیرخالی و حداکثر ۲۸۰ نویسه باشد.',
    }
    message = specific.get(reason, message)
    if isinstance(text, str) and len(text) <= 280 and reason in {'unsafe_content', 'draft_without_intent'}:
        normal = _normal(text)
        patterns = (_UNSAFE_WORDS, _UNSAFE_PHRASES) if reason == 'unsafe_content' else (_INSULTS, _MASKED_INSULTS)
        match = next((m for p in patterns if (m := p.search(normal))), None)
        if match and 1 <= len(match[0]) <= 48 and not any(c.isdigit() for c in match[0]):
            message += f' عبارت «{match[0]}» در بررسی اولیه مشکل‌دار تشخیص داده شد.'
    return code, message
