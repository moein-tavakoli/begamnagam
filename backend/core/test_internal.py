import os
import subprocess
import sys
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from config.origins import local_otp_origin_allowed
from .providers.http import endpoint, ProviderDisabled


class InternalDeploymentTests(SimpleTestCase):
    def test_only_explicit_rfc1918_https_host_extends_local_otp_scope(self):
        self.assertTrue(local_otp_origin_allowed("https://192.168.1.123", "192.168.1.123"))
        self.assertTrue(local_otp_origin_allowed("http://localhost:3000", ""))
        for origin, host in [
            ("http://192.168.1.123", "192.168.1.123"),
            ("https://192.168.1.124", "192.168.1.123"),
            ("https://192.168.1.123", ""),
            ("https://8.8.8.8", "8.8.8.8"),
            ("https://example.invalid", "example.invalid"),
            ("https://192.168.1.123:8443", "192.168.1.123"),
            ("https://user@192.168.1.123", "192.168.1.123"),
            ("https://192.168.1.123/extra", "192.168.1.123"),
        ]:
            with self.subTest(origin=origin, host=host):
                self.assertFalse(local_otp_origin_allowed(origin, host))

    @override_settings(DEMO_MODE=True, LOCAL_REAL_OTP_ENABLED=True, LIVE_PROVIDERS_ENABLED=False,
        OTP_BACKEND="kavenegar", SMS_BACKEND="console", PAYMENT_BACKEND="demo",
        PROVIDER_NETWORK_MODE="disabled", APP_BASE_URL="https://192.168.1.123", INTERNAL_DEMO_HOST="192.168.1.123")
    def test_private_origin_keeps_wire_scope_limited_to_fixed_otp_paths(self):
        self.assertTrue(endpoint("https://api.kavenegar.com", "/v1/synthetic/verify/lookup.json", {"api.kavenegar.com"}, otp=True).startswith("https:"))
        for path, otp in [("/v1/synthetic/sms/send.json", False), ("/v1/synthetic/sms/status.json", True)]:
            with self.assertRaises(ProviderDisabled):
                endpoint("https://api.kavenegar.com", path, {"api.kavenegar.com"}, otp=otp)

    def test_internal_startup_enforces_tls_secrets_proxy_and_demo_boundaries(self):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE="config.internal_settings", DEBUG="0", DEMO_MODE="1",
            TRUST_INTERNAL_PROXY="1", INTERNAL_DEMO_HOST="192.168.1.123", APP_BASE_URL="https://192.168.1.123",
            DJANGO_SECRET_KEY="s"*64, PHONE_HASH_KEY="h"*64,
            PHONE_ENCRYPTION_KEY="aXVyaWdoaG9wbHF3ZXJ0eXVpb3Bhc2RmZ2hqa2x6eGM=",
            PROVIDER_NETWORK_MODE="disabled", LIVE_PROVIDERS_ENABLED="0", SMS_BACKEND="console",
            PAYMENT_BACKEND="demo", OTP_BACKEND="demo", LOCAL_REAL_OTP_ENABLED="0")
        command=[sys.executable, "-c", "from config import internal_settings as s; assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT"]
        result=subprocess.run(command,env=env,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode())
        for changes in [{"DEBUG":"1"}, {"TRUST_INTERNAL_PROXY":"0"}, {"DJANGO_SECRET_KEY":"weak"},
                        {"APP_BASE_URL":"http://192.168.1.123"}, {"SMS_BACKEND":"kavenegar"},
                        {"PAYMENT_BACKEND":"zarinpal"}, {"INTERNAL_DEMO_HOST":"8.8.8.8","APP_BASE_URL":"https://8.8.8.8"}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(subprocess.run(command,env=dict(env,**changes),capture_output=True).returncode,0)
