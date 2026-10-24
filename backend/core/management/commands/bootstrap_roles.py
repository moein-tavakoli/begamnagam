from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create inspection-only foundation roles; does not assign staff or users.'

    def handle(self, *args, **options):
        roles = {
            'support_observer': ['order', 'moderationaudit', 'messagedelivery'],
            'finance_observer': ['order', 'paymentattempt', 'refund', 'financialevent'],
        }
        for name, models in roles.items():
            group, _ = Group.objects.get_or_create(name=name)
            # Re-running does not remove permissions previously assigned by an owner.
            group.permissions.add(*Permission.objects.filter(content_type__app_label='core',
                codename__in=[f'view_{model}' for model in models]))
            self.stdout.write(f'{name}: view permissions available; no user assigned')
