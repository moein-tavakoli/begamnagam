"""The fixed login-code contract; never accepts arbitrary SMS content."""
import re
from zoneinfo import ZoneInfo

import jdatetime
from django.conf import settings
from django.utils import timezone

from config.origins import web_otp_sms_host

OTP_LENGTH = 4
OTP_PATTERN = re.compile(r'[0-9]{4}')


def valid_otp(code):
    return isinstance(code, str) and OTP_PATTERN.fullmatch(code) is not None


def otp_sms(code, *, sent_at=None):
    if not valid_otp(code):
        raise ValueError('invalid_otp_code')
    local = timezone.localtime(sent_at or timezone.now(), ZoneInfo('Asia/Tehran'))
    day = jdatetime.date.fromgregorian(date=local.date())
    stamp = f'{day.year:04d}/{day.month:02d}/{day.day:02d} {local:%H:%M:%S}'
    text = f'بگم نگم\nکد تأیید ورود به سامانه:\nCode: {code}\n{stamp}'
    host = web_otp_sms_host(settings.APP_BASE_URL)
    if host:
        text += f'\n\n@{host} #{code}'
    return text
