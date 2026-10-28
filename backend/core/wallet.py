"""Integer-toman wallet ledger. Every movement and its balance commit together.

Lock order: target order/purchase/topup, then Account. No path acquires a target
after locking the account. Refund credits ignore feature switches by design.
"""
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Account, FinancialEvent, Order, PaymentAttempt, Refund, WalletEntry, WalletTopup
from .payment_options import WALLET_TERMS_VERSION, options
from .providers import Zarinpal, ProviderDisabled, ProviderRejected, ProviderUnknown
from .services import APIError, limited


def balance_field(environment=None):
    return 'wallet_balance_toman' if (environment == 'live' if environment else not settings.DEMO_MODE) else 'demo_wallet_balance_toman'


def has_open_checkout(user):
    rows = PaymentAttempt.objects.filter(Q(order__owner=user) | Q(purchase__owner=user) | Q(wallet_topup__owner=user),
        status__in=['created', 'pending', 'unknown'])
    rows = rows.exclude(environment='live') if settings.DEMO_MODE else rows.filter(environment='live')
    return rows.exists()


def summary(user):
    account = Account.objects.get(user=user)
    return {**options(), 'balance_toman': str(getattr(account, balance_field())), 'withdrawable': False}


def topup_data(topup):
    attempt = PaymentAttempt.objects.filter(wallet_topup=topup).first()
    status = 'credited' if topup.credited_at else attempt.status if attempt else 'unknown'
    return {'id': str(topup.pk), 'amount_toman': topup.amount_toman, 'status': status,
        'created_at': topup.created_at, 'redirect_url': attempt.redirect_url if attempt and status == 'pending' else None}


def movement(account, kind, amount, environment, **source):
    """Internal helper; caller has a target lock and an atomic transaction."""
    if type(amount) is not int or not 1 <= amount <= 2147483647:
        raise APIError('invalid_amount', 'مبلغ تراکنش معتبر نیست.', 422)
    account = Account.objects.select_for_update().get(pk=account.pk)
    field = balance_field(environment)
    delta = -amount if kind in {'order_debit', 'package_debit'} else amount
    result = getattr(account, field) + delta
    if result < 0:
        raise APIError('wallet_insufficient', 'موجودی کیف پول کافی نیست؛ ابتدا آن را شارژ کن.', 409)
    if result > 9223372036854775807:
        raise APIError('wallet_reconciliation', 'موجودی نیازمند بررسی است.', 503)
    entry = WalletEntry.objects.create(account=account, kind=kind, amount_toman=amount,
        balance_after_toman=result, environment=environment, **source)
    setattr(account, field, result)
    account.save(update_fields=[field])
    return entry


def begin_topup(user, data, key):
    if (not isinstance(data, dict) or set(data) != {'amount_toman', 'consent', 'terms_version'}
            or type(data.get('amount_toman')) is not int or not 1 <= data['amount_toman'] <= 2147483647):
        raise APIError('invalid_input', 'مبلغ شارژ باید عدد صحیح و مثبت به تومان باشد.', 422)
    if data.get('consent') is not True or data.get('terms_version') != WALLET_TERMS_VERSION:
        raise APIError('wallet_consent_required', 'شرایط اعتبار غیرقابل برداشت کیف پول را تأیید کن.', 422)
    try:
        key = uuid.UUID(str(key))
    except (TypeError, ValueError, AttributeError):
        raise APIError('invalid_input', 'کلید یکتای درخواست شارژ معتبر نیست.', 422) from None
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        account = Account.objects.get(user=user)
        if account.suspended or account.deletion_requested_at:
            raise APIError('account_unavailable', 'شارژ این حساب فعلاً مجاز نیست.', 403)
        previous = WalletTopup.objects.filter(owner=user, idempotency_key=key).first()
        if previous:
            if previous.amount_toman != data['amount_toman'] or (previous.environment == 'live') != (not settings.DEMO_MODE):
                raise APIError('idempotency_conflict', 'کلید قبلی برای مبلغ دیگری ثبت شده است.', 409)
            return topup_data(previous)
        state = options()
        if not state['wallet_enabled'] or not state['gateway_enabled']:
            raise APIError('payment_disabled', 'شارژ کیف پول فعلاً فعال نیست.', 409)
        limited('wallet-topup', str(user.pk), 5, 60)
        if has_open_checkout(user):
            raise APIError('payment_reconciliation', 'یک پرداخت باز داری؛ ابتدا وضعیت آن را بررسی کن.', 409)
        topup = WalletTopup.objects.create(owner=user, idempotency_key=key, amount_toman=data['amount_toman'],
            environment=settings.PROVIDER_ENVIRONMENT, consent_at=timezone.now(), terms_version=WALLET_TERMS_VERSION)
        attempt = PaymentAttempt.objects.create(wallet_topup=topup, provider='zarinpal', environment=topup.environment,
            amount_toman=topup.amount_toman, status='unknown', return_to_wallet=True)
    try:
        result = Zarinpal().request(amount_toman=attempt.amount_toman,
            callback_url=settings.APP_BASE_URL + '/api/v1/payments/return/zarinpal')
    except ProviderRejected:
        PaymentAttempt.objects.filter(pk=attempt.pk).update(status='failed', checked_at=timezone.now())
        return topup_data(topup)
    except (ProviderUnknown, ProviderDisabled):
        return topup_data(topup)
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        attempt.authority, attempt.redirect_url, attempt.status = result.authority, result.redirect_url, 'pending'
        attempt.save(update_fields=['authority', 'redirect_url', 'status', 'updated_at'])
    return topup_data(topup)


def verify_topup(attempt_id):
    meta = PaymentAttempt.objects.filter(pk=attempt_id, provider='zarinpal', wallet_topup__isnull=False).values('wallet_topup_id').first()
    if not meta:
        return
    with transaction.atomic():
        topup = WalletTopup.objects.select_for_update().get(pk=meta['wallet_topup_id'])
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        if attempt.environment != settings.PROVIDER_ENVIRONMENT:
            return
        if topup.credited_at or not attempt.authority or (attempt.lease_until and attempt.lease_until > timezone.now()):
            return
        attempt.lease_until = timezone.now() + timedelta(seconds=30)
        attempt.save(update_fields=['lease_until'])
        authority, amount = attempt.authority, attempt.amount_toman
    try:
        verified = Zarinpal().verify(authority=authority, amount_toman=amount)
    except (ProviderUnknown, ProviderRejected, ProviderDisabled):
        PaymentAttempt.objects.filter(pk=attempt_id).update(status='unknown', checked_at=timezone.now(), lease_until=None)
        return
    try:
        with transaction.atomic():
            topup = WalletTopup.objects.select_for_update().get(pk=meta['wallet_topup_id'])
            attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
            if topup.credited_at:
                return
            if attempt.amount_toman != topup.amount_toman or attempt.environment != topup.environment:
                raise APIError('payment_mismatch', 'پرداخت نیازمند تطبیق است.', 409)
            # Persist proof first; all following writes roll back on any mismatch.
            attempt.status, attempt.provider_reference = 'verified', verified.reference
            attempt.checked_at, attempt.lease_until = timezone.now(), None
            attempt.save(update_fields=['status', 'provider_reference', 'checked_at', 'lease_until', 'updated_at'])
            account = Account.objects.get(user_id=topup.owner_id)
            movement(account, 'topup', amount, topup.environment, topup=topup)
            FinancialEvent.objects.get_or_create(payment=attempt, kind='payment', defaults={'amount_toman': amount})
            topup.credited_at = timezone.now()
            topup.save(update_fields=['credited_at'])
    except IntegrityError:
        # The same bank receipt cannot fund a second wallet or checkout.
        PaymentAttempt.objects.filter(pk=attempt_id).exclude(status='verified').update(
            status='unknown', checked_at=timezone.now(), lease_until=None)
        from .models import OperationalAlert
        OperationalAlert.objects.update_or_create(code='wallet_receipt_conflict',
            defaults={'severity': 'critical', 'active': True, 'count': 1})


@transaction.atomic
def credit_refund(refund_id):
    meta = Refund.objects.select_related('payment__order', 'payment__purchase').get(pk=refund_id)
    payment = meta.payment
    if payment.order_id:
        Order.objects.select_for_update().get(pk=payment.order_id)
    elif payment.purchase_id:
        from .models import CreditPurchase
        purchase = CreditPurchase.objects.select_for_update().get(pk=payment.purchase_id)
        if purchase.credited_at:
            raise APIError('refund_conflict', 'اعتبار بسته قبلاً تخصیص یافته؛ ابتدا باید تطبیق انجام شود.', 409)
    payment = PaymentAttempt.objects.select_for_update().get(pk=payment.pk)
    refund = Refund.objects.select_for_update().get(pk=refund_id)
    if refund.status == 'refunded' or WalletEntry.objects.filter(refund=refund).exists():
        return
    if not payment.return_to_wallet or payment.status != 'verified' or refund.amount_toman != payment.amount_toman or payment.wallet_topup_id:
        raise APIError('refund_conflict', 'برگشت اعتبار نیازمند تطبیق است.', 409)
    owner_id = meta.payment.order.owner_id if payment.order_id else meta.payment.purchase.owner_id
    account = Account.objects.get(user_id=owner_id)
    movement(account, 'payment_return', refund.amount_toman, payment.environment, refund=refund)
    refund.status, refund.provider_reference = 'refunded', 'wallet:' + str(refund.pk)
    refund.save(update_fields=['status', 'provider_reference', 'updated_at'])
    FinancialEvent.objects.get_or_create(refund=refund, defaults={'payment': payment, 'kind': 'refund', 'amount_toman': refund.amount_toman})


@transaction.atomic
def return_order(order, reason):
    """Caller holds the order lock. No unknown outcome is blindly replayed."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    debit = WalletEntry.objects.filter(order=order, kind='order_debit').first()
    if debit and order.status not in {'failed', 'cancelled'}:
        from .models import MessageDelivery
        uncertain = reason == 'unknown_deadline' and MessageDelivery.objects.filter(order=order,
            status__in=['unknown', 'accepted', 'submitting'], created_at__lt=timezone.now()-timedelta(hours=24)).exists()
        if not uncertain:
            raise APIError('refund_conflict', 'نتیجهٔ این ارسال برای برگشت هزینه تعیین تکلیف نشده است.', 409)
    if debit and not WalletEntry.objects.filter(order=order, kind='order_return').exists():
        account = Account.objects.get(pk=debit.account_id)
        movement(account, 'order_return', debit.amount_toman, debit.environment, order=order)


@transaction.atomic
def pay_order(user, order_id):
    """Read an already-paid historical wallet order without charging it again."""
    order = Order.objects.select_for_update().filter(owner=user, pk=order_id).first()
    if not order:
        raise APIError('not_found', 'سفارش پیدا نشد.', 404)
    if order.payment_method == 'wallet' and order.paid_at:
        return order
    raise APIError('package_required', 'کیف پول برای خرید بستهٔ پیام است؛ پرداخت تکی ارسال بسته است.', 409)
