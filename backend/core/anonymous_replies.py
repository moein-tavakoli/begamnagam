"""Resolve and reserve an anonymous reply without accepting a destination from the client."""
import re

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.utils import timezone

from .models import Account, Order, RecipientGrant
from .privacy import decrypt, digest
from .recipient_codes import REPLY_TOKEN_PATTERN
from .services import APIError, recipient_unavailable

MAX_REPLIES = 3


def unavailable():
    return APIError('reply_unavailable',
        'این لینک پاسخ در دسترس نیست. با همان شماره‌ای وارد شو که پیامک را دریافت کرده است؛ ممکن است مهلت لینک یا نوبت پاسخ تمام شده باشد.', 404)


def parent_for_token(user, token):
    if not isinstance(token, str) or not re.fullmatch(REPLY_TOKEN_PATTERN, token):
        raise unavailable()
    parent = Order.objects.filter(preview__recipient_grant__reply_token_digest=digest('reply-token:' + token),
                                  recipient_hash=user.account.phone_hash).first()
    if parent is None:
        raise unavailable()
    return parent


def counterpart_phone(parent, user):
    if parent.owner_id == user.pk or parent.recipient_hash != user.account.phone_hash:
        raise unavailable()
    counterpart = Account.objects.filter(user_id=parent.owner_id).exclude(phone_cipher='').first()
    if counterpart is None:
        raise recipient_unavailable()
    try:
        phone = decrypt(counterpart.phone_cipher)
    except InvalidToken:
        raise recipient_unavailable() from None
    if digest(phone) != counterpart.phone_hash:
        raise recipient_unavailable()
    return phone


def check_turn(parent, user):
    """For reservations the caller holds a row lock on the parent."""
    allowed = {Order.Status.DELIVERED_DEMO} if settings.DEMO_MODE else {Order.Status.ACCEPTED, Order.Status.DELIVERED}
    environment = 'demo' if settings.DEMO_MODE else settings.PROVIDER_ENVIRONMENT
    if (parent.reply_depth >= MAX_REPLIES or parent.status not in allowed or not parent.full_sms or not parent.recipient_cipher
            or not hasattr(parent, 'delivery') or parent.delivery.environment != environment
            or not RecipientGrant.objects.filter(preview_id=parent.preview_id, reply_token_digest__isnull=False,
                activated_at__isnull=False, report_expires_at__gt=timezone.now(),
                recipient_hash=user.account.phone_hash).exists()):
        raise unavailable()
    # A provider-accepted reply could have reached the recipient even if a late
    # reconciliation fails. A grant that was activated consumes the turn for good.
    if parent.replies.exclude(status__in=[Order.Status.FAILED, Order.Status.CANCELLED],
                              preview__recipient_grant__activated_at__isnull=True).exists():
        raise unavailable()
    return parent.reply_depth + 1
