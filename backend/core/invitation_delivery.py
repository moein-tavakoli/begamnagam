from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .budget import reserve_cost, observe_cost
from .invitations import compose, lock_phone
from .models import Account, Invitation, InvitationSend, Order, RecipientGrant, SafetyControl
from .privacy import decrypt, digest
from .providers import Kavenegar, ProviderDisabled, ProviderRejected, ProviderUnknown
from .services import models_busy_query


def locked(send_id):
    meta = InvitationSend.objects.filter(pk=send_id).values('invitation_id', 'invitation__phone_hash').first()
    if not meta:
        return None
    state = lock_phone(meta['invitation__phone_hash'])
    invitation = Invitation.objects.select_for_update().get(pk=meta['invitation_id'])
    send = InvitationSend.objects.select_for_update().get(pk=send_id)
    return state, invitation, send


def fail(send, code, status='cancelled'):
    send.status, send.last_error_code, send.lease_until = status, code, None
    send.save(update_fields=['status', 'last_error_code', 'lease_until', 'updated_at'])


def eligible(state, invitation, send):
    if invitation.registered_at or Account.objects.filter(phone_hash=invitation.phone_hash).exists():
        fail(send, 'registered')
        return False
    account = Account.objects.select_for_update(of=('self',)).select_related('user').get(user_id=invitation.inviter_id)
    if account.suspended or account.deletion_requested_at or not account.user.is_active:
        fail(send, 'account_unavailable')
        return False
    if state.blocked:
        fail(send, 'recipient_unavailable')
        return False
    return True


def apply_result(state, send, result):
    now = timezone.now()
    send.lease_until, send.checked_at = None, now
    if result.reference:
        send.provider_reference = result.reference
    send.status = result.status if result.status in ['accepted', 'delivered', 'failed', 'delivered_demo'] else 'unknown'
    if send.status in ['accepted', 'delivered', 'delivered_demo'] and not send.accepted_at:
        send.accepted_at = now
        state.last_sent_at = now
        state.save(update_fields=['last_sent_at', 'updated_at'])
        RecipientGrant.objects.filter(invitation_send=send, activated_at__isnull=True).update(
            activated_at=now, stop_expires_at=now+timedelta(days=365), report_expires_at=now+timedelta(days=30))
    send.last_error_code = 'provider_terminal_failure' if send.status == 'failed' else ''
    send.save()


def check_snapshot(send):
    token = send.full_sms.rsplit('/r/', 1)[-1]
    return (len(token) == 8 and token.isascii() and token.isalnum() and send.full_sms == compose(token)
        and RecipientGrant.objects.filter(invitation_send=send, token_digest=digest('recipient-token:'+token)).exists())


def submit(send_id):
    # Intent is committed before the bounded network call. A worker crash or
    # timeout leaves a submitting row for status lookup, never another submit.
    with transaction.atomic():
        rows = locked(send_id)
        if not rows:
            return
        state, invitation, send = rows
        if send.status != 'pending' or send.available_at > timezone.now():
            return
        if send.created_at < timezone.now()-timedelta(hours=48):
            fail(send, 'queue_expired')
            return
        if not eligible(state, invitation, send):
            return
        from .safety import defer_until_open
        if defer_until_open(send):
            return
        if not check_snapshot(send):
            fail(send, 'snapshot_invalid', 'failed')
            return
        if state.last_sent_at and state.last_sent_at > timezone.now()-timedelta(hours=24):
            send.available_at = state.last_sent_at+timedelta(hours=24)
            send.last_error_code = 'recipient_cooldown'
            send.save(update_fields=['available_at', 'last_error_code'])
            return
        if Order.objects.filter(recipient_hash=invitation.phone_hash).filter(models_busy_query(timezone.now())).exists():
            send.available_at = timezone.now()+timedelta(minutes=15)
            send.last_error_code = 'recipient_unavailable'
            send.save(update_fields=['available_at', 'last_error_code'])
            return
        demo = send.provider == 'console' and settings.DEMO_MODE and settings.SMS_BACKEND == 'console'
        if not demo:
            if send.provider != 'kavenegar' or settings.SMS_BACKEND != 'kavenegar':
                fail(send, 'sms_disabled', 'failed')
                return
            try:
                if settings.PROVIDER_NETWORK_MODE == 'external' and settings.SMS_RECIPIENT_POLICY != 'all' and invitation.phone_hash not in settings.PILOT_RECIPIENT_HASHES:
                    raise ProviderDisabled('outside_pilot_allowlist')
                reserve_cost('invite:'+str(send.pk), 'invitation', settings.SMS_MAX_COST_RIAL)
            except ProviderDisabled as error:
                if str(error) == 'daily_budget_exhausted':
                    tomorrow = timezone.localtime()+timedelta(days=1)
                    send.available_at = tomorrow.replace(hour=settings.SENDING_START_HOUR, minute=0, second=0, microsecond=0)
                    send.last_error_code = 'service_unavailable'
                    send.save(update_fields=['available_at', 'last_error_code'])
                else:
                    fail(send, 'policy_unavailable', 'failed')
                return
        send.status = 'submitting'
        send.lease_until = timezone.now()+timedelta(seconds=30)
        send.save(update_fields=['status', 'lease_until', 'updated_at'])
    with transaction.atomic():
        state, invitation, send = locked(send_id)
        if send.status != 'submitting':
            return
        if not eligible(state, invitation, send):
            return
        # Stop/halt that committed before this lock wins over submission.
        SafetyControl.objects.select_for_update().get(pk=1)
        from .safety import defer_until_open
        if defer_until_open(send):
            send.status, send.lease_until = 'pending', None
            send.save(update_fields=['status', 'lease_until'])
            return
        send.submitted_at = timezone.now()
        send.save(update_fields=['submitted_at'])
        if demo:
            from .providers.kavenegar import SMSResult
            apply_result(state, send, SMSResult('delivered_demo'))
            return
        try:
            result = Kavenegar().submit(phone=decrypt(invitation.phone_cipher), text=send.full_sms, local_id=send.local_id)
        except ProviderRejected:
            fail(send, 'provider_rejected', 'failed')
        except (ProviderUnknown, ProviderDisabled):
            fail(send, 'submission_uncertain', 'unknown')
        else:
            observe_cost('invite:'+str(send.pk), result.cost_rial)
            apply_result(state, send, result)


def reconcile(send_id):
    with transaction.atomic():
        rows = locked(send_id)
        if not rows:
            return
        state, invitation, send = rows
        now = timezone.now()
        if send.provider != 'kavenegar' or send.status not in ['accepted', 'submitting', 'unknown']:
            return
        if (send.lease_until and send.lease_until > now) or (send.checked_at and send.checked_at > now-timedelta(minutes=5)):
            return
        send.lease_until = now+timedelta(seconds=30)
        send.save(update_fields=['lease_until'])
        local_id, reference = send.local_id, send.provider_reference
    try:
        result = Kavenegar().status(local_id=local_id, message_id=reference)
    except (ProviderDisabled, ProviderRejected, ProviderUnknown):
        InvitationSend.objects.filter(pk=send_id).update(lease_until=None, checked_at=timezone.now())
        return
    with transaction.atomic():
        state, invitation, send = locked(send_id)
        if send.status in ['delivered', 'failed']:
            return
        observe_cost('invite:'+str(send.pk), result.cost_rial)
        apply_result(state, send, result)
