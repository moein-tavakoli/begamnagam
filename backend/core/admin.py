from django import forms
from django.contrib import admin
from . import ai_admin  # noqa: F401 — register the shared AI configuration
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .models import Account, ModerationAudit, Order, Outbox, RecipientState, Invitation, InvitationSend
from .account_options import OPTION_PERMISSIONS, update_account_options


class AccountOptionsForm(forms.ModelForm):
    settings_reason = forms.CharField(label="دلیل تغییر تنظیمات", required=False, max_length=200,
        help_text="برای تغییر تیک‌ها دلیل کوتاه بنویس؛ شماره، کد ورود یا اطلاعات خصوصی ننویس.")

    class Meta:
        model = Account
        fields = ("unlimited_demo_sends", "direct_message_tone")

    def clean(self):
        cleaned = super().clean()
        if any(key in self.changed_data for key in OPTION_PERMISSIONS):
            if len(cleaned.get("settings_reason", "").strip()) < 3:
                self.add_error("settings_reason", "دلیل تغییر را در حداقل ۳ نویسه بنویس.")
            from .demo_limits import test_tools_enabled
            if ("unlimited_demo_sends" in self.changed_data and cleaned.get("unlimited_demo_sends")
                    and not test_tools_enabled()):
                self.add_error("unlimited_demo_sends", "این گزینه فقط در محیط ارسال و پرداخت آزمایشی فعال می‌شود.")
        return cleaned


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(ReadOnlyAdmin):
    list_display = ("id", "status", "amount_toman", "created_at")
    list_filter = ("status", "category", "payment_mode")
    fields = ("id", "status", "amount_toman", "payment_mode", "paid_at", "created_at")
    readonly_fields = fields

    def get_fields(self, request, obj=None):
        from .message_review import may_review_messages
        return self.fields + (("original_message", "reviewed_message") if may_review_messages(request.user) else ())

    def get_readonly_fields(self, request, obj=None):
        return self.get_fields(request, obj)

    @admin.display(description="متن اولیهٔ کاربر — فقط مدیریت")
    def original_message(self, obj):
        return obj.preview.original_text or "متن اولیه برای این سابقه موجود نیست."

    @admin.display(description="متن نهایی بررسی‌شده")
    def reviewed_message(self, obj):
        from .message_review import message_texts
        return message_texts(obj)["final_text"] or "متن طبق سیاست نگهداری حذف شده است."

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from .message_review import may_review_messages, audit_review
        if request.method == "GET" and self.has_view_permission(request) and may_review_messages(request.user):
            obj = self.get_object(request, object_id)
            if obj:
                audit_review(request.user, obj, "django_order_text_review")
        return super().change_view(request, object_id, form_url, extra_context)


@admin.register(Account)
class AccountAdmin(ReadOnlyAdmin):
    form = AccountOptionsForm
    change_list_template = "admin/core/account/change_list.html"
    list_display = ("id", "phone_masked", "free_sends_remaining", "unlimited_demo_sends", "direct_message_tone", "created_at")
    list_filter = ("unlimited_demo_sends", "direct_message_tone")
    search_fields = ("phone_masked",)
    fields = ("id", "phone_masked", "free_sends_remaining", "free_sends_earned_total", "purchased_sends_remaining", "demo_sends_remaining", "created_at")
    readonly_fields = fields


    def has_change_permission(self, request, obj=None):
        return any(request.user.has_perm(permission) for permission in OPTION_PERMISSIONS.values())

    def get_fields(self, request, obj=None):
        return (*self.fields, *OPTION_PERMISSIONS,
                *(("settings_reason",) if self.has_change_permission(request, obj) else ()))

    def get_readonly_fields(self, request, obj=None):
        return (*self.readonly_fields, *(key for key, permission in OPTION_PERMISSIONS.items()
                                        if not request.user.has_perm(permission)))

    def save_model(self, request, obj, form, change):
        changes = {key: form.cleaned_data[key] for key in OPTION_PERMISSIONS if key in form.changed_data}
        if changes:
            update_account_options(request.user, obj.pk, changes, form.cleaned_data["settings_reason"])

    def get_urls(self):
        return [path("test-limits/", self.admin_site.admin_view(self.test_limits_view),
                     name="core_account_test_limits")] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        from .demo_limits import test_tools_enabled
        context = {"can_reset_demo_limits": test_tools_enabled() and request.user.has_perm("core.reset_demo_limits")}
        context.update(extra_context or {})
        return super().changelist_view(request, extra_context=context)

    def test_limits_view(self, request):
        from .demo_limits import reset_demo_limits, test_tools_enabled
        if not request.user.has_perm("core.reset_demo_limits") or not test_tools_enabled():
            raise PermissionDenied
        if request.method not in {"GET", "POST"}:
            return HttpResponseNotAllowed(["GET", "POST"])
        form = DemoLimitResetForm(request.POST if request.method == "POST" else None)
        if request.method == "POST" and form.is_valid():
            try:
                reset = reset_demo_limits(request.user, **form.cleaned_data)
            except (APIError, ValueError) as exc:
                form.add_error(None, exc.message if isinstance(exc, APIError) else str(exc))
            else:
                self.message_user(request, f"محدودیت آزمایشی ریست شد؛ سابقهٔ اقدام {reset.pk} ثبت شد.")
                return HttpResponseRedirect(reverse("admin:core_account_test_limits"))
        return TemplateResponse(request, "admin/core/account/test_limits.html", {
            **self.admin_site.each_context(request), "opts": self.model._meta,
            "title": "ریست محدودیت آزمایشی", "form": form,
        })


@admin.register(RecipientState)
class RecipientStateAdmin(ReadOnlyAdmin):
    list_display = ("identifier", "blocked", "last_sent_at", "updated_at")
    list_filter = ("blocked",)
    fields = ("identifier", "blocked", "last_sent_at", "updated_at")
    readonly_fields = ("identifier", "blocked", "last_sent_at", "updated_at")

    @admin.display(description="شناسه ناشناس")
    def identifier(self, obj):
        return obj.phone_hash[:12] + "…"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ModerationAudit)
class ModerationAuditAdmin(ReadOnlyAdmin):
    list_display = ("event_id", "category", "outcome", "reason_code", "created_at")
    list_filter = ("outcome", "category")
    fields = ("event_id", "category", "outcome", "reason_code", "created_at")
    readonly_fields = fields


@admin.register(Outbox)
class OutboxAdmin(ReadOnlyAdmin):
    list_display = ("id", "state", "attempts", "last_error_code", "created_at")
    fields = ("id", "state", "attempts", "last_error_code", "created_at", "processed_at")
    readonly_fields = fields


admin.site.site_header = "مدیریت بگم نگم"
admin.site.site_title = "بگم نگم"

from . import limit_admin  # noqa: F401,E402


# Foundation records are inspection-only, including for superusers. Future
# support/refund actions need separate services and an explicit phase approval.
from .models import FinancialEvent, MessageDelivery, PaymentAttempt, Refund


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(ReadOnlyAdmin):
    list_display = ("id", "order_id", "status", "amount_toman", "environment", "created_at")
    list_filter = ("status", "environment")
    fields = ("id", "order", "purchase", "status", "amount_toman", "currency", "environment", "applied_to_order", "created_at", "updated_at")
    readonly_fields = fields


@admin.register(MessageDelivery)
class MessageDeliveryAdmin(ReadOnlyAdmin):
    list_display = ("id", "order_id", "status", "attempts", "environment", "created_at")
    list_filter = ("status", "environment")
    fields = ("id", "order", "status", "attempts", "environment", "last_error_code", "created_at", "updated_at")
    readonly_fields = fields


@admin.register(Refund)
class RefundAdmin(ReadOnlyAdmin):
    list_display = ("id", "status", "amount_toman", "reason_code", "created_at")
    fields = ("id", "payment", "status", "amount_toman", "reason_code", "created_at", "updated_at")
    readonly_fields = fields


@admin.register(FinancialEvent)
class FinancialEventAdmin(ReadOnlyAdmin):
    list_display = ("id", "kind", "amount_toman", "created_at")
    fields = ("id", "payment", "refund", "kind", "amount_toman", "created_at")
    readonly_fields = fields

# State changes use audited services. Account option fields above are the only
# scoped editable fields; private identity, balances and foundation records stay read-only.
from django.contrib.admin.helpers import ActionForm
from .models import AbuseReport, OperatorAudit, SafetyControl, OperationalAlert, SpendBudget
from .safety import operator_action
from .services import APIError


class DemoLimitResetForm(forms.Form):
    sender_phone = forms.CharField(label="شمارهٔ فرستندهٔ تست", max_length=32,
        help_text="شماره‌ای که قبلاً با آن وارد محصول شده‌ای.",
        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "dir": "ltr", "autocomplete": "off", "data-normalize-digits": ""}))
    recipient_phone = forms.CharField(label="شمارهٔ گیرندهٔ تست", max_length=32,
        widget=forms.TextInput(attrs={"type": "tel", "inputmode": "tel", "dir": "ltr", "autocomplete": "off", "data-normalize-digits": ""}))
    reason = forms.CharField(label="دلیل تست", min_length=3, max_length=200,
        help_text="فقط دلیل کوتاه بنویس؛ شماره، کد ورود یا اطلاعات خصوصی ننویس.")

    def clean_sender_phone(self):
        from .privacy import normalize_phone
        try:
            return normalize_phone(self.cleaned_data["sender_phone"])
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from None

    def clean_recipient_phone(self):
        from .privacy import normalize_phone
        try:
            return normalize_phone(self.cleaned_data["recipient_phone"])
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from None


from .models import DemoLimitReset


@admin.register(DemoLimitReset)
class DemoLimitResetAdmin(ReadOnlyAdmin):
    list_display = ("id", "sender_id", "recipient_identifier", "actor_id", "created_at")
    fields = ("id", "sender", "recipient_identifier", "actor", "created_at")
    readonly_fields = fields

    @admin.display(description="شناسهٔ گیرندهٔ تست")
    def recipient_identifier(self, obj):
        return obj.recipient_hash[:12] + "…"


class AuditedActionForm(ActionForm):
    reason = forms.CharField(label='دلیل اقدام', required=False, max_length=200)
    reference = forms.CharField(label='مرجع مستند بازپرداخت', required=False, max_length=100)


def perform_action(modeladmin, request, queryset, action):
    # Check reason in the service; empty submissions never change state.
    try:
        for obj in queryset:
            operator_action(request.user, action, obj.pk, request.POST.get('reason', ''), request.POST.get('reference', ''))
    except APIError as exc:
        modeladmin.message_user(request, exc.message, level='ERROR')
    else:
        modeladmin.message_user(request, 'اقدام و سابقه ممیزی ثبت شد.')


@admin.action(description='تعلیق ارسال حساب‌های انتخاب‌شده', permissions=['suspend'])
def suspend_accounts(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'suspend')


@admin.action(description='رفع تعلیق ارسال با ثبت دلیل', permissions=['suspend'])
def resume_accounts(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'unsuspend')


AccountAdmin.actions = [suspend_accounts, resume_accounts]
AccountAdmin.action_form = AuditedActionForm
AccountAdmin.has_suspend_permission = lambda self, request: request.user.has_perm('core.suspend_account')


@admin.action(description='ثبت بازپرداخت انجام‌شده با مرجع مستند', permissions=['confirm'])
def confirm_refunds(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'confirm_refund')


RefundAdmin.actions = [confirm_refunds]
RefundAdmin.action_form = AuditedActionForm
RefundAdmin.has_confirm_permission = lambda self, request: request.user.has_perm('core.confirm_refund')


@admin.action(description='بستن گزارش با ثبت دلیل', permissions=['triage'])
def close_reports(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'close_report')


@admin.action(description='تمدید نگهداری پرونده برای۳۰روز با ثبت دلیل', permissions=['triage'])
def hold_reports(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'hold_report')


@admin.register(AbuseReport)
class AbuseReportAdmin(ReadOnlyAdmin):
    list_display = ('id', 'reason', 'status', 'created_at', 'closed_at')
    list_filter = ('status', 'reason')
    fields = ('id', 'reason', 'details', 'reviewed_text', 'status', 'created_at', 'closed_at', 'hold_until')
    readonly_fields = fields
    actions = [close_reports, hold_reports]
    action_form = AuditedActionForm

    def has_triage_permission(self, request):
        return request.user.has_perm('core.triage_report')

    @admin.display(description='متن بررسی‌شده مرتبط با پرونده')
    def reviewed_text(self, obj):
        if obj.grant.preview_id:
            return obj.grant.preview.generated_body or obj.grant.preview.text
        from .invitations import INVITE_BODY
        return INVITE_BODY if obj.grant.invitation_send_id else 'متن طبق سیاست نگهداری حذف شده است.'

    def change_view(self, request, object_id, form_url='', extra_context=None):
        if self.has_view_permission(request):
            OperatorAudit.objects.create(actor=request.user, action='report_viewed', object_id=str(object_id), reason='role_based_case_review')
        return super().change_view(request, object_id, form_url, extra_context)


@admin.action(description='توقف فوری پذیرش و ارسال جدید', permissions=['operate'])
def halt_sending(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'halt')


@admin.action(description='ازسرگیری با ثبت دلیل', permissions=['operate'])
def resume_sending(modeladmin, request, queryset):
    perform_action(modeladmin, request, queryset, 'resume')


@admin.register(SafetyControl)
class SafetyControlAdmin(ReadOnlyAdmin):
    list_display = ('id', 'halted', 'updated_at')
    fields = ('id', 'halted', 'updated_at')
    readonly_fields = fields
    actions = [halt_sending, resume_sending]
    action_form = AuditedActionForm

    def has_operate_permission(self, request):
        return request.user.has_perm('core.operate_safety')


@admin.register(OperatorAudit)
class OperatorAuditAdmin(ReadOnlyAdmin):
    list_display = ('id', 'action', 'object_id', 'actor_id', 'created_at')
    list_filter = ('action',)
    fields = ('id', 'action', 'object_id', 'actor', 'reason', 'before', 'after', 'created_at')
    readonly_fields = fields


@admin.register(OperationalAlert)
class OperationalAlertAdmin(ReadOnlyAdmin):
    list_display = ('code', 'severity', 'active', 'count', 'acknowledged_by', 'updated_at')
    list_filter = ('active', 'severity')


@admin.register(SpendBudget)
class SpendBudgetAdmin(ReadOnlyAdmin):
    list_display = ('day', 'reserved_rial', 'limit_rial')


@admin.register(Invitation)
class InvitationAdmin(ReadOnlyAdmin):
    list_display = ('id', 'phone_masked', 'created_at', 'registered_at', 'reward_awarded_at')
    fields = list_display
    readonly_fields = fields


@admin.register(InvitationSend)
class InvitationSendAdmin(ReadOnlyAdmin):
    list_display = ('id', 'ordinal', 'status', 'created_at', 'accepted_at')
    list_filter = ('status', 'provider')
    fields = ('id', 'ordinal', 'status', 'provider', 'last_error_code', 'consent_at', 'consent_version', 'created_at', 'accepted_at')
    readonly_fields = fields

# Bundle settings share the same audited service with the Next management UI.
from . import package_admin  # noqa: F401,E402
from . import wallet_admin  # noqa: F401,E402
