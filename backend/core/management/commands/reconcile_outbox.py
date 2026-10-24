from django.core.management.base import BaseCommand
from core.tasks import reconcile_outbox


class Command(BaseCommand):
    help = "Publish pending committed outbox events; safe to repeat."

    def handle(self, *args, **options):
        reconcile_outbox()
        self.stdout.write(self.style.SUCCESS("Pending outbox events dispatched."))
