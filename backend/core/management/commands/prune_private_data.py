from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from core.models import Account, AbuseReport, ModerationAudit, OTPChallenge, Order, Preview, RecipientState, RecipientGrant, OperatorAudit, Invitation, InvitationSend, RewriteUsage, SupportMessage


class Command(BaseCommand):
    help = 'Enforce private-data retention without deleting finance or suppression. Supports --dry-run.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        counts = {'otp': 0, 'unused_preview': 0, 'orders_redacted': 0, 'accounts_redacted': 0, 'reports_redacted': 0, 'invitations_redacted': 0}
        with transaction.atomic():
            otp = OTPChallenge.objects.filter(expires_at__lt=now-timedelta(days=1))
            previews = Preview.objects.filter(expires_at__lt=now-timedelta(days=1), order__isnull=True)
            counts['otp'], counts['unused_preview'] = otp.count(), previews.count()
            # Unresolved records keep identifiers needed for reconciliation; overdue
            # private data is surfaced by operations rather than silently erased.
            candidates = Order.objects.exclude(status__in=['queued', 'accepted', 'unknown']).filter(updated_at__lt=now-timedelta(days=31)).exclude(recipient_cipher='', full_sms='', text='', preview__original_text='')
            for order in candidates.select_for_update().iterator(chunk_size=200):
                if AbuseReport.objects.filter(grant__preview_id=order.preview_id, hold_until__gt=now).exists():
                    continue
                counts['orders_redacted'] += 1
                if not options['dry_run']:
                    # Keep amount/status/provider references/date and suppression.
                    Order.objects.filter(pk=order.pk).update(recipient_cipher='', recipient_masked='حذف‌شده', recipient_hash='', text='', full_sms='')
                    Preview.objects.filter(pk=order.preview_id).update(original_text='', text='', full_sms='', generated_body='', review_signature='', session_key='', recipient_hash='')
            accounts = Account.objects.filter(deletion_requested_at__lt=now-timedelta(days=30)).exclude(phone_cipher='')
            counts['accounts_redacted'] = accounts.count()
            reports = AbuseReport.objects.filter(Q(closed_at__lt=now-timedelta(days=180)) | Q(closed_at__isnull=True, created_at__lt=now-timedelta(days=180))).filter(Q(hold_until__isnull=True) | Q(hold_until__lte=now)).exclude(details='')
            counts['reports_redacted'] = reports.count()
            invitations = Invitation.objects.filter(created_at__lt=now-timedelta(days=90)).exclude(phone_cipher='').exclude(
                pk__in=InvitationSend.objects.filter(status__in=['pending', 'submitting', 'unknown', 'accepted']).values('invitation_id'))
            for invitation in invitations.select_for_update().iterator(chunk_size=200):
                if AbuseReport.objects.filter(grant__invitation_send__invitation=invitation, hold_until__gt=now).exists():
                    continue
                counts['invitations_redacted'] += 1
                if not options['dry_run']:
                    Invitation.objects.filter(pk=invitation.pk).update(phone_cipher='', phone_masked='حذف‌شده')
                    invitation.sends.update(full_sms='')
            support = SupportMessage.objects.filter(Q(created_at__lt=now-timedelta(days=90)) | Q(conversation__account__deletion_requested_at__lt=now-timedelta(days=30))).filter(redacted_at__isnull=True)
            counts['support_redacted'] = support.count()
            if not options['dry_run']:
                support.update(text='', redacted_at=now)
                otp.delete()
                previews.delete()
                accounts.update(phone_cipher='', phone_masked='حذف‌شده')
                reports.update(details='')
                Preview.objects.filter(expires_at__lt=now-timedelta(days=1)).update(session_key='')
                for expired in RecipientGrant.objects.filter(stop_expires_at__lt=now).exclude(recipient_hash='').iterator(chunk_size=200):
                    # Keep only the opaque digest reserved: a printed short code
                    # must never be reassigned to another recipient after expiry.
                    RecipientGrant.objects.filter(pk=expired.pk).update(recipient_hash='')
                ModerationAudit.objects.filter(created_at__lt=now-timedelta(days=30)).delete()
                RewriteUsage.objects.filter(created_at__lt=now-timedelta(days=90)).delete()
                OperatorAudit.objects.filter(created_at__lt=now-timedelta(days=180)).delete()
                # An active stop survives account/content cleanup, including forever
                # until the verified owner re-enables receipt. Never bulk-delete it.
                RecipientState.objects.filter(blocked=False, last_sent_at__lt=now-timedelta(days=31)).exclude(phone_hash__in=Order.objects.filter(status__in=['queued', 'accepted', 'unknown']).values('recipient_hash')).exclude(phone_hash__in=Invitation.objects.values('phone_hash')).delete()
        self.stdout.write(('Dry run: ' if options['dry_run'] else 'Applied: ') + str(counts))
