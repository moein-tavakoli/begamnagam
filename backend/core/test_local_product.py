"""Configuration-only checks; these processes never connect to a provider."""
import os
import subprocess
import sys

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase

from .models import Account, OTPChallenge, Order
from .privacy import digest, encrypt, mask


class LocalProductStartupTests(SimpleTestCase):
    def test_real_local_profile_preserves_tls_and_rejects_demo_or_shared_data(self):
        env = dict(os.environ, DJANGO_TESTING="0", DJANGO_SETTINGS_MODULE="config.local_live_settings",
            LOCAL_LIVE_PRODUCT_ENABLED="1", DEBUG="0", DEMO_MODE="0",
            APP_BASE_URL="https://localhost:3000", ALLOWED_HOSTS="localhost,127.0.0.1",
            CSRF_TRUSTED_ORIGINS="https://localhost:3000", DJANGO_SECRET_KEY="s" * 64,
            PHONE_HASH_KEY="h" * 64, PHONE_ENCRYPTION_KEY="aXVyaWdoaG9wbHF3ZXJ0eXVpb3Bhc2RmZ2hqa2x6eGM=",
            DATABASE_URL="postgresql://synthetic:synthetic@127.0.0.1:15439/begamnagam_local_product",
            REDIS_URL="redis://127.0.0.1:16389/8", CACHE_KEY_PREFIX="begamnagam-local-real-v1",
            CELERY_BROKER_URL="amqp://synthetic:synthetic@127.0.0.1:15679//",
            CELERY_TASK_DEFAULT_QUEUE="begamnagam-local-real", CELERY_TASK_ALWAYS_EAGER="0",
            TRUST_DOMAIN_PROXY="0", PROVIDER_NETWORK_MODE="external", LIVE_PROVIDERS_ENABLED="1",
            PROVIDER_ENVIRONMENT="live", OTP_BACKEND="kavenegar", SMS_BACKEND="kavenegar",
            PAYMENT_BACKEND="disabled", LOCAL_REAL_OTP_ENABLED="0", DEMO_TEST_TOOLS_ENABLED="0",
            SMS_RECIPIENT_POLICY="all", KAVENEGAR_API_KEY="synthetic-key", KAVENEGAR_SENDER="10000000",
            KAVENEGAR_OTP_MODE="sms", KAVENEGAR_BASE_URL="https://api.kavenegar.com",
            PROVIDER_DAILY_BUDGET_UNLIMITED="1", PROVIDER_DAILY_BUDGET_RIAL="100000",
            OTP_MAX_COST_RIAL="10000", SMS_MAX_COST_RIAL="20000", TERMS_VERSION="v0.10.2")
        command = [sys.executable, "-c", "from config import local_live_settings as s; "
            "assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT; "
            "assert not getattr(s, 'SECURE_PROXY_SSL_HEADER', None)"]
        result = subprocess.run(command, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        for changes in [{"LOCAL_LIVE_PRODUCT_ENABLED": "0"}, {"DEMO_MODE": "1"}, {"DEBUG": "1"},
                {"SMS_BACKEND": "console"}, {"OTP_BACKEND": "demo"}, {"PAYMENT_BACKEND": "demo"},
                {"DJANGO_TESTING": "1"}, {"APP_BASE_URL": "http://localhost:3000"},
                {"DATABASE_URL": "postgresql://synthetic:synthetic@127.0.0.1:15439/begamnagam"},
                {"REDIS_URL": "redis://127.0.0.1:16389/0"}, {"CACHE_KEY_PREFIX": ""},
                {"CELERY_TASK_DEFAULT_QUEUE": "celery"}, {"CELERY_TASK_ALWAYS_EAGER": "1"}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(subprocess.run(command, env=dict(env, **changes), capture_output=True).returncode, 0)


class ProfileSessionTests(TestCase):
    def test_logout_requires_csrf_and_removes_account_information(self):
        # Session fixture only: no OTP adapter, preview, order or delivery runs.
        phone = "09123456789"
        user = get_user_model().objects.create_user(username="profile-session-fixture")
        Account.objects.create(user=user, phone_hash=digest(phone), phone_cipher=encrypt(phone),
                               phone_masked=mask(phone), free_sends_remaining=5, free_sends_earned_total=3)
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        value = client.get("/api/v1/bootstrap").json()
        self.assertTrue(value["authenticated"])
        self.assertEqual((value["free_sends_remaining"], value["free_sends_total"], value["free_sends_earned_total"]), (5, 6, 3))
        self.assertNotIn(phone, str(value))
        self.assertEqual(client.post("/api/v1/auth/logout", data="{}", content_type="application/json").status_code, 403)
        self.assertTrue(client.get("/api/v1/bootstrap").json()["authenticated"])
        result = client.post("/api/v1/auth/logout", data="{}", content_type="application/json",
                             HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(result.status_code, 200)
        value = client.get("/api/v1/bootstrap").json()
        self.assertFalse(value["authenticated"])
        self.assertNotIn("phone_masked", value)
        self.assertNotIn("free_sends_remaining", value)
        self.assertFalse(OTPChallenge.objects.exists())
        self.assertFalse(Order.objects.exists())
