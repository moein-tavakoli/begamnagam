import re
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import RecipientGrant, RecipientState, AbuseReport
from .privacy import digest
from .services import APIError


def activate_grant(order):
    now = timezone.now()
    RecipientGrant.objects.filter(preview=order.preview, activated_at__isnull=True).update(
        activated_at=now, stop_expires_at=now+timedelta(days=365), report_expires_at=now+timedelta(days=30))


def lookup_grant(token, *, report=False, lock=False):
    if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', token):
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
