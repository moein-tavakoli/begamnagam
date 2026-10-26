"""One-time restoration of demo-only gift balances; never resends old orders."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Account, MessageDelivery, OperatorAudit, Outbox, Order, RecipientState, SafetyControl


class Command(BaseCommand):
    help = "Restore three gift sends for demo-only accounts once, while dispatch is halted."

    @transaction.atomic
    def handle(self, *args, **options):
        if (settings.DEMO_MODE or settings.PAYMENT_BACKEND != "disabled"
                or settings.SMS_BACKEND != "kavenegar" or settings.PROVIDER_NETWORK_MODE != "external"):
            raise CommandError("Requires the explicitly activated live gift SMS profile")
        control, _ = SafetyControl.objects.get_or_create(pk=1, defaults={"halted": True})
        control = SafetyControl.objects.select_for_update().get(pk=control.pk)
        if not control.halted:
            raise CommandError("Halt dispatch before the one-time gift launch")
        action = "live_gift_launch"
        if OperatorAudit.objects.filter(action=action, object_id="global").exists():
            self.stdout.write("Already applied; no balances changed")
            return
        if Outbox.objects.exclude(state__in=["sent", "failed", "cancelled"]).exists():
            raise CommandError("Resolve outstanding deliveries before the gift launch")
        changed = []
        for account in Account.objects.select_for_update().filter(free_sends_remaining__lt=3):
            if (MessageDelivery.objects.filter(order__owner_id=account.user_id, provider="kavenegar").exists()
                    or Order.objects.filter(owner_id=account.user_id, status="awaiting_payment").exists()):
                continue
            changed.append({"account_id": account.pk, "before": account.free_sends_remaining, "after": 3})
            account.free_sends_remaining = 3
            account.save(update_fields=["free_sends_remaining"])
        # A simulated delivery must not consume the first real recipient window.
        # Keep opt-outs, reports and every state touched by a real provider intact.
        demo_recipients = Order.objects.filter(status='delivered_demo').values('recipient_hash')
        real_recipients = MessageDelivery.objects.filter(provider='kavenegar').values('order__recipient_hash')
        cleared = RecipientState.objects.filter(phone_hash__in=demo_recipients,
            last_sent_at__isnull=False).exclude(phone_hash__in=real_recipients).update(last_sent_at=None)
        OperatorAudit.objects.create(action=action, object_id="global",
            reason="User authorized three real gift sends; restore credits used only in demo",
            after={"accounts": changed, "count": len(changed), "demo_cooldowns_cleared": cleared})
        self.stdout.write(f"Restored {len(changed)} demo-only gift balances; no messages dispatched")
