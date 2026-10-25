"""Scoped operator changes; no public endpoint can grant these options."""
from django.contrib.auth import get_user_model
from django.db import transaction

from .demo_limits import test_tools_enabled
from .models import Account, OperatorAudit
from .services import APIError


OPTION_PERMISSIONS = {
    "unlimited_demo_sends": "core.manage_test_sending",
    "direct_message_tone": "core.manage_message_tone",
}


def update_account_options(actor, account_id, changes, reason):
    if (not actor.is_active or not actor.is_staff or not changes
            or any(key not in OPTION_PERMISSIONS or type(value) is not bool
                   or not actor.has_perm(OPTION_PERMISSIONS[key]) for key, value in changes.items())):
        raise APIError("forbidden", "مجوز تغییر این تنظیمات را ندارید.", 403)
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
        raise APIError("reason_required", "دلیل تغییر باید بین ۳ تا ۲۰۰ نویسه باشد.")
    if changes.get("unlimited_demo_sends") and not test_tools_enabled():
        raise APIError("test_tools_disabled", "ارسال نامحدود فقط در محیط ارسال و پرداخت آزمایشی فعال می‌شود.", 403)
    with transaction.atomic():
        user_id = Account.objects.values_list("user_id", flat=True).get(pk=account_id)
        # Match the sender lock in checkout; never overwrite concurrent gift usage.
        get_user_model().objects.select_for_update().get(pk=user_id)
        account = Account.objects.select_for_update().get(pk=account_id)
        before = {key: getattr(account, key) for key in changes}
        changed = {key: value for key, value in changes.items() if before[key] != value}
        if changed:
            for key, value in changed.items():
                setattr(account, key, value)
            account.save(update_fields=list(changed))
            OperatorAudit.objects.create(actor=actor, action="account_send_options", object_id=str(account.pk),
                reason=reason.strip(), before={key: before[key] for key in changed}, after=changed)
        return account
