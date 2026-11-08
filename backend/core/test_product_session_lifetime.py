from datetime import timedelta
from unittest.mock import patch
from django.conf import settings
from django.contrib.sessions.models import Session
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from . import test_api_v2 as api_tests


@override_settings(
    DEMO_MODE=True,
    OTP_BACKEND='demo',
    SMS_BACKEND='console',
    PAYMENT_BACKEND='demo',
    PROVIDER_NETWORK_MODE='disabled',
    AI_MODE='template',
)
class MonthlyProductSessionTests(TestCase):
    setUp = api_tests.IntegrationAPITests.setUp
    session, mutate, login = (
        api_tests.IntegrationAPITests.session,
        api_tests.IntegrationAPITests.mutate,
        api_tests.IntegrationAPITests.login,
    )

    def test_verified_login_issues_persistent_30_day_cookie_and_database_expiry(self):
        before = timezone.now()
        self.login()
        session = self.client.session
        remaining = (
            Session.objects.get(session_key=session.session_key).expire_date - before
        ).total_seconds()
        self.assertAlmostEqual(remaining, 30 * 86400, delta=5)
        self.assertAlmostEqual(
            int(self.client.cookies[settings.SESSION_COOKIE_NAME]['max-age']),
            30 * 86400,
            delta=5,
        )
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME]['expires'])
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME]['httponly'])
        self.assertFalse(session.get_expire_at_browser_close())
        self.assertAlmostEqual(session.get_expiry_age(), 30 * 86400, delta=5)
        self.assertEqual(settings.SESSION_COOKIE_AGE, 7 * 86400)

    @override_settings(SESSION_EXPIRE_AT_BROWSER_CLOSE=True)
    def test_reopened_client_remains_logged_in_after_20_days_and_sensitive_auth_is_not_extended(
        self,
    ):
        self.login()
        now = timezone.now()
        reopened = Client()
        reopened.cookies.update(self.client.cookies)
        with patch('django.utils.timezone.now', return_value=now + timedelta(days=20)):
            response = reopened.get('/api/v2/session')
            self.assertTrue(response.json()['authenticated'])
            self.assertFalse(response.json()['recent_auth'])
            self.assertAlmostEqual(response.json()['expires_in'], 10 * 86400, delta=5)
        with patch('django.utils.timezone.now', return_value=now + timedelta(days=31)):
            self.assertFalse(reopened.get('/api/v2/session').json()['authenticated'])

    def test_short_cookie_override_is_reset_by_successful_product_otp(self):
        self.session()
        session = self.client.session
        session.set_expiry(8 * 3600)
        session.save()
        self.login()
        self.assertAlmostEqual(
            self.client.session.get_expiry_age(), 30 * 86400, delta=5
        )

    def test_writes_do_not_extend_fixed_expiry_and_logout_revokes_session(self):
        self.login()
        now = timezone.now()
        original = self.client.session.get_expiry_date()
        with patch('django.utils.timezone.now', return_value=now + timedelta(days=20)):
            session = self.client.session
            session['nonprivate_test_counter'] = 1
            session.save()
            self.assertEqual(session.get_expiry_date(), original)
        response = self.mutate('/session', method='DELETE')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(self.client.get('/api/v2/session').json()['authenticated'])
