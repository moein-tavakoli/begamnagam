from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create scoped observer/operator roles and safety control; does not assign staff or users.'

    def handle(self, *args, **options):
        from django.conf import settings
        from core.models import SafetyControl
        SafetyControl.objects.get_or_create(pk=1, defaults={"halted": not settings.DEMO_MODE})
        roles = {
            'support_observer': ['order', 'moderationaudit', 'messagedelivery'],
            'finance_observer': ['order', 'paymentattempt', 'refund', 'financialevent', 'creditpurchase', 'creditentry'],
        }
        for name, models in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            # Re-running does not remove permissions previously assigned by an owner.
            group.permissions.add(*Permission.objects.filter(content_type__app_label='core',
                codename__in=[f'view_{model}' for model in models]))
            self.stdout.write(f'{name}: view permissions available; no user assigned')

        operators = {
            'content_support': ['view_abusereport', 'triage_report', 'view_account', 'suspend_account', 'view_order', 'view_operationalalert', 'view_operations'],
            'finance_operator': ['view_creditpurchase', 'view_creditentry', 'view_paymentattempt', 'view_refund', 'view_financialevent', 'view_order', 'view_spendbudget', 'confirm_refund', 'view_operations'],
            'safety_operator': ['view_safetycontrol', 'operate_safety', 'view_operatoraudit', 'view_operationalalert', 'view_operations'],
        }
        for name, codenames in operators.items():
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(*Permission.objects.filter(content_type__app_label='core', codename__in=codenames))
            self.stdout.write(f'{name}: scoped permissions available; no user assigned')
