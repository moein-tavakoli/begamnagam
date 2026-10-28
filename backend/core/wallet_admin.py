from django.contrib import admin
from .admin import ReadOnlyAdmin
from .models import WalletEntry, WalletTopup


@admin.register(WalletEntry)
class WalletEntryAdmin(ReadOnlyAdmin):
    list_display = ('id', 'kind', 'amount_toman', 'balance_after_toman', 'environment', 'created_at')
    list_filter = ('kind', 'environment')
    fields = ('id', 'kind', 'amount_toman', 'balance_after_toman', 'environment', 'created_at')
    readonly_fields = fields


@admin.register(WalletTopup)
class WalletTopupAdmin(ReadOnlyAdmin):
    list_display = ('id', 'amount_toman', 'environment', 'created_at', 'credited_at')
    list_filter = ('environment',)
    fields = ('id', 'amount_toman', 'environment', 'terms_version', 'consent_at', 'created_at', 'credited_at')
    readonly_fields = fields
