"""Initialize admin-visible controls; explicit relaxation never changes credits."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.limit_defaults import REQUEST_LIMITS
from core.limits import defaults, wake_policy_deferrals
from core.models import OperatorAudit, RequestLimit, SiteLimits


class Command(BaseCommand):
    help = "Initialize runtime limits, optionally remove business count/time restrictions."

    def add_arguments(self, parser):
        parser.add_argument("--relax-business", action="store_true")
        parser.add_argument("--reason", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        reason = options["reason"].strip()
        if not 3 <= len(reason) <= 200:
            raise CommandError("A reason of 3–200 characters is required")
        if options["relax_business"] and settings.PAYMENT_BACKEND != "disabled":
            raise CommandError("Relaxation is limited to the explicitly authorized gift product with payments disabled")
        initial = defaults()
        data = {field.name: getattr(initial, field.name) for field in SiteLimits._meta.fields if field.editable}
        value, created = SiteLimits.objects.get_or_create(pk=1, defaults=data)
        value = SiteLimits.objects.select_for_update().get(pk=value.pk)
        before = {field.name: getattr(value, field.name) for field in SiteLimits._meta.fields if field.editable}
        if options["relax_business"]:
            for name in ("sender_limit", "recipient_limit", "recipient_cooldown_hours", "pair_cooldown_hours",
                         "invitation_max_sends", "invitation_limit", "invitation_cooldown_hours", "invitation_validity_days"):
                setattr(value, name, 0)
            value.sending_window_enabled = False
        value.full_clean()
        after = {field.name: getattr(value, field.name) for field in SiteLimits._meta.fields if field.editable}
        changed = created or before != after
        if changed:
            value.revision += 1
            value.save()
        rates = []
        for scope, (_, maximum, seconds, security) in REQUEST_LIMITS.items():
            rule, new = RequestLimit.objects.get_or_create(scope=scope, defaults={"maximum": maximum, "window_seconds": seconds})
            if options["relax_business"] and not security and rule.enabled:
                rule.enabled = False
                new = True
            rule.full_clean()
            if new:
                rule.revision += 1
                rule.save()
                rates.append({"scope": scope, "enabled": rule.enabled})
        if changed or rates:
            OperatorAudit.objects.create(action="configure_site_limits", object_id="global", reason=reason,
                before=before, after={"policy": after, "request_limits": rates})
            wake_policy_deferrals()
        self.stdout.write("Runtime policy ready; gift credits, opt-outs, delivery history and provider modes unchanged.")
