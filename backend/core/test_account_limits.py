from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from . import test_runtime_limits as runtime_tests
from .account_options import update_account_options
from .models import Account, OperatorAudit, Order, RewriteBudget, RewriteUsage
from .services import APIError


class AccountCountLimitTests(TestCase):
    setUp = runtime_tests.RuntimeLimitsTests.setUp
    post, preview = runtime_tests.RuntimeLimitsTests.post, runtime_tests.RuntimeLimitsTests.preview
    configure, order = runtime_tests.RuntimeLimitsTests.configure, runtime_tests.RuntimeLimitsTests.order

    def change(self, **values):
        actor, _ = get_user_model().objects.get_or_create(username='limit-operator', defaults={'is_staff': True, 'is_superuser': True})
        return update_account_options(actor, Account.objects.get(user=self.user).pk, values, 'آزمون سقف اختصاصی')

    def test_thousand_and_unlimited_raise_sender_cap_without_granting_credits(self):
        self.configure(sender_limit=1, recipient_cooldown_hours=0, pair_cooldown_hours=0)
        self.change(sender_daily_limit=1000)
        for _ in range(3):
            response = self.order();self.assertEqual(response.status_code, 200, response.content)
            Order.objects.filter(pk=response.json()['id']).update(status='delivered_demo')
        response = self.order()
        self.assertEqual(response.json()['error']['code'], 'credit_required')
        self.change(sender_daily_limit=0)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 0)
        self.assertEqual(self.order().json()['error']['code'], 'credit_required')
        self.assertEqual(Order.objects.count(), 3)

    def test_lower_custom_cap_and_return_to_site_preserve_previous_usage(self):
        self.configure(sender_limit=10, recipient_cooldown_hours=0, pair_cooldown_hours=0)
        self.change(sender_daily_limit=1)
        first = self.order();self.assertEqual(first.status_code, 200, first.content)
        Order.objects.filter(pk=first.json()['id']).update(status='delivered_demo')
        self.assertEqual(self.order().json()['error']['code'], 'daily_limit')
        self.change(sender_daily_limit=None)
        self.assertEqual(self.order().status_code, 200)
        self.assertEqual(Order.objects.count(), 2)

    def test_unlimited_account_still_respects_recipient_optout_and_suspension(self):
        from .models import RecipientState
        from .privacy import digest
        self.configure(sender_limit=1)
        self.change(sender_daily_limit=0, rewrite_daily_limit=0)
        RecipientState.objects.create(phone_hash=digest('09901234567'), blocked=True)
        self.assertEqual(self.order().status_code, 409)
        Account.objects.filter(user=self.user).update(suspended=True)
        self.assertEqual(self.order('09901234568').status_code, 403)
        self.assertFalse(Order.objects.exists())

    @override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
        GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=1)
    def test_rewrite_override_preserves_usage_and_global_budget(self):
        from .freeform import reserve
        from .moderation import RewriteUnavailable
        self.change(rewrite_daily_limit=2)
        reserve(self.user);reserve(self.user)
        with self.assertRaises(APIError) as error:reserve(self.user)
        self.assertEqual(error.exception.code, 'rewrite_daily_limit')
        self.change(rewrite_daily_limit=0);reserve(self.user)
        self.assertEqual(RewriteUsage.objects.count(), 3)
        RewriteBudget.objects.update(reserved_requests=20)
        with self.assertRaises(RewriteUnavailable):reserve(self.user)
        self.change(rewrite_daily_limit=None)
        with self.assertRaises(APIError):reserve(self.user)
        self.assertEqual(RewriteUsage.objects.count(), 3)

    def test_permission_strict_types_and_audit_do_not_modify_balances(self):
        actor = get_user_model().objects.create_user(username='limited-operator', is_staff=True)
        account = Account.objects.get(user=self.user)
        with self.assertRaises(APIError):update_account_options(actor, account.pk, {'sender_daily_limit': 1000}, 'آزمون مجوز')
        actor.user_permissions.add(Permission.objects.get(codename='manage_account_limits'))
        actor = get_user_model().objects.get(pk=actor.pk)
        for value in [-1, True, '1000', 1.2, 1000001]:
            with self.subTest(value=value), self.assertRaises(APIError):
                update_account_options(actor, account.pk, {'sender_daily_limit': value}, 'آزمون مقدار')
        changed = update_account_options(actor, account.pk, {'sender_daily_limit': 1000, 'rewrite_daily_limit': 0}, 'سقف حساب انتخاب‌شده')
        self.assertEqual(changed.free_sends_remaining, 3)
        audit = OperatorAudit.objects.get(action='account_send_options')
        self.assertEqual(audit.before, {'sender_daily_limit': None, 'rewrite_daily_limit': None})
        self.assertEqual(audit.after, {'sender_daily_limit': 1000, 'rewrite_daily_limit': 0})

    def test_staff_api_exposes_null_zero_and_custom_and_requires_permission(self):
        self.configure(sender_limit=5)
        actor = get_user_model().objects.create_superuser(username='limits-admin', password='synthetic-admin-password')
        self.client.force_login(actor);self.client.get('/api/v1/manage/session')
        account = Account.objects.get(user=self.user)
        payload = {'action': 'account_limits', 'object_id': str(account.pk), 'reason': 'آزمون سقف حساب',
            'values': {'sender_daily_limit': 1000, 'rewrite_daily_limit': 0}}
        self.assertEqual(self.post('/manage/actions', payload).status_code, 200)
        account.refresh_from_db();self.assertEqual(account.sender_daily_limit, 1000);self.assertEqual(account.rewrite_daily_limit, 0)
        response = self.post('/manage/records/accounts', {})
        row = next(r for r in response.json()['rows'] if r['record_id']==str(account.pk))
        self.assertEqual(row['sender_daily_limit'], 1000);self.assertEqual(row['rewrite_daily_limit'], 0)
        payload['values']={'sender_daily_limit': None};self.assertEqual(self.post('/manage/actions', payload).status_code, 200)
        self.client.force_login(self.user)
        self.assertEqual(self.post('/manage/actions', payload).status_code, 403)
