import json
import base64
import hashlib
import os
import subprocess
import sys
from io import StringIO
from unittest.mock import patch
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from config.database import connection_options
from .cache import JSONSerializer
from .services import api


class SafeConfigurationTests(SimpleTestCase):
    def test_default_debug_is_disabled(self):
        environment = dict(os.environ)
        environment.pop("DEBUG", None)
        result = subprocess.run([sys.executable, "-c", "from config import settings; assert settings.DEBUG is False"], env=environment, capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_application_keys_are_required_without_fallback_or_derivation(self):
        for name in ("DJANGO_SECRET_KEY", "PHONE_HASH_KEY", "PHONE_ENCRYPTION_KEY"):
            with self.subTest(name=name):
                environment = dict(os.environ)
                environment.pop(name, None)
                result = subprocess.run([sys.executable, "-c", "import config.settings"], env=environment, capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(name + " must be supplied through the private environment", result.stderr)
                for value in (settings.SECRET_KEY, settings.PHONE_HASH_KEY, settings.PHONE_ENCRYPTION_KEY):
                    self.assertNotIn(value, result.stderr)

    def test_automated_test_keys_are_fresh_environment_values(self):
        from config.ephemeral_environment import prepare_ephemeral_secrets
        from cryptography.fernet import Fernet
        results = []
        for _ in range(2):
            with patch.dict(os.environ, {}, clear=True):
                prepare_ephemeral_secrets()
                values = tuple(os.environ[key] for key in ("DJANGO_SECRET_KEY", "PHONE_HASH_KEY", "PHONE_ENCRYPTION_KEY"))
                prepare_ephemeral_secrets()
                self.assertEqual(values, tuple(os.environ[key] for key in ("DJANGO_SECRET_KEY", "PHONE_HASH_KEY", "PHONE_ENCRYPTION_KEY")))
                Fernet(values[2].encode())
                results.append(values)
        self.assertTrue(all(a != b for a, b in zip(*results)))

    def test_live_settings_reject_reused_or_derived_application_keys(self):
        secret = "synthetic-independent-secret-" + "s"*50
        encryption = "aXVyaWdoaG9wbHF3ZXJ0eXVpb3Bhc2RmZ2hqa2x6eGM="
        environment = dict(os.environ, DJANGO_SETTINGS_MODULE="config.settings", DEMO_MODE="0", DEBUG="0",
            DJANGO_SECRET_KEY=secret, PHONE_HASH_KEY="synthetic-independent-hash-"+"h"*40, PHONE_ENCRYPTION_KEY=encryption,
            DATABASE_URL="postgresql://synthetic:synthetic@127.0.0.1/synthetic",
            REDIS_URL="redis://127.0.0.1:6379/15", SMS_BACKEND="disabled", OTP_BACKEND="disabled",
            PAYMENT_BACKEND="disabled", LIVE_PROVIDERS_ENABLED="0", PROVIDER_NETWORK_MODE="disabled",
            LOCAL_REAL_OTP_ENABLED="0", PROVIDER_DAILY_BUDGET_UNLIMITED="0", ALLOWED_HOSTS="begamnagam.ir",
            CSRF_TRUSTED_ORIGINS="https://begamnagam.ir")
        command = [sys.executable, "-c", "import config.settings"]
        self.assertEqual(subprocess.run(command, env=environment, capture_output=True).returncode, 0)
        for changes in [{"PHONE_HASH_KEY": secret}, {"PHONE_HASH_KEY": encryption},
                        {"PHONE_ENCRYPTION_KEY": base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()).decode()}]:
            result = subprocess.run(command, env=dict(environment, **changes), capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b"independently generated", result.stderr)

    def test_cache_serializer_roundtrips_data_and_keeps_redis_counters_atomic(self):
        serializer = JSONSerializer()
        for value in [0, 3, "متن عمومی", {"status": "ok"}, [1, None, False], True]:
            serialized = serializer.dumps(value)
            wire_value = str(serialized).encode() if type(serialized) is int else serialized
            self.assertEqual(serializer.loads(wire_value), value)
        self.assertEqual(serializer.dumps(3), 3)
        with patch("pickle.loads") as executable_deserializer:
            with self.assertRaises((ValueError, UnicodeDecodeError)):
                serializer.loads(b"\x80\x05malicious-pickle")
            executable_deserializer.assert_not_called()

    def test_database_tls_options_are_preserved_and_unknown_or_duplicate_options_fail_closed(self):
        result = connection_options("sslmode=verify-full&sslrootcert=%2Ftrusted%2Fca.pem&connect_timeout=4")
        self.assertEqual(result, {"connect_timeout": 4, "sslmode": "verify-full", "sslrootcert": "/trusted/ca.pem"})
        for query in ["sslmode=unknown", "sslmode=require&sslmode=disable", "sslmode=", "connect_timeout=0",
                      "connect_timeout=100", "connect_timeout=unbounded", "sslmod=require", "unsafe-secret"]:
            with self.subTest(query=query), self.assertRaises(ImproperlyConfigured) as raised:
                connection_options(query)
            self.assertNotIn(query, str(raised.exception))

    def test_unexpected_value_errors_cannot_expose_private_data(self):
        @api(["GET"])
        def fail(request):
            raise ValueError("synthetic-private-provider-credential")
        response = fail(RequestFactory().get("/api/v1/test"))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b"synthetic-private", response.content)


@override_settings(ADMIN_LOGIN_PAIR_LIMIT=2, ADMIN_LOGIN_IP_LIMIT=4)
class SecurityBoundaryTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_default_rate_limit_preserves_a_predeployment_counter(self):
        from .privacy import digest
        from .services import APIError, limited
        key = "rate:otp-ip-flood:" + digest("synthetic-existing-client")
        cache.set(key, 2, timeout=600)
        with self.assertRaises(APIError) as raised:
            limited("otp-ip-flood", "synthetic-existing-client", 2, 600)
        self.assertEqual(raised.exception.status, 429)
        self.assertEqual(cache.get(key), 3)

    def test_admin_throttle_survives_session_changes_and_does_not_authenticate_blocked_attempt(self):
        with patch("django.contrib.auth.forms.authenticate", return_value=None) as authenticate:
            for index in range(2):
                response = Client().post("/admin/login/", {"username": "operator", "password": "synthetic-wrong-password"})
                self.assertEqual(response.status_code, 200)
            response = Client().post("/admin/login/", {"username": "operator", "password": "synthetic-wrong-password"})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(authenticate.call_count, 2)
            self.assertEqual(response["Retry-After"], "600")
            self.assertEqual(response["Cache-Control"], "no-store")

    def test_admin_ip_limit_cannot_be_bypassed_by_changing_username(self):
        with patch("django.contrib.auth.forms.authenticate", return_value=None) as authenticate:
            for index in range(4):
                self.assertEqual(Client().post("/admin/login/", {"username": f"operator-{index}", "password": "wrong"}).status_code, 200)
            self.assertEqual(Client().post("/admin/login/", {"username": "fresh-operator", "password": "wrong"}).status_code, 429)
            self.assertEqual(authenticate.call_count, 4)

    def test_admin_cache_failure_fails_closed(self):
        with patch("core.middleware.cache.add", side_effect=ConnectionError("synthetic-secret")), \
                patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = self.client.post("/admin/login/", {"username": "operator", "password": "wrong"})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn(b"synthetic-secret", response.content)
            authenticate.assert_not_called()

    def test_admin_post_still_requires_csrf_before_rate_limiter(self):
        with patch("core.middleware.cache.add") as counter:
            response = Client(enforce_csrf_checks=True).post("/admin/login/", {"username": "operator", "password": "wrong"})
            self.assertEqual(response.status_code, 403)
            counter.assert_not_called()

    @override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=32)
    def test_large_json_body_is_rejected_without_debug_content_or_provider_calls(self):
        with patch("core.providers.Kavenegar.otp") as provider:
            response = self.client.post("/api/v1/auth/request-otp", json.dumps({"phone": "x"*100}), content_type="application/json")
            self.assertEqual(response.status_code, 413)
            self.assertEqual(response.json()["error"]["code"], "request_too_large")
            provider.assert_not_called()

    def test_admin_api_and_static_responses_have_enforced_security_headers(self):
        for path in ["/admin/login/", "/api/v1/messages", "/api/v1/operations/status", "/static/admin/css/base.css"]:
            response = self.client.get(path)
            self.assertIn("script-src 'self'", response["Content-Security-Policy"])
            self.assertIn("frame-ancestors 'none'", response["Content-Security-Policy"])
            self.assertIn("form-action 'self'", response["Content-Security-Policy"])
            self.assertIn("camera=()", response["Permissions-Policy"])

    def test_read_only_audit_reports_its_scope_and_does_not_print_secrets(self):
        output = StringIO()
        call_command("audit_security", stdout=output)
        value = output.getvalue()
        report = json.loads(value)
        self.assertTrue(report["read_only"])
        self.assertEqual(report["scope"], "loaded_process_configuration")
        for secret in [settings.SECRET_KEY, settings.PHONE_HASH_KEY, settings.PHONE_ENCRYPTION_KEY]:
            self.assertNotIn(secret, value)

    def test_reviewed_message_bodies_are_encrypted_in_both_tables_and_rotate_without_changing_text(self):
        import uuid
        from datetime import timedelta
        from cryptography.fernet import Fernet
        from django.utils import timezone
        from .models import Order, Preview
        message = "پیام بررسی‌شدهٔ خصوصی برای آزمون"
        user = get_user_model().objects.create_user(username="security-test-sender")
        preview = Preview.objects.create(owner=user, session_key="synthetic", category="appreciation",
            text=message, moderation_mode="template", price_toman=2000, expires_at=timezone.now()+timedelta(minutes=5))
        order = Order.objects.create(owner=user, preview=preview, idempotency_key=uuid.uuid4(), text=message,
            category="appreciation", amount_toman=2000, recipient_hash="synthetic", recipient_cipher="", recipient_masked="synthetic")
        for table in ("core_preview", "core_order"):
            with connection.cursor() as cursor:
                instance = preview if table == "core_preview" else order
                identifier = instance._meta.pk.get_db_prep_value(instance.pk, connection)
                cursor.execute(f'SELECT text FROM "{table}" WHERE id = %s', [identifier])
                stored = cursor.fetchone()[0]
            self.assertTrue(stored.startswith("enc:v1:"))
            self.assertNotIn(message, stored)
        original_key = settings.PHONE_ENCRYPTION_KEY
        with override_settings(PHONE_ENCRYPTION_KEY=Fernet.generate_key().decode(), PHONE_ENCRYPTION_FALLBACK_KEYS=[original_key]):
            call_command("rotate_encryption", apply=True, stdout=StringIO())
            self.assertEqual(Preview.objects.get(pk=preview.pk).text, message)
            self.assertEqual(Order.objects.get(pk=order.pk).text, message)


class MessageEncryptionMigrationTests(TransactionTestCase):
    def test_existing_plaintext_is_encrypted_and_an_intentional_rollback_restores_it(self):
        import uuid
        from datetime import timedelta
        from django.db.migrations.executor import MigrationExecutor
        from django.utils import timezone
        previous, current = [("core", "0016_runtime_site_limits")], [("core", "0017_encrypt_reviewed_message_bodies")]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(previous)
            apps = executor.loader.project_state(previous).apps
            user = apps.get_model("auth", "User").objects.create(username="legacy-security-test")
            message = "متن خصوصی پیش از مهاجرت"
            preview = apps.get_model("core", "Preview").objects.create(owner_id=user.pk,
                session_key="synthetic", category="appreciation", text=message, moderation_mode="template",
                price_toman=2000, expires_at=timezone.now()+timedelta(minutes=5))
            order = apps.get_model("core", "Order").objects.create(owner_id=user.pk, preview_id=preview.pk,
                idempotency_key=uuid.uuid4(), text=message, category="appreciation", amount_toman=2000,
                recipient_hash="synthetic", recipient_cipher="", recipient_masked="synthetic")
            MigrationExecutor(connection).migrate(current)
            for table, pk in [("core_preview", preview.pk), ("core_order", order.pk)]:
                with connection.cursor() as cursor:
                    prepared = apps.get_model("core", "Preview")._meta.pk.get_db_prep_value(pk, connection)
                    cursor.execute(f'SELECT text FROM "{table}" WHERE id=%s', [prepared])
                    self.assertTrue(cursor.fetchone()[0].startswith("enc:v1:"))
            MigrationExecutor(connection).migrate(previous)
            self.assertEqual(apps.get_model("core", "Preview").objects.get(pk=preview.pk).text, message)
            self.assertEqual(apps.get_model("core", "Order").objects.get(pk=order.pk).text, message)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate([node for node in executor.loader.graph.leaf_nodes() if node[0] == "core"])
