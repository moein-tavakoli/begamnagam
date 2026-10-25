import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Order, Outbox, RecipientState, MessageDelivery
from .moderation import TEMPLATES, ModerationRejected, moderate

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def deliver_message(event_id):
    if MessageDelivery.objects.filter(order__outbox__pk=event_id, provider="kavenegar").exists():
        from .provider_delivery import submit_delivery
        return submit_delivery(event_id)
    # A committed outbox and row locks make repeated broker deliveries harmless.
    # Live adapters are deliberately unavailable until a provider-specific
    # idempotency and delivery-receipt implementation exists.
    with transaction.atomic():
        event_meta = Outbox.objects.filter(pk=event_id).values("order_id").first()
        if not event_meta:
            return
        order = Order.objects.select_for_update().get(id=event_meta["order_id"])
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        event = Outbox.objects.select_for_update().get(pk=event_id)
        if event.state != "pending" or event.available_at > timezone.now():
            return
        from .safety import defer_until_open
        if defer_until_open(event): return
        if order.status != Order.Status.QUEUED or not order.paid_at:
            event.state = "cancelled"
        elif state.blocked or order.owner.account.suspended or order.owner.account.deletion_requested_at:
            order.status = Order.Status.CANCELLED
            event.state = "cancelled"
            event.last_error_code = "recipient_unavailable"
        elif not settings.DEMO_MODE or settings.SMS_BACKEND != "console":
            order.status = Order.Status.FAILED
            event.state = "failed"
            event.last_error_code = "sms_disabled"
        else:
            try:
                moderate(order.text)
                if order.text not in TEMPLATES.get(order.category, []):
                    raise ModerationRejected("unreviewed_template")
            except ModerationRejected:
                order.status = Order.Status.FAILED
                event.state = "failed"
                event.last_error_code = "moderation_rejected"
            else:
                # No phone, message content or sender identity is logged.
                logger.info("Demo SMS simulated order=%s recipient=%s", order.id, order.recipient_masked)
                state.last_sent_at = timezone.now()
                state.save(update_fields=["last_sent_at", "updated_at"])
                from .recipient import activate_grant
                activate_grant(order)
                order.status = Order.Status.DELIVERED_DEMO
                event.state = "sent"
        delivery, _ = MessageDelivery.objects.get_or_create(order=order)
        delivery.status = {"sent": "delivered_demo", "cancelled": "suppressed", "failed": "failed"}[event.state]
        delivery.attempts += 1
        delivery.resolved_at = timezone.now()
        delivery.save(update_fields=["status", "attempts", "resolved_at", "updated_at"])
        if event.state in {"cancelled", "failed"}:
            from .services import record_demo_refund
            record_demo_refund(order, "delivery_unavailable")
        event.attempts += 1
        event.processed_at = timezone.now()
        event.save(update_fields=["state", "attempts", "processed_at", "last_error_code"])
        order.save(update_fields=["status", "updated_at"])


@shared_task(ignore_result=True)
def reconcile_outbox():
    from .services import dispatch
    for event_id in Outbox.objects.filter(state="pending", available_at__lte=timezone.now()).values_list("id", flat=True)[:100]:
        dispatch(event_id)


@shared_task(ignore_result=True)
def expire_unpaid_orders():
    now = timezone.now()
    from .services import release_free_credit
    expired = Order.objects.filter(status=Order.Status.AWAITING_PAYMENT,
        created_at__lt=now-timedelta(minutes=15)).values_list("pk", flat=True)[:100]
    for order_id in expired:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_id)
            if order.status != Order.Status.AWAITING_PAYMENT or order.created_at >= now-timedelta(minutes=15):
                continue
            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])
            release_free_credit(order)
    # An emergency/broker outage must not hold an unsubmitted paid order forever.
    # Leased/accepted/unknown submissions are queried, never expired as unsent.
    due = Order.objects.filter(status=Order.Status.QUEUED, paid_at__lt=now-timedelta(hours=24)).values_list('pk', flat=True)[:100]
    for order_id in due:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_id)
            RecipientState.objects.select_for_update().filter(phone_hash=order.recipient_hash).first()
            event = Outbox.objects.select_for_update().filter(order=order, state='pending').first()
            delivery = MessageDelivery.objects.select_for_update().filter(order=order, status='queued').first()
            if not event or not delivery or order.status != 'queued': continue
            order.status = 'cancelled'
            event.state, event.last_error_code, event.processed_at = 'cancelled', 'queue_expired', now
            delivery.status, delivery.resolved_at = 'expired', now
            order.save(update_fields=['status','updated_at'])
            event.save(update_fields=['state','last_error_code','processed_at'])
            delivery.save(update_fields=['status','resolved_at','updated_at'])
            from .services import record_demo_refund
            record_demo_refund(order, 'queue_expired')


@shared_task(ignore_result=True)
def prune_private_data():
    from io import StringIO
    from django.core.management import call_command
    call_command("prune_private_data", stdout=StringIO())
    call_command("clearsessions", stdout=StringIO())


@shared_task(ignore_result=True)
def reconcile_providers():
    from .provider_services import reconcile_payments, process_refund
    from .provider_delivery import reconcile_delivery
    from .models import Refund
    from .safety import refresh_alerts
    refresh_alerts()
    reconcile_payments()
    for delivery_id in MessageDelivery.objects.filter(provider='kavenegar', status__in=['submitting', 'unknown', 'accepted']).values_list('pk', flat=True)[:100]:
        reconcile_delivery(delivery_id)
    for refund_id in Refund.objects.exclude(status='refunded').values_list('pk', flat=True)[:100]:
        process_refund(refund_id)


@shared_task(ignore_result=True)
def verify_provider_payment(attempt_id):
    from .provider_services import verify_payment
    verify_payment(attempt_id)
