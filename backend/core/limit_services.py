"""One audited write path for the Django and Next management interfaces."""
from django.core.exceptions import ValidationError
from django.db import models, transaction
from .limit_defaults import REQUEST_LIMITS
from .limits import defaults, wake_policy_deferrals
from .models import OperatorAudit, RequestLimit, SiteLimits
from .services import APIError

LIMIT_SECTIONS = (
    ("روش‌های پرداخت", ("wallet_enabled", "gateway_enabled")),
    ("ارسال و دریافت", ("sender_limit", "sender_window_hours", "recipient_limit", "recipient_window_hours", "recipient_cooldown_hours", "pair_cooldown_hours")),
    ("ساعت مجاز ارسال", ("sending_window_enabled", "sending_start_hour", "sending_end_hour")),
    ("دعوت دوستان", ("invitation_max_sends", "invitation_limit", "invitation_window_hours", "invitation_cooldown_hours", "invitation_validity_days")),
    ("اعتبار ورود و پیش‌نمایش", ("otp_validity_seconds", "otp_max_attempts", "preview_validity_seconds")),
    ("هزینهٔ پیامک — ریال", ("provider_budget_unlimited", "provider_daily_budget_rial", "otp_max_cost_rial", "sms_max_cost_rial")),
    ("بازنویسی GapGPT", ("rewrite_daily_unlimited", "rewrite_daily_limit", "rewrite_user_limit")),
)


def editable_values(instance):
    return {field.name: getattr(instance, field.name) for field in instance._meta.fields
            if field.editable and not field.primary_key and field.name not in {"scope", "price_toman"}}


def validate_reason(reason):
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 200:
        raise APIError("reason_required", "دلیل تغییر باید بین ۳ تا ۲۰۰ نویسه باشد.", 422)
    return reason.strip()


@transaction.atomic
def update_limits(actor, kind, values, revision, reason, *, scope=None):
    if not actor.is_active or not actor.is_staff or not actor.has_perm("core.manage_site_limits"):
        raise APIError("forbidden", "مجوز تغییر محدودیت‌ها را ندارید.", 403)
    reason = validate_reason(reason)
    if type(revision) is not int or revision < 0 or not isinstance(values, dict) or not values:
        raise APIError("invalid_input", "مقادیر و نسخهٔ تنظیمات معتبر نیست.", 422)
    if kind == "site":
        initial = defaults()
        instance, created = SiteLimits.objects.get_or_create(pk=1, defaults=editable_values(initial))
        instance = SiteLimits.objects.select_for_update().get(pk=instance.pk)
    elif kind == "request" and scope in REQUEST_LIMITS:
        _, maximum, seconds, _ = REQUEST_LIMITS[scope]
        instance, created = RequestLimit.objects.get_or_create(scope=scope,
            defaults={"maximum": maximum, "window_seconds": seconds})
        instance = RequestLimit.objects.select_for_update().get(pk=instance.pk)
    else:
        raise APIError("not_found", "تنظیم پیدا نشد.", 404)
    if revision != instance.revision:
        raise APIError("settings_changed", "مدیر دیگری تنظیمات را تغییر داده است؛ تازه‌سازی کن و دوباره بررسی کن.", 409)
    before = editable_values(instance)
    for key, value in values.items():
        if key not in before:
            raise APIError("invalid_input", "فیلد تنظیمات معتبر نیست.", 422)
        field = instance._meta.get_field(key)
        expected = bool if isinstance(field, models.BooleanField) else int
        if type(value) is not expected:
            raise APIError("invalid_settings", "نوع مقدار تنظیم معتبر نیست.", 422, {key: ["یک مقدار معتبر وارد کن."]})
        setattr(instance, key, value)
    try:
        instance.full_clean()
    except ValidationError as error:
        fields = error.message_dict if hasattr(error, "message_dict") else {"__all__": error.messages}
        raise APIError("invalid_settings", "مقادیر مشخص‌شده را اصلاح کن.", 422, fields) from None
    after = editable_values(instance)
    if kind == 'site' and after.get('gateway_enabled') and not before.get('gateway_enabled'):
        from .payment_options import gateway_problem
        problem = gateway_problem()
        if problem:
            raise APIError('gateway_not_ready', problem, 422, {'gateway_enabled': [problem]})
    if created or before != after:
        instance.revision += 1
        instance.save()
        OperatorAudit.objects.create(actor=actor, action="update_site_limits",
            object_id=f"{instance._meta.model_name}:{instance.pk}", reason=reason, before=before, after=after)
        if kind == "site":
            wake_policy_deferrals()
    return instance
