"""Directed consent with outward handles that cannot link anonymous senders."""
import re
import uuid
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction

from .identity_settings import identity_requests_enabled
from .models import Account, IdentityConsent, IdentityReceipt, OperatorAudit, Order
from .privacy import decrypt, digest, normalize_phone
from .recipient_codes import ACTION_CODE_PATTERN
from .services import APIError, api, is_product_authenticated, limited
from .views import body


def unavailable():
    return APIError('identity_unavailable', 'این درخواست در دسترس نیست یا اجازهٔ نمایش شماره وجود ندارد.', 404)


def require_enabled():
    if not identity_requests_enabled():
        raise unavailable()


def active_accounts():
    return Account.objects.filter(
        user__is_active=True, suspended=False, deletion_requested_at__isnull=True,
    ).exclude(phone_cipher='')


def environment():
    return 'demo' if settings.DEMO_MODE else settings.PROVIDER_ENVIRONMENT


def lock_parties(subject_id, requester_id):
    # Account deletion takes Account -> Consent. Admission first locks its Order
    # to follow provider reconciliation's Order -> Account ordering too.
    return list(Account.objects.select_for_update(of=('self',)).filter(
        pk__in=[subject_id, requester_id],
    ).order_by('pk'))


def lock_actor(user):
    # Serialize with order creation's User lock before taking Order/Account.
    # NO KEY UPDATE permits unrelated audit FK key-share locks on this user.
    get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)


def source_context(source):
    return source.created_at.isoformat() if source and source.owner_hidden_at is None else None


def serialize(record):
    source = record.source_order
    return {
        'id': str(record.decision_id), 'status': record.status, 'revision': record.revision,
        'message_created_at': source_context(source),
        'message_excerpt': source.text[:100] if source_context(source) else '',
    }


def serialize_receipt(receipt):
    # Never disclose the shared pair ID, generation, revision or another source
    # message. Never-approved denials remain neutral to avoid linking messages
    # through simultaneous status changes on one internal pair.
    status = receipt.status if receipt.approved_once else 'pending'
    return {
        'id': str(receipt.pk), 'status': status, 'revision': 0,
        'message_created_at': None, 'requested_at': receipt.created_at.isoformat(),
    }


def audit(record, actor, action):
    OperatorAudit.objects.create(
        actor=actor, action='identity_' + action, object_id=str(record.pk),
        reason='explicit_account_action', before={}, after={'status': record.status, 'revision': record.revision},
    )


def request_identity(request, data):
    require_enabled()
    if not is_product_authenticated(request.user):
        raise APIError('authentication_required', 'همان شماره‌ای را تأیید کن که پیامک را دریافت کرده است.', 401)
    if set(data) != {'token'}:
        raise APIError('invalid_input', 'درخواست را فقط از لینک پیام دریافتی ثبت کن.', 422)
    requester = active_accounts().filter(user=request.user).first()
    if requester is None:
        raise unavailable()
    limited('identity-request-attempt', str(requester.pk), 30, 600)
    if not isinstance(data['token'], str) or not re.fullmatch(ACTION_CODE_PATTERN, data['token']):
        raise unavailable()
    from .recipient import lookup_grant
    grant = lookup_grant(data['token'], recipient_hash=requester.phone_hash)
    statuses = [Order.Status.DELIVERED_DEMO] if settings.DEMO_MODE else [Order.Status.ACCEPTED, Order.Status.DELIVERED]
    order = Order.objects.filter(
        preview_id=grant.preview_id, recipient_hash=requester.phone_hash,
        owner_hidden_at__isnull=True, status__in=statuses, delivery__environment=environment(),
    ).exclude(owner=request.user).first() if grant.preview_id else None
    subject = active_accounts().filter(user_id=order.owner_id).first() if order else None
    if subject is None:
        raise unavailable()
    with transaction.atomic():
        lock_actor(request.user)
        order = Order.objects.select_for_update(of=('self',)).filter(
            pk=order.pk, owner_id=subject.user_id, owner_hidden_at__isnull=True,
            recipient_hash=requester.phone_hash, status__in=statuses, delivery__environment=environment(),
        ).first()
        if order is None:
            raise unavailable()
        lock_parties(subject.pk, requester.pk)
        if active_accounts().filter(pk__in=[subject.pk, requester.pk]).count() != 2:
            raise unavailable()
        lookup_grant(data['token'], recipient_hash=requester.phone_hash)
        require_enabled()
        # Every accepted submission is counted equally; pair transitions must
        # not reveal whether separate anonymous sources share an author.
        limited('identity-submission', str(requester.pk), 20, 86400)
        record, created = IdentityConsent.objects.get_or_create(
            subject=subject, requester=requester, environment=environment(), defaults={'source_order': order},
        )
        record = IdentityConsent.objects.select_for_update().get(pk=record.pk)
        if created or record.status in {IdentityConsent.Status.DECLINED, IdentityConsent.Status.REVOKED}:
            if not created:
                record.status = IdentityConsent.Status.PENDING
                record.source_order = order
                record.revision = 0
                record.generation += 1
                record.decision_id = uuid.uuid4()
                record.save(update_fields=['status', 'source_order', 'revision', 'generation', 'decision_id', 'updated_at'])
            audit(record, request.user, 'requested')
        receipt = IdentityReceipt.objects.filter(consent=record, source_order=order, generation=record.generation).first()
        if receipt is None:
            receipt = IdentityReceipt.objects.filter(consent=record, source_order=order, approved_once=False).first()
            if receipt is None:
                receipt = IdentityReceipt(consent=record, source_order=order)
            receipt.generation = record.generation
            receipt.status = record.status
            receipt.approved_once = record.status == IdentityConsent.Status.APPROVED
            receipt.save()
        return serialize_receipt(receipt)


@api(['GET'], authenticated=True)
def collection(request):
    require_enabled()
    direction = request.GET.get('direction', 'incoming')
    if direction not in {'incoming', 'outgoing'}:
        raise APIError('invalid_input', 'جهت درخواست معتبر نیست.', 422)
    try:
        page = int(request.GET.get('page', '1'))
    except (TypeError, ValueError):
        page = 0
    if not 1 <= page <= 1000000:
        raise APIError('invalid_input', 'صفحهٔ درخواست معتبر نیست.', 422)
    if direction == 'incoming':
        rows = IdentityConsent.objects.filter(
            subject=request.user.account, environment=environment(), status__in=['pending', 'approved'],
        ).order_by('-updated_at', '-pk')
        serializer = serialize
    else:
        rows = IdentityReceipt.objects.filter(consent__requester=request.user.account, consent__environment=environment()).order_by('-created_at', '-pk')
        serializer = serialize_receipt
    rows = rows.select_related('source_order') if direction == 'incoming' else rows
    return {
        'results': [serializer(row) for row in rows[(page-1)*20:page*20]],
        'count': rows.count(), 'page': page,
    }


@api(['POST'], authenticated=True)
def decision(request, consent_id):
    data = body(request)
    action = data.get('action')
    if action != 'revoke':
        require_enabled()
    if (set(data) - {'action', 'revision', 'consent'}
            or not isinstance(action, str) or action not in {'approve', 'decline', 'revoke'}
            or type(data.get('revision')) is not int or data['revision'] < 0):
        raise APIError('invalid_input', 'اقدام و نسخهٔ درخواست معتبر را بفرست.', 422)
    with transaction.atomic():
        lock_actor(request.user)
        pair = IdentityConsent.objects.filter(decision_id=consent_id, subject__user=request.user, environment=environment()).first()
        if pair is None:
            raise unavailable()
        lock_parties(pair.subject_id, pair.requester_id)
        record = IdentityConsent.objects.select_for_update(of=('self',)).filter(
            decision_id=consent_id, subject__user=request.user, environment=environment(),
        ).first()
        if record is None:
            raise unavailable()
        if action != 'revoke':
            require_enabled()
        if action == 'revoke' and record.status == IdentityConsent.Status.REVOKED:
            return serialize(record)
        if record.revision != data['revision']:
            raise APIError('identity_changed', 'وضعیت درخواست عوض شده است. آن را دوباره بررسی کن.', 409)
        if action == 'approve':
            if data.get('consent') is not True:
                raise APIError('consent_required', 'نمایش شمارهٔ خودت فقط برای همین درخواست‌دهنده را تأیید کن.', 422)
            if record.status != IdentityConsent.Status.PENDING:
                raise APIError('identity_changed', 'برای نمایش دوبارهٔ شماره، درخواست تازه را بررسی کن.', 409)
            if active_accounts().filter(pk__in=[record.subject_id, record.requester_id]).count() != 2:
                raise unavailable()
        record.status = {
            'approve': IdentityConsent.Status.APPROVED,
            'decline': IdentityConsent.Status.DECLINED,
            'revoke': IdentityConsent.Status.REVOKED,
        }[action]
        record.revision += 1
        record.save(update_fields=['status', 'revision', 'updated_at'])
        updates = {'status': record.status}
        if action == 'approve':
            updates['approved_once'] = True
        IdentityReceipt.objects.filter(consent=record, generation=record.generation).update(**updates)
        audit(record, request.user, action)
        return serialize(record)


@api(['GET'], authenticated=True)
def phone(request, consent_id):
    require_enabled()
    # Read permission under the same lock as revocation. Every response checks
    # current consent and active accounts, without caching a decrypted number.
    with transaction.atomic():
        receipt = IdentityReceipt.objects.filter(
            pk=consent_id, consent__requester__user=request.user, consent__environment=environment(),
        ).select_related('consent').first()
        if receipt is None:
            raise unavailable()
        lock_parties(receipt.consent.subject_id, receipt.consent.requester_id)
        record = IdentityConsent.objects.select_for_update(of=('self',)).filter(
            pk=receipt.consent_id, requester__user=request.user, environment=environment(),
            status=IdentityConsent.Status.APPROVED,
        ).first()
        if (record is None or not active_accounts().filter(pk=record.requester_id).exists()
                or not IdentityReceipt.objects.filter(pk=consent_id, consent=record, generation=record.generation,
                                                      status=IdentityConsent.Status.APPROVED).exists()):
            raise unavailable()
        subject = active_accounts().filter(pk=record.subject_id).first()
        if subject is None:
            raise unavailable()
        require_enabled()
        try:
            value = normalize_phone(decrypt(subject.phone_cipher))
        except (InvalidToken, ValueError):
            raise unavailable() from None
        if digest(value) != subject.phone_hash:
            raise unavailable()
        return {'phone': value}
