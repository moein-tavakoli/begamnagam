from django.contrib import admin

from .models import Account, ModerationAudit, Order, Outbox, RecipientState


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


@admin.register(Account)
class AccountAdmin(ReadOnlyAdmin):
    list_display = ("id", "phone_masked", "created_at")
    fields = ("id", "phone_masked", "created_at")
    readonly_fields = fields


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


# Foundation records are inspection-only, including for superusers. Future
# support/refund actions need separate services and an explicit phase approval.
from .models import FinancialEvent, MessageDelivery, PaymentAttempt, Refund


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(ReadOnlyAdmin):
    list_display = ("id", "order_id", "status", "amount_toman", "environment", "created_at")
    list_filter = ("status", "environment")
    fields = ("id", "order", "status", "amount_toman", "currency", "environment", "applied_to_order", "created_at", "updated_at")
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

# Every state-changing action below calls an audited service; default model editing
# stays disabled, including for superusers.
from django import forms
from django.contrib.admin.helpers import ActionForm
from .models import AbuseReport, OperatorAudit, SafetyControl, OperationalAlert, SpendBudget
from .safety import operator_action
from .services import APIError


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
        return obj.grant.preview.text

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
