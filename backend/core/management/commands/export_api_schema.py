import json
from pathlib import Path

from django.core.management.base import BaseCommand

from core.api_v2.openapi import specification


class Command(BaseCommand):
    help = 'Export the v2 OpenAPI contract locally without enabling HTTP documentation.'

    def add_arguments(self, parser):
        parser.add_argument('--output', help='Local destination; omit to print JSON.')

    def handle(self, *args, **options):
        value = json.dumps(specification(), ensure_ascii=False, indent=2) + '\n'
        if options['output']:
            Path(options['output']).write_text(value, encoding='utf-8')
            self.stdout.write('OpenAPI contract exported.')
        else:
            self.stdout.write(value, ending='')
