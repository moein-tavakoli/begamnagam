"""Audited, versioned admin changes; application credentials are never editable."""
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db import connection
from .limits import defaults
from .models import RequestLimit, SiteLimits


class AuditedLimitForm(forms.ModelForm):
    reason = forms.CharField(label="دلیل تغییر", min_length=3, max_length=200,
        help_text="دلیل کوتاه؛ شماره، کد ورود یا اطلاعات خصوصی ننویسید.")
    source_revision = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source_revision"].initial = self.instance.revision
        if isinstance(self.instance, SiteLimits) and self.instance._state.adding:
            self.initial.update({field.name: getattr(defaults(), field.name) for field in SiteLimits._meta.fields if field.editable})
        if isinstance(self.instance, RequestLimit) and self.instance.pk:
            self.fields["scope"].disabled = True

    def clean(self):
        cleaned = super().clean()
        if isinstance(self.instance, SiteLimits) and cleaned.get('gateway_enabled'):
            from .payment_options import gateway_problem
            problem = gateway_problem()
            if problem:
                self.add_error('gateway_enabled', problem)
        if not self.instance._state.adding:
            rows = type(self.instance).objects
            if connection.in_atomic_block:
                rows = rows.select_for_update()
            current = rows.get(pk=self.instance.pk)
            if cleaned.get("source_revision") != current.revision:
                raise forms.ValidationError("تنظیمات توسط مدیر دیگری تغییر کرده است؛ صفحه را تازه کنید و دوباره ذخیره کنید.")
        return cleaned


class SiteLimitsForm(AuditedLimitForm):
    class Meta:
        model = SiteLimits
        fields = "__all__"


class RequestLimitForm(AuditedLimitForm):
    class Meta:
        model = RequestLimit
        fields = "__all__"


class AuditedLimitAdmin(admin.ModelAdmin):
    readonly_fields = ("revision", "updated_at")

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff and request.user.has_perm("core.manage_site_limits")

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj) or super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        from .limit_services import editable_values, update_limits
        saved = update_limits(request.user, "site" if isinstance(obj, SiteLimits) else "request",
            editable_values(obj), form.cleaned_data["source_revision"], form.cleaned_data["reason"],
            scope=getattr(obj, "scope", None))
        obj.__dict__.update(saved.__dict__)


@admin.register(SiteLimits)
class SiteLimitsAdmin(AuditedLimitAdmin):
    form = SiteLimitsForm
    list_display = ("__str__", "sender_limit", "recipient_limit", "sending_window_enabled", "updated_at")
    fieldsets = (
        ("روش‌های پرداخت", {"fields": ("wallet_enabled", "gateway_enabled")}),
        ("تعداد ارسال و دریافت — ۰ یعنی بدون محدودیت", {"fields": ("sender_limit", "sender_window_hours", "recipient_limit", "recipient_window_hours", "recipient_cooldown_hours", "pair_cooldown_hours")}),
        ("ساعت مجاز ارسال", {"fields": ("sending_window_enabled", "sending_start_hour", "sending_end_hour")}),
        ("دعوت با شماره", {"fields": ("invitation_max_sends", "invitation_limit", "invitation_window_hours", "invitation_cooldown_hours", "invitation_validity_days")}),
        ("اعتبار ورود و پیش‌نمایش", {"classes": ("collapse",), "fields": ("otp_validity_seconds", "otp_max_attempts", "preview_validity_seconds")}),
        ("هزینهٔ پیامک — ریال", {"classes": ("collapse",), "fields": ("provider_budget_unlimited", "provider_daily_budget_rial", "otp_max_cost_rial", "sms_max_cost_rial")}),
        ("سقف بازنویسی GapGPT", {"classes": ("collapse",), "fields": ("rewrite_daily_unlimited", "rewrite_daily_limit", "rewrite_user_limit")}),
        ("ثبت تغییر", {"fields": ("reason", "source_revision", "revision", "updated_at")}),
    )

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not SiteLimits.objects.exists()


@admin.register(RequestLimit)
class RequestLimitAdmin(AuditedLimitAdmin):
    form = RequestLimitForm
    list_display = ("scope", "enabled", "maximum", "window_seconds", "updated_at")
    list_filter = ("enabled",)
    fields = ("scope", "enabled", "maximum", "window_seconds", "reason", "source_revision", "revision", "updated_at")
