import json
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.bot_conversations import new_credential
from core.models import BotIntegration, OperatorAudit


class Command(BaseCommand):
    help = 'Create, rotate or disable a private Telegram/Bale adapter key. No provider network calls.'

    def add_arguments(self, parser):
        parser.add_argument('--platform', choices=['telegram', 'bale'], required=True)
        parser.add_argument('--bot-id', required=True)
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument('--rotate', action='store_true')
        modes.add_argument('--disable', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if not re.fullmatch(r'[1-9][0-9]{0,19}', options['bot_id']):
            raise CommandError('Use the canonical decimal bot id, not a username or vendor token.')
        integration = BotIntegration.objects.select_for_update().filter(platform=options['platform'], bot_id=options['bot_id']).first()
        if options['disable']:
            if integration is None:
                raise CommandError('Integration does not exist.')
            integration.active = False
            integration.save(update_fields=['active'])
            OperatorAudit.objects.create(action='bot_integration_disabled', object_id=str(integration.pk),
                reason='operator_command', before={}, after={'active': False})
            self.stdout.write(json.dumps({'id': str(integration.pk), 'active': False}))
            return
        if integration and not options['rotate']:
            raise CommandError('Integration exists. Use --rotate to issue a new key; existing secrets are never readable.')
        if integration is None:
            if options['rotate']:
                raise CommandError('Integration does not exist.')
            integration = BotIntegration(platform=options['platform'], bot_id=options['bot_id'])
        credential = new_credential(integration)
        integration.active = True
        integration.save()
        OperatorAudit.objects.create(action='bot_integration_key_issued', object_id=str(integration.pk),
            reason='operator_rotation' if options['rotate'] else 'operator_creation', before={},
            after={'platform': integration.platform, 'bot_id': integration.bot_id, 'active': True})
        self.stdout.write(json.dumps({'id': str(integration.pk), 'platform': integration.platform,
            'bot_id': integration.bot_id, 'api_key': credential}))
