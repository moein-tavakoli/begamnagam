"""Unlimited site rewriting still accounts for use and enforces account caps."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import tests as legacy
from .ai_config import available
from .freeform import prepare, reserve
from .gapgpt import GapGPTUnavailable
from .limit_services import update_limits
from .limits import defaults
from .models import (AIConfiguration, Account, OperatorAudit, RewriteBudget,
                     RewriteUsage, SafetyControl, SiteLimits, SpendReservation)
from .moderation import RewriteUnavailable
from .privacy import digest, encrypt, mask
from .services import APIError


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key',
                   GAPGPT_MODEL='synthetic-model', GAPGPT_DAILY_REQUEST_LIMIT=1,
                   GAPGPT_DAILY_REQUEST_UNLIMITED=False, GAPGPT_USER_DAILY_LIMIT=10)
class RewriteSiteLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(username='rewrite-limit-fixture')
        Account.objects.create(user=self.user, phone_hash=digest('09123456789'),
                               phone_cipher=encrypt('09123456789'), phone_masked=mask('09123456789'))
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})

    def configure(self, **changes):
        value = defaults()
        for name, data in changes.items():
            setattr(value, name, data)
        value.full_clean()
        value.save()
        return value

    def test_unlimited_bypasses_exhausted_site_budget_without_resetting_ledger(self):
        self.configure(rewrite_daily_unlimited=True)
        budget = RewriteBudget.objects.create(day=timezone.localdate(), limit_requests=1,
                                              reserved_requests=20)
        reserve(self.user)
        cache.clear()
        reserve(self.user)
        budget.refresh_from_db()
        self.assertEqual(budget.reserved_requests, 22)
        self.assertEqual(budget.limit_requests, 1)
        self.assertEqual(RewriteUsage.objects.filter(owner=self.user).count(), 2)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_ten_account_slots_still_count_failed_provider_requests(self):
        self.configure(rewrite_daily_unlimited=True)
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTUnavailable()) as model:
            for _ in range(10):
                with self.assertRaises(RewriteUnavailable):
                    prepare(self.user, 'لطفاً جلوی در پارک نکن', max_units=140)
            with self.assertRaises(APIError) as failure:
                prepare(self.user, 'لطفاً جلوی در پارک نکن', max_units=140)
        self.assertEqual(failure.exception.code, 'rewrite_daily_limit')
        self.assertEqual(model.call_count, 10)
        self.assertEqual(RewriteBudget.objects.get().reserved_requests, 10)
        self.assertEqual(RewriteUsage.objects.count(), 10)
        self.assertFalse(SpendReservation.objects.exists())

    def test_reenabled_site_cap_uses_all_usage_accumulated_while_unlimited(self):
        value = self.configure(rewrite_daily_unlimited=True)
        reserve(self.user)
        reserve(self.user)
        actor = get_user_model().objects.create_superuser('rewrite-limits-admin')
        value = update_limits(actor, 'site', {'rewrite_daily_unlimited': False}, value.revision,
                              'Restore the daily site cap')
        with self.assertRaises(RewriteUnavailable):
            reserve(self.user)
        update_limits(actor, 'site', {'rewrite_daily_limit': 3}, value.revision,
                      'Increase the daily site cap')
        reserve(self.user)
        with self.assertRaises(RewriteUnavailable):
            reserve(self.user)
        self.assertEqual(RewriteBudget.objects.get().reserved_requests, 3)
        self.assertEqual(RewriteUsage.objects.count(), 3)

    @override_settings(GAPGPT_DAILY_REQUEST_LIMIT=0)
    def test_zero_daily_default_still_disables_gapgpt_without_explicit_unlimited(self):
        self.assertFalse(available())
        with self.assertRaises(APIError) as failure:
            reserve(self.user)
        self.assertEqual(failure.exception.code, 'freeform_unavailable')
        self.assertFalse(RewriteUsage.objects.exists())

    @override_settings(GAPGPT_DAILY_REQUEST_LIMIT=0, GAPGPT_DAILY_REQUEST_UNLIMITED=True)
    def test_explicit_env_unlimited_bypasses_old_budget_snapshot(self):
        self.assertFalse(SiteLimits.objects.exists())
        RewriteBudget.objects.create(day=timezone.localdate(), limit_requests=1, reserved_requests=20)
        self.assertTrue(available())
        reserve(self.user)
        self.assertEqual(RewriteBudget.objects.get().reserved_requests, 21)

    def test_unlimited_does_not_bypass_credentials_or_positive_account_limit(self):
        self.configure(rewrite_daily_unlimited=True, rewrite_daily_limit=0)
        self.assertTrue(available())
        for setting in ({'GAPGPT_API_KEY': ''}, {'GAPGPT_MODEL': ''}):
            with self.subTest(setting=setting), override_settings(**setting):
                self.assertFalse(available())
        SiteLimits.objects.filter(pk=1).update(rewrite_user_limit=0)
        self.assertFalse(available())
        self.assertFalse(RewriteUsage.objects.exists())

    def test_gapgpt_unlimited_does_not_disable_ollama_limit(self):
        self.configure(rewrite_daily_unlimited=True)
        config = AIConfiguration(provider='ollama', daily_limit=1, user_daily_limit=10)
        reserve(self.user, config)
        with self.assertRaises(RewriteUnavailable):
            reserve(self.user, config)
        self.assertEqual(RewriteUsage.objects.count(), 1)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   GAPGPT_DAILY_REQUEST_UNLIMITED=False)
class RewriteLimitManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user('rewrite-limits-staff', is_staff=True)
        self.client.force_login(self.staff)

    def post(self, values, revision=0, reason='Configure the site rewrite cap', client=None):
        return (client or self.client).post('/api/v1/manage/limits', json.dumps({
            'values': values, 'revision': revision, 'reason': reason}), content_type='application/json')

    def permit(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='manage_site_limits'))

    def test_unlimited_control_requires_permission_and_is_audited_with_revision(self):
        self.assertEqual(self.post({'rewrite_daily_unlimited': True}).status_code, 403)
        self.permit()
        initial = self.client.get('/api/v1/manage/limits').json()
        field = next(field for section in initial['sections'] for field in section['fields']
                     if field['key'] == 'rewrite_daily_unlimited')
        self.assertEqual(field['type'], 'bool')
        self.assertTrue(field['help'])
        self.assertFalse(initial['values']['rewrite_daily_unlimited'])
        result = self.post({'rewrite_daily_unlimited': True, 'rewrite_user_limit': 10},
                           initial['revision'])
        self.assertEqual(result.status_code, 200, result.content)
        saved = result.json()
        self.assertTrue(saved['values']['rewrite_daily_unlimited'])
        self.assertEqual(saved['values']['rewrite_user_limit'], 10)
        audit = OperatorAudit.objects.get(action='update_site_limits')
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertFalse(audit.before['rewrite_daily_unlimited'])
        self.assertTrue(audit.after['rewrite_daily_unlimited'])
        self.assertEqual(self.post({'rewrite_daily_unlimited': False}, initial['revision']).status_code, 409)
        self.assertEqual(self.post({'rewrite_daily_unlimited': 'true'}, saved['revision']).status_code, 422)
        self.assertEqual(self.post({'rewrite_daily_unlimited': False}, saved['revision'], reason='').status_code, 422)
        self.assertEqual(OperatorAudit.objects.filter(action='update_site_limits').count(), 1)
        self.assertContains(self.client.get(reverse('admin:core_sitelimits_change', args=[1])),
                            'name="rewrite_daily_unlimited"')

    def test_unlimited_mutation_requires_csrf(self):
        self.permit()
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.staff)
        self.assertEqual(self.post({'rewrite_daily_unlimited': True}, client=protected).status_code, 403)
        self.assertFalse(SiteLimits.objects.exists())


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
                   GAPGPT_DAILY_REQUEST_LIMIT=1, GAPGPT_DAILY_REQUEST_UNLIMITED=True,
                   GAPGPT_USER_DAILY_LIMIT=10)
class UnlimitedRewriteConcurrencyTests(TransactionTestCase):
    setUp = legacy.PostgreSQLConcurrencyTests.setUp
    parallel = legacy.PostgreSQLConcurrencyTests.parallel

    def test_parallel_requests_cannot_exceed_ten_account_slots(self):
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})
        for _ in range(9):
            reserve(self.user)

        def operation(user):
            try:
                reserve(user)
                return 'reserved'
            except APIError as error:
                if error.code == 'rewrite_daily_limit':
                    return 'limited'
                raise

        self.assertCountEqual(self.parallel(operation), ['reserved', 'limited'])
        self.assertEqual(RewriteUsage.objects.count(), 10)
        self.assertEqual(RewriteBudget.objects.get().reserved_requests, 10)
