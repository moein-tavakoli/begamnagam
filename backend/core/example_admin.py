from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.db import transaction

from .models import ExampleCategory, MessageExample
from .message_examples import FIELDS, write_record
from .services import APIError


class ExampleCategoryForm(forms.ModelForm):
    reason = forms.CharField(label='دلیل تغییر', min_length=3, max_length=200)
    source_revision = forms.IntegerField(widget=forms.HiddenInput)

    class Meta:
        model = ExampleCategory
        fields = FIELDS['groups']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_revision'].initial = self.instance.revision


class MessageExampleForm(ExampleCategoryForm):
    class Meta:
        model = MessageExample
        fields = ('group', 'label', 'description', 'text', 'topic', 'active', 'sort_order')
        widgets = {'text': forms.Textarea(attrs={'rows': 3})}


class CatalogAdmin(admin.ModelAdmin):
    list_filter = ('active',)

    def has_change_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_staff and request.user.has_perm('core.manage_message_examples')

    has_view_permission = has_change_permission
    has_delete_permission = has_change_permission

    def has_add_permission(self, request):
        return self.has_change_permission(request)

    def save_model(self, request, obj, form, change):
        saved = write_record(request.user, self.kind, {'values': {key: getattr(obj, key) for key in FIELDS[self.kind]},
            'revision': form.cleaned_data['source_revision'], 'reason': form.cleaned_data['reason']}, obj.pk if change else None)
        obj.pk, obj.revision = saved['id'], saved['revision']
        obj._state.adding = False

    def delete_model(self, request, obj):
        write_record(request.user, self.kind, {'revision': obj.revision, 'reason': 'حذف از مدیریت جنگو'}, obj.pk, delete=True)

    @transaction.atomic
    def delete_queryset(self, request, queryset):
        for obj in queryset:
            self.delete_model(request, obj)

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except APIError as error:
            self.message_user(request, error.message, messages.ERROR)
            return HttpResponseRedirect(request.path)


@admin.register(ExampleCategory)
class ExampleCategoryAdmin(CatalogAdmin):
    kind = 'groups'
    form = ExampleCategoryForm
    fields = (*FIELDS['groups'], 'reason', 'source_revision')
    list_display = ('name', 'active', 'sort_order')
    search_fields = ('name',)


@admin.register(MessageExample)
class MessageExampleAdmin(CatalogAdmin):
    kind = 'examples'
    form = MessageExampleForm
    fields = (*MessageExampleForm.Meta.fields, 'reason', 'source_revision')
    list_display = ('label', 'group', 'active', 'sort_order')
    list_filter = ('active', 'group', 'topic')
    search_fields = ('label', 'text')
