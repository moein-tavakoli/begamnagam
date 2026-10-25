import uuid

from django.conf import settings
from django.db import models
from .fields import EncryptedTextField


class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="account")
    phone_hash = models.CharField(max_length=64, unique=True)
    phone_cipher = models.TextField()
    phone_masked = models.CharField(max_length=20)
    suspended = models.BooleanField(default=False)
    free_sends_remaining = models.PositiveSmallIntegerField(default=3)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [('suspend_account', 'Suspend or resume product senders')]
        constraints = [models.CheckConstraint(condition=models.Q(free_sends_remaining__lte=3), name="free_sends_max_three")]


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
    is_free = models.BooleanField(default=False)
    recipient_hash = models.CharField(max_length=64, blank=True)
    terms_version = models.CharField(max_length=40, blank=True)
    full_sms = EncryptedTextField(blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=64)
    category = models.CharField(max_length=32)
    text = models.TextField()
    moderation_mode = models.CharField(max_length=32)
    price_toman = models.PositiveIntegerField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class RecipientState(models.Model):
    phone_hash = models.CharField(primary_key=True, max_length=64)
    blocked = models.BooleanField(default=False)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


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
    text = models.TextField()
    category = models.CharField(max_length=32)
    amount_toman = models.PositiveIntegerField()
    status = models.CharField(max_length=24, choices=Status, default=Status.AWAITING_PAYMENT)
    payment_mode = models.CharField(max_length=16, default="demo")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "idempotency_key"], name="unique_owner_idempotency"),
            models.CheckConstraint(condition=models.Q(is_free=True, amount_toman=0) | models.Q(is_free=False, amount_toman__gt=0), name="order_free_or_positive_price")]
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


# Independent financial and delivery records. Network activation is guarded separately.
class PaymentAttempt(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "ایجادشده"
        PENDING = "pending", "در انتظار"
        VERIFIED = "verified", "تأییدشده"
        FAILED = "failed", "ناموفق"
        UNKNOWN = "unknown", "نیازمند تطبیق"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="payment_attempts")
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
            models.CheckConstraint(condition=models.Q(amount_toman__gt=0), name="payment_positive_amount"),
            models.CheckConstraint(condition=models.Q(currency="IRT"), name="payment_integer_toman"),
            models.CheckConstraint(condition=models.Q(environment="demo", provider="demo") | models.Q(environment__in=["sandbox", "live"], provider="zarinpal"), name="payment_provider_environment"),
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
    preview = models.OneToOneField(Preview, on_delete=models.CASCADE, related_name='recipient_grant')
    token_digest = models.CharField(max_length=64, unique=True)
    recipient_hash = models.CharField(max_length=64, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    stop_expires_at = models.DateTimeField(null=True, blank=True)
    report_expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


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
