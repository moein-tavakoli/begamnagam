"""Configurable credit bundles; no client-supplied monetary or credit amounts."""
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .limit_services import validate_reason
from .models import Account, CreditEntry, CreditPurchase, MessagePackage, OperatorAudit, PaymentAttempt, FinancialEvent
from .providers import Zarinpal, ProviderDisabled, ProviderRejected, ProviderUnknown
from .services import APIError, limited

PACKAGE_FIELDS = ('name', 'message_count', 'price_toman', 'active', 'sort_order')


def package_data(package):
    return {'id': package.pk, **{key: getattr(package, key) for key in PACKAGE_FIELDS}, 'revision': package.revision}


def balance_field(environment=None):
    return 'demo_sends_remaining' if (environment != 'live' if environment else settings.DEMO_MODE) else 'purchased_sends_remaining'


def credit_environment():
    return 'demo' if settings.DEMO_MODE else 'live'


def checkout_enabled():
    from .payment_options import options
    available = options()
    return (settings.DEMO_MODE and settings.PAYMENT_BACKEND == 'demo') or available['wallet_enabled'] or available['gateway_enabled']


@transaction.atomic
def save_package(actor, data, package_id=None):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('core.manage_message_packages'):
        raise APIError('forbidden', 'مجوز مدیریت بسته‌ها را ندارید.', 403)
    if not isinstance(data, dict) or set(data) - {'values', 'revision', 'reason'}:
        raise APIError('invalid_input', 'اطلاعات بسته معتبر نیست.', 422)
    reason = validate_reason(data.get('reason'))
    values, revision = data.get('values'), data.get('revision')
    if not isinstance(values, dict) or set(values) != set(PACKAGE_FIELDS) or type(revision) is not int:
        raise APIError('invalid_input', 'همهٔ مشخصات بسته و نسخهٔ فعلی را وارد کن.', 422)
    for key, value in values.items():
        expected = str if key == 'name' else bool if key == 'active' else int
        if type(value) is not expected:
            raise APIError('invalid_input', 'نوع مقادیر بسته معتبر نیست.', 422)
    if package_id is None:
        package, before = MessagePackage(), {}
    else:
        package = MessagePackage.objects.select_for_update().filter(pk=package_id).first()
        if not package:
            raise APIError('not_found', 'بسته پیدا نشد.', 404)
        before = package_data(package)
    if package.revision != revision:
        raise APIError('settings_changed', 'مشخصات بسته تغییر کرده؛ تازه‌سازی کن.', 409)
    for key, value in values.items():
        setattr(package, key, value.strip() if key == 'name' else value)
    try:
        package.full_clean()
    except ValidationError:
        raise APIError('invalid_package', 'نام، تعداد و قیمت مثبت و معتبر برای بسته وارد کن.', 422) from None
    package.revision += 1
    package.save()
    OperatorAudit.objects.create(actor=actor, action='update_message_package', object_id=str(package.pk),
        reason=reason, before=before, after=package_data(package))
    return package


def purchase_data(purchase):
    attempt = PaymentAttempt.objects.filter(purchase=purchase).first()
    returned = attempt and attempt.return_to_wallet and attempt.refunds.filter(status='refunded').exists()
    return {'id': str(purchase.pk), 'package_id': purchase.package_id, 'name': purchase.package_name,
        'message_count': purchase.message_count, 'amount_toman': purchase.amount_toman,
        'environment': purchase.environment, 'payment_method': purchase.payment_method,
        'status': 'credited' if purchase.credited_at else 'wallet_returned' if returned else attempt.status if attempt else 'created',
        'created_at': purchase.created_at.isoformat(),
        'redirect_url': attempt.redirect_url if attempt and attempt.status == 'pending' else None}


def begin_purchase(user, data, key):
    if not isinstance(data, dict) or set(data) - {'package_id', 'package_revision', 'payment_method', 'wallet_consent', 'wallet_terms_version'} or type(data.get('package_id')) is not int or type(data.get('package_revision')) is not int:
        raise APIError('invalid_input', 'شناسه و نسخهٔ بسته را انتخاب کن؛ مبلغ و تعداد از سرور خوانده می‌شود.', 422)
    method = data.get('payment_method', 'gateway')
    if not isinstance(method, str) or method not in {'wallet', 'gateway'}:
        raise APIError('invalid_input', 'روش پرداخت معتبر نیست.', 422)
    try:
        key = uuid.UUID(str(key))
    except (TypeError, ValueError, AttributeError):
        raise APIError('invalid_input', 'کلید یکتای خرید معتبر نیست.', 422) from None
    from .safety import ensure_open
    ensure_open()
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        account = Account.objects.get(user=user)
        if account.suspended or account.deletion_requested_at:
            raise APIError('account_unavailable', 'خرید با این حساب فعلاً مجاز نیست.', 403)
        previous = CreditPurchase.objects.filter(owner=user, idempotency_key=key).first()
        if previous:
            if (previous.package_id != data['package_id'] or previous.payment_method != method
                    or (previous.environment == 'live') != (not settings.DEMO_MODE)):
                raise APIError('idempotency_conflict', 'کلید خرید برای بستهٔ دیگری ثبت شده.', 409)
            return purchase_data(previous)
        if not checkout_enabled():
            raise APIError('payment_disabled', 'خرید بسته فعلاً فعال نیست.', 409)
        from .payment_options import options, WALLET_TERMS_VERSION
        available = options()
        demo = settings.DEMO_MODE and settings.PAYMENT_BACKEND == 'demo' and method == 'gateway'
        if not demo and not available[method + '_enabled']:
            raise APIError('payment_disabled', 'این روش پرداخت فعلاً فعال نیست.', 409)
        accepted = data.get('wallet_consent') is True and data.get('wallet_terms_version') == WALLET_TERMS_VERSION
        if not demo and not accepted:
            raise APIError('wallet_consent_required', 'شرایط اعتبار غیرقابل برداشت را تأیید کن.', 422)
        limited('credit-purchases', str(user.pk), 5, 60)
        # A lost HTTP response must not cause a second automatic checkout.
        from .wallet import has_open_checkout
        if has_open_checkout(user):
            raise APIError('payment_reconciliation', 'یک پرداخت باز داری؛ وضعیتش را در صفحهٔ خرید بسته بررسی کن.', 409)
        package = MessagePackage.objects.select_for_update().filter(pk=data['package_id'], active=True).first()
        if not package or package.revision != data['package_revision']:
            raise APIError('package_changed', 'این بسته تغییر کرده یا غیرفعال شده؛ بسته‌ها را تازه‌سازی کن.', 409)
        environment = credit_environment() if method == 'wallet' else 'demo' if demo else settings.PROVIDER_ENVIRONMENT
        # Sandbox money can never fund real SMS.
        if not settings.DEMO_MODE and environment != 'live':
            raise APIError('payment_disabled', 'درگاه محیط واقعی آماده نیست.', 409)
        purchase = CreditPurchase.objects.create(owner=user, package=package, idempotency_key=key,
            payment_method=method, wallet_refund_consent=accepted, wallet_terms_version=WALLET_TERMS_VERSION if accepted else '',
            package_name=package.name, message_count=package.message_count, amount_toman=package.price_toman, environment=environment)
        if method == 'wallet':
            from .wallet import movement
            account = Account.objects.select_for_update().get(pk=account.pk)
            field = balance_field(environment)
            if getattr(account, field) + purchase.message_count > 2147483647:
                raise APIError('credit_capacity', 'ماندهٔ اعتبار نیازمند بررسی است.', 409)
            movement(account, 'package_debit', purchase.amount_toman, environment, purchase=purchase)
            CreditEntry.objects.create(account=account, purchase=purchase, kind='purchase', units=purchase.message_count, environment=environment)
            Account.objects.filter(pk=account.pk).update(**{field: F(field)+purchase.message_count})
            purchase.credited_at = timezone.now()
            purchase.save(update_fields=['credited_at'])
            return purchase_data(purchase)
        attempt = PaymentAttempt.objects.create(purchase=purchase, amount_toman=purchase.amount_toman,
            return_to_wallet=accepted,
            provider='demo' if demo else 'zarinpal', environment=environment, status='created' if demo else 'unknown')
        if demo:
            _apply_verified(purchase, attempt, 'demo-package-' + str(purchase.pk))
            return purchase_data(purchase)
    try:
        result = Zarinpal().request(amount_toman=attempt.amount_toman,
            callback_url=settings.APP_BASE_URL + '/api/v1/payments/return/zarinpal')
    except ProviderRejected:
        PaymentAttempt.objects.filter(pk=attempt.pk).update(status='failed', checked_at=timezone.now())
        return purchase_data(purchase)
    except (ProviderUnknown, ProviderDisabled):
        # Retain the uncertain attempt; do not retry the request or grant credits.
        return purchase_data(purchase)
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt.pk)
        attempt.authority, attempt.redirect_url, attempt.status = result.authority, result.redirect_url, 'pending'
        attempt.save(update_fields=['authority', 'redirect_url', 'status', 'updated_at'])
    return purchase_data(purchase)


def _apply_verified(purchase, attempt, reference):
    """Caller locks purchase and attempt; grant, receipt and units commit together."""
    if purchase.credited_at or (attempt.return_to_wallet and attempt.refunds.filter(status='refunded').exists()):
        return
    if (attempt.purchase_id != purchase.pk or attempt.amount_toman != purchase.amount_toman
            or attempt.environment != purchase.environment):
        raise APIError('payment_mismatch', 'پرداخت نیاز به تطبیق دارد.', 409)
    account = Account.objects.select_for_update().get(user_id=purchase.owner_id)
    field = balance_field(purchase.environment)
    unavailable = account.suspended or account.deletion_requested_at or getattr(account, field) + purchase.message_count > 2147483647
    if unavailable and not attempt.return_to_wallet:
        raise APIError('credit_limit', 'موجودی حساب نیاز به بررسی دارد.', 409)
    attempt.status, attempt.provider_reference = 'verified', reference
    attempt.checked_at, attempt.lease_until = timezone.now(), None
    attempt.save(update_fields=['status', 'provider_reference', 'checked_at', 'lease_until', 'updated_at'])
    FinancialEvent.objects.get_or_create(payment=attempt, kind='payment', defaults={'amount_toman': attempt.amount_toman})
    if unavailable:
        from .provider_services import request_refund
        request_refund(attempt, 'package_unavailable')
        return
    CreditEntry.objects.create(account=account, purchase=purchase, kind='purchase', units=purchase.message_count, environment=purchase.environment)
    Account.objects.filter(pk=account.pk).update(**{field: F(field) + purchase.message_count})
    purchase.credited_at = timezone.now()
    purchase.save(update_fields=['credited_at'])


def verify_purchase(attempt_id):
    meta = PaymentAttempt.objects.filter(pk=attempt_id, provider='zarinpal', purchase__isnull=False).values('purchase_id').first()
    if not meta:
        return
    with transaction.atomic():
        purchase = CreditPurchase.objects.select_for_update().get(pk=meta['purchase_id'])
        attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
        if (attempt.environment != settings.PROVIDER_ENVIRONMENT or purchase.credited_at
                or (attempt.return_to_wallet and attempt.refunds.filter(status='refunded').exists())
                or not attempt.authority or (attempt.lease_until and attempt.lease_until > timezone.now())):
            return
        attempt.lease_until = timezone.now() + timedelta(seconds=30)
        attempt.save(update_fields=['lease_until'])
        authority, amount = attempt.authority, attempt.amount_toman
    try:
        result = Zarinpal().verify(authority=authority, amount_toman=amount)
    except (ProviderUnknown, ProviderDisabled, ProviderRejected):
        PaymentAttempt.objects.filter(pk=attempt_id).update(status='unknown', checked_at=timezone.now(), lease_until=None)
        return
    try:
        with transaction.atomic():
            purchase = CreditPurchase.objects.select_for_update().get(pk=meta['purchase_id'])
            attempt = PaymentAttempt.objects.select_for_update().get(pk=attempt_id)
            _apply_verified(purchase, attempt, result.reference)
    except IntegrityError:
        # A receipt already assigned to another purchase cannot mint more units.
        PaymentAttempt.objects.filter(pk=attempt_id).exclude(status='verified').update(
            status='unknown', checked_at=timezone.now(), lease_until=None)


def reserve_credit(user, order):
    """Called in the order transaction. Conditional UPDATE prevents overspending."""
    field, environment = balance_field(), credit_environment()
    account = Account.objects.get(user=user)
    if not Account.objects.filter(pk=account.pk, **{field + '__gt': 0}).update(**{field: F(field)-1}):
        raise APIError('credit_required', 'اعتبار پیام تمام شده؛ یک بسته بخر و دوباره تأیید کن.', 409)
    CreditEntry.objects.create(account=account, order=order, kind='reserve', units=-1, environment=environment)


def release_credit(order):
    """Caller holds order lock. Uncertain/accepted sends never call this path."""
    if not order.uses_purchased_credit or order.purchased_credit_released_at:
        return
    environment = 'demo' if order.payment_mode == 'credit_demo' else 'live'
    field = balance_field(environment)
    account = Account.objects.get(user_id=order.owner_id)
    CreditEntry.objects.create(account=account, order=order, kind='release', units=1, environment=environment)
    Account.objects.filter(pk=account.pk).update(**{field: F(field)+1})
    order.purchased_credit_released_at = timezone.now()
    order.save(update_fields=['purchased_credit_released_at'])
