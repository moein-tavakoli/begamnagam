"""Privileged operational archival; never asserts a delivery outcome or refunds."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import MessageDelivery, OperatorAudit, Order, Outbox
from .services import APIError


def archivable_outbox(now):
    cutoff = now - timedelta(hours=48)
    return Outbox.objects.filter(state='unknown', created_at__lte=cutoff,
        order__status=Order.Status.UNKNOWN, order__delivery__status=MessageDelivery.Status.UNKNOWN,
        order__delivery__created_at__lte=cutoff)


def archive_unknown_outbox(event_id, reason, *, actor=None):
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
        raise APIError('reason_required', 'دلیل بایگانی باید بین ۳ تا ۲۰۰ نویسه باشد.')
    order_id = Outbox.objects.values_list('order_id', flat=True).get(pk=event_id)
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_id)
        event = Outbox.objects.select_for_update().get(pk=event_id)
        delivery = MessageDelivery.objects.select_for_update().get(order=order)
        if event.state == 'archived':
            return event
        now = timezone.now()
        if not archivable_outbox(now).filter(pk=event.pk).exists():
            raise APIError('archive_conflict', 'فقط ارسال نامعلوم قدیمی‌تر از ۴۸ ساعت قابل بایگانی است.', 409)
        event.state = 'archived'
        event.processed_at = now
        event.save(update_fields=['state', 'processed_at'])
        OperatorAudit.objects.create(actor=actor, action='archive_unknown_outbox', object_id=str(event.pk),
            reason=reason.strip(), before={'queue_state': 'unknown'},
            after={'queue_state': 'archived', 'order_status': order.status, 'delivery_status': delivery.status})
        return event
