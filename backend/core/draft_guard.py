"""Conservative local checks for freeform drafts and verified model bodies.

This is a bounded lexical guard, not a claim to detect every harmful meaning or
obfuscation. The model's separate intent/safety review and sender confirmation
are still required. Rejections contain only a fixed code, never private input.
"""
import re
import unicodedata

from .moderation import ModerationRejected, moderate
from .privacy import DIGITS


MAX_DRAFT_CHARACTERS = 280
_PERSIAN = re.compile(r'[\u0621-\u063a\u0641-\u064a\u067e\u0686\u0698\u06a9\u06af\u06cc]')
_TRANSLATE = str.maketrans({'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'أ': 'ا', 'إ': 'ا', 'ٱ': 'ا', 'ة': 'ه'})


def _normal(text):
    value = unicodedata.normalize('NFKC', text).translate(_TRANSLATE)
    # Remove vowel marks, tatweel and invisible joiners before matching. Space
    # and visible punctuation remain so unrelated words do not get joined.
    value = ''.join(char for char in value if char != '\u0640'
                    and unicodedata.category(char) not in {'Mn', 'Cf'})
    return re.sub(r'\s+', ' ', value).strip()


def _word_pattern(words, *, suffix=''):
    # Optional separators catch "ا ح م ق" and "اح.مق" as well as the ordinary
    # token; boundaries prevent English "class"/"Scunthorpe" false positives.
    alternatives = []
    for word in sorted(set(words), key=len, reverse=True):
        letters = re.sub(r'\s+', '', _normal(word))
        alternatives.append(r'[\W_]*'.join(re.escape(char) for char in letters))
    return re.compile(r'(?<!\w)(?:' + '|'.join(alternatives) + ')' + suffix + r'(?!\w)', re.I)


_INSULTS = _word_pattern([
    'احمق', 'ابله', 'نفهم', 'بیشعور', 'بی شعور', 'بی عرضه', 'بی عقل',
    'بی شرف', 'بی ناموس', 'بی تربیت', 'بی ادب', 'بی لیاقت', 'کله پوک',
    'نامرد', 'کثافت', 'عوضی',
    'آشغال', 'لعنتی', 'لعنت', 'نکبت', 'خاک بر سر', 'خر', 'گاو', 'حیوان',
    'گمشو', 'گم شو', 'خفه شو', 'خفه',
    'حرامزاده', 'حرومزاده', 'حروم', 'کسکش', 'کصکش', 'کوسکش', 'کونی', 'جنده',
    'فاحشه', 'پفیوز', 'دیوث', 'کیر', 'کص', 'کوس', 'کسشر', 'کصشر',
    'کسخل', 'کصخل', 'گوه', 'گه', 'فاک', 'فاکیو',
    'idiot', 'moron', 'stupid', 'dumbass', 'ass', 'asshole', 'bastard',
    'fuck', 'fucking', 'fucker', 'fuckyou', 'fuk', 'fck', 'motherfucker', 'bitch', 'shit', 'bullshit',
    'cunt', 'dick', 'prick',
], suffix=r'(?:ها|های|هایی|ی|ید|ین|ند|م|ت|ش|ا|ان|ون)?')
_MASKED_INSULTS = re.compile(
    r'(?<!\w)(?:f[\W_]*[u*#][\W_]*[c*#][\W_]*k(?:ing)?|'
    r'sh[!1*]t|b[!1*]tch|a[$*]s?[$*]hole)(?!\w)', re.I)

# These are harmful purposes or sensitive claims, not just a rude adjective.
# Do not make a polite threat/accusation by deleting the offending phrase.
_UNSAFE_WORDS = _word_pattern([
    'تهدید', 'می کشمت', 'میکشمت', 'بکش', 'میزنمت',
    'بمیر', 'بمیری', 'کشتن', 'گروگان', 'باج', 'انتقام',
    'می زنمت', 'کتکت', 'خودکشی', 'تجاوز', 'سکس', 'سکسی',
    'برهنه', 'لخت', 'پورن', 'سکست', 'جق', 'استمنا', 'بخوابیم',
    'دزد', 'دزدی', 'دزدیدی', 'دزدیده', 'کلاهبردار', 'کلاهبرداری',
    'قاچاقچی', 'قاچاق', 'قاتل', 'اختلاس', 'پولشویی', 'رشوه',
    'قومیت', 'نژاد', 'مذهب', 'یهودی', 'افغانی', 'افغان', 'عرب',
    'همجنس', 'معلول', 'بیماری', 'ایدز', 'سرطان', 'معتاد', 'اعتیاد',
    'بارداری', 'حامله', 'افسردگی', 'اختلال روانی',
    'kill', 'murder', 'suicide', 'rape', 'nigger', 'nazi', 'porn', 'nude',
    'sex', 'blackmail', 'stalk',
], suffix=r'(?:ها|های|ی|ید|ند|م|ت|ش|ات|ایت)?')
_UNSAFE_PHRASES = re.compile(
    r'حسابت\s*ر[وا]\s*می\s*رسم|حسابت[و]?\s*می\s*رسم|'
    r'پدرت[و]?\s*(?:را\s*)?در\s*می\s*ارم|'
    r'آدمت\s*می\s*کنم|زنده\s*نمی\s*مان|'
    r'(?:خواهم|خواهیم)\s*کشت|(?:نابودت|لهت|آتیشت|اتیشت)\s*می\s*(?:کنم|زنم)|'
    r'(?:تو|شما)\s*(?:را|رو)?\s*می\s*(?:کشم|زنم)|'
    r'می\s*(?:کشم|زنم)\s*(?:تو|شما)(?:\s|$)|'
    r'پشیم[او]نت\s*می\s*کنم|برات\s*بد\s*می\s*شه|'
    r'آبرو[یتتاش]*\s*(?:را|رو)?\s*می\s*برم|'
    r'عکس[های]*[تاش]*\s*(?:را|رو)?\s*پخش|'
    r'بیا\s*(?:با\s*من\s*)?بخواب|باید\s*بمیری|کاش\s*بمیری|'
    r'سر\s*(?:تو|ت|شما)\s*(?:را|رو)?\s*می\s*برم|'
    r'(?:you\s+will\s+pay|i\s+will\s+hurt|watch\s+your\s+back)', re.I)
_INSTRUCTIONS = re.compile(
    r'هوش\s*مصنوعی|مدل\s*زبانی|چت\s*جی\s*پی\s*تی|'
    r'گپ\s*جی\s*پی\s*تی|پرامپت|دستور(?:ات|های)?\s*قبلی|'
    r'نادیده\s*بگیر|(?:فقط|عینا|عیناً)\s*بنویس|'
    r'(?:قوانین|محدودیتها|محدودیت\s*ها)\s*را\s*(?:فراموش|نادیده)|'
    r'(?<!\w)(?:chatgpt|gapgpt|system|assistant|developer|prompt|json|'
    r'ignore\s+(?:all|previous|above)|disregard|jailbreak)(?!\w)|'
    r'\[/?INST\]|<\|[^>]*\|>|```|[{}]', re.I)
_CONTACT = re.compile(
    r'https?\s*[:/]|www\s*\.|@|'
    r'\b[a-z0-9](?:[a-z0-9-]{0,62})\s*\.\s*'
    r'(?:ir|com|net|org|io|app|me|co|dev|info|online|site|xyz|edu|gov)(?!\w)|'
    r'تلگرام|واتساپ|واتس\s*اپ|اینستاگرام|ایمیل|'
    r'کد\s*ملی|شماره\s*(?:کارت|حساب|تماس|تلفن|موبایل|شناسنامه)|'
    r'رمز\s*(?:عبور|کارت)|شماره\s*شبا|نام\s*خانوادگی|'
    r'(?:آدرس|نشانی)\s*(?:خانه|منزل|محل|او|شما|من|ما)|'
    r'خیابان.+(?:کوچه|پلاک)|پلاک\s*[\d۰-۹٠-٩]', re.I | re.X)


def _check_intent(value):
    if _INSTRUCTIONS.search(value):
        raise ModerationRejected('draft_instructions')
    if (_CONTACT.search(value)
            or len(re.sub(r'\D', '', value.translate(DIGITS))) >= 5):
        raise ModerationRejected('contact_details')
    # The compact scan is only for longer dangerous phrases. Token matching
    # handles ordinary words without treating "پارکینگ" as an English insult.
    compact = re.sub(r'[\W_]', '', value)
    if (_UNSAFE_WORDS.search(value) or _UNSAFE_PHRASES.search(value)
            or _UNSAFE_PHRASES.search(compact)):
        raise ModerationRejected('unsafe_content')


_FILLER = frozenset('تو شما او من ما یک یه این آن اون خیلی واقعا واقعاً هستی هستید هست هستم است بود هستن هستین چقدر چرا چه هم و را رو به از با که فقط دیگه لعنت بر نیست نیستی نیستید'.split())


def sanitize_draft(text):
    """Return a usable draft with known insults removed *before* networking."""
    if (not isinstance(text, str) or not text.strip()
            or len(text) > MAX_DRAFT_CHARACTERS
            or any(unicodedata.category(char) in {'Cs', 'Co'} for char in text)
            or any(unicodedata.category(char) == 'Cc' and char not in '\r\n\t' for char in text)):
        raise ModerationRejected('invalid_draft')
    value = _normal(text)
    _check_intent(value)
    value, removed = _INSULTS.subn(' ', value)
    value, masked_removed = _MASKED_INSULTS.subn(' ', value)
    value = re.sub(r'\s+', ' ', value).strip(' \t.,،؛:!?؟«»"\'()[]-*_/')
    # Deleting a token must not assemble a previously separated instruction or
    # contact phrase that would otherwise get passed to the model unchecked.
    _check_intent(value)
    meaningful = [word for word in re.findall(r'[^\W\d_]+', value)
                  if word not in _FILLER and _PERSIAN.search(word)]
    if (not meaningful or ((removed or masked_removed) and len(meaningful) < 2)
            or not _PERSIAN.search(value)):
        raise ModerationRejected('draft_without_intent')
    # Existing moderation remains a second fail-closed local check. Its return
    # value applies the same normal form used by the existing preview flow.
    return moderate(value)


def validate_polite_body(text, *, max_units):
    """Validate one plain, short Persian message body; never repair a model body."""
    if (not isinstance(text, str) or not text or text != text.strip()
            or type(max_units) is not int or not 1 <= max_units <= 201
            or len(text) > 201
            or any(unicodedata.category(char) in {'Cc', 'Cs', 'Co', 'So'} for char in text)
            or any(unicodedata.category(char) == 'Cf' and char != '\u200c' for char in text)
            or len(text.encode('utf-16-le')) // 2 > max_units
            or not _PERSIAN.search(text)
            or any(char in text for char in ('`', '<', '>', '{', '}', '[', ']', '|'))
            or not re.fullmatch(r'[\u0600-\u06ff\s\d.,!?;:()،؛؟٪%\u200c\u2013\u2014-]+', text)
            or text[0] in '"\'«' or text[-1] in '"\'»'):
        raise ModerationRejected('invalid_polite_body')
    value = _normal(text)
    _check_intent(value)
    if (_INSULTS.search(value) or _MASKED_INSULTS.search(value)
            or re.search(r'نمیدونم\s*بهت\s*بگم|نمی\s*دونم\s*بهت\s*بگم|'
                         r'بگم\s*نگم|لغو\s*(?:دریافت)?\s*:|'
                         r'^(?:متن|پیام|پاسخ|بازنویسی|ترجمه)\s*(?:نهایی|اصلاحشده|محترمانه)?\s*:|'
                         r'^(?:حتما|البته)[،,:]|^(?:نسخه|بازنویسی)\s*(?:محترمانه|اصلاحشده)', value)):
        raise ModerationRejected('invalid_polite_body')
    moderate(value)
    return text
