"""Provider workflows: commit intent, make one bounded call, reconcile uncertainty."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import Order, PaymentAttempt, FinancialEvent, MessageDelivery, Outbox, RecipientState, Refund
from .providers import Zarinpal, ProviderDisabled, ProviderRejected, ProviderUnknown
from .services import APIError, PAYMENT_WINDOW, dispatch, recipient_unavailable


def request_refund(payment, reason):
    # Full refund only; all reasons converge on the same durable obligation.
    refund, _ = Refund.objects.get_or_create(payment=payment,
        defaults={'amount_toman': payment.amount_toman, 'reason_code': reason})
    return refund


def begin_payment(user, order_id, key):
    if settings.PAYMENT_BACKEND != 'zarinpal':
        raise APIError('payment_disabled', 'درگاه هنوز فعال نشده است.', 503)
    from .safety import ensure_open
    ensure_open()
    try:
        request_key = uuid.UUID(str(key))
    except (ValueError, TypeError, AttributeError):
        raise APIError('invalid_input', 'کلید یکتای پرداخت معتبر نیست.')
    with transaction.atomic():
        order = Order.objects.select_for_update().filter(id=order_id, owner=user).first()
        if not order:
            raise APIError('not_found', 'درخواست پیدا نشد.', 404)
        if order.paid_at:
            return {'order_id': str(order.id), 'paid': True}
        attempt = order.payment_attempts.order_by('-created_at').first()
        if attempt:
            if attempt.authority and attempt.status == 'pending':
                return {'attempt_id': str(attempt.id), 'redirect_url': attempt.redirect_url}
            # A request timeout may have created an authority we did not receive.
            # Do not create another payment request automatically.
            raise APIError('payment_reconciliation', 'وضعیت تلاش قبلی در حال بررسی است؛ دوباره پرداخت نکن.', 409)
        if order.status != 'awaiting_payment' or order.created_at + PAYMENT_WINDOW <= timezone.now():
            raise APIError('payment_expired', 'مهلت پرداخت تمام شده است.', 409)
        state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
        if state.blocked:
            raise recipient_unavailable()
        if PaymentAttempt.objects.filter(request_key=request_key).exists():
            raise APIError('idempotency_conflict', 'این کلید برای تلاش دیگری ثبت شده است.', 409)
        attempt = PaymentAttempt.objects.create(order=order, request_key=request_key,
            provider='zarinpal', environment=settings.PROVIDER_ENVIRONMENT,
            amount_toman=order.amount_toman, status='unknown')
    try:
        result = Zarinpal().request(amount_toman=attempt.amount_toman,
            callback_url=settings.APP_BASE_URL + '/api/v1/payments/return/zarinpal')
    except (ProviderUnknown, ProviderDisabled):
        raise APIError('payment_reconciliation', 'وضعیت پرداخت نیاز به بررسی دارد؛ دوباره پرداخت نکن.', 503) from None
    except ProviderRejected:
        PaymentAttempt.objects.filter(pk=attempt.pk).update(status='failed', checked_at=timezone.now())
        raise APIError('payment_unavailable', 'درگاه این درخواست را نپذیرفت؛ هزینه‌ای تأیید نشده است.', 503) from None
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        attempt.authority, attempt.redirect_url, attempt.status = result.authority, result.redirect_url, 'pending'
        attempt.save(update_fields=['authority', 'redirect_url', 'status', 'updated_at'])
    return {'attempt_id': str(attempt.id), 'redirect_url': attempt.redirect_url}


def verify_payment(attempt_id):
    meta = PaymentAttempt.objects.filter(pk=attempt_id, provider='zarinpal').values('order_id').first()
    if not meta:
        return
    with transaction.atomic():
        Order.objects.select_for_update().get(pk=meta['order_id'])
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        if not attempt.authority or attempt.applied_to_order or attempt.status == 'verified':
            return
        if attempt.lease_until and attempt.lease_until > timezone.now():
            return
        attempt.lease_until = timezone.now() + timedelta(seconds=30)
        attempt.save(update_fields=['lease_until'])
        authority, amount = attempt.authority, attempt.amount_toman
    try:
        verified = Zarinpal().verify(authority=authority, amount_toman=amount)
    except (ProviderUnknown, ProviderDisabled):
        PaymentAttempt.objects.filter(pk=attempt_id).update(status='unknown', checked_at=timezone.now(), lease_until=None)
        return
    except ProviderRejected as exc:
        # -51 (not paid yet) may be followed by a later successful payment. The
        # reconciler retains the authority until it reaches a terminal outcome.
        PaymentAttempt.objects.filter(pk=attempt_id).update(status='pending' if str(exc) == 'payment_rejected_51' else 'unknown', checked_at=timezone.now(), lease_until=None)
        return
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=meta['order_id'])
        state = RecipientState.objects.select_for_update().filter(phone_hash=order.recipient_hash).first()
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        if attempt.status == 'verified':
            return
        attempt.provider_reference = verified.reference
        attempt.status = 'verified'
        attempt.checked_at = timezone.now()
        attempt.lease_until = None
        FinancialEvent.objects.get_or_create(payment=attempt, kind='payment', defaults={'amount_toman': amount})
        valid = not order.paid_at and order.status == 'awaiting_payment' and order.created_at + PAYMENT_WINDOW > timezone.now()
        valid = valid and state is not None and not state.blocked and not order.owner.account.suspended and not order.owner.account.deletion_requested_at
        if valid:
            attempt.applied_to_order = True
            order.paid_at = timezone.now()
            order.payment_mode = attempt.environment
            order.status = 'queued'
            order.save(update_fields=['paid_at', 'payment_mode', 'status', 'updated_at'])
            MessageDelivery.objects.get_or_create(order=order, defaults={'provider': 'kavenegar',
                'environment': attempt.environment, 'status': 'queued', 'local_id': (uuid.uuid4().int % (2**63-1)) or 1})
            event, _ = Outbox.objects.get_or_create(order=order, defaults={'available_at': timezone.now()})
            transaction.on_commit(lambda: dispatch(event.pk))
        else:
            # Late success or extra receipt is captured but never creates another SMS.
            request_refund(attempt, 'late_or_unavailable')
            if not order.paid_at:
                order.status = 'cancelled'
                order.save(update_fields=['status', 'updated_at'])
        attempt.save(update_fields=['provider_reference', 'status', 'checked_at', 'lease_until', 'applied_to_order', 'updated_at'])


def reconcile_payments():
    due = timezone.now() - timedelta(seconds=30)
    for attempt in PaymentAttempt.objects.filter(provider='zarinpal', authority__gt='', status__in=['pending', 'unknown']).order_by('created_at')[:100]:
        if not attempt.checked_at or attempt.checked_at < due:
            verify_payment(attempt.id)


def process_refund(refund_id):
    meta = Refund.objects.filter(pk=refund_id).values('payment__order_id').first()
    if not meta:
        return
    with transaction.atomic():
        Order.objects.select_for_update().get(pk=meta['payment__order_id'])
        refund = Refund.objects.select_for_update().select_related('payment__order').get(pk=refund_id)
        if refund.status == 'refunded':
            return
        if refund.payment.provider == 'demo':
            refund.status = 'refunded'
            refund.provider_reference = 'demo-refund-' + str(refund.id)
            refund.save(update_fields=['status', 'provider_reference', 'updated_at'])
            FinancialEvent.objects.get_or_create(refund=refund, defaults={'payment': refund.payment, 'kind': 'refund', 'amount_toman': refund.amount_toman})
            return
        if refund.status == 'processing' and refund.updated_at > timezone.now() - timedelta(seconds=30):
            return
        reconcile_only = refund.status in {'processing', 'unknown'}
        refund.status = 'processing'
        refund.save(update_fields=['status', 'updated_at'])
        authority = refund.payment.authority
        # Reversal is not a general post-settlement refund. Those cases stay as
        # manual obligations with alerts; never mark a submitted request refunded.
        outside_reverse_window = refund.payment.created_at < timezone.now() - timedelta(minutes=30)
    try:
        if reconcile_only or outside_reverse_window:
            if Zarinpal().inquire(authority=authority) != 'REVERSED':
                raise ProviderUnknown('refund_requires_operator')
        else:
            Zarinpal().reverse(authority=authority)
    except (ProviderUnknown, ProviderRejected, ProviderDisabled):
        Refund.objects.filter(pk=refund_id).update(status='unknown', updated_at=timezone.now())
        return
    with transaction.atomic():
        refund = Refund.objects.select_for_update().get(pk=refund_id)
        refund.status = 'refunded'
        refund.provider_reference = 'reverse-' + authority
        refund.save(update_fields=['status', 'provider_reference', 'updated_at'])
        FinancialEvent.objects.get_or_create(refund=refund, defaults={'payment': refund.payment, 'kind': 'refund', 'amount_toman': refund.amount_toman})
