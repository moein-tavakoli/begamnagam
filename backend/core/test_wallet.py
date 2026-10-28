"""Isolated money-flow tests; no bank or SMS provider is contacted."""
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from . import tests as fixture
from .limits import defaults
from .models import (Account, CreditEntry, CreditPurchase, FinancialEvent, MessageDelivery,
    MessagePackage, OperationalAlert, Order, Outbox, PaymentAttempt, Preview, RecipientState, Refund, SiteLimits, WalletEntry, WalletTopup)
from .payment_options import WALLET_TERMS_VERSION
from .providers import ProviderUnknown
from .providers.zarinpal import PaymentRequest, VerifiedPayment
from .services import APIError
from .wallet import begin_topup, credit_refund, movement, pay_order, return_order, verify_topup


@override_settings(DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console', PAYMENT_BACKEND='zarinpal',
    PROVIDER_ENVIRONMENT='sandbox', PROVIDER_NETWORK_MODE='disabled', LIVE_PROVIDERS_ENABLED=False,
    SENDING_WINDOW_ENABLED=False)
class WalletTests(TestCase):
    post, authenticate = fixture.APITestCase.post, fixture.APITestCase.authenticate

    def setUp(self):
        fixture.APITestCase.setUp(self)
        self.user = self.authenticate()
        Account.objects.filter(user=self.user).update(demo_sends_remaining=0)
        limits = defaults(); limits.wallet_enabled = limits.gateway_enabled = True
        limits.otp_max_cost_rial, limits.sms_max_cost_rial = 10000, 20000; limits.save()
        self.ready = patch('core.payment_options.gateway_problem', return_value='')
        self.ready.start(); self.addCleanup(self.ready.stop)
        self.authority = 'A' + 'w'*20

    def balance(self, live=False):
        account = Account.objects.get(user=self.user)
        return account.wallet_balance_toman if live else account.demo_wallet_balance_toman

    def topup(self, amount=10000, key=None, **extra):
        return self.post('/wallet/topups', {'amount_toman': amount, 'consent': True,
            'terms_version': WALLET_TERMS_VERSION, **extra}, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def fund(self, amount=10000):
        with patch('core.wallet.Zarinpal.request', return_value=PaymentRequest(self.authority, 'https://www.zarinpal.com/pg/StartPay/'+self.authority)):
            response = self.topup(amount)
        self.assertEqual(response.status_code, 200, response.content)
        attempt = PaymentAttempt.objects.get(wallet_topup_id=response.json()['id'])
        with patch('core.wallet.Zarinpal.verify', return_value=VerifiedPayment(str(uuid.uuid4().int)[:25])):
            verify_topup(attempt.pk)
        return attempt

    def order(self, method='wallet', recipient='09901234567'):
        # Historical fixture only. The public API can no longer create money orders.
        from .privacy import digest, encrypt, mask
        quote = self.post('/messages/preview', {'category': 'body', 'text': 'تنت بو میده'})
        self.assertEqual(quote.status_code, 200, quote.content)
        preview = Preview.objects.get(pk=quote.json()['preview_id'])
        preview.payment_method, preview.price_toman, preview.wallet_policy_version = method, 2000, WALLET_TERMS_VERSION
        preview.save()
        RecipientState.objects.get_or_create(phone_hash=digest(recipient))
        return Order.objects.create(owner=self.user, preview=preview, idempotency_key=uuid.uuid4(),
            category=preview.category, text=preview.text, full_sms=preview.full_sms, amount_toman=2000,
            recipient_hash=digest(recipient), recipient_cipher=encrypt(recipient), recipient_masked=mask(recipient),
            payment_method=method, wallet_refund_consent=True,
            consent_at=timezone.now(), terms_version=preview.terms_version)

    def historical_wallet_payment(self, order):
        with transaction.atomic():
            movement(self.user.account, 'order_debit', order.amount_toman, 'demo', order=order)
            Order.objects.filter(pk=order.pk).update(paid_at=timezone.now(), payment_mode='wallet', status='queued')
            MessageDelivery.objects.create(order=order, provider='demo', environment='demo', status='queued')
            Outbox.objects.create(order=order, available_at=timezone.now())

    def test_topup_credit_requires_server_verification_and_is_idempotent(self):
        key = uuid.uuid4()
        with patch('core.wallet.Zarinpal.request', return_value=PaymentRequest(self.authority, 'https://www.zarinpal.com/pg/StartPay/'+self.authority)) as request:
            first = self.topup(key=key); second = self.topup(key=key)
            self.assertEqual(first.json()['id'], second.json()['id'])
            self.assertEqual(self.balance(), 0)
            self.assertEqual(self.topup(20000, key).status_code, 409)
            self.assertEqual(self.topup().status_code, 409)
            request.assert_called_once_with(amount_toman=10000, callback_url='http://localhost:3000/api/v1/payments/return/zarinpal')
        self.client.get('/api/v1/payments/return/zarinpal?Authority=FAKE&Status=OK')
        self.assertEqual(self.balance(), 0)
        attempt = PaymentAttempt.objects.get()
        with patch('core.wallet.Zarinpal.verify', return_value=VerifiedPayment('123456')) as verify:
            callback = self.client.get('/api/v1/payments/return/zarinpal', {'Authority': self.authority, 'Status': 'NOK'})
            verify_topup(attempt.pk)
            verify.assert_called_once_with(authority=self.authority, amount_toman=10000)
        self.assertIn('/wallet?topup=', callback['Location'])
        self.assertEqual((self.balance(), self.balance(live=True)), (10000, 0))
        self.assertEqual((WalletEntry.objects.count(), FinancialEvent.objects.count()), (1, 1))

    def test_lost_request_and_unknown_verification_cannot_mint_or_resubmit(self):
        key = uuid.uuid4()
        with patch('core.wallet.Zarinpal.request', side_effect=ProviderUnknown) as request:
            self.assertEqual(self.topup(key=key).json()['status'], 'unknown')
            self.assertEqual(self.topup(key=key).json()['status'], 'unknown')
            request.assert_called_once()
        attempt = PaymentAttempt.objects.get()
        PaymentAttempt.objects.filter(pk=attempt.pk).update(authority=self.authority)
        with patch('core.wallet.Zarinpal.verify', side_effect=ProviderUnknown): verify_topup(attempt.pk)
        self.assertEqual(self.balance(), 0); self.assertFalse(WalletEntry.objects.exists())

    def test_mismatched_amount_and_environment_never_credit(self):
        with patch('core.wallet.Zarinpal.request', return_value=PaymentRequest(self.authority, 'https://www.zarinpal.com/pg/StartPay/'+self.authority)):
            self.topup()
        attempt = PaymentAttempt.objects.get()
        PaymentAttempt.objects.filter(pk=attempt.pk).update(environment='live')
        with patch('core.wallet.Zarinpal.verify') as verify:
            verify_topup(attempt.pk); verify.assert_not_called()
        PaymentAttempt.objects.filter(pk=attempt.pk).update(environment='sandbox', amount_toman=1)
        with patch('core.wallet.Zarinpal.verify', return_value=VerifiedPayment('123456')), self.assertRaises(APIError): verify_topup(attempt.pk)
        self.assertEqual(self.balance(), 0)

    def test_reused_receipt_cannot_fund_second_wallet_charge(self):
        first = self.fund()
        self.authority = 'A'+'z'*20
        with patch('core.wallet.Zarinpal.request', return_value=PaymentRequest(self.authority, 'https://www.zarinpal.com/pg/StartPay/'+self.authority)):
            result = self.topup()
        second = PaymentAttempt.objects.get(wallet_topup_id=result.json()['id'])
        with patch('core.wallet.Zarinpal.verify', return_value=VerifiedPayment(first.provider_reference or PaymentAttempt.objects.get(pk=first.pk).provider_reference)):
            verify_topup(second.pk)
        self.assertEqual(self.balance(), 10000)
        self.assertEqual(WalletEntry.objects.count(), 1)
        self.assertTrue(OperationalAlert.objects.filter(code='wallet_receipt_conflict', active=True).exists())

    def test_historical_wallet_payment_replay_never_debits_again(self):
        self.fund(); order = self.order()
        self.historical_wallet_payment(order)
        SiteLimits.objects.update(price_toman=9000)
        with self.captureOnCommitCallbacks(execute=False):
            first = self.post(f'/orders/{order.pk}/pay-wallet')
            second = self.post(f'/orders/{order.pk}/pay-wallet')
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(self.balance(), 10000-order.amount_toman)
        self.assertEqual(WalletEntry.objects.filter(kind='order_debit').count(), 1)
        self.assertEqual(Outbox.objects.filter(order=order).count(), 1)
        self.assertEqual(FinancialEvent.objects.count(), 1)  # no second cash capture
        self.assertEqual(first.json()['financial_status'], 'wallet_paid')

    def test_insufficient_wallet_is_atomic_and_cannot_spend_demo_money_live(self):
        self.fund(1); order = self.order()
        self.assertEqual(self.post(f'/orders/{order.pk}/pay-wallet').json()['error']['code'], 'package_required')
        self.assertEqual(self.balance(), 1); self.assertFalse(Outbox.objects.exists())
        self.assertFalse(WalletEntry.objects.filter(kind='order_debit').exists())
        with override_settings(DEMO_MODE=False, SMS_BACKEND='kavenegar', LIVE_PROVIDERS_ENABLED=True, PROVIDER_NETWORK_MODE='external'):
            self.assertEqual(self.client.get('/api/v1/wallet').json()['balance_toman'], '0')
            self.assertEqual(self.client.get('/api/v1/wallet').json()['entries'], [])
            order.consent_at = timezone.now(); order.terms_version = order.preview.terms_version; order.save()
            with self.assertRaises(APIError) as failure: pay_order(self.user, order.pk)
            self.assertEqual(failure.exception.code, 'package_required')

    def test_failed_wallet_send_returns_exact_debit_once_even_when_disabled(self):
        self.fund(); order = self.order()
        self.historical_wallet_payment(order)
        SiteLimits.objects.update(wallet_enabled=False, gateway_enabled=False, price_toman=9000)
        Order.objects.filter(pk=order.pk).update(status='failed')
        return_order(order, 'failed'); return_order(order, 'failed')
        self.assertEqual(self.balance(), 10000)
        self.assertEqual(WalletEntry.objects.filter(kind='order_return').get().amount_toman, order.amount_toman)
        self.assertEqual(self.post(f'/orders/{order.pk}/pay-wallet').status_code, 200)
        self.assertEqual(WalletEntry.objects.filter(kind='order_debit').count(), 1)

    def test_delivery_failure_integration_returns_wallet_and_never_calls_bank_reverse(self):
        from .tasks import deliver_message
        self.fund(); order = self.order()
        self.historical_wallet_payment(order)
        from .models import RecipientState
        RecipientState.objects.filter(phone_hash=order.recipient_hash).update(blocked=True)
        with patch('core.provider_services.Zarinpal.reverse') as reverse:
            deliver_message(Outbox.objects.get().pk); deliver_message(Outbox.objects.get().pk)
            reverse.assert_not_called()
        self.assertEqual(self.balance(), 10000)
        self.assertEqual(WalletEntry.objects.filter(kind='order_return').count(), 1)

    def test_unknown_requires_24h_and_success_cannot_be_refunded(self):
        self.fund(); order = self.order()
        self.historical_wallet_payment(order)
        with self.assertRaises(APIError): return_order(order, 'unknown_deadline')
        MessageDelivery.objects.filter(order=order).update(status='unknown', created_at=timezone.now()-timedelta(hours=25))
        Order.objects.filter(pk=order.pk).update(status='unknown')
        return_order(order, 'unknown_deadline'); return_order(order, 'unknown_deadline')
        self.assertEqual(self.balance(), 10000)

    def test_gateway_late_success_credits_wallet_without_changing_legacy_refund_rules(self):
        from .provider_services import begin_payment, verify_payment
        order = self.order('gateway')
        attempt = PaymentAttempt.objects.create(order=order, amount_toman=order.amount_toman,
            provider='zarinpal', environment='sandbox', authority=self.authority, status='pending', return_to_wallet=True)
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now()-timedelta(hours=1))
        SiteLimits.objects.update(gateway_enabled=False, wallet_enabled=False)
        with patch('core.provider_services.Zarinpal.verify', return_value=VerifiedPayment('775544')), patch('core.provider_services.Zarinpal.reverse') as reverse:
            verify_payment(attempt.pk); verify_payment(attempt.pk); reverse.assert_not_called()
        self.assertEqual(self.balance(), order.amount_toman)
        self.assertEqual(WalletEntry.objects.filter(kind='payment_return').count(), 1)
        self.assertEqual(Refund.objects.get().status, 'refunded'); self.assertFalse(Outbox.objects.exists())

    def test_wallet_package_purchase_is_atomic_and_idempotent(self):
        self.fund()
        package = MessagePackage.objects.create(name='سه پیام', message_count=3, price_toman=9000, active=True)
        key = str(uuid.uuid4()); payload = {'package_id': package.pk, 'package_revision': 0, 'payment_method': 'wallet',
            'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION}
        first = self.post('/credit-purchases', payload, HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()['status'], 'credited')
        self.assertEqual(self.post('/credit-purchases', payload, HTTP_IDEMPOTENCY_KEY=key).json()['id'], first.json()['id'])
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(Account.objects.get(user=self.user).demo_sends_remaining, 3)
        self.assertEqual(WalletEntry.objects.filter(kind='package_debit').count(), 1)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)
        payload['package_revision'] = package.revision
        failure = self.post('/credit-purchases', payload, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(failure.json()['error']['code'], 'wallet_insufficient')
        self.assertEqual(CreditPurchase.objects.count(), 1)

    def test_credited_package_cannot_also_be_refunded_to_wallet(self):
        package = MessagePackage.objects.create(name='سه پیام', message_count=3, price_toman=10000, active=True)
        purchase = CreditPurchase.objects.create(owner=self.user, package=package, idempotency_key=uuid.uuid4(),
            package_name=package.name, message_count=3, amount_toman=10000, environment='sandbox', credited_at=timezone.now())
        attempt = PaymentAttempt.objects.create(purchase=purchase, amount_toman=10000, status='verified', return_to_wallet=True, provider='zarinpal', environment='sandbox')
        refund = Refund.objects.create(payment=attempt, amount_toman=10000, reason_code='test')
        with self.assertRaises(APIError): credit_refund(refund.pk)
        self.assertEqual(self.balance(), 0)

    def test_unallocatable_verified_package_returns_money_to_wallet_once(self):
        from .packages import begin_purchase, verify_purchase, purchase_data
        package = MessagePackage.objects.create(name='سه پیام', message_count=3, price_toman=10000, active=True)
        data = {'package_id': package.pk, 'package_revision': 0, 'payment_method': 'gateway',
            'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION}
        with patch('core.packages.Zarinpal.request', return_value=PaymentRequest(self.authority, 'https://www.zarinpal.com/pg/StartPay/'+self.authority)):
            result = begin_purchase(self.user, data, str(uuid.uuid4()))
        attempt = PaymentAttempt.objects.get(purchase_id=result['id'])
        Account.objects.filter(user=self.user).update(demo_sends_remaining=2147483647)
        with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('886644')) as verify:
            verify_purchase(attempt.pk); verify_purchase(attempt.pk); verify.assert_called_once()
        self.assertEqual(self.balance(), 10000)
        self.assertEqual(purchase_data(CreditPurchase.objects.get())['status'], 'wallet_returned')
        self.assertFalse(CreditEntry.objects.exists())
        self.assertEqual(FinancialEvent.objects.filter(kind='payment').count(), 1)
        self.assertEqual(FinancialEvent.objects.filter(kind='refund').count(), 1)

    def test_permissions_csrf_ownership_and_strict_inputs(self):
        self.assertEqual(Client().get('/api/v1/wallet').status_code, 401)
        for extra in ({'amount_toman': True}, {'amount_toman': 0}, {'amount_toman': 1.5}, {'amount_toman': 2147483648},
                {'consent': False}, {'terms_version': 'old'}, {'owner_id': self.user.pk}, {'balance_toman': 10000}):
            self.assertEqual(self.topup(**extra).status_code, 422)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.user)
        self.assertEqual(self.post('/wallet/topups', {}, csrf).status_code, 403)
        self.fund(); topup = WalletTopup.objects.get()
        other = Client(); self.authenticate('09901234561', other)
        self.assertEqual(other.get(f'/api/v1/wallet/topups/{topup.pk}').status_code, 404)
        order = self.order()
        self.assertEqual(self.post(f'/orders/{order.pk}/pay-wallet', {}, other).status_code, 404)
        self.assertEqual(self.post(f'/orders/{order.pk}/pay-wallet', {'amount_toman': 1}).status_code, 422)
        payload = self.client.get('/api/v1/wallet')
        self.assertEqual(payload['Cache-Control'], 'no-store')
        for private in ('authority', 'provider_reference', 'phone_hash', 'original_text', self.authority):
            self.assertNotIn(private, payload.content.decode())
        self.assertFalse(payload.json()['withdrawable'])
        self.assertEqual(self.post('/wallet/withdraw', {'amount_toman': 1}).status_code, 404)

    def test_admin_switches_are_audited_versioned_and_gateway_requires_configuration(self):
        admin = get_user_model().objects.create_user('wallet-manager', is_staff=True)
        admin.user_permissions.add(Permission.objects.get(codename='manage_site_limits'))
        staff = Client(); staff.force_login(admin)
        current = staff.get('/api/v1/manage/limits').json()
        response = self.post('/manage/limits', {'revision': current['revision'], 'reason': 'Disable payment methods',
            'values': {'gateway_enabled': False, 'wallet_enabled': False}}, staff)
        self.assertEqual(response.status_code, 200, response.content)
        with patch('core.payment_options.gateway_problem', return_value='Missing merchant'):
            result = self.post('/manage/limits', {'revision': response.json()['revision'], 'reason': 'Enable gateway',
                'values': {'gateway_enabled': True, 'wallet_enabled': True}}, staff)
        self.assertEqual(result.json()['error']['code'], 'gateway_not_ready')
        result = self.post('/manage/limits', {'revision': response.json()['revision'], 'reason': 'Invalid switch state',
            'values': {'gateway_enabled': True}}, staff)
        self.assertEqual(result.status_code, 422)
        self.assertEqual(self.topup().status_code, 409)
        self.assertEqual(self.post('/manage/limits', {'revision': 1, 'reason': 'Member change', 'values': {'wallet_enabled': True}}).status_code, 403)

    def test_database_rejects_negative_balance_and_orphan_movements(self):
        for operation in (lambda: Account.objects.filter(user=self.user).update(wallet_balance_toman=-1),
                lambda: WalletEntry.objects.create(account=self.user.account, kind='topup', amount_toman=1, balance_after_toman=1, environment='live')):
            with self.assertRaises(IntegrityError), transaction.atomic(): operation()

    def test_money_quotes_are_rejected_before_ai_even_with_both_switches_on(self):
        for gifts in (0, 3):
            Account.objects.filter(user=self.user).update(free_sends_remaining=gifts)
            with patch('core.gapgpt.rewrite_message') as ai, patch('core.ollama_rewrite.rewrite_message') as local:
                for method in ('wallet', 'gateway'):
                    response = self.post('/messages/preview', {'category': 'body', 'text': 'تنت بو میده', 'payment_method': method})
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json()['error']['code'], 'package_required')
                ai.assert_not_called(); local.assert_not_called()
        self.assertFalse(Preview.objects.exists()); self.assertFalse(PaymentAttempt.objects.exists())

    def test_legacy_money_quote_cannot_create_new_order_even_with_consent(self):
        for method in ('wallet', 'gateway'):
            quote = self.post('/messages/preview', {'category': 'body', 'text': 'تنت بو میده'}).json()
            Preview.objects.filter(pk=quote['preview_id']).update(payment_method=method, price_toman=2000,
                wallet_policy_version=WALLET_TERMS_VERSION)
            response = self.post('/orders', {'preview_id': quote['preview_id'], 'recipient_phone': '09901234567',
                'consent': True, 'terms_version': settings.TERMS_VERSION, 'wallet_consent': True},
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['error']['code'], 'package_required')
        self.assertFalse(Order.objects.exists()); self.assertFalse(WalletEntry.objects.exists())

    def test_wallet_balance_does_not_replace_package_credit_or_fund_direct_order(self):
        self.fund()
        quote = self.post('/messages/preview', {'category': 'body', 'text': 'تنت بو میده'}).json()
        payload = {'preview_id': quote['preview_id'], 'recipient_phone': '09901234567'}
        response = self.post('/orders', payload, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.json()['error']['code'], 'credit_required')
        for extra in ({'price_toman': 1}, {'amount_toman': 1}, {'payment_method': 'wallet'}):
            self.assertEqual(self.post('/orders', {**payload, **extra}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code, 422)
        self.assertEqual(self.balance(), 10000); self.assertFalse(Order.objects.exists())

    def test_new_direct_charge_is_closed_in_http_and_all_service_entrypoints(self):
        from .provider_services import begin_payment
        from .services import pay_order as demo_pay
        self.fund(); wallet_order = self.order(); gateway_order = self.order('gateway', '09901234568')
        with patch('core.provider_services.Zarinpal.request') as bank:
            for method, order in [('pay-wallet', wallet_order), ('payments', gateway_order)]:
                response = self.post(f'/orders/{order.pk}/{method}', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
                self.assertEqual(response.json()['error']['code'], 'package_required')
            for operation in (lambda: pay_order(self.user, wallet_order.pk), lambda: begin_payment(self.user, gateway_order.pk, str(uuid.uuid4()))):
                with self.assertRaises(APIError) as failure: operation()
                self.assertEqual(failure.exception.code, 'package_required')
            with override_settings(PAYMENT_BACKEND='demo'):
                with self.assertRaises(APIError) as failure: demo_pay(self.user, gateway_order.pk)
                self.assertEqual(failure.exception.code, 'package_required')
            bank.assert_not_called()
        self.assertEqual(self.balance(), 10000)
        self.assertFalse(WalletEntry.objects.filter(kind='order_debit').exists()); self.assertFalse(Outbox.objects.exists())
        self.assertFalse(PaymentAttempt.objects.filter(order__isnull=False).exists())

    def test_existing_gateway_authority_resumes_without_a_new_bank_request(self):
        order = self.order('gateway')
        attempt = PaymentAttempt.objects.create(order=order, amount_toman=2000, provider='zarinpal', environment='sandbox',
            status='pending', authority=self.authority, redirect_url='https://sandbox.zarinpal.com/pg/StartPay/'+self.authority)
        with patch('core.provider_services.Zarinpal.request') as bank:
            first = self.post(f'/orders/{order.pk}/payments', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertEqual(first.json()['attempt_id'], str(attempt.pk)); bank.assert_not_called()
            with override_settings(DEMO_MODE=False, PROVIDER_ENVIRONMENT='live'):
                self.assertEqual(self.post(f'/orders/{order.pk}/payments').json()['error']['code'], 'payment_reconciliation')

    def test_nonlive_topup_key_cannot_resume_in_live_product(self):
        key = uuid.uuid4()
        with patch('core.wallet.Zarinpal.request', side_effect=ProviderUnknown): self.topup(key=key)
        with override_settings(DEMO_MODE=False, PROVIDER_ENVIRONMENT='live'), patch('core.wallet.Zarinpal.request') as bank:
            self.assertEqual(self.topup(key=key).json()['error']['code'], 'idempotency_conflict')
            self.assertEqual(self.client.get('/api/v1/wallet').json()['topups'], [])
            bank.assert_not_called()


@override_settings(DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console', PAYMENT_BACKEND='zarinpal',
    PROVIDER_ENVIRONMENT='sandbox', PROVIDER_NETWORK_MODE='disabled', SENDING_WINDOW_ENABLED=False)
class WalletConcurrencyTests(TransactionTestCase):
    parallel = fixture.PostgreSQLConcurrencyTests.parallel

    def setUp(self):
        if connection.vendor != 'postgresql': self.skipTest('PostgreSQL row locks required')
        cache.clear()
        self.user = get_user_model().objects.create_user('wallet-concurrent')
        self.account = Account.objects.create(user=self.user, phone_hash='wallet-user', phone_cipher='', phone_masked='test',
            free_sends_remaining=0)
        limits = defaults(); limits.wallet_enabled = limits.gateway_enabled = True; limits.save()
        ready = patch('core.payment_options.gateway_problem', return_value=''); ready.start(); self.addCleanup(ready.stop)

    def test_simultaneous_topup_callbacks_credit_once(self):
        topup = WalletTopup.objects.create(owner=self.user, idempotency_key=uuid.uuid4(), amount_toman=10000,
            environment='sandbox', consent_at=timezone.now(), terms_version=WALLET_TERMS_VERSION)
        attempt = PaymentAttempt.objects.create(wallet_topup=topup, amount_toman=10000, environment='sandbox',
            provider='zarinpal', authority='A'+'c'*20, status='pending')
        with patch('core.wallet.Zarinpal.verify', return_value=VerifiedPayment('987654')):
            self.parallel(lambda user: verify_topup(attempt.pk))
        self.assertEqual(Account.objects.get(pk=self.account.pk).demo_wallet_balance_toman, 10000)
        self.assertEqual(WalletEntry.objects.count(), 1)
        self.assertEqual(FinancialEvent.objects.count(), 1)

    def test_two_simultaneous_spends_cannot_overdraw_balance(self):
        from .packages import begin_purchase
        Account.objects.filter(pk=self.account.pk).update(demo_wallet_balance_toman=2500)
        package = MessagePackage.objects.create(name='Concurrent wallet package', message_count=3, price_toman=2000, active=True)
        data = {'package_id': package.pk, 'package_revision': 0, 'payment_method': 'wallet',
            'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION}
        def pay(user):
            try:
                return begin_purchase(user, data, str(uuid.uuid4()))['status']
            except APIError as error: return error.code
        self.assertCountEqual(self.parallel(pay), ['credited', 'wallet_insufficient'])
        self.assertEqual(Account.objects.get(pk=self.account.pk).demo_wallet_balance_toman, 500)
        self.assertEqual(WalletEntry.objects.filter(kind='package_debit').count(), 1)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)
        self.assertFalse(Outbox.objects.exists())
