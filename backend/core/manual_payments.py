"""Audited bank-transfer purchases. Receipt claims never authorize credit."""
import re
import uuid
from datetime import date
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import Account, CreditPurchase, ManualPayment, ManualPaymentSettings, MessagePackage, OperatorAudit, PaymentAttempt
from .packages import _apply_verified, credit_environment
from .privacy import DIGITS, digest
from .services import APIError, limited
from .limit_services import validate_reason
from .payment_options import WALLET_TERMS_VERSION

SETTING_FIELDS = ('enabled', 'card_number', 'card_holder', 'bank_name', 'bale_username', 'telegram_username')


def current():
    return ManualPaymentSettings.objects.filter(pk=1).first() or ManualPaymentSettings()


def channels(value=None):
    value = value or current()
    return [{'name': name, 'label': label, 'url': base+getattr(value, field)}
        for name, label, base, field in [('bale', 'ارسال رسید در بله', 'https://ble.ir/', 'bale_username'),
        ('telegram', 'ارسال رسید در تلگرام', 'https://t.me/', 'telegram_username')]
        if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}', getattr(value, field) or '')]


def environment_problem():
    if settings.DEMO_MODE:
        return ''
    if not (settings.PROVIDER_ENVIRONMENT == 'live' and settings.PROVIDER_NETWORK_MODE == 'external'
        and settings.LIVE_PROVIDERS_ENABLED and settings.PROVIDER_CONTRACT_APPROVED
        and settings.REFUND_PROCESS_APPROVED and settings.OPERATIONS_OWNER and settings.SUPPORT_CONTACT
        and settings.PILOT_RECIPIENT_HASHES and settings.SMS_RECIPIENT_POLICY == 'pilot'
        and settings.PROVIDER_DAILY_BUDGET_RIAL > 0 and not settings.PROVIDER_DAILY_BUDGET_UNLIMITED):
        return 'پروفایل مجازِ خرید واقعی، قرارداد و شرایط برگشت هزینه هنوز آماده نیست.'
    return ''


def valid_card(value):
    if not re.fullmatch(r'[0-9]{16}', value) or len(set(value)) == 1:
        return False
    total = sum((int(c)*2-9 if int(c)*2>9 else int(c)*2) if i%2==0 else int(c) for i,c in enumerate(value))
    return total % 10 == 0


def configured(value):
    return valid_card(value.card_number) and len(value.card_holder.strip()) >= 2 and bool(channels(value))


def available(value=None):
    value = value if value is not None else current()
    return value.enabled and configured(value) and not environment_problem()


def require_permission(actor, permission):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('core.'+permission):
        raise APIError('forbidden', 'مجوز این اقدام را ندارید.', 403)


def settings_data(value=None):
    value = value or current()
    return {'values': {k:getattr(value,k) for k in SETTING_FIELDS}, 'revision':value.revision,
        'ready': available(value), 'problem': environment_problem()}


@transaction.atomic
def save_settings(actor, data):
    require_permission(actor, 'manage_manual_payments')
    if not isinstance(data, dict) or set(data) != {'values', 'revision', 'reason'} or type(data['revision']) is not int:
        raise APIError('invalid_input', 'فرم تنظیمات معتبر نیست.', 422)
    reason = validate_reason(data['reason']);values = data['values']
    if not isinstance(values, dict) or set(values) != set(SETTING_FIELDS) or type(values.get('enabled')) is not bool or any(not isinstance(values.get(k),str) for k in SETTING_FIELDS[1:]):
        raise APIError('invalid_input', 'مقادیر تنظیمات معتبر نیست.', 422)
    ManualPaymentSettings.objects.get_or_create(pk=1)
    value = ManualPaymentSettings.objects.select_for_update().get(pk=1)
    if value.revision != data['revision']:
        raise APIError('settings_changed', 'تنظیمات تغییر کرده؛ تازه‌سازی کن.', 409)
    before = {'enabled': value.enabled, 'card_last4': value.card_number[-4:], 'revision': value.revision}
    value.enabled = values['enabled']
    value.card_number = re.sub(r'[\s-]', '', values['card_number'].translate(DIGITS))
    value.card_holder = values['card_holder'].strip()
    value.bank_name = values['bank_name'].strip()
    for key in ('bale_username','telegram_username'):
        setattr(value,key,values[key].strip().removeprefix('@'))
    if (value.card_number and not valid_card(value.card_number)) or len(value.card_holder)>80 or len(value.bank_name)>80 or any(getattr(value,k) and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}',getattr(value,k)) for k in ('bale_username','telegram_username')):
        raise APIError('invalid_manual_settings', 'شمارهٔ کارت ۱۶رقمی معتبر و شناسهٔ شخصِ پشتیبان بدون لینک وارد کن.', 422)
    if value.enabled and (not configured(value) or environment_problem()):
        raise APIError('manual_payment_not_ready', environment_problem() or 'کارت، نام صاحب کارت و حداقل یک راه ارتباط پشتیبان را کامل کن.', 409)
    value.revision += 1;value.save()
    OperatorAudit.objects.create(actor=actor, action='manual_payment_settings', object_id='manual-settings:1', reason=reason,
        before=before, after={'enabled':value.enabled,'card_last4':value.card_number[-4:],'revision':value.revision})
    return settings_data(value)


def _key(value):
    try:return uuid.UUID(str(value))
    except (TypeError,ValueError,AttributeError):raise APIError('invalid_input','کلید یکتای درخواست معتبر نیست.',422) from None


def _reference(value):
    if not isinstance(value,str):raise APIError('invalid_receipt','مرجع بانکی معتبر وارد کن.',422)
    value = re.sub(r'[\s-]', '', value.translate(DIGITS)).upper()
    if not re.fullmatch(r'[A-Z0-9]{6,64}',value):raise APIError('invalid_receipt','مرجع بانکی باید ۶ تا ۶۴ حرف یا رقم باشد.',422)
    return value


def _new_purchase(user, package, key, config, consent):
    environment = credit_environment()
    purchase = CreditPurchase.objects.create(owner=user, package=package, idempotency_key=key,
        package_name=package.name, message_count=package.message_count, amount_toman=package.price_toman,
        environment=environment, payment_method='card', wallet_refund_consent=consent,
        wallet_terms_version=WALLET_TERMS_VERSION if consent else '')
    PaymentAttempt.objects.create(purchase=purchase, provider='manual', environment=environment,
        amount_toman=purchase.amount_toman, status='pending', return_to_wallet=consent)
    ManualPayment.objects.create(purchase=purchase, card_number=config.card_number, card_holder=config.card_holder, bank_name=config.bank_name,
        bale_username=config.bale_username, telegram_username=config.telegram_username)
    return purchase


def begin_purchase(user, data, key):
    allowed = {'package_id','package_revision','payment_method','wallet_consent','wallet_terms_version'}
    if not isinstance(data,dict) or set(data)-allowed or data.get('payment_method')!='card' or type(data.get('package_id')) is not int or type(data.get('package_revision')) is not int:
        raise APIError('invalid_input','بسته و روش پرداخت را انتخاب کن؛ مبلغ از سرور خوانده می‌شود.',422)
    if data.get('wallet_consent') is not True or data.get('wallet_terms_version')!=WALLET_TERMS_VERSION:
        raise APIError('wallet_consent_required','شرایط اعتبار را تأیید کن.',422)
    key = _key(key)
    from .safety import ensure_open
    ensure_open()
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=user.pk)
        account = Account.objects.get(user=user)
        if account.suspended or account.deletion_requested_at:
            raise APIError('account_unavailable','خرید با این حساب فعلاً مجاز نیست.',403)
        previous = CreditPurchase.objects.filter(owner=user,idempotency_key=key).first()
        if previous:
            if previous.payment_method!='card' or previous.package_id!=data['package_id'] or previous.environment!=credit_environment():
                raise APIError('idempotency_conflict','کلید خرید برای درخواست دیگری ثبت شده.',409)
            return previous
        config = ManualPaymentSettings.objects.select_for_update().filter(pk=1).first()
        if config is None or not available(config):raise APIError('payment_disabled','کارت‌به‌کارت فعلاً آمادهٔ پرداخت نیست.',409)
        limited('credit-purchases',str(user.pk),5,60)
        from .wallet import has_open_checkout
        if has_open_checkout(user):raise APIError('payment_reconciliation','یک پرداخت باز داری؛ ابتدا همان درخواست را بررسی کن.',409)
        package = MessagePackage.objects.select_for_update().filter(pk=data['package_id'],active=True).first()
        if not package or package.revision!=data['package_revision']:
            raise APIError('package_changed','بسته تغییر کرده؛ فهرست را تازه‌سازی کن.',409)
        return _new_purchase(user,package,key,config,True)


@transaction.atomic
def submit_receipt(user, purchase, data):
    if not isinstance(data,dict) or set(data)-{'receipt_sent','reference'} or data.get('receipt_sent') is not True:
        raise APIError('receipt_required','رسید را برای پشتیبانی بفرست و ثبت آن را تأیید کن.',422)
    reference = _reference(data.get('reference')) if data.get('reference') else ''
    get_user_model().objects.select_for_update().get(pk=user.pk)
    purchase = CreditPurchase.objects.select_for_update().filter(pk=purchase.pk,owner=user).first()
    if not purchase:raise APIError('not_found','خرید پیدا نشد.',404)
    manual = ManualPayment.objects.select_for_update().get(purchase=purchase)
    if manual.status in {'approved','awaiting_review'}:return purchase
    if manual.status!='awaiting_transfer':raise APIError('payment_closed','این درخواست بسته شده است؛ با پشتیبانی پیگیری کن.',409)
    manual.receipt_reference=reference;manual.receipt_submitted_at=timezone.now();manual.status='awaiting_review'
    manual.save(update_fields=['receipt_reference','receipt_submitted_at','status'])
    return purchase


@transaction.atomic
def cancel_purchase(user, purchase):
    get_user_model().objects.select_for_update().get(pk=user.pk)
    purchase = CreditPurchase.objects.select_for_update().filter(pk=purchase.pk,owner=user).first()
    if not purchase:raise APIError('not_found','خرید پیدا نشد.',404)
    manual = ManualPayment.objects.select_for_update().get(purchase=purchase)
    if manual.status=='cancelled':return purchase
    if manual.status!='awaiting_transfer':raise APIError('payment_reconciliation','درخواست دارای رسید باید توسط پشتیبانی بررسی شود.',409)
    manual.status='cancelled';manual.save(update_fields=['status'])
    PaymentAttempt.objects.filter(purchase=purchase).update(status='failed')
    return purchase


def _approve(actor, purchase, data):
    reason=validate_reason(data.get('reason'))
    if data.get('bank_verified') is not True or type(data.get('amount_toman')) is not int or data['amount_toman']!=purchase.amount_toman:
        raise APIError('payment_mismatch','مبلغ کامل واریز را با صورتحساب بانک تطبیق بده و تیک تأیید را بزن.',422)
    reference=_reference(data.get('bank_reference'))
    try:paid_date=date.fromisoformat(data.get('paid_date',''))
    except (ValueError,TypeError):raise APIError('invalid_receipt','تاریخ واریز معتبر وارد کن.',422) from None
    if paid_date>timezone.localdate():raise APIError('invalid_receipt','تاریخ واریز نمی‌تواند در آینده باشد.',422)
    manual=ManualPayment.objects.select_for_update().get(purchase=purchase)
    fingerprint=digest('bank-transfer-v1:'+manual.card_number+':'+paid_date.isoformat()+':'+reference)
    if purchase.environment!=credit_environment():raise APIError('payment_environment','محیط این خرید با محصول جاری یکسان نیست.',409)
    if manual.status=='approved' and purchase.credited_at:
        if manual.confirmed_reference_digest!=fingerprint:raise APIError('idempotency_conflict','این پرداخت با مرجع دیگری تأیید شده است.',409)
        return purchase
    if manual.status not in {'awaiting_transfer','awaiting_review'} or purchase.credited_at:
        raise APIError('payment_closed','این درخواست قابل تأیید تازه نیست.',409)
    if ManualPayment.objects.filter(confirmed_reference_digest=fingerprint).exclude(pk=manual.pk).exists():
        raise APIError('receipt_used','این رسید قبلاً برای خرید دیگری تأیید شده است.',409)
    attempt=PaymentAttempt.objects.select_for_update().get(purchase=purchase,provider='manual')
    _apply_verified(purchase,attempt,'manual:'+fingerprint,require_credit=True)
    manual.status='approved';manual.confirmed_reference=reference;manual.confirmed_reference_digest=fingerprint
    manual.paid_date=paid_date;manual.reviewed_by=actor;manual.reviewed_at=timezone.now();manual.review_note=reason
    manual.save()
    OperatorAudit.objects.create(actor=actor,action='approve_manual_payment',object_id=str(manual.pk),reason=reason,
        before={'status':'awaiting_review' if manual.receipt_submitted_at else 'awaiting_transfer'},
        after={'status':'approved','purchase_id':str(purchase.pk),'units':purchase.message_count,'amount_toman':purchase.amount_toman})
    return purchase


def approve(actor, manual_id, data):
    require_permission(actor,'approve_manual_payments')
    if not isinstance(data,dict) or set(data)-{'reason','bank_verified','amount_toman','bank_reference','paid_date'}:
        raise APIError('invalid_input','فقط اطلاعات تطبیق رسید را ارسال کن.',422)
    meta=ManualPayment.objects.filter(pk=manual_id).values('purchase_id').first()
    if not meta:raise APIError('not_found','درخواست پیدا نشد.',404)
    try:
        with transaction.atomic():
            purchase=CreditPurchase.objects.select_for_update().get(pk=meta['purchase_id'])
            return _approve(actor,purchase,data)
    except IntegrityError:raise APIError('receipt_used','رسید هم‌زمان برای خرید دیگری ثبت شد؛ دوباره بررسی کن.',409) from None


@transaction.atomic
def reject(actor, manual_id, data):
    require_permission(actor,'approve_manual_payments')
    if not isinstance(data,dict) or set(data)!={'reason'}:raise APIError('invalid_input','دلیل بررسی را وارد کن.',422)
    reason=validate_reason(data.get('reason'))
    meta=ManualPayment.objects.filter(pk=manual_id).values('purchase_id').first()
    if not meta:raise APIError('not_found','درخواست پیدا نشد.',404)
    purchase=CreditPurchase.objects.select_for_update().get(pk=meta['purchase_id'])
    manual=ManualPayment.objects.select_for_update().get(pk=manual_id)
    if manual.status=='rejected':return purchase
    if purchase.credited_at or manual.status not in {'awaiting_transfer','awaiting_review'}:
        raise APIError('payment_closed','پرداخت تأییدشده را از مسیر بازپرداخت پیگیری کن.',409)
    manual.status='rejected';manual.reviewed_by=actor;manual.reviewed_at=timezone.now();manual.review_note=reason;manual.save()
    PaymentAttempt.objects.filter(purchase=purchase).update(status='failed')
    OperatorAudit.objects.create(actor=actor,action='reject_manual_payment',object_id=str(manual.pk),reason=reason,
        after={'status':'rejected','purchase_id':str(purchase.pk)})
    return purchase


def grant_package(actor, data, key):
    require_permission(actor,'approve_manual_payments')
    if not isinstance(data,dict) or set(data)-{'account_id','package_id','package_revision','reason','bank_verified','amount_toman','bank_reference','paid_date'} or any(type(data.get(k)) is not int for k in ('account_id','package_id','package_revision')):
        raise APIError('invalid_input','حساب، بسته و اطلاعات کامل واریز را انتخاب کن.',422)
    key=_key(key)
    account=Account.objects.filter(pk=data['account_id']).first()
    if not account:raise APIError('not_found','حساب پیدا نشد.',404)
    try:
        with transaction.atomic():
            user=get_user_model().objects.select_for_update().get(pk=account.user_id)
            previous=CreditPurchase.objects.select_for_update().filter(owner=user,idempotency_key=key).first()
            if previous:
                if previous.payment_method!='card' or previous.package_id!=data['package_id']:
                    raise APIError('idempotency_conflict','کلید برای خرید دیگری ثبت شده.',409)
                return _approve(actor,previous,data)
            config=ManualPaymentSettings.objects.select_for_update().filter(pk=1).first()
            if config is None or environment_problem() or not configured(config):
                raise APIError('manual_payment_not_ready',environment_problem() or 'تنظیمات کارت مقصد و پشتیبانی را کامل کن.',409)
            from .wallet import has_open_checkout
            if has_open_checkout(user):raise APIError('payment_reconciliation','کاربر پرداخت باز دارد؛ همان درخواست را بررسی کن.',409)
            package=MessagePackage.objects.select_for_update().filter(pk=data['package_id'],active=True).first()
            if not package or package.revision!=data['package_revision']:
                raise APIError('package_changed','بسته تغییر کرده یا غیرفعال است.',409)
            purchase=_new_purchase(user,package,key,config,False)
            return _approve(actor,purchase,data)
    except IntegrityError:raise APIError('receipt_used','این رسید قبلاً استفاده شده؛ دوباره بررسی کن.',409) from None
