import re
import secrets
import string
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import RecipientGrant, RecipientState, AbuseReport
from .privacy import digest
from .services import APIError


def generate_short_code():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))


def issue_grant(preview, recipient_hash, *, invitation_send=None):
    # A uniqueness constraint arbitrates collisions across concurrent workers.
    # Savepoints keep a rare collision from poisoning the enclosing preview tx.
    for _ in range(5):
        token = generate_short_code()
        token_digest = digest('recipient-token:' + token)
        try:
            with transaction.atomic():
                RecipientGrant.objects.create(preview=preview, invitation_send=invitation_send, token_digest=token_digest,
                                              recipient_hash=recipient_hash)
        except IntegrityError:
            if (not RecipientGrant.objects.filter(token_digest=token_digest).exists()
                    or (RecipientGrant.objects.filter(invitation_send=invitation_send).exists() if invitation_send
                        else RecipientGrant.objects.filter(preview=preview).exists())):
                raise
        else:
            return token
    raise APIError('link_generation_unavailable', 'ساخت لینک موقتاً ممکن نیست؛ دوباره تلاش کنید.', 503)


def activate_grant(order):
    now = timezone.now()
    RecipientGrant.objects.filter(preview=order.preview, activated_at__isnull=True).update(
        activated_at=now, stop_expires_at=now+timedelta(days=365), report_expires_at=now+timedelta(days=30))


def lookup_grant(token, *, report=False, lock=False):
    # Old message snapshots keep their original 256-bit capabilities.
    if not isinstance(token, str) or not re.fullmatch(r'(?:[A-Za-z0-9]{8}|[A-Za-z0-9_-]{43})', token):
        raise APIError('link_unavailable', 'این لینک فعال نیست یا مهلتش تمام شده است.', 404)
    query = RecipientGrant.objects.select_for_update() if lock else RecipientGrant.objects
    grant = query.filter(token_digest=digest('recipient-token:' + token), activated_at__isnull=False).first()
    expiry = grant.report_expires_at if grant and report else grant.stop_expires_at if grant else None
    if not expiry or expiry <= timezone.now():
        raise APIError('link_unavailable', 'این لینک فعال نیست یا مهلتش تمام شده است.', 404)
    return grant


def inspect(token):
    grant = lookup_grant(token)
    # No sender, order, recipient identity or private message is returned.
    return {'active': True, 'can_report': bool(grant.report_expires_at and grant.report_expires_at > timezone.now())}


def stop(token):
    grant = lookup_grant(token)
    with transaction.atomic():
        # Same lock order as submission: recipient then grant. Scanner GETs never
        # reach this function; stopping is an explicit CSRF-protected POST.
        RecipientState.objects.get_or_create(phone_hash=grant.recipient_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=grant.recipient_hash)
        lookup_grant(token, lock=True)
        state.blocked = True
        state.save(update_fields=['blocked', 'updated_at'])
    return {'blocked': True}


def report(token, reason, details):
    if reason not in {'unwanted', 'harassment', 'wrong_number', 'other'} or not isinstance(details, str) or len(details) > 500:
        raise APIError('invalid_input', 'دلیل و توضیح حداکثر۵۰۰نویسه‌ای گزارش را بررسی کن.')
    grant = lookup_grant(token, report=True)
    with transaction.atomic():
        RecipientState.objects.get_or_create(phone_hash=grant.recipient_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=grant.recipient_hash)
        grant = lookup_grant(token, report=True, lock=True)
        item, _ = AbuseReport.objects.get_or_create(grant=grant, defaults={'reason': reason, 'details': details})
        state.blocked = True
        state.save(update_fields=['blocked', 'updated_at'])
    return {'receipt': str(item.id), 'blocked': True}
