from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import ModerationAudit, OTPChallenge, Order, Preview


class Command(BaseCommand):
    help = "Remove expired OTPs and unused previews; redact completed recipient ciphertext after 30 days."

    def handle(self, *args, **options):
        now = timezone.now()
        OTPChallenge.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()
        Preview.objects.filter(expires_at__lt=now - timedelta(days=1), order__isnull=True).delete()
        Order.objects.filter(created_at__lt=now - timedelta(days=30)).exclude(status=Order.Status.QUEUED).update(recipient_cipher="")
        ModerationAudit.objects.filter(created_at__lt=now - timedelta(days=30)).delete()
        self.stdout.write(self.style.SUCCESS("Expired private data pruned."))
