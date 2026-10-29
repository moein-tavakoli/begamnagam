from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from .models import CreditEntry, CreditPurchase, MessagePackage
from .packages import PACKAGE_FIELDS, save_package
from .services import APIError


class PackageForm(forms.ModelForm):
    reason = forms.CharField(label='دلیل تغییر', min_length=3, max_length=200)
    source_revision = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = MessagePackage
        fields = PACKAGE_FIELDS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_revision'].initial = self.instance.revision


@admin.register(MessagePackage)
class PackageAdmin(admin.ModelAdmin):
    form = PackageForm
    list_display = ('name', 'message_count', 'price_toman', 'active', 'sort_order')
    list_filter = ('active',)
    fields = (*PACKAGE_FIELDS, 'reason', 'source_revision')

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff and request.user.has_perm('core.manage_message_packages')

    has_view_permission = has_change_permission

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        data = {'values': {key: getattr(obj, key) for key in PACKAGE_FIELDS},
            'revision': form.cleaned_data['source_revision'], 'reason': form.cleaned_data['reason']}
        saved = save_package(request.user, data, obj.pk if change else None)
        obj.__dict__.update(saved.__dict__)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except APIError as error:
            self.message_user(request, error.message, messages.ERROR)
            return HttpResponseRedirect(request.path)


class CreditReadOnlyAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CreditPurchase)
class PurchaseAdmin(CreditReadOnlyAdmin):
    list_display = ('id', 'package_name', 'message_count', 'amount_toman', 'environment', 'credited_at', 'created_at')
    list_filter = ('environment',)


@admin.register(CreditEntry)
class EntryAdmin(CreditReadOnlyAdmin):
    list_display = ('id', 'account_id', 'kind', 'units', 'environment', 'created_at')


from .models import ManualPaymentSettings, ManualPayment
from .manual_payments import SETTING_FIELDS, save_settings


class ManualSettingsForm(forms.ModelForm):
    reason = forms.CharField(label='دلیل تغییر', min_length=3, max_length=200)
    source_revision = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = ManualPaymentSettings
        fields = SETTING_FIELDS
        widgets = {'card_number': forms.TextInput(attrs={'inputmode':'numeric','autocomplete':'off'})}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['source_revision'].initial = self.instance.revision


@admin.register(ManualPaymentSettings)
class ManualSettingsAdmin(admin.ModelAdmin):
    form = ManualSettingsForm
    fields = (*SETTING_FIELDS, 'reason', 'source_revision')

    def has_change_permission(self,request,obj=None):
        return request.user.is_active and request.user.is_staff and request.user.has_perm('core.manage_manual_payments')

    has_view_permission = has_change_permission

    def has_add_permission(self,request):
        return self.has_change_permission(request) and not ManualPaymentSettings.objects.exists()

    def has_delete_permission(self,request,obj=None):return False

    def save_model(self,request,obj,form,change):
        save_settings(request.user,{'values':{key:getattr(obj,key) for key in SETTING_FIELDS},
            'revision':form.cleaned_data['source_revision'],'reason':form.cleaned_data['reason']})
        obj.__dict__.update(ManualPaymentSettings.objects.get(pk=1).__dict__)

    def changeform_view(self,request,object_id=None,form_url='',extra_context=None):
        try:return super().changeform_view(request,object_id,form_url,extra_context)
        except APIError as error:
            self.message_user(request,error.message,messages.ERROR)
            return HttpResponseRedirect(request.path)


@admin.register(ManualPayment)
class ManualPaymentAdmin(CreditReadOnlyAdmin):
    list_display = ('id','purchase_id','status','receipt_submitted_at','reviewed_at','created_at')
    list_filter = ('status',)
    def get_fields(self,request,obj=None):
        return ('id','purchase','status','receipt_submitted_at','paid_date','reviewed_by','reviewed_at','review_note','created_at')
