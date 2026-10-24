import hashlib
import hmac
import re

from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings


DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_phone(value):
    if not isinstance(value, str) or len(value) > 32:
        raise ValueError("شماره موبایل معتبر ایران را وارد کنید.")
    value = re.sub(r"[\s()\-]", "", value.translate(DIGITS))
    if value.startswith("0098"):
        value = "0" + value[4:]
    elif value.startswith("+98"):
        value = "0" + value[3:]
    elif value.startswith("98"):
        value = "0" + value[2:]
    if not re.fullmatch(r"09[0-9]{9}", value):
        raise ValueError("شماره موبایل معتبر ایران را وارد کنید.")
    return value


def digest(value):
    return hmac.new(settings.PHONE_HASH_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def encrypt(value):
    return Fernet(settings.PHONE_ENCRYPTION_KEY.encode()).encrypt(value.encode()).decode()


def decrypt(value):
    keys = [settings.PHONE_ENCRYPTION_KEY, *settings.PHONE_ENCRYPTION_FALLBACK_KEYS]
    return MultiFernet([Fernet(k.encode()) for k in keys]).decrypt(value.encode()).decode()


def mask(phone):
    return phone[:3] + "•••••" + phone[-3:]
