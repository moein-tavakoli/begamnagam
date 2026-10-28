"""Audited test baselines; never modify orders, opt-outs, OTPs or provider spend."""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Account, DemoLimitReset, OperatorAudit, Order, RecipientState
from .privacy import digest, normalize_phone


def test_tools_enabled():
    return (settings.DEMO_TEST_TOOLS_ENABLED and settings.DEMO_MODE
            and settings.SMS_BACKEND == "console" and settings.PAYMENT_BACKEND == "demo"
            and settings.PROVIDER_NETWORK_MODE == "disabled" and not settings.LIVE_PROVIDERS_ENABLED)


def unlimited_demo_sends(user):
    # Query current authorization rather than a potentially cached user.account.
    return bool(test_tools_enabled() and user and user.is_authenticated and Account.objects.filter(
        user_id=user.pk, unlimited_demo_sends=True, suspended=False, deletion_requested_at__isnull=True).exists())


def quota_start(now, *, hours, sender=None, recipient_hash=None):
    start = now - timedelta(hours=hours)
    if not test_tools_enabled():
        return start
    resets = DemoLimitReset.objects.filter(created_at__gt=start)
    if sender is not None:
        resets = resets.filter(sender=sender)
    if recipient_hash is not None:
        resets = resets.filter(recipient_hash=recipient_hash)
    return resets.order_by("-created_at").values_list("created_at", flat=True).first() or start


def recipient_in_cooldown(state, now, *, sender=None):
    from .limits import recipient_next_allowed
    return recipient_next_allowed(state, now, sender=sender) is not None


def reset_demo_limits(actor, sender_phone, recipient_phone, reason):
    from .services import APIError, models_busy_query

    if not actor.is_active or not actor.is_staff or not actor.has_perm("core.reset_demo_limits"):
        raise APIError("forbidden", "مجوز ریست محدودیت آزمایشی را ندارید.", 403)
    if not test_tools_enabled():
        raise APIError("test_tools_disabled", "ابزار تست فقط در محیط ارسال و پرداخت آزمایشی فعال است.", 403)
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
        raise APIError("reason_required", "دلیل تست باید بین ۳ تا ۲۰۰ نویسه باشد.")
    sender_hash = digest(normalize_phone(sender_phone))
    recipient_hash = digest(normalize_phone(recipient_phone))
    if sender_hash == recipient_hash:
        raise APIError("invalid_test_target", "گیرنده باید با فرستنده متفاوت باشد.")
    with transaction.atomic():
        account = Account.objects.filter(phone_hash=sender_hash).first()
        if not account:
            raise APIError("unknown_test_sender", "فرستنده باید قبلاً با شمارهٔ خود وارد محصول شده باشد.")
        # Match submission lock order: sender first, then recipient.
        get_user_model().objects.select_for_update().get(pk=account.user_id)
        RecipientState.objects.get_or_create(phone_hash=recipient_hash)
        state = RecipientState.objects.select_for_update().get(phone_hash=recipient_hash)
        if account.suspended or account.deletion_requested_at or state.blocked:
            raise APIError("test_target_unavailable", "قطع دریافت یا تعلیق حساب با ابزار تست برداشته نمی‌شود.", 409)
        if Order.objects.filter(recipient_hash=recipient_hash).filter(models_busy_query(timezone.now())).exists():
            raise APIError("test_target_busy", "سفارش باز گیرنده باید ابتدا تعیین تکلیف شود؛ سپس ریست کن.", 409)
        reset = DemoLimitReset.objects.create(sender=account.user, recipient_hash=recipient_hash, actor=actor)
        OperatorAudit.objects.create(actor=actor, action="reset_demo_limits", object_id=str(reset.pk),
            reason=reason.strip(), after={"sender_id": account.user_id, "recipient_key": recipient_hash[:12],
                                       "reset_at": reset.created_at.isoformat()})
        return reset
