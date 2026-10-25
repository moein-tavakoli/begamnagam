import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from . import tests as legacy
from .models import Account, FinancialEvent, MessageDelivery, Order, Outbox, PaymentAttempt, Preview, RecipientState
from .privacy import digest
from .services import APIError, confirm_free_order, create_order
from .tasks import deliver_message, expire_unpaid_orders


class FreeSendsTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    preview = legacy.APITestCase.preview
    order = legacy.APITestCase.order

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate(free_sends=None)

    def remaining(self):
        return Account.objects.get(user=self.user).free_sends_remaining

    def test_three_previews_and_fourth_paid_after_reserving_three(self):
        for index in range(3):
            preview = self.preview()
            self.assertEqual(preview["price_toman"], 0)
            self.assertTrue(preview["is_free"])
            self.assertEqual(self.remaining(), 3-index)
            result = self.order(recipient=f"0990123456{index}", preview=preview).json()
            self.assertTrue(result["is_free"])
            self.assertEqual(result["amount_toman"], 0)
        next_preview = self.preview()
        self.assertFalse(next_preview["is_free"])
        self.assertEqual(next_preview["price_toman"], 2000)
        fourth = self.order(recipient="09901234567", preview=next_preview).json()
        self.assertEqual(fourth["amount_toman"], 2000)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post(f"/orders/{fourth['id']}/pay-demo").status_code, 200)
        self.assertEqual(PaymentAttempt.objects.count(), 1)

    def test_preview_and_new_login_do_not_consume_or_regrant(self):
        self.preview()
        self.assertEqual(self.remaining(), 3)
        self.order()
        self.authenticate(free_sends=None)
        self.assertEqual(self.remaining(), 2)
        bootstrap = self.client.get("/api/v1/bootstrap").json()
        self.assertEqual(bootstrap["free_sends_remaining"], 2)
        self.assertEqual(bootstrap["free_sends_total"], 3)

    def test_idempotent_order_and_confirmation_use_one_credit_and_no_money(self):
        preview, key = self.preview(), str(uuid.uuid4())
        order = self.order(preview=preview, key=key).json()
        self.assertEqual(self.order(preview=preview, key=key).json()["id"], order["id"])
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                result = self.post(f"/orders/{order['id']}/confirm-free")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()["financial_status"], "free")
        self.assertEqual(self.remaining(), 2)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.get().status, "delivered_demo")
        self.assertFalse(PaymentAttempt.objects.exists())
        self.assertFalse(FinancialEvent.objects.exists())

    def test_stale_free_quote_requires_new_review_and_never_silently_charges(self):
        stale = self.preview()
        for index in range(3):
            self.order(recipient=f"0990123456{index}")
        response = self.order(recipient="09901234567", preview=stale)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "free_quota_changed")
        self.assertEqual(Order.objects.count(), 3)
        self.assertEqual(self.remaining(), 0)
        self.assertEqual(self.preview()["price_toman"], 2000)

    def test_expired_reservation_returns_credit_once(self):
        order = self.order().json()
        Order.objects.filter(pk=order["id"]).update(created_at=timezone.now()-timedelta(minutes=16))
        expire_unpaid_orders()
        expire_unpaid_orders()
        self.assertEqual(self.remaining(), 3)
        self.assertEqual(Order.objects.get().status, "cancelled")
        self.assertEqual(self.post(f"/orders/{order['id']}/confirm-free").status_code, 409)
        self.assertFalse(Outbox.objects.exists())

    def test_definite_worker_failure_returns_once_and_unknown_does_not(self):
        order = self.order().json()
        with self.captureOnCommitCallbacks(execute=False):
            self.post(f"/orders/{order['id']}/confirm-free")
        RecipientState.objects.update(blocked=True)
        event = Outbox.objects.get()
        deliver_message(event.pk)
        deliver_message(event.pk)
        self.assertEqual(self.remaining(), 3)
        self.assertEqual(self.post(f"/orders/{order['id']}/confirm-free").json()["financial_status"], "free_credit_returned")
        self.assertFalse(FinancialEvent.objects.exists())
        RecipientState.objects.update(blocked=False)
        other = self.order(recipient="09901234568").json()
        Order.objects.filter(pk=other["id"]).update(status="unknown", paid_at=timezone.now()-timedelta(days=2))
        expire_unpaid_orders()
        self.assertEqual(self.remaining(), 2)

    def test_paid_quote_is_not_repriced_after_credit_returns_and_fake_free_fields_ignored(self):
        orders = [self.order(recipient=f"0990123456{i}").json() for i in range(3)]
        paid_quote = self.preview()
        Order.objects.filter(pk=orders[0]["id"]).update(created_at=timezone.now()-timedelta(minutes=16))
        expire_unpaid_orders()
        response = self.post("/orders", {"preview_id":paid_quote["preview_id"], "recipient_phone":"09901234567",
            "is_free":True, "amount_toman":0}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_free"])
        self.assertEqual(response.json()["amount_toman"], 2000)
        self.assertEqual(self.remaining(), 1)
        self.assertEqual(self.post(f"/orders/{response.json()['id']}/confirm-free").status_code, 409)

    def test_free_sends_keep_recipient_rules_and_daily_cap(self):
        RecipientState.objects.create(phone_hash=digest("09901234567"), blocked=True)
        self.assertEqual(self.order().status_code, 409)
        self.assertEqual(self.remaining(), 3)
        self.assertEqual(self.order(recipient="09123456789").status_code, 409)
        with override_settings(SENDER_DAILY_LIMIT=1):
            self.assertEqual(self.order(recipient="09901234568").status_code, 200)
            self.assertEqual(self.order(recipient="09901234569").status_code, 429)
        self.assertEqual(self.remaining(), 2)

    def test_provider_unknown_holds_credit_until_definitive_failure(self):
        from .provider_delivery import apply_result
        from .providers.kavenegar import SMSResult
        order_id = self.order().json()["id"]
        with self.captureOnCommitCallbacks(execute=False):
            self.post(f"/orders/{order_id}/confirm-free")
        for status, expected in [("unknown", 2), ("failed", 3), ("failed", 3)]:
            with transaction.atomic():
                order = Order.objects.select_for_update().get(pk=order_id)
                state = RecipientState.objects.select_for_update().get(phone_hash=order.recipient_hash)
                apply_result(order, state, Outbox.objects.get(order=order), MessageDelivery.objects.get(order=order), SMSResult(status))
            self.assertEqual(self.remaining(), expected)
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_database_protects_credit_range_and_free_price(self):
        for invalid in [-1, 4]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                Account.objects.filter(user=self.user).update(free_sends_remaining=invalid)
        order = self.order().json()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Order.objects.filter(pk=order["id"]).update(amount_toman=2000)

    def test_unsubmitted_free_queue_expiry_returns_credit(self):
        order = self.order().json()
        with self.captureOnCommitCallbacks(execute=False):
            self.post(f"/orders/{order['id']}/confirm-free")
        Order.objects.filter(pk=order["id"]).update(paid_at=timezone.now()-timedelta(hours=25))
        expire_unpaid_orders()
        expire_unpaid_orders()
        self.assertEqual(self.remaining(), 3)
        self.assertEqual(Order.objects.get().status, "cancelled")
        self.assertFalse(FinancialEvent.objects.exists())

    def test_confirmation_is_owned_csrf_protected_and_does_not_bypass_provider_guards(self):
        order = self.order().json()
        stranger = Client()
        self.authenticate("09901234560", stranger, free_sends=None)
        self.assertEqual(self.post(f"/orders/{order['id']}/confirm-free", client=stranger).status_code, 404)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(self.post(f"/orders/{order['id']}/confirm-free", client=csrf_client).status_code, 403)
        with override_settings(DEMO_MODE=False, SMS_BACKEND="disabled"), self.assertRaises(APIError):
            confirm_free_order(self.user, order["id"])
        with override_settings(PAYMENT_BACKEND="zarinpal"):
            self.assertEqual(self.post(f"/orders/{order['id']}/payments", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code, 409)
        self.assertFalse(PaymentAttempt.objects.exists())


class FreeSendsConcurrencyTests(TransactionTestCase):
    setUp = legacy.PostgreSQLConcurrencyTests.setUp
    parallel = legacy.PostgreSQLConcurrencyTests.parallel
    def test_last_free_credit_cannot_be_used_by_two_parallel_orders(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=1)
        recipients = iter(["09901234567", "09901234568"])
        def submit(user):
            preview = Preview.objects.create(owner=user, session_key="session", category=self.preview.category,
                text=self.preview.text, moderation_mode="template", price_toman=0, is_free=True,
                expires_at=timezone.now()+timedelta(minutes=15))
            try:
                return create_order(user, "session", {"preview_id": str(preview.pk), "recipient_phone": next(recipients)}, str(uuid.uuid4())).is_free
            except APIError as exc:
                return exc.code
        self.assertCountEqual(self.parallel(submit), [True, "free_quota_changed"])
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 0)
        self.assertEqual(Order.objects.count(), 1)

    def test_parallel_free_confirmations_make_one_outbox(self):
        self.preview.is_free, self.preview.price_toman = True, 0
        self.preview.save()
        Account.objects.filter(user=self.user).update(free_sends_remaining=1)
        order = create_order(self.user, "session", {"preview_id":str(self.preview.pk), "recipient_phone":"09901234567"}, str(uuid.uuid4()))
        with patch("core.services.dispatch"):
            self.parallel(lambda user: str(confirm_free_order(user, order.pk).pk))
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertFalse(PaymentAttempt.objects.exists())
        self.assertFalse(FinancialEvent.objects.exists())
