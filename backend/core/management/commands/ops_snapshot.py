import json
from django.core.management.base import BaseCommand
from core.safety import refresh_alerts


class Command(BaseCommand):
    help = 'Emit aggregate operational metrics and refresh durable alerts; no phones, tokens or content.'

    def handle(self, *args, **options):
        self.stdout.write(json.dumps(refresh_alerts(), sort_keys=True))
