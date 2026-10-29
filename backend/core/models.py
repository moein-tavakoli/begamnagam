import uuid

from django.conf import settings
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .fields import EncryptedTextField


class Account(models.Model):
    wallet_balance_toman = models.PositiveBigIntegerField('موجودی کیف پول (تومان)', default=0, db_default=0, editable=False)
    demo_wallet_balance_toman = models.PositiveBigIntegerField(default=0, db_default=0, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account")
    phone_hash = models.CharField(max_length=64, unique=True)
    phone_cipher = models.TextField()
    phone_masked = models.CharField(max_length=20)
    suspended = models.BooleanField(default=False)
    free_sends_remaining = models.PositiveIntegerField(default=3)
    free_sends_earned_total = models.PositiveIntegerField(default=0, db_default=0)
    purchased_sends_remaining = models.PositiveIntegerField('اعتبار خریداری‌شده', default=0, db_default=0, editable=False)
    demo_sends_remaining = models.PositiveIntegerField('اعتبار بستهٔ آزمایشی', default=0, db_default=0, editable=False)
    unlimited_demo_sends = models.BooleanField("ارسال نامحدود برای تست", default=False, db_default=False,
        help_text="فقط در محیط آزمایشی: حذف سقف روزانه و فاصلهٔ ارسال برای همین فرستنده؛ قطع دریافت، سفارش باز و OTP حفظ می‌شوند.")
    direct_message_tone = models.BooleanField("لحن صریح‌تر و محترمانه", default=False, db_default=False,
        help_text="پیام‌های این فرستنده واضح‌تر و کم‌تعارف‌تر آماده می‌شوند؛ توهین، تحقیر و تهدید همچنان ممنوع‌اند.")
    sender_daily_limit = models.PositiveIntegerField('سقف اختصاصی ارسال در ۲۴ ساعت', null=True, blank=True, default=None, db_default=None,
        validators=[MaxValueValidator(1000000)], help_text='خالی = تنظیم سایت؛ ۰ = تعداد نامحدود؛ مثلاً ۱۰۰۰. اعتبار پیام، فاصله و کنترل گیرنده و محتوا حفظ می‌شوند.')
    rewrite_daily_limit = models.PositiveIntegerField('سقف اختصاصی بازنویسی روزانه', null=True, blank=True, default=None, db_default=None,
        validators=[MaxValueValidator(1000000)], help_text='خالی = تنظیم سایت؛ ۰ = تعداد نامحدود برای این حساب. سقف کلی سایت و روشن‌بودن سرویس همچنان لازم‌اند؛ مصرف پاک نمی‌شود.')
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [('suspend_account', 'Suspend or resume product senders'),
                       ('manage_test_sending', 'Manage unlimited simulated sending for individual accounts'),
                       ('manage_message_tone', 'Manage respectful direct message tone for individual accounts'),
                       ('manage_account_limits', 'Manage individual sender and rewrite count limits')]
        constraints = [models.CheckConstraint(condition=models.Q(free_sends_remaining__lte=models.F('free_sends_earned_total')+3), name="free_sends_within_grants")]


class OTPChallenge(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    phone_hash = models.CharField(max_length=64, db_index=True)
    phone_cipher = models.TextField()
    code_digest = models.CharField(max_length=64)
    session_key = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Preview(models.Model):
    message_tone = models.CharField(max_length=12, choices=[('polite', 'مودبانه'), ('firm', 'کمی مودبانه'), ('angry', 'بی‌ادبانه')], default='polite', db_default='polite', editable=False)
    payment_method = models.CharField(max_length=12, default='credit', db_default='credit', editable=False)
    wallet_policy_version = models.CharField(max_length=24, blank=True, default='', db_default='', editable=False)
    original_text = EncryptedTextField("متن اولیهٔ کاربر", blank=True, default='', db_default='', editable=False)
    generated_body = EncryptedTextField(blank=True, default='', db_default='')
    review_signature = models.CharField(max_length=64, blank=True, default='', db_default='')
    is_free = models.BooleanField(default=False)
    recipient_hash = models.CharField(max_length=64, blank=True)
    terms_version = models.CharField(max_length=40, blank=True)
    full_sms = EncryptedTextField(blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=64)
    category = models.CharField(max_length=32)
    text = EncryptedTextField()
    moderation_mode = models.CharField(max_length=32)
    price_toman = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class RecipientState(models.Model):
    phone_hash = models.CharField(primary_key=True, max_length=64)
    blocked = models.BooleanField(default=False)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class RewriteBudget(models.Model):
    day = models.DateField(primary_key=True)
    reserved_requests = models.PositiveIntegerField(default=0)
    limit_requests = models.PositiveIntegerField()


class RewriteUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    budget = models.ForeignKey(RewriteBudget, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['owner', 'created_at'])]


class DemoLimitReset(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="demo_limit_resets")
    recipient_hash = models.CharField(max_length=64, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="performed_demo_limit_resets")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "ریست محدودیت آزمایشی"
        verbose_name_plural = "ریست‌های محدودیت آزمایشی"
        permissions = [("reset_demo_limits", "Reset simulated sender/recipient quotas")]
        indexes = [models.Index(fields=["sender", "created_at"])]


class Order(models.Model):
    payment_method = models.CharField(max_length=12, default='legacy', db_default='legacy', editable=False)
    wallet_refund_consent = models.BooleanField(default=False, db_default=False, editable=False)
    uses_purchased_credit = models.BooleanField(default=False, db_default=False)
    purchased_credit_released_at = models.DateTimeField(null=True, blank=True)
    is_free = models.BooleanField(default=False)
    free_credit_released_at = models.DateTimeField(null=True, blank=True)
    consent_at = models.DateTimeField(null=True, blank=True)
    terms_version = models.CharField(max_length=40, blank=True)
    full_sms = EncryptedTextField(blank=True)

    class Status(models.TextChoices):
        AWAITING_PAYMENT = "awaiting_payment", "منتظر پرداخت آزمایشی"
        QUEUED = "queued", "در صف شبیه‌سازی"
        DELIVERED_DEMO = "delivered_demo", "ارسال شبیه‌سازی شد"
        ACCEPTED = "accepted", "پذیرفته‌شده توسط سرویس‌دهنده"
        DELIVERED = "delivered", "رسیده به گیرنده"
        UNKNOWN = "unknown", "در حال بررسی نتیجه"
        CANCELLED = "cancelled", "لغوشده"
        FAILED = "failed", "ناموفق"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders")
    preview = models.OneToOneField(Preview, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    recipient_hash = models.CharField(max_length=64, db_index=True)
    recipient_cipher = models.TextField()
    recipient_masked = models.CharField(max_length=20)
    text = EncryptedTextField()
    category = models.CharField(max_length=32)
    amount_toman = models.PositiveIntegerField()
    status = models.CharField(max_length=24, choices=Status, default=Status.AWAITING_PAYMENT)
    payment_mode = models.CharField(max_length=16, default="demo")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [("view_private_message_text", "View original and reviewed message text with an audit trail")]
        constraints = [models.UniqueConstraint(fields=["owner", "idempotency_key"], name="unique_owner_idempotency"),
            models.CheckConstraint(condition=models.Q(is_free=True, amount_toman=0, uses_purchased_credit=False) | models.Q(is_free=False, amount_toman__gt=0, uses_purchased_credit=False) | models.Q(is_free=False, amount_toman=0, uses_purchased_credit=True, payment_mode__in=['credit_live', 'credit_demo']), name="order_free_or_positive_price")]
        indexes = [models.Index(fields=["owner", "created_at"]), models.Index(fields=["recipient_hash", "status"])]


class Outbox(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="outbox")
    state = models.CharField(max_length=16, default="pending", db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ModerationAudit(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    category = models.CharField(max_length=32, blank=True)
    outcome = models.CharField(max_length=16)
    reason_code = models.CharField(max_length=40)
    content_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)


class MessagePackage(models.Model):
    name = models.CharField('نام بسته', max_length=80)
    message_count = models.PositiveIntegerField('تعداد پیام', validators=[MinValueValidator(1), MaxValueValidator(1000000)])
    price_toman = models.PositiveIntegerField('قیمت بسته (تومان)', validators=[MinValueValidator(1), MaxValueValidator(2147483647)])
    active = models.BooleanField('فعال', default=False)
    sort_order = models.PositiveIntegerField('ترتیب نمایش', default=0)
    revision = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'pk']
        verbose_name = 'بستهٔ پیام'
        verbose_name_plural = 'بسته‌های پیام'
        permissions = [('manage_message_packages', 'Manage message credit packages')]
        constraints = [models.CheckConstraint(condition=models.Q(message_count__gte=1, message_count__lte=1000000, price_toman__gte=1), name='positive_message_package')]

    def __str__(self):
        return self.name


class CreditPurchase(models.Model):
    payment_method = models.CharField(max_length=12, default='gateway', db_default='gateway', editable=False)
    wallet_refund_consent = models.BooleanField(default=False, db_default=False, editable=False)
    wallet_terms_version = models.CharField(max_length=24, default='', db_default='', editable=False)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='credit_purchases')
    package = models.ForeignKey(MessagePackage, on_delete=models.PROTECT)
    idempotency_key = models.UUIDField()
    package_name = models.CharField(max_length=80)
    message_count = models.PositiveIntegerField()
    amount_toman = models.PositiveIntegerField()
    environment = models.CharField(max_length=8)
    credited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'idempotency_key'], name='unique_credit_purchase_key'),
            models.CheckConstraint(condition=models.Q(message_count__gte=1, amount_toman__gte=1, environment__in=['demo', 'sandbox', 'live']), name='valid_credit_purchase')]


class CreditEntry(models.Model):
    """Append-only message units. Money is recorded separately in FinancialEvent."""
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='credit_entries')
    purchase = models.OneToOneField(CreditPurchase, null=True, blank=True, on_delete=models.PROTECT)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=8, choices=[('purchase', 'خرید'), ('reserve', 'رزرو ارسال'), ('release', 'برگشت اعتبار')])
    units = models.IntegerField()
    environment = models.CharField(max_length=8)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['order', 'kind'], condition=models.Q(order__isnull=False), name='one_credit_action_per_order'),
            models.CheckConstraint(condition=models.Q(kind='purchase', units__gt=0, purchase__isnull=False, order__isnull=True) | models.Q(kind='reserve', units=-1, purchase__isnull=True, order__isnull=False) | models.Q(kind='release', units=1, purchase__isnull=True, order__isnull=False), name='credit_entry_relation')]


# Independent financial and delivery records. Network activation is guarded separately.
class PaymentAttempt(models.Model):
    wallet_topup = models.OneToOneField('WalletTopup', null=True, blank=True, on_delete=models.PROTECT, related_name='payment')
    return_to_wallet = models.BooleanField(default=False, db_default=False, editable=False)
    class Status(models.TextChoices):
        CREATED = "created", "ایجادشده"
        PENDING = "pending", "در انتظار"
        VERIFIED = "verified", "تأییدشده"
        FAILED = "failed", "ناموفق"
        UNKNOWN = "unknown", "نیازمند تطبیق"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT, related_name="payment_attempts")
    purchase = models.OneToOneField(CreditPurchase, null=True, blank=True, on_delete=models.PROTECT, related_name='payment')
    request_key = models.UUIDField(default=uuid.uuid4, unique=True)
    provider = models.CharField(max_length=24, default="demo")
    environment = models.CharField(max_length=8, default="demo")
    provider_reference = models.CharField(max_length=128, blank=True)
    authority = models.CharField(max_length=128, blank=True)
    redirect_url = models.URLField(max_length=400, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    amount_toman = models.PositiveIntegerField()
    currency = models.CharField(max_length=3, default="IRT")
    status = models.CharField(max_length=12, choices=Status, default=Status.CREATED)
    applied_to_order = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(order__isnull=False, purchase__isnull=True, wallet_topup__isnull=True)
                | models.Q(order__isnull=True, purchase__isnull=False, wallet_topup__isnull=True)
                | models.Q(order__isnull=True, purchase__isnull=True, wallet_topup__isnull=False)), name='payment_one_target'),
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="payment_positive_amount"),
            models.CheckConstraint(condition=models.Q(currency="IRT"), name="payment_integer_toman"),
            models.CheckConstraint(condition=models.Q(environment="demo", provider="demo") | models.Q(environment__in=["sandbox", "live"], provider="zarinpal") | models.Q(environment__in=['demo', 'live'], provider='manual'), name="payment_provider_environment"),
            models.CheckConstraint(condition=models.Q(status__in=["created", "pending", "verified", "failed", "unknown"]), name="payment_known_status"),
            models.CheckConstraint(condition=models.Q(applied_to_order=False) | models.Q(status="verified"), name="payment_apply_verified_only"),
            models.UniqueConstraint(fields=["order"], condition=models.Q(applied_to_order=True), name="one_applied_payment_per_order"),
            models.UniqueConstraint(fields=["provider", "environment", "provider_reference"], condition=~models.Q(provider_reference=""), name="unique_payment_provider_reference"),
            models.UniqueConstraint(fields=["provider", "environment", "authority"], condition=~models.Q(authority=""), name="unique_payment_authority"),
        ]
        indexes = [models.Index(fields=["status", "updated_at"])]


class Refund(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "درخواست‌شده"
        PROCESSING = "processing", "در حال بررسی"
        REFUNDED = "refunded", "مستردشده"
        FAILED = "failed", "ناموفق"
        UNKNOWN = "unknown", "نیازمند تطبیق"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(PaymentAttempt, on_delete=models.PROTECT, related_name="refunds")
    request_key = models.UUIDField(default=uuid.uuid4, unique=True)
    amount_toman = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status, default=Status.REQUESTED)
    reason_code = models.CharField(max_length=40)
    provider_reference = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="refund_positive_amount"),
            models.CheckConstraint(condition=models.Q(status__in=["requested", "processing", "refunded", "failed", "unknown"]), name="refund_known_status"),
            models.UniqueConstraint(fields=["payment"], name="one_full_refund_per_payment"),
        ]
        indexes = [models.Index(fields=["status", "updated_at"])]


class MessageDelivery(models.Model):
    class Status(models.TextChoices):
        NOT_READY = "not_ready", "آماده نشده"
        QUEUED = "queued", "در صف"
        SUBMITTING = "submitting", "در حال ارسال"
        ACCEPTED = "accepted", "پذیرفته‌شده"
        DELIVERED_DEMO = "delivered_demo", "تحویل آزمایشی"
        DELIVERED = "delivered", "رسیده به گیرنده"
        FAILED = "failed", "ناموفق"
        UNKNOWN = "unknown", "نیازمند تطبیق"
        SUPPRESSED = "suppressed", "متوقف‌شده"
        EXPIRED = "expired", "منقضی‌شده"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="delivery")
    submission_key = models.UUIDField(default=uuid.uuid4, unique=True)
    local_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    environment = models.CharField(max_length=8, default="demo")
    provider = models.CharField(max_length=24, default="demo")
    provider_reference = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.NOT_READY)
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_until = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(environment="demo", provider="demo") | models.Q(environment__in=["sandbox", "live"], provider="kavenegar"), name="delivery_provider_environment"),
            models.CheckConstraint(condition=models.Q(status__in=["not_ready", "queued", "submitting", "accepted", "delivered_demo", "delivered", "failed", "unknown", "suppressed", "expired"]), name="delivery_known_status"),
            models.UniqueConstraint(fields=["provider", "environment", "provider_reference"], condition=~models.Q(provider_reference=""), name="unique_delivery_provider_reference"),
        ]
        indexes = [models.Index(fields=["status", "updated_at"])]


class FinancialEvent(models.Model):
    """Restricted audit schema, not a complete accounting ledger or live adapter."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(PaymentAttempt, on_delete=models.PROTECT, related_name="events")
    refund = models.OneToOneField(Refund, null=True, blank=True, on_delete=models.PROTECT)
    event_key = models.UUIDField(default=uuid.uuid4, unique=True)
    kind = models.CharField(max_length=12, choices=[("payment", "دریافت"), ("refund", "استرداد")])
    amount_toman = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="financial_event_positive_amount"),
            models.CheckConstraint(condition=models.Q(kind="payment", refund__isnull=True) | models.Q(kind="refund", refund__isnull=False), name="financial_event_refund_relation"),
            models.UniqueConstraint(fields=["payment"], condition=models.Q(kind="payment"), name="one_capture_event_per_payment"),
        ]


class SpendBudget(models.Model):
    day = models.DateField(primary_key=True)
    reserved_rial = models.PositiveBigIntegerField(default=0)
    limit_rial = models.PositiveBigIntegerField()


class SpendReservation(models.Model):
    operation_key = models.CharField(max_length=100, unique=True)
    budget = models.ForeignKey(SpendBudget, on_delete=models.PROTECT)
    amount_rial = models.PositiveBigIntegerField()
    actual_rial = models.PositiveBigIntegerField(null=True, blank=True)
    kind = models.CharField(max_length=12)
    state = models.CharField(max_length=12, default='reserved')
    created_at = models.DateTimeField(auto_now_add=True)


class RecipientGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    preview = models.OneToOneField(Preview, null=True, blank=True, on_delete=models.CASCADE, related_name='recipient_grant')
    invitation_send = models.OneToOneField('InvitationSend', null=True, blank=True, on_delete=models.CASCADE, related_name='recipient_grant')
    token_digest = models.CharField(max_length=64, unique=True)
    recipient_hash = models.CharField(max_length=64, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    stop_expires_at = models.DateTimeField(null=True, blank=True)
    report_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=(models.Q(preview__isnull=False, invitation_send__isnull=True) |
            models.Q(preview__isnull=True, invitation_send__isnull=False)), name='recipient_grant_one_source')]


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='invitations')
    # Retained after redaction so a number cannot be claimed by another inviter.
    phone_hash = models.CharField(max_length=64, unique=True)
    phone_cipher = models.TextField()
    phone_masked = models.CharField(max_length=20)
    registered_at = models.DateTimeField(null=True, blank=True)
    reward_awarded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['inviter', '-created_at'])]


def invitation_local_id():
    import secrets
    return secrets.randbelow(2**63-1)+1


class InvitationSend(models.Model):
    """Durable outbox and delivery record; an uncertain submission is never resent."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(Invitation, on_delete=models.PROTECT, related_name='sends')
    ordinal = models.PositiveIntegerField()
    idempotency_key = models.UUIDField(unique=True)
    consent_version = models.CharField(max_length=32)
    consent_at = models.DateTimeField()
    full_sms = EncryptedTextField()
    local_id = models.BigIntegerField(default=invitation_local_id, unique=True)
    provider = models.CharField(max_length=16)
    status = models.CharField(max_length=20, default='pending', db_index=True)
    provider_reference = models.CharField(max_length=100, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)
    available_at = models.DateTimeField()
    lease_until = models.DateTimeField(null=True, blank=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['invitation', 'ordinal'], name='invitation_send_ordinal'),
            models.CheckConstraint(condition=models.Q(ordinal__gte=1), name='invitation_positive_ordinal')]


class AIConfiguration(models.Model):
    """A single audited choice for new, synchronous AI previews."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    provider = models.CharField("سرویس فعال", max_length=12, default="template", choices=[
        ("template", "متن آماده — هوش مصنوعی خاموش"), ("ollama", "Ollama — مدل محلی"), ("gapgpt", "GapGPT — سرویس بیرونی")])
    tone_polite_enabled = models.BooleanField('مودبانه', default=True, db_default=True)
    tone_firm_enabled = models.BooleanField('کمی مودبانه', default=False, db_default=False)
    tone_angry_enabled = models.BooleanField('بی‌ادبانه — خیلی جدی، بدون توهین و تهدید', default=False, db_default=False)
    ollama_model = models.CharField("مدل محلی", max_length=100, default="qwen3:4b-instruct-2507-q4_K_M")
    gapgpt_model = models.CharField("مدل GapGPT", max_length=100, blank=True)
    timeout_seconds = models.PositiveSmallIntegerField("مهلت کل بازنویسی و بازبینی محلی (ثانیه)", default=20)
    parallel_requests = models.PositiveSmallIntegerField("درخواست محلی هم‌زمان؛ بدون صف", default=2)
    daily_limit = models.PositiveIntegerField("سقف روزانهٔ بازنویسی محلی", default=10000)
    user_daily_limit = models.PositiveIntegerField("سقف روزانهٔ محلی برای هر حساب", default=100)
    revision = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات هوش مصنوعی"
        verbose_name_plural = "هوش مصنوعی"
        permissions = [("manage_ai", "Manage AI provider and local model")]
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_ai_configuration")]

    def __str__(self):
        return "انتخاب Ollama یا GapGPT"

    def clean(self):
        import re
        from django.core.exceptions import ValidationError
        errors = {}
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}', self.ollama_model)
                or '/' in self.ollama_model or 'cloud' in self.ollama_model.lower()):
            errors['ollama_model'] = "نام یک مدل نصب‌شدهٔ محلی وارد کن؛ مدل ابری مجاز نیست."
        if self.gapgpt_model and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}', self.gapgpt_model):
            errors['gapgpt_model'] = "نام مدل معتبر نیست."
        for name, low, high in [('timeout_seconds', 2, 20), ('parallel_requests', 1, 2),
                              ('daily_limit', 1, 100000), ('user_daily_limit', 1, 10000)]:
            if not low <= getattr(self, name) <= high:
                errors[name] = f"مقدار باید بین {low} و {high} باشد."
        if errors:
            raise ValidationError(errors)


class SiteLimits(models.Model):
    """One durable policy shared by web and workers; zero disables business caps."""
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    wallet_enabled = models.BooleanField('کیف پول فعال باشد', default=False, db_default=False,
        help_text='پرداخت از موجودی؛ خاموش‌کردن، موجودی یا برگشت هزینهٔ قبلی را پاک نمی‌کند.')
    gateway_enabled = models.BooleanField('درگاه زرین‌پال فعال باشد', default=False, db_default=False,
        help_text='خرید و شارژ جدید؛ به تنظیم معتبر درگاه و کیف پول فعال نیاز دارد. تراکنش قبلی همچنان تعیین تکلیف می‌شود.')
    price_toman = models.PositiveIntegerField("مبلغ هر ارسال غیرهدیه (تومان)", default=2000,
        validators=[MinValueValidator(1), MaxValueValidator(2147483647)],
        help_text="عدد صحیح و مثبت به تومان؛ برای پیش‌نمایش‌های جدید. ارسال‌های هدیه رایگان‌اند و تغییر مبلغ، پرداخت پولی را فعال نمی‌کند.")
    sender_limit = models.PositiveIntegerField("حداکثر درخواست پیام هر فرستنده", default=5, help_text="۰ = بدون سقف؛ شامل درخواست‌های ثبت‌شده در بازه است.")
    sender_window_hours = models.PositiveIntegerField("بازهٔ شمارش ارسال (ساعت)", default=24,
        help_text="۰ = غیرفعال‌کردن سقف تعداد ارسال در این بازه؛ تعداد تنظیم‌شده و سابقهٔ مصرف حفظ می‌شوند.")
    recipient_limit = models.PositiveIntegerField("حداکثر دریافت از مجموع فرستندگان و دعوت‌ها", default=0, help_text="۰ = بدون سقف تعداد؛ پیام‌های پذیرفته‌شده/رسیده و نتیجهٔ نامعلوم شمرده می‌شوند.")
    recipient_window_hours = models.PositiveIntegerField("بازهٔ شمارش دریافت (ساعت)", default=24,
        help_text="۰ = غیرفعال‌کردن سقف تعداد دریافت در این بازه؛ فاصلهٔ دریافت جداگانه تنظیم می‌شود.")
    recipient_cooldown_hours = models.PositiveIntegerField("حداقل فاصلهٔ دریافت پیام و دعوت (ساعت)", default=24, help_text="۰ = بدون فاصلهٔ اجباری.")
    pair_cooldown_hours = models.PositiveIntegerField("فاصلهٔ ارسال هر فرستنده به یک گیرنده (ساعت)", default=24, help_text="۰ = بدون فاصلهٔ اجباری.")
    sending_window_enabled = models.BooleanField("ارسال فقط در ساعت مجاز", default=True)
    sending_start_hour = models.PositiveSmallIntegerField("شروع ساعت مجاز به وقت تهران", default=9,
        help_text="ساعت شبانه‌روز، از ۰ تا ۲۳؛ ۰ یعنی نیمه‌شب. برای حذف محدودیت ساعت، تیک «ارسال فقط در ساعت مجاز» را بردارید.")
    sending_end_hour = models.PositiveSmallIntegerField("پایان ساعت مجاز به وقت تهران", default=21,
        help_text="از ۰ تا ۲۴؛ ۰ و ۲۴ یعنی نیمه‌شب. پایان می‌تواند روز بعد باشد؛ مثلاً ۲۲ تا ۸. برای تمام شبانه‌روز تیک بالا را بردارید.")
    invitation_max_sends = models.PositiveIntegerField("حداکثر پیامک دعوت هر مخاطب", default=3, help_text="۰ = بدون سقف.")
    invitation_limit = models.PositiveIntegerField("حداکثر درخواست دعوت هر دعوت‌کننده", default=5, help_text="۰ = بدون سقف.")
    invitation_window_hours = models.PositiveIntegerField("بازهٔ شمارش دعوت (ساعت)", default=24,
        help_text="۰ = غیرفعال‌کردن سقف تعداد دعوت در این بازه؛ تعداد دعوت هر مخاطب و فاصلهٔ دعوت جداگانه تنظیم می‌شوند.")
    invitation_cooldown_hours = models.PositiveIntegerField("فاصلهٔ دو درخواست دعوت (ساعت)", default=24, help_text="۰ = بدون فاصله.")
    invitation_validity_days = models.PositiveIntegerField("مهلت درخواست مجدد دعوت (روز)", default=30, help_text="۰ = بدون محدودیت زمانی برای درخواست مجدد؛ انقضای لینک‌های قبلی تغییر نمی‌کند.")
    otp_validity_seconds = models.PositiveIntegerField("اعتبار کد ورود تازه (ثانیه)", default=300)
    otp_max_attempts = models.PositiveIntegerField("حداکثر تلاش برای هر کد ورود", default=5, help_text="برای جلوگیری از حدس رمز باید مثبت بماند.")
    preview_validity_seconds = models.PositiveIntegerField("اعتبار پیش‌نمایش تازه (ثانیه)", default=900)
    provider_budget_unlimited = models.BooleanField("بدون سقف هزینهٔ روزانهٔ پیامک", default=False, help_text="فقط در پروفایل مجاز هدیهٔ واقعی؛ دفتر هزینه و کنترل هزینهٔ هر تماس حفظ می‌شوند.")
    provider_daily_budget_rial = models.PositiveBigIntegerField("سقف هزینهٔ روزانهٔ پیامک (ریال)", default=0)
    otp_max_cost_rial = models.PositiveIntegerField("حد هزینهٔ غیرعادی هر OTP (ریال)", default=0)
    sms_max_cost_rial = models.PositiveIntegerField("حد هزینهٔ غیرعادی هر پیام/دعوت (ریال)", default=0)
    rewrite_daily_unlimited = models.BooleanField("بدون سقف روزانهٔ کل بازنویسی GapGPT", default=False, db_default=False,
        help_text="با فعال‌بودن این گزینه، سقف عددی کل سایت اعمال نمی‌شود؛ شمارش مصرف و سقف هر حساب حفظ می‌شوند.")
    rewrite_daily_limit = models.PositiveIntegerField("سقف روزانهٔ کل بازنویسی GapGPT", default=0,
        help_text="وقتی گزینهٔ بدون سقف خاموش است اعمال می‌شود؛ در آن حالت ۰ یعنی غیرفعال. کلید و مدل جداگانه تنظیم می‌شوند.")
    rewrite_user_limit = models.PositiveIntegerField("سقف روزانهٔ بازنویسی هر حساب", default=0)
    revision = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "تنظیمات محدودیت‌های سایت"
        verbose_name_plural = "تنظیمات محدودیت‌های سایت"
        permissions = [("manage_site_limits", "Manage runtime site limits")]
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_site_limits"),
            models.CheckConstraint(condition=models.Q(price_toman__gte=1), name="positive_site_price"),
            models.CheckConstraint(condition=models.Q(gateway_enabled=False) | models.Q(wallet_enabled=True), name='gateway_requires_wallet')]

    def __str__(self):
        return "تنظیمات مشترک سایت و پردازشگر پیامک"

    def clean(self):
        from django.conf import settings
        from django.core.exceptions import ValidationError
        errors = {}
        if self.gateway_enabled and not self.wallet_enabled:
            errors['gateway_enabled'] = 'برای برگشت هزینه به کیف پول، ابتدا کیف پول را فعال کنید.'
        for name in ("otp_validity_seconds", "otp_max_attempts", "preview_validity_seconds"):
            if getattr(self, name) < 1:
                errors[name] = "اعتبار کد و پیش‌نمایش و تعداد تلاش ورود باید مثبت بمانند."
        for name in ("sender_window_hours", "recipient_window_hours", "recipient_cooldown_hours", "pair_cooldown_hours", "invitation_window_hours", "invitation_cooldown_hours"):
            if getattr(self, name) > 876000:
                errors[name] = "بازه نمی‌تواند بیشتر از ۱۰۰ سال باشد."
        for name in ("otp_validity_seconds", "preview_validity_seconds"):
            if getattr(self, name) > 31536000:
                errors[name] = "اعتبار نمی‌تواند بیشتر از یک سال باشد."
        if self.otp_max_attempts > 1000:
            errors["otp_max_attempts"] = "تعداد تلاش حداکثر ۱۰۰۰ است."
        if self.invitation_validity_days > 36500:
            errors["invitation_validity_days"] = "مهلت نمی‌تواند بیشتر از ۱۰۰ سال باشد."
        if not 0 <= self.sending_start_hour < 24:
            errors["sending_start_hour"] = "ساعت شروع باید بین ۰ تا ۲۳ باشد؛ ۰ یعنی نیمه‌شب."
        if not 0 <= self.sending_end_hour <= 24:
            errors["sending_end_hour"] = "ساعت پایان باید بین ۰ تا ۲۴ باشد؛ ۰ و ۲۴ یعنی نیمه‌شب."
        if self.sending_window_enabled and self.sending_start_hour == self.sending_end_hour:
            errors["sending_end_hour"] = "شروع و پایان بازهٔ فعال باید متفاوت باشند؛ برای حذف محدودیت ساعت، تیک «ارسال فقط در ساعت مجاز» را بردارید."
        if self.provider_budget_unlimited and not settings.PROVIDER_DAILY_BUDGET_UNLIMITED:
            errors["provider_budget_unlimited"] = "حالت نامحدود در تنظیمات این محیط مجاز نشده است."
        if settings.PROVIDER_NETWORK_MODE == "external":
            for name in ("otp_max_cost_rial", "sms_max_cost_rial"):
                if getattr(self, name) < 1:
                    errors[name] = "کنترل هزینهٔ هر تماس واقعی باید مثبت بماند."
        if errors:
            raise ValidationError(errors)


class RequestLimit(models.Model):
    from .limit_defaults import REQUEST_LIMITS
    scope = models.CharField("نوع درخواست", max_length=40, unique=True, choices=[(key, value[0]) for key, value in REQUEST_LIMITS.items()])
    enabled = models.BooleanField("فعال", default=True)
    maximum = models.PositiveIntegerField("حداکثر تعداد درخواست", default=1)
    window_seconds = models.PositiveIntegerField("بازهٔ شمارش (ثانیه)", default=600)
    revision = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "کنترل تعداد درخواست"
        verbose_name_plural = "کنترل تعداد درخواست‌ها"

    def __str__(self):
        return self.get_scope_display()

    def clean(self):
        from django.core.exceptions import ValidationError
        from .limit_defaults import REQUEST_LIMITS
        if not self.maximum or not self.window_seconds:
            raise ValidationError("تعداد و بازه باید مثبت باشند؛ برای برداشتن سقف، تیک فعال را بردارید.")
        if self.scope in REQUEST_LIMITS and REQUEST_LIMITS[self.scope][3] and not self.enabled:
            raise ValidationError({"enabled": "کنترل حدس رمز، لینک خصوصی و بازگشت پرداخت باید فعال بماند؛ تعداد و بازه قابل تنظیم‌اند."})


class AbuseReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant = models.OneToOneField(RecipientGrant, on_delete=models.PROTECT, related_name='report')
    reason = models.CharField(max_length=24)
    details = EncryptedTextField(blank=True)
    status = models.CharField(max_length=12, default='open')
    closed_at = models.DateTimeField(null=True, blank=True)
    hold_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [('triage_report', 'Triage abuse reports')]


class OperatorAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    action = models.CharField(max_length=32)
    object_id = models.CharField(max_length=100, blank=True)
    reason = models.CharField(max_length=200)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class SafetyControl(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    halted = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [('operate_safety', 'Halt or resume sending'), ('view_operations', 'Inspect operational metrics'), ('confirm_refund', 'Confirm documented manual refunds')]
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='single_safety_control')]


class OperationalAlert(models.Model):
    code = models.CharField(max_length=40, unique=True)
    severity = models.CharField(max_length=12)
    active = models.BooleanField(default=True)
    count = models.PositiveIntegerField(default=0)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    updated_at = models.DateTimeField(auto_now=True)


class WalletTopup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='wallet_topups')
    idempotency_key = models.UUIDField()
    amount_toman = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(2147483647)])
    environment = models.CharField(max_length=8)
    consent_at = models.DateTimeField()
    terms_version = models.CharField(max_length=24)
    credited_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'idempotency_key'], name='unique_wallet_topup_key'),
            models.CheckConstraint(condition=models.Q(amount_toman__gte=1, environment__in=['live', 'sandbox']), name='valid_wallet_topup')]


class WalletEntry(models.Model):
    """Immutable movements; cash capture and internal spending are distinct."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='wallet_entries')
    kind = models.CharField(max_length=20, choices=[('topup', 'شارژ'), ('order_debit', 'هزینهٔ پیام'),
        ('order_return', 'برگشت هزینهٔ پیام'), ('package_debit', 'خرید بسته'), ('payment_return', 'برگشت پرداخت')])
    amount_toman = models.PositiveIntegerField()
    balance_after_toman = models.PositiveBigIntegerField()
    environment = models.CharField(max_length=8)
    topup = models.OneToOneField(WalletTopup, null=True, blank=True, on_delete=models.PROTECT)
    order = models.ForeignKey(Order, null=True, blank=True, on_delete=models.PROTECT)
    purchase = models.OneToOneField(CreditPurchase, null=True, blank=True, on_delete=models.PROTECT)
    refund = models.OneToOneField(Refund, null=True, blank=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['order', 'kind'], condition=models.Q(order__isnull=False), name='one_wallet_order_movement'),
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0, environment__in=['live', 'sandbox', 'demo']), name='valid_wallet_movement'),
            models.CheckConstraint(condition=(
                models.Q(kind='topup', topup__isnull=False, order__isnull=True, purchase__isnull=True, refund__isnull=True)
                | models.Q(kind__in=['order_debit', 'order_return'], topup__isnull=True, order__isnull=False, purchase__isnull=True, refund__isnull=True)
                | models.Q(kind='package_debit', topup__isnull=True, order__isnull=True, purchase__isnull=False, refund__isnull=True)
                | models.Q(kind='payment_return', topup__isnull=True, order__isnull=True, purchase__isnull=True, refund__isnull=False)
            ), name='wallet_movement_source')]


class ManualPaymentSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    enabled = models.BooleanField('کارت‌به‌کارت فعال باشد', default=False)
    card_number = EncryptedTextField('شمارهٔ کارت مقصد', blank=True, default='', db_default='')
    card_holder = models.CharField('نام صاحب کارت', max_length=80, blank=True)
    bank_name = models.CharField('نام بانک', max_length=80, blank=True, default='', db_default='')
    bale_username = models.CharField('شناسهٔ پشتیبان در بله', max_length=32, blank=True)
    telegram_username = models.CharField('شناسهٔ پشتیبان در تلگرام', max_length=32, blank=True)
    revision = models.PositiveIntegerField(default=0, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'تنظیم کارت‌به‌کارت'
        verbose_name_plural = 'تنظیم کارت‌به‌کارت'
        permissions = [('manage_manual_payments', 'Configure merchant card and receipt channels')]


class ManualPayment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purchase = models.OneToOneField(CreditPurchase, on_delete=models.PROTECT, related_name='manual_payment')
    status = models.CharField('وضعیت', max_length=24, default='awaiting_transfer', choices=[
        ('awaiting_transfer', 'در انتظار واریز'), ('awaiting_review', 'در انتظار بررسی رسید'),
        ('approved', 'تأییدشده'), ('rejected', 'تأییدنشده'), ('cancelled', 'لغوشده')])
    card_number = EncryptedTextField(default='', db_default='', editable=False)
    card_holder = models.CharField(max_length=80, editable=False)
    bank_name = models.CharField(max_length=80, blank=True, default="", db_default="", editable=False)
    bale_username = models.CharField(max_length=32, blank=True, editable=False)
    telegram_username = models.CharField(max_length=32, blank=True, editable=False)
    receipt_reference = EncryptedTextField(blank=True, default='', db_default='', editable=False)
    receipt_submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    confirmed_reference = EncryptedTextField(blank=True, default='', db_default='', editable=False)
    confirmed_reference_digest = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    paid_date = models.DateField(null=True, blank=True, editable=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='reviewed_manual_payments', editable=False)
    reviewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    review_note = models.CharField(max_length=200, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رسید کارت‌به‌کارت'
        verbose_name_plural = 'رسیدهای کارت‌به‌کارت'
        permissions = [('approve_manual_payments', 'Review bank transfers and grant purchased message packages')]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['awaiting_transfer', 'awaiting_review', 'approved', 'rejected', 'cancelled']), name='manual_payment_known_status'),
            models.CheckConstraint(condition=~models.Q(status='approved') | models.Q(reviewed_by__isnull=False, reviewed_at__isnull=False, confirmed_reference_digest__isnull=False), name='manual_payment_approval_evidence')]


class SupportConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.OneToOneField(Account, on_delete=models.PROTECT, related_name='support_conversation')
    status = models.CharField(max_length=8, default='open', choices=[('open', 'باز'), ('closed', 'بسته')])
    last_sequence = models.PositiveIntegerField(default=0)
    last_customer_sequence = models.PositiveIntegerField(default=0)
    answered_customer_sequence = models.PositiveIntegerField(default=0)
    staff_read_sequence = models.PositiveIntegerField(default=0)
    customer_read_sequence = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'گفت‌وگوی پشتیبانی'
        verbose_name_plural = 'گفت‌وگوهای پشتیبانی'
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['open', 'closed']), name='support_known_status'),
            models.CheckConstraint(condition=models.Q(last_customer_sequence__lte=models.F('last_sequence')), name='support_customer_sequence_bound'),
            models.CheckConstraint(condition=models.Q(answered_customer_sequence__lte=models.F('last_customer_sequence')), name='support_answer_sequence_bound'),
            models.CheckConstraint(condition=models.Q(staff_read_sequence__lte=models.F('last_sequence')), name='support_staff_read_bound'),
            models.CheckConstraint(condition=models.Q(customer_read_sequence__lte=models.F('last_sequence')), name='support_customer_read_bound'),
            models.CheckConstraint(condition=~models.Q(status='closed') | models.Q(last_customer_sequence__lte=models.F('answered_customer_sequence')), name='support_close_answered_only'),
        ]


class SupportMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(SupportConversation, on_delete=models.PROTECT, related_name='messages')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='support_messages')
    role = models.CharField(max_length=8, choices=[('customer', 'کاربر'), ('staff', 'پشتیبانی')])
    sequence = models.PositiveIntegerField()
    client_key = models.UUIDField(editable=False)
    text = EncryptedTextField(default='', db_default='', editable=False)
    text_digest = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    redacted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'پیام پشتیبانی'
        verbose_name_plural = 'پیام‌های پشتیبانی'
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['conversation', 'sequence'], name='support_unique_sequence'),
            models.UniqueConstraint(fields=['conversation', 'author', 'client_key'], name='support_unique_client_key'),
            models.CheckConstraint(condition=models.Q(sequence__gt=0), name='support_positive_sequence'),
            models.CheckConstraint(condition=models.Q(role__in=['customer', 'staff']), name='support_known_role'),
        ]
        indexes = [models.Index(fields=['conversation', 'role', 'sequence'], name='support_role_sequence_idx')]
