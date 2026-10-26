import io
import os
import subprocess
import sys
import uuid
from unittest.mock import patch

from django.core.management import call_command, CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings

from .models import Account, MessageDelivery, OperatorAudit, Order, Outbox, PaymentAttempt, SafetyControl, SpendBudget
from .providers.http import endpoint, ProviderDisabled
from .providers.kavenegar import SMSResult
from .provider_delivery import submit_delivery
from . import tests as legacy


class LiveSMSStartupTests(SimpleTestCase):
    def test_free_live_profile_needs_no_payment_credentials_and_rejects_unsafe_modes(self):
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='config.live_sms_settings', DEBUG='0', DEMO_MODE='0',
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
            KAVENEGAR_SENDER='10000000', KAVENEGAR_OTP_MODE='sms',
            PROVIDER_DAILY_BUDGET_RIAL='100000', SMS_MAX_COST_RIAL='20000', OTP_MAX_COST_RIAL='10000',
            TERMS_VERSION='v0.8.15-live-sms', PROVIDER_CONTRACT_APPROVED='0', REFUND_PROCESS_APPROVED='0',
            TERMS_APPROVED='0', PRIVACY_POLICY_APPROVED='0')
        cmd = [sys.executable, '-c', 'from config import live_sms_settings as s; assert s.SESSION_COOKIE_SECURE and s.SECURE_SSL_REDIRECT']
        result = subprocess.run(cmd, env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        for changes in [{'DEMO_MODE':'1'}, {'LIVE_PROVIDERS_ENABLED':'0'}, {'LOCAL_REAL_OTP_ENABLED':'1'},
                {'PAYMENT_BACKEND':'demo'}, {'PAYMENT_BACKEND':'zarinpal'}, {'SMS_BACKEND':'console'},
                {'SMS_RECIPIENT_POLICY':'pilot'}, {'SMS_MAX_COST_RIAL':'0'}, {'KAVENEGAR_API_KEY':''},
                {'KAVENEGAR_BASE_URL':'https://example.invalid'}, {'TRUST_DOMAIN_PROXY':'0'},
                {'CENTRAL_NGINX_IP':'8.8.8.8'}, {'DEMO_TEST_TOOLS_ENABLED':'1'}, {'TERMS_VERSION':'draft-old'}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(subprocess.run(cmd, env=dict(env, **changes), capture_output=True).returncode, 0)


class LiveGiftSMSTests(TestCase):
    post, authenticate, preview = legacy.APITestCase.post, legacy.APITestCase.authenticate, legacy.APITestCase.preview

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.user = self.authenticate(free_sends=None)
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted':False})
        config = override_settings(DEMO_MODE=False, LIVE_PROVIDERS_ENABLED=True, PROVIDER_NETWORK_MODE='external',
            PROVIDER_ENVIRONMENT='live', SMS_BACKEND='kavenegar', PAYMENT_BACKEND='disabled',
            OTP_BACKEND='kavenegar', LOCAL_REAL_OTP_ENABLED=False, SMS_RECIPIENT_POLICY='all',
            PILOT_RECIPIENT_HASHES=set(), TERMS_VERSION='v0.8.15-live-sms', SENDING_WINDOW_ENABLED=False,
            PROVIDER_DAILY_BUDGET_RIAL=100000, SMS_MAX_COST_RIAL=20000, OTP_MAX_COST_RIAL=10000)
        config.enable()
        self.addCleanup(config.disable)

    def make_order(self, recipient='09901234567', quote=None, key=None):
        quote = quote or self.preview(category='appreciation', text='تشکر از تو')
        return self.post('/orders', {'preview_id':quote['preview_id'], 'recipient_phone':recipient,
            'consent':True, 'terms_version':quote['terms_version']}, HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))

    def confirm(self, order):
        with self.captureOnCommitCallbacks(execute=False):
            result = self.post(f"/orders/{order['id']}/confirm-free")
        self.assertEqual(result.status_code, 200, result.content)

    def test_real_free_submission_for_unlisted_recipient_is_exact_and_idempotent(self):
        quote, key = self.preview(category='appreciation', text='تشکر از تو'), str(uuid.uuid4())
        order = self.make_order(quote=quote, key=key).json()
        self.assertEqual(self.make_order(quote=quote, key=key).json()['id'], order['id'])
        self.confirm(order)
        self.confirm(order)
        delivery = MessageDelivery.objects.get()
        self.assertEqual((delivery.provider, delivery.environment), ('kavenegar', 'live'))
        with patch('core.provider_delivery.Kavenegar.submit', return_value=SMSResult('accepted', '700', 1000)) as wire:
            submit_delivery(Outbox.objects.get().pk)
            submit_delivery(Outbox.objects.get().pk)
        wire.assert_called_once_with(phone='09901234567', text=quote['full_sms'], local_id=delivery.local_id)
        self.assertEqual(Order.objects.get().status, 'accepted')
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 2)
        self.assertEqual(SpendBudget.objects.get().reserved_rial, 20000)
        self.assertFalse(PaymentAttempt.objects.exists())

    def test_fourth_order_and_both_payment_endpoints_are_closed(self):
        for i in range(3):
            result = self.make_order(recipient=f'0990123456{i}')
            self.assertEqual(result.status_code, 200, result.content)
        result = self.make_order(recipient='09901234569')
        self.assertEqual(result.status_code, 409)
        self.assertEqual(result.json()['error']['code'], 'payment_disabled')
        order = Order.objects.first()
        self.assertEqual(self.post(f'/orders/{order.pk}/pay-demo').status_code, 503)
        self.assertEqual(self.post(f'/orders/{order.pk}/payments').status_code, 503)
        self.assertFalse(PaymentAttempt.objects.exists())
        self.assertEqual(Order.objects.count(), 3)
        with self.assertRaises(ProviderDisabled):
            endpoint('https://api.zarinpal.com', '/pg/v4/payment/request.json', {'api.zarinpal.com'})

    def test_old_demo_quote_and_awaiting_order_cannot_become_real(self):
        with override_settings(TERMS_VERSION='draft-old'):
            quote = self.preview(category='appreciation', text='تشکر از تو')
            old = self.make_order(quote=quote).json()
        self.assertEqual(self.make_order(quote=quote, recipient='09901234568').status_code, 409)
        self.assertEqual(self.post(f"/orders/{old['id']}/confirm-free").status_code, 409)
        self.assertFalse(Outbox.objects.exists())

    def test_definite_block_and_budget_exhaustion_do_not_touch_the_wire(self):
        from .models import RecipientState
        for i in range(2):
            order = self.make_order(recipient=f'0990123456{i}').json()
            self.confirm(order)
        first, second = list(Outbox.objects.order_by('created_at'))
        RecipientState.objects.filter(phone_hash=first.order.recipient_hash).update(blocked=True)
        from django.utils import timezone
        SpendBudget.objects.create(day=timezone.localdate(), limit_rial=100000, reserved_rial=100000)
        with patch('core.provider_delivery.Kavenegar.submit') as wire:
            submit_delivery(first.pk)
            submit_delivery(second.pk)
        wire.assert_not_called()
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_demo_gift_restoration_requires_halt_and_is_one_time(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=0)
        with self.assertRaises(CommandError):
            call_command('launch_live_gifts', stdout=io.StringIO())
        SafetyControl.objects.update(halted=True)
        for _ in range(2):
            call_command('launch_live_gifts', stdout=io.StringIO())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
        self.assertEqual(OperatorAudit.objects.filter(action='live_gift_launch').count(), 1)
        self.assertFalse(Outbox.objects.exists())

    def test_gift_restoration_skips_accounts_with_real_delivery(self):
        order = self.make_order().json()
        self.confirm(order)
        Outbox.objects.update(state='sent')
        SafetyControl.objects.update(halted=True)
        call_command('launch_live_gifts', stdout=io.StringIO())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 2)
