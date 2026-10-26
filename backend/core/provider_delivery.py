from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Order, Outbox, RecipientState, MessageDelivery
from .moderation import is_reviewed_template, moderate, ModerationRejected
from .privacy import decrypt
from .budget import reserve_cost
from .providers import Kavenegar, ProviderDisabled, ProviderRejected, ProviderUnknown
from .provider_services import request_refund


def fail_paid(order, event, delivery, code, suppressed=False):
    order.status = 'cancelled' if suppressed else 'failed'
    event.state = 'cancelled' if suppressed else 'failed'
    event.last_error_code = code
    event.processed_at = timezone.now()
    delivery.status = 'suppressed' if suppressed else 'failed'
    delivery.last_error_code = code
    delivery.resolved_at = timezone.now()
    delivery.lease_until = None
    payment = order.payment_attempts.filter(applied_to_order=True).first()
    if payment:
        request_refund(payment, 'delivery_unavailable')
    elif order.is_free:
        from .services import release_free_credit
        release_free_credit(order)
    order.save(update_fields=['status', 'updated_at'])
    event.save(update_fields=['state', 'last_error_code', 'processed_at'])
    delivery.save()


def apply_result(order, state, event, delivery, result):
    delivery.checked_at = timezone.now()
    delivery.lease_until = None
    if result.reference:
        delivery.provider_reference = result.reference
    if result.status in {'accepted', 'delivered'}:
        if not delivery.accepted_at:
            from .recipient import activate_grant
            activate_grant(order)
            delivery.accepted_at = timezone.now()
            state.last_sent_at = timezone.now()
            state.save(update_fields=['last_sent_at', 'updated_at'])
        delivery.status = result.status
        order.status = result.status
        event.state = 'sent'
        event.processed_at = timezone.now()
        if result.status == 'delivered':
            delivery.resolved_at = timezone.now()
    elif result.status == 'failed':
        fail_paid(order, event, delivery, 'provider_terminal_failure')
        return
    else:
        delivery.status = 'unknown'
        order.status = 'unknown'
        event.state = 'unknown'
    delivery.save()
    order.save(update_fields=['status', 'updated_at'])
    event.save(update_fields=['state', 'processed_at'])


def submit_delivery(event_id):
    meta = Outbox.objects.filter(pk=event_id).values('order_id').first()
    if not meta:
        return
    # Persist submission intent before touching the network. An interrupted worker
    # leaves a leased submitting row, which is queried instead of re-submitted.
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=meta['order_id'])
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        event = Outbox.objects.select_for_update().get(pk=event_id)
        delivery = MessageDelivery.objects.select_for_update().get(order=order)
        if delivery.status != 'queued' or event.state != 'pending' or event.available_at > timezone.now():
            return
        from .safety import defer_until_open
        if defer_until_open(event): return
        if not hasattr(order.owner, 'account') or order.owner.account.suspended or order.owner.account.deletion_requested_at:
            fail_paid(order, event, delivery, 'account_unavailable', True)
            return
        if state.blocked:
            fail_paid(order, event, delivery, 'recipient_unavailable', True)
            return
        if settings.SMS_BACKEND != 'kavenegar':
            fail_paid(order, event, delivery, 'sms_disabled')
            return
        try:
            moderate(order.text)
            if not is_reviewed_template(order.category, order.text) or order.full_sms != order.preview.full_sms:
                raise ModerationRejected('unreviewed_snapshot')
            if (settings.PROVIDER_NETWORK_MODE == 'external' and settings.SMS_RECIPIENT_POLICY != 'all'
                    and order.recipient_hash not in settings.PILOT_RECIPIENT_HASHES):
                raise ProviderDisabled('outside_pilot_allowlist')
            reserve_cost('sms:' + str(delivery.submission_key), 'sms', settings.SMS_MAX_COST_RIAL)
        except ModerationRejected:
            fail_paid(order, event, delivery, 'moderation_rejected', True)
            return
        except ProviderDisabled:
            fail_paid(order, event, delivery, 'policy_unavailable', True)
            return
        delivery.status = 'submitting'
        delivery.lease_until = timezone.now() + timedelta(seconds=30)
        delivery.attempts += 1
        event.state = 'submitting'
        event.attempts += 1
        delivery.save()
        event.save(update_fields=['state', 'attempts'])
    # The recipient lock covers the actual bounded submission. A stop that commits
    # before this lock is checked suppresses; a stop after acceptance cannot recall.
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=meta['order_id'])
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        event = Outbox.objects.select_for_update().get(pk=event_id)
        delivery = MessageDelivery.objects.select_for_update().get(order=order)
        from .models import Account, SafetyControl
        from .safety import defer_until_open
        account = Account.objects.select_for_update().filter(user_id=order.owner_id).first()
        SafetyControl.objects.select_for_update().get(pk=1)
        if defer_until_open(event):
            delivery.status = 'queued'
            delivery.lease_until = None
            delivery.attempts -= 1
            event.state = 'pending'
            event.attempts -= 1
            delivery.save()
            event.save(update_fields=['state','attempts'])
            return
        if not account or account.suspended or account.deletion_requested_at:
            fail_paid(order, event, delivery, 'account_unavailable', True)
            return
        if state.blocked:
            fail_paid(order, event, delivery, 'recipient_unavailable', True)
            return
        try:
            result = Kavenegar().submit(phone=decrypt(order.recipient_cipher), text=order.full_sms, local_id=delivery.local_id)
        except ProviderRejected:
            fail_paid(order, event, delivery, 'provider_rejected')
        except (ProviderUnknown, ProviderDisabled):
            delivery.status = 'unknown'
            delivery.lease_until = None
            delivery.last_error_code = 'submission_uncertain'
            delivery.save()
            order.status = 'unknown'
            order.save(update_fields=['status', 'updated_at'])
            event.state = 'unknown'
            event.save(update_fields=['state'])
        else:
            from .budget import observe_cost
            observe_cost("sms:" + str(delivery.submission_key), result.cost_rial)
            apply_result(order, state, event, delivery, result)


def reconcile_delivery(delivery_id):
    meta = MessageDelivery.objects.filter(pk=delivery_id, provider='kavenegar').values('order_id').first()
    if not meta:
        return
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=meta['order_id'])
        delivery = MessageDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status not in {'accepted', 'submitting', 'unknown'} or (delivery.lease_until and delivery.lease_until > timezone.now()):
            return
        if delivery.checked_at and delivery.checked_at > timezone.now() - timedelta(seconds=30):
            return
        delivery.lease_until = timezone.now() + timedelta(seconds=30)
        delivery.save(update_fields=['lease_until'])
        local_id, reference = delivery.local_id, delivery.provider_reference
    try:
        result = Kavenegar().status(local_id=local_id, message_id=reference)
    except (ProviderUnknown, ProviderRejected, ProviderDisabled):
        MessageDelivery.objects.filter(pk=delivery_id).update(lease_until=None, checked_at=timezone.now())
        if delivery.created_at < timezone.now() - timedelta(hours=24):
            with transaction.atomic():
                locked = Order.objects.select_for_update().get(pk=meta['order_id'])
                payment = locked.payment_attempts.filter(applied_to_order=True).first()
                if payment: request_refund(payment, 'unknown_deadline')
        return
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=meta['order_id'])
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        event = Outbox.objects.select_for_update().get(order=order)
        delivery = MessageDelivery.objects.select_for_update().get(pk=delivery_id)
        if delivery.status == 'delivered':
            return
        apply_result(order, state, event, delivery, result)
        # A missing/aged provider record is never proof of no submission. After24h
        # compensate the buyer but retain reconciliation and never resend.
        if result.status == 'unknown' and delivery.created_at < timezone.now() - timedelta(hours=24):
            payment = order.payment_attempts.filter(applied_to_order=True).first()
            if payment:
                request_refund(payment, 'unknown_deadline')
