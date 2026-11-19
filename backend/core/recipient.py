import re
from datetime import timedelta
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from .models import RecipientGrant, RecipientState, AbuseReport
from .privacy import digest, normalize_phone
from .recipient_codes import STOP_TOKEN_PATTERN, generate_short_code, is_short_code
from .services import APIError


def issue_grant(preview, recipient_hash, *, invitation_send=None, with_reply=False):
    # A uniqueness constraint arbitrates collisions across concurrent workers.
    # Savepoints keep a rare collision from poisoning the enclosing preview tx.
    for _ in range(5):
        token = generate_short_code('a' if with_reply else 'c')
        token_digest = digest('recipient-token:' + token)
        reply_digest = digest('reply-token:' + token) if with_reply else None
        try:
            with transaction.atomic():
                RecipientGrant.objects.create(preview=preview, invitation_send=invitation_send, token_digest=token_digest,
                                              recipient_hash=recipient_hash, reply_token_digest=reply_digest)
        except IntegrityError:
            collisions = Q(token_digest=token_digest)
            if reply_digest:
                collisions |= Q(reply_token_digest=reply_digest)
            source = {'invitation_send': invitation_send} if invitation_send else {'preview': preview}
            if RecipientGrant.objects.filter(**source).exists() or not RecipientGrant.objects.filter(collisions).exists():
                raise
        else:
            return token
    raise APIError('link_generation_unavailable', 'ساخت لینک موقتاً ممکن نیست؛ دوباره تلاش کنید.', 503)


def activate_grant(order):
    now = timezone.now()
    RecipientGrant.objects.filter(preview_id=order.preview_id, recipient_hash=order.recipient_hash, activated_at__isnull=True).update(
        activated_at=now, stop_expires_at=now+timedelta(days=365), report_expires_at=now+timedelta(days=30))


def lookup_grant(token, *, report=False, lock=False, recipient_hash=None):
    # Old message snapshots keep their original 256-bit capabilities.
    if not isinstance(token, str) or not re.fullmatch(STOP_TOKEN_PATTERN, token):
        raise APIError('link_unavailable', 'این لینک فعال نیست یا مهلتش تمام شده است.', 404)
    query = RecipientGrant.objects.select_for_update() if lock else RecipientGrant.objects
    query = query.filter(token_digest=digest('recipient-token:' + token), activated_at__isnull=False)
    if recipient_hash is not None:
        query = query.filter(recipient_hash=recipient_hash)
    grant = query.first()
    expiry = grant.report_expires_at if grant and report else grant.stop_expires_at if grant else None
    if not expiry or expiry <= timezone.now():
        raise APIError('link_unavailable', 'این لینک فعال نیست یا مهلتش تمام شده است.', 404)
    return grant


def inspect(token):
    grant = lookup_grant(token)
    # No sender, order, recipient identity or private message is returned.
    return {'active': True, 'can_report': bool(grant.report_expires_at and grant.report_expires_at > timezone.now())}


def confirmed_phone_hash(token, phone):
    if not is_short_code(token):
        return None
    try:
        return digest(normalize_phone(phone))
    except ValueError:
        raise APIError('recipient_confirmation_required', 'شمارهٔ موبایلی را وارد کنید که این پیامک را دریافت کرده است.', 422) from None


def stop(token, *, phone=None):
    phone_hash = confirmed_phone_hash(token, phone)
    grant = lookup_grant(token, recipient_hash=phone_hash)
    with transaction.atomic():
        # Same lock order as submission: recipient then grant. Scanner GETs never
        # reach this function; stopping is an explicit CSRF-protected POST.
        RecipientState.objects.get_or_create(phone_hash=grant.recipient_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=grant.recipient_hash)
        lookup_grant(token, lock=True, recipient_hash=phone_hash)
        state.blocked = True
        state.save(update_fields=['blocked', 'updated_at'])
    return {'blocked': True}


def report(token, reason, details, *, phone=None):
    if reason not in {'unwanted', 'harassment', 'wrong_number', 'other'} or not isinstance(details, str) or len(details) > 500:
        raise APIError('invalid_input', 'دلیل و توضیح حداکثر۵۰۰نویسه‌ای گزارش را بررسی کن.')
    phone_hash = confirmed_phone_hash(token, phone)
    grant = lookup_grant(token, report=True, recipient_hash=phone_hash)
    with transaction.atomic():
        RecipientState.objects.get_or_create(phone_hash=grant.recipient_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=grant.recipient_hash)
        grant = lookup_grant(token, report=True, lock=True, recipient_hash=phone_hash)
        item, _ = AbuseReport.objects.get_or_create(grant=grant, defaults={'reason': reason, 'details': details})
        state.blocked = True
        state.save(update_fields=['blocked', 'updated_at'])
    return {'receipt': str(item.id), 'blocked': True}
