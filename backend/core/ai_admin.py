from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from .ai_config import current, update, values
from .models import AIConfiguration
from .services import APIError


class AIForm(forms.ModelForm):
    reason = forms.CharField(label='دلیل تغییر', min_length=3, max_length=200)
    source_revision = forms.IntegerField(widget=forms.HiddenInput, required=True)

    class Meta:
        model = AIConfiguration
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_revision'].initial = self.instance.revision


@admin.register(AIConfiguration)
class AIConfigurationAdmin(admin.ModelAdmin):
    form = AIForm
    list_display = ('__str__', 'provider', 'ollama_model', 'updated_at')
    readonly_fields = ('revision', 'updated_at')
    fieldsets = (
        ('سرویس فعال برای پیش‌نمایش‌های تازه', {'fields': ('provider',),
            'description': 'پردازش داخل همان درخواست انجام می‌شود؛ صف AI و جایگزینی خودکار سرویس وجود ندارد.'}),
        ('لحن‌های قابل انتخاب کاربران', {'fields': ('tone_polite_enabled', 'tone_firm_enabled', 'tone_angry_enabled'),
            'description': 'فقط لحن‌های تیک‌خورده زیر کادر متن نمایش داده می‌شوند. بدون تیک، حالت مودبانهٔ فعلی برقرار است. هیچ لحنی توهین، تهدید یا اطلاعات خصوصی را مجاز نمی‌کند.'}),
        ('Ollama — اجرای محلی', {'fields': ('ollama_model', 'timeout_seconds', 'parallel_requests', 'daily_limit', 'user_daily_limit')}),
        ('GapGPT', {'fields': ('gapgpt_model',), 'description': 'کلید فقط از env سرور خوانده می‌شود؛ فعال‌سازی به سهمیهٔ مثبت GapGPT نیاز دارد.'}),
        ('ثبت تغییر', {'fields': ('reason', 'source_revision', 'revision', 'updated_at')}),
    )

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff and request.user.has_perm('core.manage_ai')

    def has_view_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def has_add_permission(self, request):
        return self.has_change_permission(request) and not AIConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        saved = update(request.user, values(obj), form.cleaned_data['source_revision'], form.cleaned_data['reason'])
        obj.__dict__.update(saved.__dict__)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except APIError as error:
            self.message_user(request, error.message, messages.ERROR)
            return HttpResponseRedirect(request.path)
