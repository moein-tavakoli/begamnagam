import json
from django.core.management.base import BaseCommand, CommandError
from core.models import Outbox
from core.queue_archive import archive_unknown_outbox
from core.services import APIError


class Command(BaseCommand):
    help = 'Archive one old unknown delivery from the active queue; retain records and never resend.'

    def add_arguments(self, parser):
        parser.add_argument('--id', type=int, required=True)
        parser.add_argument('--reason', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            event = (archive_unknown_outbox(options['id'], options['reason']) if options['apply']
                     else Outbox.objects.get(pk=options['id']))
        except (Outbox.DoesNotExist, APIError) as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(json.dumps({'id': event.pk, 'queue_state': event.state,
                                     'applied': options['apply'], 'deleted_records': 0, 'sms_sent': 0}))
