import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import tests as legacy
from .account_options import update_account_options
from .demo_limits import unlimited_demo_sends
from .models import Account, OperatorAudit, Order, Preview, RecipientState
from .moderation import DIRECT_TEMPLATES, TEMPLATES, ModerationRejected, RewriteUnavailable, moderate, rewrite
from .privacy import digest
from .services import APIError


@override_settings(DEMO_TEST_TOOLS_ENABLED=True, DEMO_MODE=True, SMS_BACKEND="console",
                   PAYMENT_BACKEND="demo", PROVIDER_NETWORK_MODE="disabled", LIVE_PROVIDERS_ENABLED=False)
class AccountOptionTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    preview = legacy.APITestCase.preview
    order = legacy.APITestCase.order

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate()
        self.actor = get_user_model().objects.create_superuser(username="account-options-operator", password=None)
        self.admin_client = Client()
        self.admin_client.force_login(self.actor)
        self.account = Account.objects.get(user=self.user)
        self.url = reverse("admin:core_account_change", args=[self.account.pk])

    def options(self, **changes):
        return update_account_options(self.actor, self.account.pk, changes, "تست تنظیمات حساب")

    def delivered(self):
        response = self.order()
        self.assertEqual(response.status_code, 200, response.content)
        with self.captureOnCommitCallbacks(execute=True):
            paid = self.post(f"/orders/{response.json()['id']}/pay-demo")
        self.assertEqual(paid.status_code, 200, paid.content)
        self.assertEqual(Order.objects.get(pk=paid.json()["id"]).status, "delivered_demo")
        return paid.json()

    def test_unlimited_sender_repeats_delivery_beyond_daily_minute_and_preview_quotas(self):
        self.assertFalse(unlimited_demo_sends(self.user))
        self.options(unlimited_demo_sends=True)
        # Cross all three previous account-bound ceilings without clearing Redis.
        for _ in range(22):
            self.delivered()
        self.assertEqual(Order.objects.filter(owner=self.user, status="delivered_demo").count(), 22)
        self.assertIsNotNone(RecipientState.objects.get(phone_hash=digest("09901234567")).last_sent_at)
        other = Client()
        self.authenticate("09901234560", other)
        self.assertEqual(self.order(client=other).status_code, 409)
        self.options(unlimited_demo_sends=False)
        self.assertEqual(self.order().status_code, 429)

    def test_enabling_is_not_a_global_reset_and_disabling_restores_cooldown(self):
        self.options(unlimited_demo_sends=True)
        self.delivered()
        self.delivered()
        self.options(unlimited_demo_sends=False)
        self.assertEqual(self.order().status_code, 409)

    def test_bypass_preserves_optout_self_send_suspension_and_open_reservation(self):
        self.options(unlimited_demo_sends=True)
        self.assertNotEqual(self.order(recipient="09123456789").status_code, 200)
        state = RecipientState.objects.create(phone_hash=digest("09901234567"), blocked=True)
        self.assertEqual(self.order().status_code, 409)
        state.blocked = False
        state.save()
        first = self.order()
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.order().status_code, 409)
        state.blocked = True
        state.save()
        self.assertEqual(self.post(f"/orders/{first.json()['id']}/pay-demo").status_code, 409)
        Account.objects.filter(pk=self.account.pk).update(suspended=True)
        self.assertFalse(unlimited_demo_sends(self.user))
        self.assertEqual(self.order(recipient="09901234568").status_code, 403)

    def test_bypass_is_ignored_and_cannot_be_enabled_outside_isolated_demo(self):
        self.options(unlimited_demo_sends=True)
        for change in [{"DEMO_TEST_TOOLS_ENABLED": False}, {"DEMO_MODE": False},
                       {"SMS_BACKEND": "kavenegar"}, {"PAYMENT_BACKEND": "zarinpal"},
                       {"PROVIDER_NETWORK_MODE": "local"}, {"LIVE_PROVIDERS_ENABLED": True}]:
            with self.subTest(change=change), override_settings(**change):
                self.assertFalse(unlimited_demo_sends(self.user))
                with self.assertRaises(APIError):
                    self.options(unlimited_demo_sends=True)
        with override_settings(DEMO_TEST_TOOLS_ENABLED=False):
            self.options(unlimited_demo_sends=False)
        self.assertFalse(unlimited_demo_sends(self.user))

    def test_bypass_does_not_increase_free_credit_or_skip_otp_limits(self):
        self.options(unlimited_demo_sends=True)
        self.account.refresh_from_db()
        self.assertEqual(self.account.free_sends_remaining, 0)
        # Authentication already used one challenge for this phone.
        self.assertEqual(self.post("/auth/request-otp", {"phone": "09123456789"}).status_code, 200)
        self.assertEqual(self.post("/auth/request-otp", {"phone": "09123456789"}).status_code, 200)
        self.assertEqual(self.post("/auth/request-otp", {"phone": "09123456789"}).status_code, 429)

    def test_database_defaults_support_previous_release_account_inserts(self):
        old_user = get_user_model().objects.create_user(username="previous-release-account")
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO core_account (user_id, phone_hash, phone_cipher, phone_masked, "
                "suspended, free_sends_remaining, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [old_user.pk, digest("09901234561"), self.account.phone_cipher, "099•••••561", False, 3, timezone.now()])
        account = Account.objects.get(user=old_user)
        self.assertFalse(account.unlimited_demo_sends)
        self.assertFalse(account.direct_message_tone)

    def test_admin_form_audits_changes_and_never_edits_balances_or_private_identity(self):
        page = self.admin_client.get(self.url)
        self.assertContains(page, 'name="unlimited_demo_sends"')
        self.assertContains(page, 'name="direct_message_tone"')
        invalid = self.admin_client.post(self.url, {"unlimited_demo_sends": "on"})
        self.assertEqual(invalid.status_code, 200)
        self.assertContains(invalid, "دلیل تغییر را")
        self.assertFalse(unlimited_demo_sends(self.user))
        response = self.admin_client.post(self.url, {"unlimited_demo_sends": "on", "direct_message_tone": "on",
            "settings_reason": "تست شخصی با ثبت دلیل", "free_sends_remaining": 3, "phone_hash": "tampered"})
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertTrue(self.account.direct_message_tone)
        self.assertTrue(self.account.unlimited_demo_sends)
        self.assertEqual(self.account.free_sends_remaining, 0)
        self.assertEqual(self.account.phone_hash, digest("09123456789"))
        audit = OperatorAudit.objects.get(action="account_send_options")
        self.assertEqual(audit.actor, self.actor)
        self.assertEqual(audit.before, {"unlimited_demo_sends": False, "direct_message_tone": False})
        self.assertEqual(audit.after, {"unlimited_demo_sends": True, "direct_message_tone": True})
        self.assertNotIn("09123456789", str(audit.after))

    def test_admin_requires_scoped_permissions_and_csrf(self):
        staff = get_user_model().objects.create_user(username="tone-only", is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename="view_account"))
        self.admin_client.force_login(staff)
        self.assertEqual(self.admin_client.post(self.url, {"direct_message_tone": "on"}).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="manage_message_tone"))
        page = self.admin_client.get(self.url)
        self.assertNotContains(page, 'name="unlimited_demo_sends"')
        self.assertContains(page, 'name="direct_message_tone"')
        response = self.admin_client.post(self.url, {"direct_message_tone": "on", "unlimited_demo_sends": "on",
                                                   "settings_reason": "تغییر لحن با مجوز مستقل"})
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertTrue(self.account.direct_message_tone)
        self.assertFalse(self.account.unlimited_demo_sends)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.actor)
        self.assertEqual(csrf.post(self.url, {"unlimited_demo_sends": "on"}).status_code, 403)
        with override_settings(DEMO_TEST_TOOLS_ENABLED=False):
            self.admin_client.force_login(self.actor)
            invalid = self.admin_client.post(self.url, {"unlimited_demo_sends": "on", "settings_reason": "تست خارج محیط مجاز"})
            self.assertEqual(invalid.status_code, 200)
            self.assertContains(invalid, "این گزینه فقط")

    @override_settings(APP_BASE_URL="https://begamnagam.ir")
    def test_global_tone_replaces_account_flag_and_is_frozen_through_delivery(self):
        from .models import AIConfiguration
        self.options(direct_message_tone=True)
        AIConfiguration.objects.create(tone_polite_enabled=False, tone_firm_enabled=True)
        for category in DIRECT_TEMPLATES:
            cache.clear()  # This case verifies tone snapshots, not request quotas.
            preview = self.post("/messages/preview", {"category": category, "text": "یک پیام محترمانه",
                "recipient_phone": "09901234567", "message_tone": "gentle"})
            self.assertEqual(preview.status_code, 422)
            preview = self.post("/messages/preview", {"category": category, "text": "یک پیام محترمانه",
                "recipient_phone": "09901234567"})
            self.assertEqual(preview.status_code, 200, preview.content)
            self.assertEqual(preview.json()["message_tone"], "firm")
            self.assertIn(preview.json()["rewritten_text"], DIRECT_TEMPLATES[category])
            self.assertLessEqual(preview.json()["sms_segments"], 3)
        quote = self.preview()
        self.options(direct_message_tone=False)
        AIConfiguration.objects.update(tone_polite_enabled=True, tone_firm_enabled=False)
        order = self.order(preview=quote).json()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post(f"/orders/{order['id']}/pay-demo").status_code, 200)
        saved = Order.objects.get(pk=order["id"])
        self.assertEqual(saved.status, "delivered_demo")
        self.assertEqual(saved.text, quote["rewritten_text"])
        self.assertEqual(saved.full_sms, Preview.objects.get(pk=quote["preview_id"]).full_sms)
        gentle = self.post("/messages/preview", {"category": "body", "text": "بوی بدن", "direct_message_tone": True})
        self.assertEqual(gentle.status_code, 422)
        gentle = self.post("/messages/preview", {"category": "body", "text": "بوی بدن"})
        self.assertEqual(gentle.json()["message_tone"], "polite")
        self.assertIn(gentle.json()["rewritten_text"], TEMPLATES["body"])


class DirectRewriteTests(TestCase):
    def test_both_pools_are_reviewed_but_unsafe_input_is_still_rejected(self):
        for category, texts in DIRECT_TEMPLATES.items():
            for text in texts:
                self.assertTrue(moderate(text))
                self.assertNotIn(text, TEMPLATES[category])
        for text in ["احمق", "شماره ۰۹۱۲۳۴۵۶۷۸۹", "https://private.invalid"]:
            with self.assertRaises(ModerationRejected):
                rewrite("body", text, direct=True)

    @override_settings(AI_MODE="ollama")
    def test_model_can_only_select_within_the_server_selected_tone(self):
        with patch("core.moderation.urllib.request.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = json.dumps({"response": '{"template_id":0}'}).encode()
            output, mode = rewrite("body", "بوی بدن", direct=True)
            self.assertEqual(output, DIRECT_TEMPLATES["body"][0])
            self.assertEqual(mode, "ollama_curated")
            prompt = json.loads(json.loads(mock.call_args.args[0].data)["prompt"])
            self.assertEqual(prompt["templates"], DIRECT_TEMPLATES["body"])
            for response in [{"template_id": True}, {"template_id": 1}, {"text": "متن آزاد"}]:
                mock.return_value.__enter__.return_value.read.return_value = json.dumps({"response": json.dumps(response)}).encode()
                with self.assertRaises(RewriteUnavailable):
                    rewrite("body", "بوی بدن", direct=True)
