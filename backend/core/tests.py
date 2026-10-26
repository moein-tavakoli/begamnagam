import json
import os
import subprocess
import sys
import threading
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import Account, ModerationAudit, OTPChallenge, Order, Outbox, Preview, RecipientState
from .moderation import ModerationRejected, RewriteUnavailable, CATEGORIES, TEMPLATES, moderate, normalized, rewrite
from .privacy import decrypt, digest, encrypt, mask, normalize_phone
from .services import APIError, create_order, pay_order
from .tasks import deliver_message, reconcile_outbox


class APITestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client()
        self.client.get("/api/v1/bootstrap")

    def post(self, path, data=None, client=None, **headers):
        return (client or self.client).post("/api/v1" + path, data=json.dumps(data or {}), content_type="application/json", **headers)

    def authenticate(self, phone="09123456789", client=None, free_sends=0):
        client = client or self.client
        client.get("/api/v1/bootstrap")
        response = self.post("/auth/request-otp", {"phone": phone}, client)
        self.assertEqual(response.status_code, 200, response.content)
        response = self.post("/auth/verify-otp", {"challenge_id": response.json()["challenge_id"], "code": response.json()["debug_code"]}, client)
        self.assertEqual(response.status_code, 200, response.content)
        account = Account.objects.get(phone_hash=digest(normalize_phone(phone)))
        # Legacy fixtures exercise paid checkout; free-credit tests preserve the grant.
        if free_sends is not None:
            Account.objects.filter(pk=account.pk).update(free_sends_remaining=free_sends)
        return account.user

    def preview(self, category="body", text="تنت بو میده", client=None):
        response = self.post("/messages/preview", {"category": category, "text": text}, client)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def order(self, recipient="09901234567", client=None, key=None, preview=None):
        preview = preview or self.preview(client=client)
        return self.post("/orders", {"preview_id": preview["preview_id"], "recipient_phone": recipient}, client,
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_bootstrap_and_health(self):
        response = self.client.get("/api/v1/bootstrap")
        self.assertEqual(response.json()["rewrite_mode"], "template")
        self.assertFalse(response.json()["authenticated"])
        self.assertIn("csrftoken", response.cookies)
        self.assertEqual({item["id"] for item in response.json()["categories"]},
            {item["id"] for item in CATEGORIES})
        self.assertEqual(self.client.get("/healthz").json()["status"], "ok")

    def test_positive_topics_complete_the_same_reviewed_delivery_flow(self):
        self.authenticate()
        for index, category in enumerate(["appreciation", "encouragement", "congratulations"]):
            preview = self.preview(category=category, text="برای تو روزهای خوبی آرزو می‌کنم")
            self.assertIn(preview["rewritten_text"], TEMPLATES[category])
            order = self.order(recipient=f"0990123456{index}", preview=preview).json()
            with self.captureOnCommitCallbacks(execute=True):
                response = self.post(f"/orders/{order['id']}/pay-demo")
            self.assertEqual(response.status_code, 200)
            saved = Order.objects.get(id=order["id"])
            self.assertEqual(saved.status, "delivered_demo")
            self.assertEqual(saved.text, preview["rewritten_text"])

    def test_csrf_is_required_and_login_rotates_token(self):
        client = Client(enforce_csrf_checks=True)
        client.get("/api/v1/bootstrap")
        self.assertEqual(self.post("/auth/request-otp", {"phone": "09123456789"}, client).status_code, 403)
        token = client.cookies["csrftoken"].value
        response = self.post("/auth/request-otp", {"phone": "09123456789"}, client, HTTP_X_CSRFTOKEN=token)
        challenge = response.json()
        response = self.post("/auth/verify-otp", {"challenge_id": challenge["challenge_id"], "code": challenge["debug_code"]}, client, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(client.cookies["csrftoken"].value, token)

    def test_auth_flow_and_anonymous_preview_survives_login(self):
        preview = self.preview()
        self.authenticate("+۹۸۹۱۲۳۴۵۶۷۸۹")
        response = self.order(preview=preview)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["amount_toman"], settings.PRICE_TOMAN)
        self.assertEqual(self.client.get("/api/v1/bootstrap").json()["phone_masked"], "091•••••789")
        self.assertNotIn("09123456789", response.content.decode())

    def test_otp_is_session_bound_single_use_and_attempts_persist(self):
        challenge = self.post("/auth/request-otp", {"phone": "09123456789"}).json()
        attacker = Client()
        attacker.get("/api/v1/bootstrap")
        payload = {"challenge_id": challenge["challenge_id"], "code": challenge["debug_code"]}
        self.assertEqual(self.post("/auth/verify-otp", payload, attacker).status_code, 400)
        wrong = "000000" if challenge["debug_code"] != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.post("/auth/verify-otp", {**payload, "code": wrong}).status_code, 400)
        self.assertEqual(OTPChallenge.objects.get(id=challenge["challenge_id"]).attempts, 5)
        self.assertEqual(self.post("/auth/verify-otp", payload).status_code, 400)

    def test_otp_expiry_and_reuse(self):
        challenge = self.post("/auth/request-otp", {"phone": "09123456789"}).json()
        OTPChallenge.objects.filter(id=challenge["challenge_id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
        payload = {"challenge_id": challenge["challenge_id"], "code": challenge["debug_code"]}
        self.assertEqual(self.post("/auth/verify-otp", payload).status_code, 400)
        challenge = self.post("/auth/request-otp", {"phone": "09123456789"}).json()
        payload = {"challenge_id": challenge["challenge_id"], "code": challenge["debug_code"]}
        self.assertEqual(self.post("/auth/verify-otp", payload).status_code, 200)
        self.assertEqual(self.post("/auth/verify-otp", payload).status_code, 400)

    def test_otp_rate_limit(self):
        for _ in range(3):
            self.assertEqual(self.post("/auth/request-otp", {"phone": "09123456789"}).status_code, 200)
        self.assertEqual(self.post("/auth/request-otp", {"phone": "09123456789"}).status_code, 429)

    def test_full_demo_flow_is_idempotent_and_never_claims_live_delivery(self):
        self.authenticate()
        preview = self.preview()
        key = uuid.uuid4()
        response = self.order(preview=preview, key=key)
        self.assertEqual(response.status_code, 200, response.content)
        item = response.json()
        duplicate = self.order(preview=preview, key=key)
        self.assertEqual(duplicate.json()["id"], item["id"])
        with self.assertLogs("core.tasks", level="INFO") as logs:
            with self.captureOnCommitCallbacks(execute=True):
                paid = self.post(f"/orders/{item['id']}/pay-demo")
        self.assertNotIn("09901234567", " ".join(logs.output))
        self.assertNotIn(preview["rewritten_text"], " ".join(logs.output))
        self.assertEqual(paid.status_code, 200)
        self.assertEqual(Outbox.objects.count(), 1)
        order = Order.objects.get(id=item["id"])
        self.assertEqual(order.status, "delivered_demo")
        self.assertEqual(self.post(f"/orders/{item['id']}/pay-demo").status_code, 200)
        deliver_message(order.outbox.pk)
        self.assertEqual(Outbox.objects.get(order=order).attempts, 1)
        history = self.client.get("/api/v1/messages").json()["results"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "delivered_demo")
        self.assertEqual(history[0]["payment_mode"], "demo")

    def test_client_price_text_and_status_are_ignored(self):
        self.authenticate()
        preview = self.preview()
        response = self.post("/orders", {"preview_id": preview["preview_id"], "recipient_phone": "09901234567",
            "amount_toman": 1, "text": "unsafe override", "status": "delivered"}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.json()["amount_toman"], settings.PRICE_TOMAN)
        self.assertEqual(response.json()["text"], preview["full_sms"])
        self.assertEqual(response.json()["status"], "awaiting_payment")

    def test_preview_price_is_snapshot_even_when_configuration_changes(self):
        self.authenticate()
        with override_settings(PRICE_TOMAN=1500):
            preview = self.preview()
        with override_settings(PRICE_TOMAN=3000):
            response = self.order(preview=preview)
        self.assertEqual(preview["price_toman"], 1500)
        self.assertEqual(response.json()["amount_toman"], 1500)

    def test_admin_session_does_not_count_as_verified_sender(self):
        admin = get_user_model().objects.create_superuser(username="admin", password="a-long-test-password")
        self.client.force_login(admin)
        self.assertFalse(self.client.get("/api/v1/bootstrap").json()["authenticated"])
        self.assertEqual(self.order().status_code, 401)
        self.assertEqual(self.client.get("/api/v1/messages").status_code, 401)

    def test_admin_preview_transfers_to_phone_account_after_otp(self):
        admin = get_user_model().objects.create_superuser(username="admin", password="a-long-test-password")
        self.client.force_login(admin)
        self.assertFalse(self.client.get("/api/v1/bootstrap").json()["authenticated"])
        preview = self.preview()
        self.assertIsNone(Preview.objects.get(id=preview["preview_id"]).owner_id)
        verified_user = self.authenticate()
        response = self.order(preview=preview)
        self.assertEqual(response.status_code, 200, response.content)
        order = Order.objects.get(id=response.json()["id"])
        self.assertEqual(order.owner_id, verified_user.pk)
        self.assertEqual(order.preview.owner_id, verified_user.pk)

    def test_independent_sessions_behind_same_proxy_have_independent_limits(self):
        for _ in range(20):
            self.preview()
        self.assertEqual(self.post("/messages/preview", {"category": "body", "text": ""}).status_code, 429)
        other = Client()
        other.get("/api/v1/bootstrap")
        self.assertEqual(self.post("/messages/preview", {"category": "body", "text": ""}, other).status_code, 200)

    def test_idempotency_key_conflict_and_missing_key(self):
        self.authenticate()
        key = uuid.uuid4()
        preview = self.preview()
        self.order(preview=preview, key=key)
        self.assertEqual(self.order(recipient="09901234568", preview=preview, key=key).status_code, 409)
        self.assertEqual(self.post("/orders", {"preview_id": preview["preview_id"], "recipient_phone": "09901234568"}).status_code, 400)

    def test_order_and_preview_ownership_and_auth(self):
        self.assertEqual(self.order().status_code, 401)
        self.authenticate()
        preview = self.preview()
        response = self.order()
        order_id = response.json()["id"]
        other = Client()
        self.authenticate("09123456780", other)
        self.assertEqual(other.get(f"/api/v1/orders/{order_id}").status_code, 404)
        self.assertEqual(self.post(f"/orders/{order_id}/pay-demo", client=other).status_code, 404)
        self.assertEqual(self.order(preview=preview, client=other).status_code, 404)
        self.assertEqual(other.get("/api/v1/messages").json()["results"], [])

    def test_expired_preview_and_payment(self):
        self.authenticate()
        preview = self.preview()
        Preview.objects.filter(id=preview["preview_id"]).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.order(preview=preview).status_code, 409)
        response = self.order()
        Order.objects.filter(id=response.json()["id"]).update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.post(f"/orders/{response.json()['id']}/pay-demo").status_code, 409)
        self.assertEqual(Outbox.objects.count(), 0)

    def test_recipient_optout_is_private_and_checked_before_payment(self):
        self.authenticate()
        recipient = Client()
        self.authenticate("09901234567", recipient)
        self.assertEqual(self.post("/preferences", {"blocked": True}, recipient).json(), {"blocked": True})
        response = self.order()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "recipient_unavailable")
        self.assertNotIn("blocked", response.content.decode())
        self.assertEqual(Order.objects.count(), 0)
        self.post("/preferences", {"blocked": False}, recipient)
        order = self.order().json()
        self.post("/preferences", {"blocked": True}, recipient)
        self.assertEqual(self.post(f"/orders/{order['id']}/pay-demo").status_code, 409)
        self.assertIsNone(Order.objects.get(id=order["id"]).paid_at)

    def test_recipient_optout_before_worker_cancels_queue(self):
        self.authenticate()
        order = self.order().json()
        with self.captureOnCommitCallbacks(execute=False):
            self.post(f"/orders/{order['id']}/pay-demo")
        RecipientState.objects.filter(phone_hash=digest("09901234567")).update(blocked=True)
        event = Outbox.objects.get(order_id=order["id"])
        deliver_message(event.id)
        event.refresh_from_db()
        self.assertEqual(event.state, "cancelled")
        self.assertEqual(Order.objects.get(id=order["id"]).status, "cancelled")

    def test_recipient_reservation_and_cooldown(self):
        self.authenticate()
        first = self.order().json()
        self.assertEqual(self.order().status_code, 409)
        with self.captureOnCommitCallbacks(execute=True):
            self.post(f"/orders/{first['id']}/pay-demo")
        self.assertEqual(self.order().status_code, 409)
        self.assertEqual(self.order(recipient="09123456789").status_code, 409)

    def test_sender_daily_cap_has_database_defense(self):
        self.authenticate()
        for i in range(settings.SENDER_DAILY_LIMIT):
            self.assertEqual(self.order(recipient=f"0990123456{i}").status_code, 200)
        cache.clear()
        self.assertEqual(self.order(recipient="09901234569").status_code, 429)

    def test_moderation_before_persistence_and_only_curated_content(self):
        for text in ["احمق", "می کشمت", "ک ث ا ف ت", "توهین به قومیت", "https://bad.example", "شماره ۰۹۱۲۳۴۵۶۷۸۹"]:
            response = self.post("/messages/preview", {"category": "body", "text": text})
            self.assertEqual(response.status_code, 422, text)
        self.assertEqual(Preview.objects.count(), 0)
        self.assertEqual(ModerationAudit.objects.filter(outcome="rejected").count(), 6)
        preview = self.preview()
        self.assertIn(preview["rewritten_text"], TEMPLATES["body"])
        self.assertEqual(preview["moderation_mode"], "template")

    def test_worker_rejects_tampered_template(self):
        self.authenticate()
        order = self.order().json()
        with self.captureOnCommitCallbacks(execute=False):
            self.post(f"/orders/{order['id']}/pay-demo")
        Order.objects.filter(id=order["id"]).update(text="unreviewed text")
        deliver_message(Outbox.objects.get(order_id=order["id"]).pk)
        self.assertEqual(Order.objects.get(id=order["id"]).status, "failed")

    def test_broker_failure_outbox_reconciliation(self):
        self.authenticate()
        order = self.order().json()
        with patch("core.tasks.deliver_message.delay", side_effect=ConnectionError()):
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.post(f"/orders/{order['id']}/pay-demo").status_code, 200)
        self.assertEqual(Outbox.objects.get(order_id=order["id"]).state, "pending")
        reconcile_outbox()
        self.assertEqual(Outbox.objects.get(order_id=order["id"]).state, "sent")

    @override_settings(DEMO_MODE=False, PAYMENT_BACKEND="disabled", SMS_BACKEND="disabled")
    def test_non_demo_cannot_expose_code_or_simulate_payment(self):
        response = self.post("/auth/request-otp", {"phone": "09123456789"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("debug_code", response.json())
        user = get_user_model().objects.create_user(username="test")
        Account.objects.create(user=user, phone_hash=digest("09123456789"), phone_cipher=encrypt("09123456789"), phone_masked=mask("09123456789"))
        self.client.force_login(user)
        self.assertEqual(self.post(f"/orders/{uuid.uuid4()}/pay-demo").status_code, 503)

    def test_invalid_json_preferences_and_phone(self):
        self.assertEqual(self.client.post("/api/v1/messages/preview", data="{", content_type="application/json").status_code, 400)
        self.assertEqual(self.post("/auth/request-otp", {"phone": "123"}).status_code, 400)
        self.assertEqual(self.post("/messages/preview", {"category": [], "text": ""}).status_code, 400)
        self.authenticate()
        self.assertEqual(self.post("/preferences", {"blocked": "false"}).status_code, 400)


class PrivacyAndRewriteTests(TestCase):
    def test_non_demo_startup_rejects_unsafe_configuration(self):
        environment = os.environ.copy()
        environment.update(DEMO_MODE="0", DEBUG="1")
        result = subprocess.run([sys.executable, "-c", "import config.settings"], env=environment,
            capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Non-demo requires DEBUG=false", result.stderr)

    def test_phone_normalization_and_encryption(self):
        for value in ["۰۹۱۲۳۴۵۶۷۸۹", "+98 912 345 6789", "00989123456789", "989123456789"]:
            self.assertEqual(normalize_phone(value), "09123456789")
        ciphertext = encrypt("09123456789")
        self.assertNotIn("09123456789", ciphertext)
        self.assertEqual(decrypt(ciphertext), "09123456789")
        self.assertNotEqual(ciphertext, encrypt("09123456789"))

    def test_all_reviewed_templates_pass_moderation(self):
        for templates in TEMPLATES.values():
            for template in templates:
                self.assertEqual(moderate(template), normalized(template))

    @override_settings(AI_MODE="ollama")
    def test_ollama_cannot_inject_arbitrary_text_or_boolean_index(self):
        for output in [{"template_id": True}, {"template_id": -1}, {"template_id": 10}, {"text": "unsafe"}]:
            with patch("core.moderation.urllib.request.urlopen") as mock:
                mock.return_value.__enter__.return_value.read.return_value = json.dumps({"response": json.dumps(output)}).encode()
                with self.assertRaises(RewriteUnavailable):
                    rewrite("body", "تنت بو میده")
        with patch("core.moderation.urllib.request.urlopen") as mock:
            mock.return_value.__enter__.return_value.read.return_value = json.dumps({"response": '{"template_id":1}'}).encode()
            text, mode = rewrite("body", "بوی بدن")
            self.assertEqual(text, TEMPLATES["body"][1])
            self.assertEqual(mode, "ollama_curated")
            outbound = json.loads(mock.call_args.args[0].data)
            self.assertNotIn("phone", outbound["prompt"])

    @override_settings(AI_MODE="ollama")
    def test_ollama_failure_closes_without_fallback_send(self):
        with patch("core.moderation.urllib.request.urlopen", side_effect=TimeoutError()):
            with self.assertRaises(RewriteUnavailable):
                rewrite("body", "تنت بو میده")


class PostgreSQLConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row-lock integration test; run CI PostgreSQL job")
        cache.clear()
        self.user = get_user_model().objects.create_user(username="concurrent-user")
        Account.objects.create(user=self.user, phone_hash=digest("09123456789"), phone_cipher=encrypt("09123456789"), phone_masked=mask("09123456789"))
        self.preview = Preview.objects.create(owner=self.user, session_key="session", category="body", text=TEMPLATES["body"][0], moderation_mode="template", price_toman=settings.PRICE_TOMAN, expires_at=timezone.now() + timedelta(minutes=15))

    def parallel(self, operation):
        barrier = threading.Barrier(2)
        results, errors = [], []
        def run():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                barrier.wait(timeout=10)
                results.append(operation(user))
            except Exception as exc:
                errors.append(exc)
            finally:
                # CONN_MAX_AGE keeps healthy connections open; explicitly close
                # each worker's thread-local connection before test DB teardown.
                connections.close_all()
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
            self.assertFalse(thread.is_alive(), "Concurrent operation timed out")
        self.assertEqual(errors, [])
        return results

    def test_concurrent_order_retries_create_one_order(self):
        key = str(uuid.uuid4())
        results = self.parallel(lambda user: str(create_order(user, "session", {"preview_id": str(self.preview.pk), "recipient_phone": "09901234567"}, key).pk))
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(Order.objects.count(), 1)

    def test_concurrent_new_orders_cannot_exceed_five_sender_slots(self):
        def quote():
            return Preview.objects.create(owner=self.user, session_key="session", category="body",
                text=TEMPLATES["body"][0], moderation_mode="template", price_toman=settings.PRICE_TOMAN,
                expires_at=timezone.now()+timedelta(minutes=15))
        for index in range(4):
            create_order(self.user, "session", {"preview_id": str(quote().pk),
                "recipient_phone": f"0990123456{index}"}, str(uuid.uuid4()))
        recipients = iter(["09901234567", "09901234568"])
        def submit(user):
            try:
                create_order(user, "session", {"preview_id": str(quote().pk),
                    "recipient_phone": next(recipients)}, str(uuid.uuid4()))
                return "created"
            except APIError as exc:
                return exc.code
        self.assertCountEqual(self.parallel(submit), ["created", "daily_limit"])
        self.assertEqual(Order.objects.count(), 5)

    def test_concurrent_payment_retries_create_one_event(self):
        order = create_order(self.user, "session", {"preview_id": str(self.preview.pk), "recipient_phone": "09901234567"}, str(uuid.uuid4()))
        with patch("core.services.dispatch"):
            self.parallel(lambda user: str(pay_order(user, order.pk).pk))
        self.assertEqual(Outbox.objects.count(), 1)
        event = Outbox.objects.get(order=order)
        self.parallel(lambda user: deliver_message(event.pk))
        event.refresh_from_db()
        self.assertEqual(event.attempts, 1)
        self.assertEqual(event.state, "sent")
