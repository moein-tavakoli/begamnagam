"""Aggregate-cap opt-out keeps the ledger and per-call safeguards intact."""
import os
import subprocess
import sys

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from .budget import observe_cost, reserve_cost
from .models import OperationalAlert, SafetyControl, SpendBudget, SpendReservation
from .providers import ProviderDisabled
from .safety import operator_action, refresh_alerts, snapshot
from .services import APIError


@override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=False, PROVIDER_DAILY_BUDGET_RIAL=100000)
class ProviderDailyBudgetTests(TestCase):
    def setUp(self):
        self.budget = SpendBudget.objects.create(day=timezone.localdate(), limit_rial=100000, reserved_rial=100000)

    def test_bounded_default_still_rejects_an_exhausted_day_without_changing_the_ledger(self):
        with self.assertRaisesRegex(ProviderDisabled, 'daily_budget_exhausted'):
            reserve_cost('synthetic:sms', 'sms', 20000)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.reserved_rial, 100000)
        self.assertFalse(SpendReservation.objects.exists())

    @override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=True)
    def test_unlimited_existing_day_counts_sms_otp_and_invites_once_without_resetting_history(self):
        for key, kind, ceiling in [('sms', 'sms', 20000), ('otp', 'otp', 10000), ('invite', 'invitation', 20000)]:
            first = reserve_cost('synthetic:'+key, kind, ceiling)
            self.assertEqual(reserve_cost('synthetic:'+key, kind, ceiling).pk, first.pk)
        observe_cost('synthetic:sms', 13000)
        observe_cost('synthetic:sms', 13000)
        self.budget.refresh_from_db()
        self.assertEqual((self.budget.limit_rial, self.budget.reserved_rial), (100000, 150000))
        self.assertEqual(SpendReservation.objects.count(), 3)
        self.assertEqual(SpendReservation.objects.get(operation_key='synthetic:sms').actual_rial, 13000)

    @override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=True, PROVIDER_DAILY_BUDGET_RIAL=0)
    def test_explicit_unlimited_mode_can_create_a_new_zero_ceiling_ledger(self):
        self.budget.delete()
        reserve_cost('synthetic:new-day', 'sms', 20000)
        self.assertEqual((SpendBudget.objects.get().limit_rial, SpendBudget.objects.get().reserved_rial), (0, 20000))

    @override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=True)
    def test_unlimited_never_allows_missing_per_call_ceilings(self):
        for amount in [0, -1, None, True, '20000']:
            with self.subTest(amount=amount), self.assertRaisesRegex(ProviderDisabled, 'cost_ceiling_missing'):
                reserve_cost('synthetic:bad-ceiling', 'sms', amount)
        self.assertFalse(SpendReservation.objects.exists())

    @override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=True)
    def test_cost_above_per_call_ceiling_still_halts_new_spend_and_counts_actual_charge_once(self):
        reserve_cost('synthetic:overage', 'sms', 20000)
        observe_cost('synthetic:overage', 21000)
        observe_cost('synthetic:overage', 21000)
        self.budget.refresh_from_db()
        self.assertEqual(self.budget.reserved_rial, 121000)
        self.assertEqual(SpendReservation.objects.get().actual_rial, 21000)
        self.assertTrue(SafetyControl.objects.get(pk=1).halted)
        with self.assertRaisesRegex(ProviderDisabled, 'provider_cost_halt'):
            reserve_cost('synthetic:after-overage', 'otp', 10000)

    def test_operator_resume_and_alerts_distinguish_unlimited_from_a_full_bounded_day(self):
        actor = get_user_model().objects.create_superuser(username='budget-operator', password=None)
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': True})
        with self.assertRaises(APIError) as caught:
            operator_action(actor, 'resume', 'global', 'synthetic bounded budget exercise')
        self.assertEqual(caught.exception.code, 'budget_exhausted')
        bounded = refresh_alerts()
        self.assertEqual(bounded['provider_budget_limit_rial'], 100000)
        self.assertFalse(bounded['provider_budget_unlimited'])
        self.assertTrue(OperationalAlert.objects.get(code='budget_80_percent').active)
        with override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=True):
            operator_action(actor, 'resume', 'global', 'synthetic authorized unlimited budget')
            unlimited = refresh_alerts()
            self.assertIsNone(unlimited['provider_budget_limit_rial'])
            self.assertTrue(unlimited['provider_budget_unlimited'])
            self.assertEqual(unlimited['provider_budget_reserved_rial'], 100000)
            self.assertFalse(OperationalAlert.objects.get(code='budget_80_percent').active)
            self.assertFalse(snapshot()['sending_halted'])
        self.budget.refresh_from_db()
        self.assertEqual((self.budget.limit_rial, self.budget.reserved_rial), (100000, 100000))

    @override_settings(PROVIDER_DAILY_BUDGET_UNLIMITED=True, PILOT_RECIPIENT_HASHES={'synthetic'}, SMS_MAX_COST_RIAL=20000, OTP_MAX_COST_RIAL=10000)
    def test_unlimited_never_claims_a_bounded_paid_pilot_is_ready(self):
        from .management.commands.release_readiness import collect
        self.assertFalse(collect()['checks']['bounded_pilot'])


class ProviderDailyBudgetStartupTests(SimpleTestCase):
    def environment(self):
        return dict(os.environ, DJANGO_SETTINGS_MODULE='config.live_sms_settings', DEBUG='0', DEMO_MODE='0',
            TRUST_INTERNAL_PROXY='1', TRUST_DOMAIN_PROXY='1', PUBLIC_DEMO_HOST='begamnagam.ir',
            INTERNAL_DEMO_HOST='192.168.1.123', CENTRAL_NGINX_IP='192.168.1.6',
            APP_BASE_URL='https://begamnagam.ir', ALLOWED_HOSTS='begamnagam.ir,192.168.1.123',
            CSRF_TRUSTED_ORIGINS='https://begamnagam.ir,https://192.168.1.123',
            DJANGO_SECRET_KEY='s'*64, PHONE_HASH_KEY='h'*64,
            PHONE_ENCRYPTION_KEY='aXVyaWdoaG9wbHF3ZXJ0eXVpb3Bhc2RmZ2hqa2x6eGM=',
            DATABASE_URL='postgresql://synthetic:synthetic@localhost/synthetic', REDIS_URL='redis://localhost/15',
            PROVIDER_NETWORK_MODE='external', LIVE_PROVIDERS_ENABLED='1', PROVIDER_ENVIRONMENT='live',
            SMS_BACKEND='kavenegar', OTP_BACKEND='kavenegar', LOCAL_REAL_OTP_ENABLED='0',
            PAYMENT_BACKEND='disabled', ZARINPAL_MERCHANT_ID='', PILOT_RECIPIENT_HASHES='',
            SMS_RECIPIENT_POLICY='all', DEMO_TEST_TOOLS_ENABLED='0',
            KAVENEGAR_BASE_URL='https://api.kavenegar.com', KAVENEGAR_API_KEY='synthetic-key',
            KAVENEGAR_SENDER='10000000', KAVENEGAR_OTP_MODE='sms', AI_MODE='template',
            PROVIDER_DAILY_BUDGET_RIAL='0', PROVIDER_DAILY_BUDGET_UNLIMITED='1',
            SMS_MAX_COST_RIAL='20000', OTP_MAX_COST_RIAL='10000', TERMS_VERSION='v0.10.1-live-sms')

    def run_startup(self, environment):
        return subprocess.run([sys.executable, '-c', 'from config import live_sms_settings'],
            env=environment, capture_output=True)

    def test_unlimited_requires_explicit_live_gift_configuration_and_positive_per_call_limits(self):
        env = self.environment()
        result = self.run_startup(env)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        for changes in [{'DEMO_MODE':'1'}, {'DEBUG':'1'}, {'PROVIDER_NETWORK_MODE':'disabled'},
                {'PROVIDER_ENVIRONMENT':'sandbox'}, {'LIVE_PROVIDERS_ENABLED':'0'},
                {'SMS_BACKEND':'console'}, {'OTP_BACKEND':'demo'}, {'PAYMENT_BACKEND':'zarinpal'},
                {'PAYMENT_BACKEND':'demo'}, {'LOCAL_REAL_OTP_ENABLED':'1'}, {'DEMO_TEST_TOOLS_ENABLED':'1'},
                {'SMS_RECIPIENT_POLICY':'pilot'}, {'SMS_MAX_COST_RIAL':'0'}, {'OTP_MAX_COST_RIAL':'0'},
                {'PROVIDER_DAILY_BUDGET_RIAL':'-1'}, {'PROVIDER_DAILY_BUDGET_UNLIMITED':'0'}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(self.run_startup(dict(env, **changes)).returncode, 0)

    def test_unlimited_defaults_off_and_zero_never_silently_removes_the_cap(self):
        env = self.environment()
        env.pop('PROVIDER_DAILY_BUDGET_UNLIMITED')
        self.assertNotEqual(self.run_startup(env).returncode, 0)
        env['PROVIDER_DAILY_BUDGET_RIAL'] = '100000'
        result = self.run_startup(env)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
