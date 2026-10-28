from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Account, OTPChallenge, Order, Preview, AbuseReport, Invitation, InvitationSend
from core.privacy import decrypt, encrypt


class Command(BaseCommand):
    help = 'Re-encrypt with the configured active key; needs old keys as fallbacks. HMAC identifiers do not change.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        count = 0
        try:
            with transaction.atomic():
                for model, field in [(Account, 'phone_cipher'), (OTPChallenge, 'phone_cipher'), (Order, 'recipient_cipher'), (Order, 'text'), (Order, 'full_sms'), (Preview, 'original_text'), (Preview, 'text'), (Preview, 'full_sms'), (Preview, 'generated_body'), (AbuseReport, 'details'), (Invitation, 'phone_cipher'), (InvitationSend, 'full_sms')]:
                    for obj in model.objects.select_for_update().iterator(chunk_size=200):
                        value = getattr(obj, field)
                        if not value:
                            continue
                        raw_cipher_field = field.endswith('_cipher')
                        plain = decrypt(value) if raw_cipher_field else value
                        if options['apply']:
                            setattr(obj, field, encrypt(plain) if raw_cipher_field else plain)
                            obj.save(update_fields=[field])
                        count += 1
        except Exception:
            raise CommandError('Key validation/rotation failed; transaction rolled back. No private data logged.') from None
        self.stdout.write(f'{"Re-encrypted" if options["apply"] else "Validated"} {count} fields; HMAC identifiers and financial events unchanged.')
