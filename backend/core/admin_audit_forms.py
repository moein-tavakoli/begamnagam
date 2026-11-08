"""Automatic action labels replace manual reasons; actor/action auditing remains."""
from django import forms


class AutomaticReasonField(forms.CharField):
    def __init__(self, *args, audit_default='django_admin_action', **kwargs):
        self.audit_default = audit_default
        kwargs.update(required=False, widget=forms.HiddenInput, initial=audit_default)
        super().__init__(*args, **kwargs)

    def clean(self, value):
        if value in self.empty_values or (isinstance(value, str) and not value.strip()):
            value = self.audit_default
        return super().clean(value)
