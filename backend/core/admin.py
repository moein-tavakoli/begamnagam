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
    list_display = ("id", "recipient_masked", "category", "status", "amount_toman", "created_at")
    list_filter = ("status", "category", "payment_mode")
    fields = ("id", "recipient_masked", "category", "text", "status", "amount_toman", "payment_mode", "paid_at", "created_at")
    readonly_fields = fields


@admin.register(Account)
class AccountAdmin(ReadOnlyAdmin):
    list_display = ("id", "phone_masked", "created_at")
    fields = ("id", "phone_masked", "created_at")
    readonly_fields = fields


@admin.register(RecipientState)
class RecipientStateAdmin(admin.ModelAdmin):
    list_display = ("identifier", "blocked", "last_sent_at", "updated_at")
    list_filter = ("blocked",)
    fields = ("identifier", "blocked", "last_sent_at", "updated_at")
    readonly_fields = ("identifier", "last_sent_at", "updated_at")

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
