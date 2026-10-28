import io
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .limits import defaults, limit_scope, next_sending_time, policy, request_limit
from .models import Account, Invitation, InvitationSend, OperatorAudit, Order, RequestLimit, SiteLimits
from .privacy import digest, encrypt, mask
from .services import APIError, limited
from . import tests as legacy


class RuntimeLimitsTests(TestCase):
    post, preview = legacy.APITestCase.post, legacy.APITestCase.preview

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.user = get_user_model().objects.create_user(username="limits-fixture")
        Account.objects.create(user=self.user, phone_hash=digest("09123456789"),
            phone_cipher=encrypt("09123456789"), phone_masked=mask("09123456789"))
        self.client.force_login(self.user)
        self.client.get("/api/v1/bootstrap")

    def configure(self, **changes):
        value = defaults()
        for name, data in changes.items():
            setattr(value, name, data)
        value.full_clean()
        value.save()
        return value

    def order(self, recipient="09901234567"):
        quote = self.preview(category="appreciation", text="تشکر از تو")
        return self.post("/orders", {"preview_id": quote["preview_id"], "recipient_phone": recipient,
                                   "consent": True, "terms_version": quote["terms_version"]},
                         HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def test_zero_caps_allow_repeated_target_without_refilling_three_gifts(self):
        self.configure(sender_limit=0, recipient_limit=0, recipient_cooldown_hours=0, pair_cooldown_hours=0)
        for _ in range(3):
            result = self.order()
            self.assertEqual(result.status_code, 200, result.content)
            Order.objects.filter(pk=result.json()["id"]).update(status="delivered_demo")
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 0)
        self.assertEqual(Order.objects.filter(is_free=True).count(), 3)

    def test_sender_and_recipient_counts_apply_updated_admin_policy(self):
        self.configure(sender_limit=0, recipient_limit=2, recipient_window_hours=1,
                       recipient_cooldown_hours=0, pair_cooldown_hours=0)
        for _ in range(2):
            result = self.order()
            self.assertEqual(result.status_code, 200, result.content)
            Order.objects.filter(pk=result.json()["id"]).update(status="delivered_demo")
        result = self.order()
        self.assertEqual(result.json()["error"]["code"], "recipient_unavailable")
        SiteLimits.objects.filter(pk=1).update(recipient_limit=3, sender_limit=2)
        result = self.order("09901234568")
        self.assertEqual(result.json()["error"]["code"], "daily_limit")
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 1)

    def test_zero_sender_window_disables_cap_and_reenable_uses_existing_history(self):
        self.configure(sender_limit=1, sender_window_hours=0, recipient_cooldown_hours=0, pair_cooldown_hours=0)
        first = self.order()
        self.assertEqual(first.status_code, 200, first.content)
        Order.objects.filter(pk=first.json()["id"]).update(status="delivered_demo", created_at=timezone.now()+timedelta(minutes=1))
        second = self.order("09901234568")
        self.assertEqual(second.status_code, 200, second.content)
        SiteLimits.objects.filter(pk=1).update(sender_window_hours=24)
        self.assertEqual(self.order("09901234569").json()["error"]["code"], "daily_limit")
        self.assertEqual(Order.objects.count(), 2)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 1)

    def test_zero_recipient_window_disables_count_but_not_recipient_opt_out(self):
        from .models import RecipientState
        self.configure(sender_limit=0, recipient_limit=1, recipient_window_hours=0,
                       recipient_cooldown_hours=0, pair_cooldown_hours=0)
        first = self.order()
        self.assertEqual(first.status_code, 200, first.content)
        Order.objects.filter(pk=first.json()["id"]).update(status="delivered_demo", updated_at=timezone.now()+timedelta(minutes=1))
        second = self.order()
        self.assertEqual(second.status_code, 200, second.content)
        Order.objects.filter(pk=second.json()["id"]).update(status="delivered_demo")
        RecipientState.objects.filter(phone_hash=digest("09901234567")).update(blocked=True)
        self.assertEqual(self.order().json()["error"]["code"], "recipient_unavailable")
        RecipientState.objects.filter(phone_hash=digest("09901234567")).update(blocked=False)
        SiteLimits.objects.filter(pk=1).update(recipient_window_hours=1)
        self.assertEqual(self.order().json()["error"]["code"], "recipient_unavailable")
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 1)

    def test_zero_clock_hours_mean_midnight_and_disabled_schedule_accepts_equal_bounds(self):
        self.configure(sending_window_enabled=True, sending_start_hour=22, sending_end_hour=0)
        now = timezone.localtime().replace(minute=0, second=0, microsecond=0)
        self.assertIsNone(next_sending_time(now.replace(hour=23)))
        self.assertEqual(next_sending_time(now.replace(hour=0)).hour, 22)
        SiteLimits.objects.filter(pk=1).update(sending_start_hour=0, sending_end_hour=21)
        self.assertIsNone(next_sending_time(now.replace(hour=0)))
        self.assertEqual(next_sending_time(now.replace(hour=21)).hour, 0)
        value = SiteLimits.objects.get(pk=1)
        value.sending_window_enabled=False;value.sending_start_hour=0;value.sending_end_hour=0
        value.full_clean();value.save()
        for hour in (0, 12, 23):
            self.assertIsNone(next_sending_time(now.replace(hour=hour)))
        value.sending_window_enabled=True
        with self.assertRaises(ValidationError):
            value.full_clean()

    def test_overnight_schedule_and_request_snapshot(self):
        self.configure(sending_window_enabled=True, sending_start_hour=22, sending_end_hour=8)
        now = timezone.localtime().replace(hour=23)
        self.assertIsNone(next_sending_time(now))
        self.assertIsNone(next_sending_time(now.replace(hour=7)))
        self.assertEqual(next_sending_time(now.replace(hour=8)).hour, 22)
        with limit_scope():
            self.assertTrue(policy().sending_window_enabled)
            SiteLimits.objects.filter(pk=1).update(sending_window_enabled=False)
            self.assertTrue(policy().sending_window_enabled)
        self.assertIsNone(next_sending_time(now.replace(hour=8)))

    def test_request_rule_changes_take_effect_and_security_rules_stay_positive(self):
        rule = RequestLimit.objects.create(scope="orders", maximum=1, window_seconds=600)
        limited("orders", "fixture", 10, 60)
        with self.assertRaises(APIError):
            limited("orders", "fixture", 10, 60)
        rule.enabled = False
        rule.save()
        limited("orders", "fixture", 10, 60)
        with self.assertRaises(ValidationError):
            RequestLimit(scope="otp-verify-session", enabled=False).full_clean()

    def test_invitation_cap_can_exceed_three_or_be_unlimited(self):
        from .invitations import request_invitation, serialize
        self.configure(invitation_max_sends=4, invitation_limit=0, invitation_cooldown_hours=0,
                       invitation_validity_days=0, recipient_cooldown_hours=0)
        with self.captureOnCommitCallbacks(execute=False):
            invitation = request_invitation(self.user, "09901234567", uuid.uuid4())
            for _ in range(3):
                InvitationSend.objects.filter(invitation=invitation).update(status="delivered")
                request_invitation(self.user, None, uuid.uuid4(), invitation.pk)
            self.assertEqual(invitation.sends.count(), 4)
            with self.assertRaises(APIError) as failure:
                request_invitation(self.user, None, uuid.uuid4(), invitation.pk)
            self.assertEqual(failure.exception.code, "invitation_limit")
            SiteLimits.objects.filter(pk=1).update(invitation_max_sends=0)
            InvitationSend.objects.filter(invitation=invitation).update(status="delivered")
            request_invitation(self.user, None, uuid.uuid4(), invitation.pk)
            result = serialize(Invitation.objects.prefetch_related("sends").get(pk=invitation.pk))
            self.assertEqual(result["send_count"], 5)
            self.assertIsNone(result["sends_remaining"])
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_zero_invitation_window_and_cooldown_disable_their_limits_without_reset(self):
        from .invitations import request_invitation, serialize
        self.configure(invitation_limit=1, invitation_window_hours=0, invitation_cooldown_hours=0)
        with self.captureOnCommitCallbacks(execute=False):
            invitation = request_invitation(self.user, "09901234567", uuid.uuid4())
            InvitationSend.objects.filter(invitation=invitation).update(status="delivered", created_at=timezone.now()+timedelta(minutes=1))
            self.assertTrue(serialize(invitation)["can_resend"])
            request_invitation(self.user, None, uuid.uuid4(), invitation.pk)
            InvitationSend.objects.filter(invitation=invitation).update(status="delivered")
            state = self.client.get("/api/v1/invitations").json()
            self.assertIsNone(state["daily_remaining"])
            self.assertIsNone(state["daily_limit"])
            self.assertEqual(state["window_hours"], 0)
            SiteLimits.objects.filter(pk=1).update(invitation_window_hours=24)
            self.assertEqual(self.client.get("/api/v1/invitations").json()["daily_remaining"], 0)
            with self.assertRaises(APIError) as failure:
                request_invitation(self.user, None, uuid.uuid4(), invitation.pk)
            self.assertEqual(failure.exception.code, "invitation_daily_limit")
        self.assertEqual(invitation.sends.count(), 2)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    @override_settings(PAYMENT_BACKEND="disabled")
    def test_explicit_relaxation_is_idempotent_and_does_not_change_credits(self):
        for _ in range(2):
            call_command("configure_limits", relax_business=True, reason="User requested local restriction removal", stdout=io.StringIO())
        self.assertEqual(SiteLimits.objects.get().sender_limit, 0)
        self.assertFalse(SiteLimits.objects.get().sending_window_enabled)
        self.assertFalse(request_limit("otp-phone").enabled)
        self.assertTrue(request_limit("otp-verify-session").enabled)
        self.assertEqual(OperatorAudit.objects.filter(action="configure_site_limits").count(), 1)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_admin_requires_permission_reason_and_current_revision(self):
        value = self.configure()
        staff = get_user_model().objects.create_user(username="limits-staff", is_staff=True)
        client = Client()
        client.force_login(staff)
        url = reverse("admin:core_sitelimits_change", args=[1])
        self.assertEqual(client.get(url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="manage_site_limits"))
        result = client.get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Referrer-Policy"], "same-origin")
        payload = {field.name: getattr(value, field.name) for field in SiteLimits._meta.fields if field.editable}
        # HTML unchecked checkboxes are absent from a submitted form.
        payload = {key: data for key, data in payload.items() if type(data) is not bool or data}
        payload.update(source_revision=value.revision, reason="Change sending cap", sender_limit=9,
                       sender_window_hours=0, recipient_window_hours=0, invitation_window_hours=0, _save="Save")
        self.assertEqual(client.post(url, payload).status_code, 302)
        self.assertEqual(SiteLimits.objects.get().sender_limit, 9)
        self.assertEqual(SiteLimits.objects.get().sender_window_hours, 0)
        self.assertEqual(OperatorAudit.objects.get(action="update_site_limits").actor_id, staff.pk)
        self.assertContains(client.post(url, payload), "توسط مدیر دیگری")
        self.assertEqual(OperatorAudit.objects.filter(action="update_site_limits").count(), 1)

    def test_invalid_and_unapproved_budget_settings_are_rejected(self):
        for changes in ({"sender_window_hours": -1}, {"recipient_window_hours": -1}, {"invitation_window_hours": -1},
                        {"otp_max_attempts": 0}, {"otp_validity_seconds": 0}, {"preview_validity_seconds": 0},
                        {"sending_start_hour": 25}, {"sending_end_hour": 25}, {"provider_budget_unlimited": True}):
            value = defaults()
            for key, data in changes.items():
                setattr(value, key, data)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                value.full_clean()

    @override_settings(DEMO_MODE=False, OTP_BACKEND="kavenegar", SMS_BACKEND="kavenegar", PAYMENT_BACKEND="disabled",
        LIVE_PROVIDERS_ENABLED=True, PROVIDER_NETWORK_MODE="external", PROVIDER_ENVIRONMENT="live",
        SMS_RECIPIENT_POLICY="all", TERMS_VERSION="limits-verified", SENDING_WINDOW_ENABLED=False,
        PROVIDER_DAILY_BUDGET_RIAL=100000, SMS_MAX_COST_RIAL=20000, OTP_MAX_COST_RIAL=10000)
    def test_worker_rechecks_updated_receiver_policy_without_duplicate_submission(self):
        from .models import MessageDelivery, Outbox, SafetyControl
        from .provider_delivery import submit_delivery
        from .providers.kavenegar import SMSResult
        from .limits import wake_policy_deferrals
        self.configure(sender_limit=0, recipient_limit=0, recipient_cooldown_hours=0, pair_cooldown_hours=0)
        SafetyControl.objects.create(pk=1, halted=False)
        response = self.order()
        self.assertEqual(response.status_code, 200, response.content)
        first = response.json()
        Order.objects.filter(pk=first["id"]).update(status="delivered", updated_at=timezone.now())
        response = self.order()
        self.assertEqual(response.status_code, 200, response.content)
        second = response.json()
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.post(f'/orders/{second["id"]}/confirm-free').status_code, 200)
        event = Outbox.objects.get(order_id=second["id"])
        SiteLimits.objects.filter(pk=1).update(recipient_limit=1)
        with patch("core.provider_delivery.Kavenegar.submit", return_value=SMSResult("accepted", "fixture", 1000)) as provider:
            submit_delivery(event.pk)
            provider.assert_not_called()
            event.refresh_from_db()
            self.assertEqual((event.state, event.last_error_code), ("pending", "recipient_cooldown"))
            SiteLimits.objects.filter(pk=1).update(recipient_window_hours=0)
            wake_policy_deferrals()
            submit_delivery(event.pk)
            submit_delivery(event.pk)
            self.assertEqual(provider.call_count, 1)
        self.assertEqual(MessageDelivery.objects.get(order_id=second["id"]).status, "accepted")
