"""Explicit opt-in alternatives from reviewed templates, never repaired harm.

An offer is encrypted, signed, short-lived and bound to its account, session,
recipient, tone and exact template. Choosing it creates a normal server preview;
it does not authorize dispatch, consume AI quota or replace the rejected intent.
"""
import re
from datetime import timedelta
from django.conf import settings
from django.core import signing
from django.utils import timezone
from .moderation import CATEGORIES, RELATED_TEMPLATE_CHOICES, ModerationRejected
from .privacy import decrypt, digest, encrypt
from .services import APIError

SALT = 'reviewed-message-alternative-v1'
MAX_AGE = 300
_TOPIC_LABELS = {item['id']: item['label'] for item in CATEGORIES} | {
    'repayment': 'درخواست برگرداندن پول',
    'save_water': 'صرفه‌جویی در آب',
    'save_electricity': 'صرفه‌جویی در برق',
}
# Offers from older clients may still be within their five-minute validity.
_LEGACY_TOPICS = frozenset({'conversation', 'good_wishes', 'appreciation', 'encouragement'})
_GREETING = re.compile(r'^(?:سلام[،,]? )?(?:لطفا[،,]? )?')
_TOPIC_PATTERNS = {
    'parking': r'(?:جلوی|مقابل) (?:در(?: ورودی)?|ورودی(?: ساختمان)?) پارک نکن(?:ید|ین)?'
               r'(?:[،,]? رفت\s*و\s*آمد سخت می\s*شه)?',
    'repayment': r'(?:پولم(?:و| رو| را)?|پولی که (?:ازم|از من) قرض گرفتی) (?:پس بده|برگردون|برگردان)',
    'body': r'(?:بوی بدنت (?:زیاده|آزاردهنده است)|به بهداشت بدنت بیشتر (?:توجه کن|برس))',
    'breath': r'(?:دهنت (?:بوی بد می\s*ده|بو می\s*ده)|به بهداشت دهانت بیشتر توجه کن)',
    'noise': r'(?:آروم|آرام)\s*تر غذا بخور(?:ید|ین)?',
    'shared_space': r'فضای مشترک(?: رو| را)? تمیز (?:کن|نگه دار)',
    'punctuality': r'(?:به\s*موقع|سر\s*وقت) (?:بیا|برس)(?:ید|ین)?',
    'listening': r'وسط (?:حرفم|صحبتم) نپر|(?:حرفم|صحبتم)(?:و| رو| را)? قطع نکن|بذار حرفم تموم بشه',
    'conversation': r'(?:با احترام|محترمانه|مودبانه|مؤدبانه) (?:حرف بزن|صحبت کن)',
    'personal_space': r'بدون اجازه (?:وسایلم(?:و| رو| را)? برندار|از وسایلم استفاده نکن)',
    'phone_etiquette': r'صدای (?:گوشیت?|تلفنت?)(?: رو| را)? (?:کم کن|پایین بیار)',
    'neighbor': r'(?:موقع|وقت|هنگام) استراحت همسایه\s*ها (?:سروصدا|سر و صدا) نکن',
    'teamwork': r'سهمت (?:از|تو|در) کار (?:گروهی|مشترک)(?: رو| را)? انجام بده',
    'apology': r'(?:حلالم کن|منو ببخش|من رو ببخش|من را ببخش)(?:[،,]? (?:داداش|رفیق))?',
    'appreciation': r'(?:مرسی از کمکت|ممنون(?:م)? از کمکت|از کمکت (?:ممنونم|متشکرم))',
    'congratulations': r'موفقیت(?:ت|تان) مبارک|موفقیتت(?: رو| را) تبریک می\s*گم',
    'encouragement': r'به تلاشت ادامه بده|دلسرد نشو',
    'good_wishes': r'(?:امیدوارم )?(?:امروز )?روز(?:ی)? (?:خوب|خوش|آرام|آروم)(?:ی)? داشته باش(?:ی|ید)?',
    'environment': r'زباله(?: رو| را)? (?:روی زمین نریز|در جای مناسب (?:بذار|بگذار))',
    'save_water': r'آب(?: رو| را)? (?:هدر نده|کمتر مصرف کن)',
    'save_electricity': r'برق(?: رو| را)? (?:هدر نده|کمتر مصرف کن)',
}
_RELATED_REJECTIONS = frozenset({
    'unsafe_content', 'generation_unclear', 'generation_rejected', 'candidate_rejected',
    'candidate_too_long', 'invalid_polite_body', 'generation_unsafe', 'review_unsafe', 'review_intent', 'review_added_claims',
    'review_format', 'review_tone', 'review_register',
})


def _topic(text, reason):
    from .draft_guard import sanitize_draft
    if reason not in _RELATED_REJECTIONS:
        return None
    try:
        cleaned = sanitize_draft(text)
    except ModerationRejected:
        return None
    cleaned = _GREETING.sub('', cleaned, count=1)
    return next((key for key, pattern in _TOPIC_PATTERNS.items() if re.fullmatch(pattern, cleaned)), None)


def _category_allowed(category):
    return (isinstance(category, str) and category in _TOPIC_LABELS
            and (not settings.PILOT_POSITIVE_ONLY or category in {'appreciation', 'encouragement'}))


def _fitting_bodies(category, candidates, layout):
    from .sms import compose_recipient_sms, sms_origin, SMSTooLong
    origin = sms_origin()
    fitting = []
    for candidate in candidates:
        try:
            compose_recipient_sms(category, candidate, origin, 'Ab12Cd34', layout=layout, exact=True)
        except (ModerationRejected, SMSTooLong):
            continue
        fitting.append(candidate)
    return fitting


def offers(owner, session, recipient_hash, tone, text, reason, *, layout):
    category = _topic(text, reason)
    if not _category_allowed(category):
        return []
    bodies = _fitting_bodies(category, RELATED_TEMPLATE_CHOICES[category], layout)
    if len(bodies) != 2:
        return []
    result = []
    for index, body in enumerate(bodies, start=1):
        payload = {'owner': owner.pk, 'session': digest(session), 'recipient': recipient_hash,
                   'category': category, 'tone': tone, 'body': digest(body)}
        result.append({'id': f'{category}-{index}', 'label': _TOPIC_LABELS[category], 'text': body, 'message_tone': tone,
                       'expires_at': (timezone.now()+timedelta(seconds=MAX_AGE)).isoformat(),
                       'token': encrypt(signing.dumps(payload, salt=SALT, compress=True))})
    return result


def resolve(token, *, owner, session, recipient_hash, tone, layout):
    try:
        if not isinstance(token, str) or not 1 <= len(token) <= 4096 or not owner or not recipient_hash:
            raise ValueError
        payload = signing.loads(decrypt(token), salt=SALT, max_age=MAX_AGE)
        if (not isinstance(payload, dict) or payload.get('owner') != owner.pk
                or payload.get('session') != digest(session) or payload.get('recipient') != recipient_hash
                or payload.get('tone') != tone or not _category_allowed(payload.get('category'))):
            raise ValueError
        category = payload['category']
        candidates = RELATED_TEMPLATE_CHOICES[category]
        if category in _LEGACY_TOPICS:
            from .message_tones import templates
            candidates = (*candidates, *templates(category, tone))
        text = next((body for body in candidates if payload.get('body') == digest(body)), None)
        if text is None:
            raise ValueError
        if not _fitting_bodies(category, (text,), layout):
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
