"""Public explanations only; never return provider errors or recipient preferences."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone


REQUEST_UNAVAILABLE = 'درخواست فعلاً انجام نشد؛ کمی بعد دوباره تلاش کن.'
RECIPIENT_LIMIT = 'به‌دلیل محدودیت ارسال یا دریافت برای این شماره، ارسال فعلاً ممکن نیست. بعداً دوباره تلاش کن.'
PUBLIC_REASONS = {
    'recipient_unavailable': RECIPIENT_LIMIT,
    'account_unavailable': 'ارسال از حساب شما محدود شده است. برای پیگیری با پشتیبانی تماس بگیر.',
    'moderation_rejected': 'این پیام با قوانین محتوا سازگار نیست؛ متن را بدون توهین، تهدید یا اطلاعات خصوصی دوباره آماده کن.',
    'queue_expired': 'مهلت ارسال این پیام تمام شد و پیام ارسال نشد. برای ارسال، متن نهایی را دوباره آماده کن.',
    'order_expired': 'مهلت تأیید سفارش تمام شد و پیام ارسال نشد. متن نهایی را دوباره آماده کن.',
}


def order_status_reason(order, delivery, event):
    # Read the stored outcome, never the recipient's current preferences/account.
    if order.status in {'failed', 'cancelled'}:
        code = (delivery.last_error_code if delivery else '') or (event.last_error_code if event else '')
        if not code and not order.paid_at and order.created_at + timedelta(minutes=15) <= timezone.now():
            code = 'order_expired'
        if code in PUBLIC_REASONS:
            return {'code': code, 'message': PUBLIC_REASONS[code]}
        return {'code': 'send_unavailable', 'message': 'ارسال این پیام انجام نشد؛ بعداً دوباره تلاش کن.'}
    if order.status == 'queued' and event and event.available_at > timezone.now() and event.last_error_code == 'outside_sending_window':
        return {'code': 'sending_window', 'message': f'ارسال پیام‌ها از ساعت {settings.SENDING_START_HOUR} تا {settings.SENDING_END_HOUR} انجام می‌شود؛ پیام شما برای شروع بازهٔ بعدی در صف است.'}
    if order.status == 'unknown':
        return {'code': 'result_pending', 'message': 'نتیجهٔ ارسال هنوز مشخص نیست؛ وضعیت همین پیام را به‌روزرسانی کن و دوباره ارسال نکن.'}
    return None
