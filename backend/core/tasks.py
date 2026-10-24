import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Order, Outbox, RecipientState
from .moderation import TEMPLATES, ModerationRejected, moderate

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def deliver_message(event_id):
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
        if order.status != Order.Status.QUEUED or not order.paid_at:
            event.state = "cancelled"
        elif state.blocked:
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
                order.status = Order.Status.DELIVERED_DEMO
                event.state = "sent"
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
    Order.objects.filter(status=Order.Status.AWAITING_PAYMENT,
        created_at__lt=timezone.now() - timedelta(minutes=15)).update(status=Order.Status.CANCELLED)


@shared_task(ignore_result=True)
def prune_private_data():
    from io import StringIO
    from django.core.management import call_command
    call_command("prune_private_data", stdout=StringIO())
    call_command("clearsessions", stdout=StringIO())
