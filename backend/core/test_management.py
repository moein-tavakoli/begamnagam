import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import models as m
from .limit_services import editable_values
from .limits import defaults
from .management_api import RESOURCES
from .privacy import digest, encrypt, mask


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_superuser("management-admin", password="test-only-password")
        self.staff = get_user_model().objects.create_user("limited-staff", is_staff=True, password="test-only-password")
        self.member = get_user_model().objects.create_user("phone-member", password="test-only-password")
        self.phone = "09123456789"
        self.account = m.Account.objects.create(user=self.member, phone_hash=digest(self.phone), phone_cipher=encrypt(self.phone), phone_masked=mask(self.phone))

    def post(self, path, data=None, client=None):
        return (client or self.client).post("/api/v1/manage/" + path, json.dumps(data or {}), content_type="application/json")

    def permit(self, *codenames):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="core", codename__in=codenames))
        self.client.force_login(self.staff)

    def preview(self):
        return m.Preview.objects.create(owner=self.member, session_key="private-session", category="appreciation", text="private-unreviewed-input",
            generated_body="reviewed-case-text", price_toman=2000, moderation_mode="template", expires_at=timezone.now()+timedelta(minutes=5))

    def test_login_only_accepts_active_staff_and_does_not_require_phone_account(self):
        self.assertFalse(self.client.get("/api/v1/manage/session").json()["authenticated"])
        for username in ("unknown", "phone-member"):
            response = self.post("login", {"username": username, "password": "test-only-password"})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["error"]["code"], "invalid_credentials")
        response = self.post("login", {"username": "management-admin", "password": "test-only-password"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["authenticated"])
        self.assertFalse(hasattr(self.admin, "account"))
        self.assertEqual(self.client.get("/api/v1/manage/dashboard").status_code, 200)
        # Staff authentication never masquerades as product phone authentication.
        self.assertFalse(self.client.get("/api/v1/bootstrap").json()["authenticated"])
        self.assertEqual(self.post("logout").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/manage/dashboard").status_code, 401)

    def test_login_and_all_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("login", {"username": "management-admin", "password": "test-only-password"}, client).status_code, 403)
        client.get("/api/v1/manage/session")
        response = client.post("/api/v1/manage/login", json.dumps({"username": "management-admin", "password": "test-only-password"}),
            content_type="application/json", HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.post("actions", {"action": "halt", "reason": "test reason"}, client).status_code, 403)
        self.assertEqual(self.post("logout", client=client).status_code, 403)

    def test_login_throttle_remains_protected(self):
        m.RequestLimit.objects.create(scope="manage-login-ip", maximum=1, window_seconds=600)
        self.assertEqual(self.post("login", {"username": "unknown", "password": "wrong"}).status_code, 401)
        self.assertEqual(self.post("login", {"username": "unknown", "password": "wrong"}).status_code, 429)

    def test_members_and_staff_without_permissions_cannot_read_or_write(self):
        for user, expected in ((None, 401), (self.member, 403), (self.staff, 403)):
            self.client.logout()
            if user:
                self.client.force_login(user)
            self.assertEqual(self.post("records/accounts").status_code, expected)
            self.assertEqual(self.client.get("/api/v1/manage/limits").status_code, expected)
            self.assertEqual(self.post("actions", {"action": "suspend", "object_id": str(self.account.pk), "reason": "test reason"}).status_code, expected)
        self.account.refresh_from_db()
        self.assertFalse(self.account.suspended)

    def test_resource_permissions_are_independent_and_output_is_masked(self):
        self.permit("view_account")
        context = self.client.get("/api/v1/manage/session").json()
        self.assertEqual([r["key"] for r in context["resources"]], ["accounts"])
        response = self.post("records/accounts", {"query": self.phone})
        self.assertEqual(response.status_code, 200)
        row = response.json()["rows"][0]
        self.assertEqual(row["phone_masked"], mask(self.phone))
        for secret in (self.phone, digest(self.phone), encrypt(self.phone), "phone_cipher", "phone_hash", "username"):
            self.assertNotIn(secret, response.content.decode())
        self.assertEqual(self.post("records/orders").status_code, 403)
        self.assertEqual(self.post("records/not-a-model").status_code, 404)

    def test_all_resources_render_and_exclude_private_content(self):
        self.client.force_login(self.admin)
        preview = self.preview()
        order = m.Order.objects.create(owner=self.member, preview=preview, idempotency_key=uuid.uuid4(), recipient_hash=digest("09999999999"),
            recipient_cipher=encrypt("09999999999"), recipient_masked=mask("09999999999"), text="private-order-body", full_sms="private-full-sms", category="appreciation", amount_toman=2000)
        package = m.MessagePackage.objects.create(name='سه پیام', message_count=3, price_toman=10000, active=True)
        purchase = m.CreditPurchase.objects.create(owner=self.member, package=package, idempotency_key=uuid.uuid4(),
            package_name=package.name, message_count=3, amount_toman=10000, environment='demo', credited_at=timezone.now())
        m.CreditEntry.objects.create(account=self.account, purchase=purchase, kind='purchase', units=3, environment='demo')
        m.Outbox.objects.create(order=order, available_at=timezone.now())
        m.MessageDelivery.objects.create(order=order)
        m.ModerationAudit.objects.create(category="appreciation", outcome="allow", reason_code="approved", content_digest="private-digest")
        invitation = m.Invitation.objects.create(inviter=self.member, phone_hash=digest("09999999998"), phone_cipher=encrypt("09999999998"), phone_masked=mask("09999999998"))
        m.InvitationSend.objects.create(invitation=invitation, ordinal=1, idempotency_key=uuid.uuid4(), consent_version="v1", consent_at=timezone.now(), full_sms="private-invite-sms", provider="demo", available_at=timezone.now())
        payment = m.PaymentAttempt.objects.create(order=order, provider="demo", environment="demo", amount_toman=2000)
        m.Refund.objects.create(payment=payment, amount_toman=2000, reason_code="test")
        m.FinancialEvent.objects.create(payment=payment, kind="payment", amount_toman=2000)
        topup = m.WalletTopup.objects.create(owner=self.member, idempotency_key=uuid.uuid4(), amount_toman=10000,
            environment='sandbox', consent_at=timezone.now(), terms_version='wallet-credit-v1', credited_at=timezone.now())
        m.WalletEntry.objects.create(account=self.account, kind='topup', amount_toman=10000,
            balance_after_toman=10000, environment='sandbox', topup=topup)
        m.Account.objects.filter(pk=self.account.pk).update(demo_wallet_balance_toman=10000)
        m.SpendBudget.objects.create(day=timezone.localdate(), reserved_rial=100, limit_rial=1000)
        m.OperationalAlert.objects.create(code="test_alert", severity="warning")
        m.OperatorAudit.objects.create(actor=self.admin, action="test", reason="audit fixture")
        grant = m.RecipientGrant.objects.create(preview=preview, token_digest="private-grant", recipient_hash=digest("09999999999"))
        m.AbuseReport.objects.create(grant=grant, reason="other", details="private-report-details")
        for resource in RESOURCES:
            with self.subTest(resource=resource):
                response = self.post("records/" + resource)
                self.assertEqual(response.status_code, 200, response.content)
                self.assertGreater(response.json()["total"], 0)
                self.assertTrue(response.json()["rows"][0]["record_id"])
                for private in ("private-order-body", "private-full-sms", "private-digest", "private-invite-sms", "private-report-details", "private-grant", "09999999999"):
                    self.assertNotIn(private, response.content.decode())

    def test_pagination_and_input_bounds(self):
        self.client.force_login(self.admin)
        m.OperationalAlert.objects.bulk_create([m.OperationalAlert(code=f"test_{i}", severity="warning") for i in range(26)])
        first, second = self.post("records/alerts").json(), self.post("records/alerts", {"page": 2}).json()
        self.assertEqual((len(first["rows"]), len(second["rows"])), (25, 1))
        self.assertNotEqual(first["rows"][0]["record_id"], second["rows"][0]["record_id"])
        self.assertIn(["sent", "sent"], self.post("records/outbox").json()["statuses"])
        self.assertEqual(self.post("records/reports").json()["statuses"], [["open", "open"], ["closed", "closed"]])
        for data in ({"page": 0}, {"page": True}, {"page": "1"}, {"query": "x"*101}, {"query": []}):
            self.assertEqual(self.post("records/accounts", data).status_code, 422)

    def test_audited_limits_are_versioned_and_not_arbitrary_model_writes(self):
        self.permit("manage_site_limits")
        current = self.client.get("/api/v1/manage/limits").json()
        response = self.post("limits", {"revision": current["revision"], "reason": "Change sender limit", "values": {"sender_limit": 9}})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["values"]["sender_limit"], 9)
        revision = response.json()["revision"]
        self.assertEqual(m.OperatorAudit.objects.get(action="update_site_limits").after["sender_limit"], 9)
        self.assertEqual(self.post("limits", {"revision": current["revision"], "reason": "Stale form", "values": {"sender_limit": 8}}).status_code, 409)
        for values in ({"sender_limit": True}, {"otp_max_attempts": 0}, {"is_superuser": True}, {"sender_window_hours": -1}):
            self.assertEqual(self.post("limits", {"revision": revision, "reason": "Invalid change", "values": values}).status_code, 422)
        self.assertEqual(self.post("limits", {"revision": revision, "values": {"sender_limit": 8}}).status_code, 422)
        self.assertEqual(self.post("request-limits/manage-login-ip", {"revision": 0, "reason": "Disable protection", "values": {"enabled": False}}).status_code, 422)
        self.assertEqual(self.post("request-limits/manage-login-ip", {"revision": 0, "reason": "Adjust login count", "values": {"maximum": 25}}).status_code, 200)
        self.assertEqual(m.Account.objects.get(pk=self.account.pk).free_sends_remaining, 3)

    def test_zero_hour_settings_save_through_manage_with_audit_and_keep_counts(self):
        self.permit("manage_site_limits")
        current = self.client.get("/api/v1/manage/limits").json()
        hours = {name: 0 for name in ("sender_window_hours", "recipient_window_hours", "invitation_window_hours",
            "recipient_cooldown_hours", "pair_cooldown_hours", "invitation_cooldown_hours",
            "sending_start_hour", "sending_end_hour")}
        response = self.post("limits", {"revision": current["revision"], "reason": "Disable selected hourly restrictions",
            "values": {**hours, "sending_window_enabled": False}})
        self.assertEqual(response.status_code, 200, response.content)
        saved = self.client.get("/api/v1/manage/limits").json()
        for name in hours:
            self.assertEqual(saved["values"][name], 0)
        for name in ("sender_limit", "recipient_limit", "invitation_limit"):
            self.assertEqual(saved["values"][name], current["values"][name])
        audit = m.OperatorAudit.objects.get(action="update_site_limits")
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertEqual(audit.before["sender_window_hours"], 24)
        self.assertEqual(audit.after["sender_window_hours"], 0)
        fields = {field["key"]: field for section in saved["sections"] for field in section["fields"]}
        self.assertIn("۰ = غیرفعال", fields["sender_window_hours"]["help"])
        self.assertEqual(m.Account.objects.get(pk=self.account.pk).free_sends_remaining, 3)

    def test_actions_require_scoped_permissions_and_reason_and_cannot_replay_sms(self):
        self.permit("suspend_account")
        values = {"action": "suspend", "object_id": str(self.account.pk), "reason": "Review complaint"}
        self.assertEqual(self.post("actions", {**values, "reason": ""}).status_code, 400)
        self.assertEqual(self.post("actions", values).status_code, 200)
        self.account.refresh_from_db()
        self.assertTrue(self.account.suspended)
        self.assertEqual(m.OperatorAudit.objects.get(action="suspend").object_id, str(self.account.pk))
        for action in ("halt", "tone", "resend", "reset_credits", "activate_paid"):
            self.assertIn(self.post("actions", {**values, "action": action, "value": True}).status_code, (403,))
        self.assertEqual(self.post("actions", {**values, "object_id": "missing"}).status_code, 400)

    def test_report_review_is_explicit_and_audited(self):
        preview = self.preview()
        grant = m.RecipientGrant.objects.create(preview=preview, token_digest="case-token", recipient_hash=digest(self.phone))
        report = m.AbuseReport.objects.create(grant=grant, reason="other", details="case details")
        path = f"reports/{report.pk}/review"
        self.client.force_login(self.staff)
        self.assertEqual(self.post(path, {"reason": "Investigate case"}).status_code, 403)
        self.permit("view_abusereport")
        self.assertNotIn("case details", self.post("records/reports").content.decode())
        self.assertEqual(self.post(path, {}).status_code, 422)
        response = self.post(path, {"reason": "Investigate case"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reviewed_text"], "reviewed-case-text")
        self.assertEqual(response.json()["details"], "case details")
        self.assertEqual(m.OperatorAudit.objects.get(action="report_viewed").object_id, str(report.pk))

    def test_inactive_staff_session_denied_and_response_not_cacheable(self):
        self.client.force_login(self.admin)
        response = self.post("records/accounts")
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertIn("noindex", response["X-Robots-Tag"])
        self.admin.is_active = False
        self.admin.save(update_fields=["is_active"])
        self.assertEqual(self.client.get("/api/v1/manage/dashboard").status_code, 401)
