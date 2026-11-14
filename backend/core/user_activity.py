"""Bounded per-user staff activity; message text is reviewed separately."""
import uuid
from django.conf import settings
from django.db.models import CharField, F, OuterRef, Q, Subquery, Value
from django.db.models.functions import Cast, Coalesce

from . import models as m
from .privacy import decrypt

PAGE_SIZE = 25


def account_summary(account):
    return {'id': account.pk, 'phone': decrypt(account.phone_cipher) if account.phone_cipher else '',
        'phone_masked': account.phone_masked, 'suspended': account.suspended}


def audit_activity(actor, account, section):
    m.OperatorAudit.objects.create(actor=actor, action='user_activity_viewed', object_id=str(account.pk),
        reason='مشاهدهٔ سابقهٔ کاربر در پنل مدیریت', after={'section': section})


def received_order_filter(account):
    if not account.phone_hash or not account.phone_cipher:
        return Q(pk__in=[])
    states = [m.Order.Status.ACCEPTED, m.Order.Status.DELIVERED]
    if settings.DEMO_MODE:
        states.append(m.Order.Status.DELIVERED_DEMO)
    return Q(recipient_hash=account.phone_hash, status__in=states)


def message_records(account):
    """Use a database union so pagination never loads full user histories."""
    empty = Value('', output_field=CharField())
    fields = ('_activity_at', '_id', '_kind', '_status', '_reason_code', '_message_tone',
        '_preview_id', '_order_id', '_direction')

    def records(rows, kind, *, identifier='pk', status='status', reason=None, tone=None,
                preview=None, order=None, direction='', activity_at=F('created_at')):
        return rows.annotate(_activity_at=activity_at, _id=Cast(identifier, CharField()),
            _kind=Value(kind, output_field=CharField()),
            _status=F(status), _reason_code=F(reason) if reason else empty,
            _message_tone=F(tone) if tone else empty,
            _preview_id=Cast(preview, CharField()) if preview else empty,
            _order_id=Cast(order, CharField()) if order else empty,
            _direction=Value(direction, output_field=CharField())).values(*fields)

    orders = m.Order.objects.filter(owner_id=account.user_id)
    received = m.Order.objects.filter(received_order_filter(account)).exclude(owner_id=account.user_id)
    combined = [
        records(orders, 'order', tone='preview__message_tone', preview='preview_id', order='pk', direction='sent'),
        records(received, 'order', tone='preview__message_tone', preview='preview_id', order='pk', direction='received',
                activity_at=Coalesce('delivery__resolved_at', 'delivery__accepted_at', 'created_at')),
    ]
    audits = m.ModerationAudit.objects.filter(owner_id=account.user_id, outcome='rejected')
    attempts = m.MessageAttempt.objects.filter(owner_id=account.user_id)
    # An accepted preview later becomes an order; show its final order only.
    unconverted = attempts.exclude(preview_id__in=orders.values('preview_id'))
    combined.append(records(unconverted, 'attempt', reason='reason_code', tone='message_tone', preview='preview_id'))
    audits = audits.exclude(event_id__in=attempts.filter(moderation_event_id__isnull=False).values('moderation_event_id'))
    combined.append(records(audits, 'moderation', identifier='event_id', status='outcome', reason='reason_code'))
    return combined[0].union(*combined[1:], all=True).order_by('-_activity_at', '_kind', '_id')


def message_recipient_phones(account, rows):
    orders = m.Order.objects.filter(Q(owner_id=account.user_id) | received_order_filter(account),
        pk__in=[row['id'] for row in rows if row['kind'] == 'order'])
    attempts = m.MessageAttempt.objects.filter(owner_id=account.user_id, pk__in=[row['id'] for row in rows if row['kind'] == 'attempt'])
    return {
        **{('order', str(pk)): decrypt(cipher) for pk, cipher in orders.values_list('pk', 'recipient_cipher') if cipher},
        **{('attempt', str(pk)): phone for pk, phone in attempts.values_list('pk', 'recipient_phone')},
    }


def message_sender_phones(account, rows):
    received_ids = [row['id'] for row in rows if row.get('direction') == 'received']
    orders = m.Order.objects.filter(received_order_filter(account), pk__in=received_ids).exclude(owner_id=account.user_id)
    return {str(pk): decrypt(cipher) for pk, cipher in orders.values_list('pk', 'owner__account__phone_cipher') if cipher}


def invitation_records(account, page):
    latest = m.InvitationSend.objects.filter(invitation_id=OuterRef('pk')).order_by('-ordinal', '-created_at', '-pk')
    invitations = m.Invitation.objects.filter(inviter_id=account.user_id).annotate(
        latest_status=Subquery(latest.values('status')[:1]), latest_reason=Subquery(latest.values('last_error_code')[:1]))
    total = invitations.count()
    rows = []
    for invitation in invitations.order_by('-created_at', '-pk')[(page-1)*PAGE_SIZE:page*PAGE_SIZE]:
        rows.append({'id': str(invitation.pk), 'record_id': str(invitation.pk), 'kind': 'invitation',
            'created_at': invitation.created_at, 'status': invitation.latest_status or 'pending',
            'reason_code': invitation.latest_reason or '',
            'phone': decrypt(invitation.phone_cipher) if invitation.phone_cipher else '',
            'phone_masked': invitation.phone_masked, 'registered_at': invitation.registered_at,
            'reward_awarded_at': invitation.reward_awarded_at})
    return total, rows


def activity_payload(account, section, page):
    if section == 'messages':
        records = message_records(account)
        total = records.count()
        rows = [{key.removeprefix('_'): value for key, value in record.items()}
            for record in records[(page-1)*PAGE_SIZE:page*PAGE_SIZE]]
        for row in rows:
            for key in ('id', 'preview_id', 'order_id'):
                if row[key]:
                    row[key] = str(uuid.UUID(row[key]))
            if not row['direction']:
                del row['direction']
            row['record_id'] = row['id']
        phones = message_recipient_phones(account, rows)
        sender_phones = message_sender_phones(account, rows)
        for row in rows:
            row['created_at'] = row.pop('activity_at')
            row['recipient_phone'] = phones.get((row['kind'], row['id']), '')
            if row.get('direction') == 'received':
                row['sender_phone'] = sender_phones.get(row['id'], '')
    else:
        total, rows = invitation_records(account, page)
    return {'account': account_summary(account), 'section': section, 'rows': rows,
        'total': total, 'page': page, 'page_size': PAGE_SIZE,
        'pagination': {'total': total, 'page': page, 'page_size': PAGE_SIZE, 'has_next': page*PAGE_SIZE < total}}
