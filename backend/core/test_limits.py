from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import tests as legacy
from .demo_limits import reset_demo_limits
from .models import DemoLimitReset, OperatorAudit, Order, RecipientState
from .privacy import digest
from .services import APIError


class DailyLimitsTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    preview = legacy.APITestCase.preview
    order = legacy.APITestCase.order

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate()

    def test_five_orders_then_sixth_rejected_even_after_cache_loss(self):
        for index in range(5):
            self.assertEqual(self.order(recipient=f"0990123456{index}").status_code, 200)
        cache.clear()
        self.assertEqual(self.order(recipient="09901234569").status_code, 429)
        Order.objects.update(created_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.order(recipient="09901234569").status_code, 200)

    def test_global_recipient_window_is_24_hours_across_senders(self):
        RecipientState.objects.create(phone_hash=digest("09901234567"), last_sent_at=timezone.now()-timedelta(hours=23))
        self.assertEqual(self.order().status_code, 409)
        RecipientState.objects.update(last_sent_at=timezone.now()-timedelta(hours=25))
        self.assertEqual(self.order().status_code, 200)

    def test_pair_window_opens_exactly_after_24_hours(self):
        old = self.order().json()
        fixed = timezone.now()
        Order.objects.filter(pk=old["id"]).update(status="delivered_demo", updated_at=fixed-timedelta(hours=24)+timedelta(seconds=1))
        cache.clear()
        with patch("core.services.timezone.now", return_value=fixed):
            self.assertEqual(self.order().status_code, 409)
        Order.objects.filter(pk=old["id"]).update(updated_at=fixed-timedelta(hours=24, seconds=1))
        with patch("core.services.timezone.now", return_value=fixed):
            self.assertEqual(self.order().status_code, 200)


@override_settings(DEMO_TEST_TOOLS_ENABLED=True, DEMO_MODE=True, SMS_BACKEND="console",
                   PAYMENT_BACKEND="demo", PROVIDER_NETWORK_MODE="disabled", LIVE_PROVIDERS_ENABLED=False)
class DemoLimitToolTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    preview = legacy.APITestCase.preview
    order = legacy.APITestCase.order

    def setUp(self):
        DailyLimitsTests.setUp(self)
        self.actor = get_user_model().objects.create_superuser(username="test-limit-operator", password=None)
        self.admin_client = Client()
        self.admin_client.force_login(self.actor)
        self.url = reverse("admin:core_account_test_limits")
        self.payload = {"sender_phone": "۰۹۱۲۳۴۵۶۷۸۹", "recipient_phone": "٠٩٩٠١٢٣٤٥٦٧", "reason": "تکرار سناریوی آزمایشی"}

    def reset(self):
        return reset_demo_limits(self.actor, "09123456789", "09901234567", "تکرار سناریوی آزمایشی")

    def delivered(self):
        order = self.order().json()
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f"/orders/{order['id']}/pay-demo")
        return Order.objects.get(pk=order["id"])

    def test_reset_reopens_selected_pair_and_payment_without_rewriting_history(self):
        old = self.delivered()
        self.assertEqual(self.order().status_code, 409)
        snapshot = Order.objects.values().get(pk=old.pk)
        from .models import FinancialEvent, PaymentAttempt, MessageDelivery
        money = (list(FinancialEvent.objects.values()), list(PaymentAttempt.objects.values()), list(MessageDelivery.objects.values()))
        reset = self.reset()
        cache.clear()
        self.assertEqual(Order.objects.values().get(pk=old.pk), snapshot)
        self.assertEqual(money, (list(FinancialEvent.objects.values()), list(PaymentAttempt.objects.values()), list(MessageDelivery.objects.values())))
        fresh = self.order().json()
        self.assertIn("id", fresh)
        with self.captureOnCommitCallbacks(execute=True):
            paid = self.post(f"/orders/{fresh['id']}/pay-demo")
        self.assertEqual(paid.status_code, 200, paid.content)
        self.assertEqual(Order.objects.get(pk=fresh["id"]).status, "delivered_demo")
        self.assertEqual(self.order().status_code, 409)
        self.assertEqual(OperatorAudit.objects.get(action="reset_demo_limits").object_id, str(reset.pk))

    def test_recipient_reset_does_not_clear_another_senders_pair_limit(self):
        other_client = Client()
        other = self.authenticate("09901234560", other_client)
        previous = self.order(client=other_client).json()
        Order.objects.filter(pk=previous["id"]).update(status="delivered_demo")
        RecipientState.objects.update(last_sent_at=timezone.now())
        self.reset()
        self.assertEqual(self.order(client=other_client).status_code, 409)
        self.assertFalse(DemoLimitReset.objects.filter(sender=other).exists())
        self.assertEqual(self.order().status_code, 200)

    def test_reset_reopens_sender_quota_and_only_selected_global_recipient(self):
        for index in range(5):
            self.order(recipient=f"0990123456{index}")
        RecipientState.objects.create(phone_hash=digest("09901234568"), last_sent_at=timezone.now())
        self.assertEqual(self.order(recipient="09901234567").status_code, 429)
        self.reset()
        self.assertEqual(self.order(recipient="09901234567").status_code, 200)
        self.assertEqual(self.order(recipient="09901234568").status_code, 409)

    def test_reset_preserves_optout_suspension_self_and_unresolved_reservations(self):
        RecipientState.objects.create(phone_hash=digest("09901234567"), blocked=True)
        with self.assertRaises(APIError):
            self.reset()
        RecipientState.objects.update(blocked=False)
        self.user.account.suspended = True
        self.user.account.save()
        with self.assertRaises(APIError):
            self.reset()
        self.user.account.suspended = False
        self.user.account.save()
        with self.assertRaises(APIError):
            reset_demo_limits(self.actor, "09123456789", "09123456789", "تست شماره خودم")
        self.order()
        with self.assertRaises(APIError):
            self.reset()
        self.assertEqual(DemoLimitReset.objects.count(), 0)

    def test_reset_does_not_change_otp_budget_or_requirements(self):
        from .models import Account, OTPChallenge, SpendBudget, SpendReservation
        before = (list(OTPChallenge.objects.values()), list(SpendBudget.objects.values()), list(SpendReservation.objects.values()), list(Account.objects.values("free_sends_remaining")))
        self.reset()
        after = (list(OTPChallenge.objects.values()), list(SpendBudget.objects.values()), list(SpendReservation.objects.values()), list(Account.objects.values("free_sends_remaining")))
        self.assertEqual(before, after)
        anonymous = Client()
        anonymous.get("/api/v1/bootstrap")
        self.assertEqual(self.order(client=anonymous).status_code, 401)

    def test_get_renders_form_but_never_resets(self):
        response = self.admin_client.get(self.url)
        self.assertContains(response, "ریست محدودیت برای تست")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "data-normalize-digits")
        self.assertContains(response, "/static/admin/js/begamnagam-demo-limits.js")
        self.assertContains(self.admin_client.get(reverse("admin:core_account_changelist")), self.url)
        with override_settings(DEMO_TEST_TOOLS_ENABLED=False):
            self.assertNotContains(self.admin_client.get(reverse("admin:core_account_changelist")), self.url)
        self.assertEqual(DemoLimitReset.objects.count(), 0)

    def test_post_normalizes_digits_and_records_one_audited_reset(self):
        response = self.admin_client.post(self.url, self.payload)
        self.assertRedirects(response, self.url)
        reset = DemoLimitReset.objects.get()
        self.assertEqual(reset.recipient_hash, digest("09901234567"))
        self.assertEqual(reset.sender, self.user)
        audit = OperatorAudit.objects.get(action="reset_demo_limits")
        self.assertEqual(audit.actor, self.actor)
        self.assertNotIn("09901234567", str(audit.after))

    def test_invalid_form_reason_or_unknown_sender_cannot_reset(self):
        for changes in [{"sender_phone": "123"}, {"sender_phone": "09901234560"}, {"reason": ""}]:
            response = self.admin_client.post(self.url, {**self.payload, **changes})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(DemoLimitReset.objects.count(), 0)

    def test_staff_requires_explicit_permission_and_post_requires_csrf(self):
        staff = get_user_model().objects.create_user(username="limited-staff", is_staff=True)
        self.admin_client.force_login(staff)
        self.assertEqual(self.admin_client.post(self.url, self.payload).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="reset_demo_limits"))
        self.assertEqual(self.admin_client.get(self.url).status_code, 200)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(staff)
        self.assertEqual(csrf_client.post(self.url, self.payload).status_code, 403)
        self.assertEqual(DemoLimitReset.objects.count(), 0)

    def test_reset_is_unavailable_and_ignored_outside_isolated_demo(self):
        self.delivered()
        self.reset()
        for changes in [{"DEMO_TEST_TOOLS_ENABLED": False}, {"DEMO_MODE": False},
                        {"PAYMENT_BACKEND": "zarinpal"}, {"SMS_BACKEND": "kavenegar"},
                        {"PROVIDER_NETWORK_MODE": "local"}, {"LIVE_PROVIDERS_ENABLED": True}]:
            with self.subTest(changes=changes), override_settings(**changes):
                self.assertEqual(self.admin_client.get(self.url).status_code, 403)
                with self.assertRaises(APIError):
                    self.reset()
                self.assertEqual(self.order().status_code, 409)
        self.assertEqual(DemoLimitReset.objects.count(), 1)
