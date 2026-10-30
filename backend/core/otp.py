"""The fixed login-code contract; never accepts arbitrary SMS content."""
import re
from django.conf import settings

from config.origins import web_otp_sms_host

OTP_LENGTH = 4
OTP_PATTERN = re.compile(r'[0-9]{4}')


def valid_otp(code):
    return isinstance(code, str) and OTP_PATTERN.fullmatch(code) is not None


def otp_sms(code):
    if not valid_otp(code):
        raise ValueError('invalid_otp_code')
    text = f'بگم نگم\nCode: {code}'
    host = web_otp_sms_host(settings.APP_BASE_URL)
    if host:
        text += f'\n\n@{host} #{code}'
    return text
