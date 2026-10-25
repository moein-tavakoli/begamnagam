import os
import subprocess
import sys

from django.test import RequestFactory, SimpleTestCase, override_settings

from config.origins import local_otp_origin_allowed
from .middleware import TrustedProxyClientIP
from .providers.http import ProviderDisabled, endpoint


class DomainRoutingTests(SimpleTestCase):
    def test_domain_origin_requires_explicit_exact_https_host_and_private_ct(self):
        self.assertTrue(local_otp_origin_allowed("https://begamnagam.ir", "192.168.1.123", "begamnagam.ir"))
        for origin, ct, domain in [
            ("https://begamnagam.ir", "192.168.1.123", ""),
            ("https://www.begamnagam.ir", "192.168.1.123", "begamnagam.ir"),
            ("https://begamnagam.ir:8443", "192.168.1.123", "begamnagam.ir"),
            ("http://begamnagam.ir", "192.168.1.123", "begamnagam.ir"),
            ("https://user@begamnagam.ir", "192.168.1.123", "begamnagam.ir"),
            ("https://begamnagam.ir/path", "192.168.1.123", "begamnagam.ir"),
            ("https://begamnagam.ir", "8.8.8.8", "begamnagam.ir"),
            ("https://begamnagam.ir", "192.168.1.123", "*.begamnagam.ir"),
        ]:
            with self.subTest(origin=origin, ct=ct, domain=domain):
                self.assertFalse(local_otp_origin_allowed(origin, ct, domain))

    @override_settings(DEMO_MODE=True, LOCAL_REAL_OTP_ENABLED=True, LIVE_PROVIDERS_ENABLED=False,
        OTP_BACKEND="kavenegar", SMS_BACKEND="console", PAYMENT_BACKEND="demo",
        PROVIDER_NETWORK_MODE="disabled", APP_BASE_URL="https://begamnagam.ir",
        INTERNAL_DEMO_HOST="192.168.1.123", PUBLIC_DEMO_HOST="begamnagam.ir", TRUST_DOMAIN_PROXY=True)
    def test_domain_does_not_enable_order_sms_or_other_provider_paths(self):
        self.assertTrue(endpoint("https://api.kavenegar.com", "/v1/synthetic/sms/send.json", set(), otp=True))
        for path, otp in [("/v1/synthetic/sms/send.json", False), ("/v1/synthetic/sms/status.json", True)]:
            with self.assertRaises(ProviderDisabled):
                endpoint("https://api.kavenegar.com", path, set(), otp=otp)
        with override_settings(TRUST_DOMAIN_PROXY=False), self.assertRaises(ProviderDisabled):
            endpoint("https://api.kavenegar.com", "/v1/synthetic/sms/send.json", set(), otp=True)

    @override_settings(TRUSTED_CLIENT_PROXY_IPS={"127.0.0.1", "::1", "192.168.1.6"})
    def test_client_ip_cannot_be_spoofed_by_an_untrusted_peer_or_forwarding_chain(self):
        middleware = TrustedProxyClientIP(lambda request: None)
        for peer, header, expected in [
            ("127.0.0.1", "203.0.113.42", "203.0.113.42"),
            ("::1", "2001:db8::42", "2001:db8::42"),
            ("198.51.100.7", "203.0.113.42", "198.51.100.7"),
            ("127.0.0.1", "203.0.113.42, 192.168.1.6", "203.0.113.42"),
            ("127.0.0.1", "1.2.3.4, 203.0.113.42, 192.168.1.6", "203.0.113.42"),
            ("127.0.0.1", "not-an-ip", "127.0.0.1"),
        ]:
            with self.subTest(peer=peer, header=header):
                request = RequestFactory().get("/healthz", REMOTE_ADDR=peer,
                    HTTP_X_VERIFIED_CLIENT_IP="1.2.3.4", HTTP_X_FORWARDED_FOR=header)
                middleware.process_request(request)
                self.assertEqual(request.META["REMOTE_ADDR"], expected)
                self.assertNotIn("HTTP_X_VERIFIED_CLIENT_IP", request.META)

    def test_startup_fails_closed_on_incomplete_or_permissive_domain_configuration(self):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE="config.internal_settings", DEBUG="0", DEMO_MODE="1",
            TRUST_INTERNAL_PROXY="1", TRUST_DOMAIN_PROXY="1", INTERNAL_DEMO_HOST="192.168.1.123",
            PUBLIC_DEMO_HOST="begamnagam.ir", CENTRAL_NGINX_IP="192.168.1.6", APP_BASE_URL="https://begamnagam.ir",
            ALLOWED_HOSTS="begamnagam.ir,192.168.1.123", CSRF_TRUSTED_ORIGINS="https://begamnagam.ir,https://192.168.1.123",
            DJANGO_SECRET_KEY="s"*64, PHONE_HASH_KEY="h"*64,
            PHONE_ENCRYPTION_KEY="aXVyaWdoaG9wbHF3ZXJ0eXVpb3Bhc2RmZ2hqa2x6eGM=",
            PROVIDER_NETWORK_MODE="disabled", LIVE_PROVIDERS_ENABLED="0", SMS_BACKEND="console",
            PAYMENT_BACKEND="demo", OTP_BACKEND="demo", LOCAL_REAL_OTP_ENABLED="0")
        command = [sys.executable, "-c", "from django.conf import settings as s; "
            "assert s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE and s.SECURE_SSL_REDIRECT; "
            "assert s.SESSION_COOKIE_DOMAIN is None and s.CSRF_COOKIE_DOMAIN is None; "
            "assert not s.USE_X_FORWARDED_HOST; assert s.SESSION_COOKIE_SAMESITE == 'Lax'"]
        result = subprocess.run(command, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        for changes in [
            {"TRUST_DOMAIN_PROXY": "0"}, {"PUBLIC_DEMO_HOST": ""}, {"APP_BASE_URL": "http://begamnagam.ir"},
            {"APP_BASE_URL": "https://other.invalid"}, {"CENTRAL_NGINX_IP": ""}, {"CENTRAL_NGINX_IP": "8.8.8.8"},
            {"ALLOWED_HOSTS": "*"}, {"ALLOWED_HOSTS": ".begamnagam.ir,192.168.1.123"},
            {"CSRF_TRUSTED_ORIGINS": "http://begamnagam.ir"}, {"SMS_BACKEND": "kavenegar"},
        ]:
            with self.subTest(changes=changes):
                self.assertNotEqual(subprocess.run(command, env=dict(env, **changes), capture_output=True).returncode, 0)
