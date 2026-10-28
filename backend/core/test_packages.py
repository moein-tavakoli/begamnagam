import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.conf import settings
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from . import tests as fixture
from .models import Account, CreditEntry, CreditPurchase, FinancialEvent, MessagePackage, Order, Outbox, PaymentAttempt, Preview, RecipientState
from .packages import begin_purchase, package_data, save_package, verify_purchase
from .providers import ProviderUnknown
from .providers.zarinpal import PaymentRequest, VerifiedPayment
from .services import APIError, create_order
from .tasks import deliver_message, expire_unpaid_orders


class PackageTests(TestCase):
    post, authenticate, preview, order = fixture.APITestCase.post, fixture.APITestCase.authenticate, fixture.APITestCase.preview, fixture.APITestCase.order

    def setUp(self):
        fixture.APITestCase.setUp(self)
        self.user = self.authenticate(free_sends=0)
        from .models import SafetyControl
        SafetyControl.objects.update_or_create(pk=1, defaults={"halted": False})
        Account.objects.filter(user=self.user).update(demo_sends_remaining=0)
        self.package = MessagePackage.objects.create(name='بستهٔ آزمون', message_count=3, price_toman=10000, active=True)
        self.manager = get_user_model().objects.create_user('package-manager', is_staff=True)
        self.manager.user_permissions.add(Permission.objects.get(codename='manage_message_packages'))
        self.staff = Client(); self.staff.force_login(self.manager)
        if settings.PAYMENT_BACKEND == 'zarinpal':
            from .limits import defaults
            limits = defaults(); limits.wallet_enabled = limits.gateway_enabled = True; limits.save()
            ready = patch('core.payment_options.gateway_problem', return_value='')
            ready.start(); self.addCleanup(ready.stop)

    def purchase(self, key=None, **extra):
        if settings.PAYMENT_BACKEND == 'zarinpal':
            from .models import SiteLimits
            from .payment_options import WALLET_TERMS_VERSION
            SiteLimits.objects.update_or_create(pk=1, defaults={'wallet_enabled': True, 'gateway_enabled': True})
            extra = {'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION, **extra}
            with patch('core.payment_options.gateway_problem', return_value=''):
                return self.post('/credit-purchases', {'package_id': self.package.pk, 'package_revision': self.package.revision, **extra}, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))
        return self.post('/credit-purchases', {'package_id': self.package.pk, 'package_revision': self.package.revision, **extra}, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def remaining(self, live=False):
        account = Account.objects.get(user=self.user)
        return account.purchased_sends_remaining if live else account.demo_sends_remaining

    def test_only_active_packages_are_public_and_staff_can_create_and_toggle(self):
        hidden = MessagePackage.objects.create(name='مخفی', message_count=1000, price_toman=2000000)
        visible = self.client.get('/api/v1/bootstrap').json()['message_packages']
        self.assertIn(self.package.pk, [p['id'] for p in visible]); self.assertNotIn(hidden.pk, [p['id'] for p in visible])
        response = self.staff.post('/api/v1/manage/packages', {'values': {'name': 'هزار پیام', 'message_count': 1000, 'price_toman': 2000000, 'active': True, 'sort_order': 2}, 'revision': 0, 'reason': 'Create requested bundle'}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        package = MessagePackage.objects.get(pk=response.json()['id'])
        values = {k: v for k, v in package_data(package).items() if k not in {'id', 'revision'}}; values['active'] = False
        save_package(self.manager, {'values': values, 'revision': package.revision, 'reason': 'Disable bundle'}, package.pk)
        self.assertNotIn(package.pk, [p['id'] for p in self.client.get('/api/v1/bootstrap').json()['message_packages']])

    def test_bad_package_values_stale_revision_permissions_and_csrf_fail(self):
        values = {k: v for k, v in package_data(self.package).items() if k not in {'id', 'revision'}}
        for key, value in [('message_count', 0), ('message_count', True), ('price_toman', -1), ('price_toman', 1.2), ('name', ''), ('active', 'true')]:
            with self.subTest(key=key, value=value), self.assertRaises(APIError):
                save_package(self.manager, {'values': {**values, key: value}, 'revision': 0, 'reason': 'Test invalid bundle'}, self.package.pk)
        with self.assertRaises(APIError): save_package(self.user, {'values': values, 'revision': 0, 'reason': 'Test permission'}, self.package.pk)
        save_package(self.manager, {'values': values, 'revision': 0, 'reason': 'First edit'}, self.package.pk)
        with self.assertRaises(APIError) as stale: save_package(self.manager, {'values': values, 'revision': 0, 'reason': 'Old edit'}, self.package.pk)
        self.assertEqual(stale.exception.code, 'settings_changed')
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.manager)
        self.assertEqual(csrf.post('/api/v1/manage/packages', {}, content_type='application/json').status_code, 403)

    def test_demo_purchase_is_repeatable_and_financially_separate_from_real_credits(self):
        key = uuid.uuid4(); first = self.purchase(key)
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()['status'], 'credited')
        self.assertEqual(self.purchase(key).json()['id'], first.json()['id'])
        self.assertEqual((self.remaining(), self.remaining(live=True)), (3, 0))
        self.assertEqual((CreditEntry.objects.count(), FinancialEvent.objects.count(), PaymentAttempt.objects.count()), (1, 1, 1))
        self.assertFalse(Order.objects.exists()); self.assertFalse(Outbox.objects.exists())

    def test_amount_quantity_and_inactive_or_changed_package_cannot_be_forged(self):
        for key in ('amount_toman', 'message_count', 'credited_at', 'status', 'owner_id'):
            self.assertEqual(self.purchase(**{key: 999}).status_code, 422)
        MessagePackage.objects.filter(pk=self.package.pk).update(active=False)
        self.assertEqual(self.purchase().json()['error']['code'], 'package_changed')
        MessagePackage.objects.filter(pk=self.package.pk).update(active=True, revision=1)
        self.assertEqual(self.purchase().json()['error']['code'], 'package_changed')
        self.assertEqual(self.remaining(), 0)

    @override_settings(PAYMENT_BACKEND='disabled', DEMO_MODE=False)
    def test_defining_or_activating_package_does_not_enable_live_checkout(self):
        self.assertEqual(self.purchase().json()['error']['code'], 'payment_disabled')
        self.assertFalse(self.client.get('/api/v1/bootstrap').json()['package_checkout_enabled'])
        self.assertFalse(CreditPurchase.objects.exists())

    def test_verified_phone_and_ownership_required_and_csrf_blocks_purchase(self):
        admin = Client(); admin.force_login(self.manager)
        self.assertEqual(self.post('/credit-purchases', {}, admin).status_code, 401)
        self.assertEqual(self.purchase().status_code, 200)
        purchase = CreditPurchase.objects.get()
        other = Client(); self.authenticate('09901234561', other)
        self.assertEqual(other.get(f'/api/v1/credit-purchases/{purchase.pk}').status_code, 404)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.user)
        self.assertEqual(self.post('/credit-purchases', {}, csrf).status_code, 403)

    @override_settings(DEMO_MODE=False, PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='live')
    def test_snapshot_survives_package_edit_and_duplicate_verified_callback_grants_once(self):
        with patch('core.packages.Zarinpal.request', return_value=PaymentRequest('A'+'x'*20, 'https://www.zarinpal.com/pg/StartPay/A'+'x'*20)) as request:
            result = self.purchase(); self.assertEqual(result.status_code, 200, result.content)
            request.assert_called_once_with(amount_toman=10000, callback_url='http://localhost:3000/api/v1/payments/return/zarinpal')
        purchase = CreditPurchase.objects.get(); attempt = PaymentAttempt.objects.get()
        MessagePackage.objects.filter(pk=self.package.pk).update(message_count=1000, price_toman=2000000, active=False)
        with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('12345')) as verify:
            verify_purchase(attempt.pk); verify_purchase(attempt.pk)
            verify.assert_called_once_with(authority=attempt.authority, amount_toman=10000)
        self.assertEqual(self.remaining(live=True), 3); self.assertEqual(self.remaining(), 0)
        self.assertEqual(FinancialEvent.objects.get().amount_toman, 10000)
        self.assertEqual(CreditEntry.objects.get().units, 3)
        self.assertFalse(Outbox.objects.exists())
        callback = self.client.get('/api/v1/payments/return/zarinpal', {'Authority': attempt.authority, 'Status': 'NOK'})
        self.assertIn('/credits?purchase='+str(purchase.pk), callback['Location'])

    @override_settings(DEMO_MODE=False, PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='live')
    def test_lost_request_and_fake_callback_never_grant_or_repeat_request(self):
        key = uuid.uuid4()
        with patch('core.packages.Zarinpal.request', side_effect=ProviderUnknown) as request:
            self.assertEqual(self.purchase(key).json()['status'], 'unknown')
            self.assertEqual(self.purchase(key).json()['status'], 'unknown')
            self.assertEqual(self.purchase().status_code, 409)
            request.assert_called_once()
        self.client.get('/api/v1/payments/return/zarinpal?Authority=FAKE&Status=OK')
        self.assertEqual(self.remaining(live=True), 0); self.assertFalse(FinancialEvent.objects.exists())

    @override_settings(DEMO_MODE=False, PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='live')
    def test_verification_timeout_and_mismatched_snapshot_do_not_grant(self):
        with patch('core.packages.Zarinpal.request', return_value=PaymentRequest('A'+'z'*20, 'https://www.zarinpal.com/pg/StartPay/A'+'z'*20)):
            self.purchase()
        attempt = PaymentAttempt.objects.get()
        with patch('core.packages.Zarinpal.verify', side_effect=ProviderUnknown): verify_purchase(attempt.pk)
        self.assertEqual(self.remaining(live=True), 0)
        PaymentAttempt.objects.filter(pk=attempt.pk).update(amount_toman=1)
        with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('9876')), self.assertRaises(APIError):
            verify_purchase(attempt.pk)
        self.assertEqual(self.remaining(live=True), 0)

    def test_only_purchase_balance_allows_non_gift_order_and_no_single_payment(self):
        quote = self.preview(); self.assertEqual(quote['price_toman'], 0)
        self.assertEqual(self.order(preview=quote).json()['error']['code'], 'credit_required')
        self.assertFalse(Order.objects.exists())
        self.purchase()
        key = uuid.uuid4(); order = self.order(preview=quote, key=key).json()
        self.assertTrue(order['uses_purchased_credit']); self.assertFalse(order['is_free'])
        self.assertEqual(self.remaining(), 2)
        self.assertEqual(self.order(preview=quote, key=key).json()['id'], order['id']); self.assertEqual(self.remaining(), 2)
        self.assertEqual(self.post(f"/orders/{order['id']}/payments", HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).json()['error']['code'], 'package_required')
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post(f"/orders/{order['id']}/confirm-credit").status_code, 200)
        self.assertEqual(Order.objects.get().status, 'delivered_demo')
        self.assertEqual(PaymentAttempt.objects.count(), 1)  # package receipt only

    def test_gifts_are_used_before_package_and_not_regranted_on_purchase(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=3)
        self.purchase(); self.order()
        account = Account.objects.get(user=self.user)
        self.assertEqual((account.free_sends_remaining, account.demo_sends_remaining), (2, 3))
        self.assertFalse(CreditEntry.objects.filter(kind='reserve').exists())

    def test_expired_and_definitive_failed_send_return_credit_once(self):
        self.purchase()
        first = self.order().json()
        Order.objects.filter(pk=first['id']).update(created_at=timezone.now()-timedelta(minutes=16))
        expire_unpaid_orders(); expire_unpaid_orders(); self.assertEqual(self.remaining(), 3)
        second = self.order(recipient='09901234568').json()
        with self.captureOnCommitCallbacks(execute=False): self.post(f"/orders/{second['id']}/confirm-credit")
        RecipientState.objects.update(blocked=True)
        deliver_message(Outbox.objects.get().pk); deliver_message(Outbox.objects.get().pk)
        self.assertEqual(self.remaining(), 3)
        self.assertEqual(CreditEntry.objects.filter(kind='release').count(), 2)
        self.assertEqual(FinancialEvent.objects.count(), 1)

    def test_unknown_delivery_holds_credit_and_demo_credit_cannot_fund_live_send(self):
        self.purchase(); first = self.order().json()
        Order.objects.filter(pk=first['id']).update(status='unknown', paid_at=timezone.now()-timedelta(days=2))
        expire_unpaid_orders(); self.assertEqual(self.remaining(), 2)
        with override_settings(DEMO_MODE=False, PAYMENT_BACKEND='disabled'):
            self.assertEqual(self.order(recipient='09901234568').json()['error']['code'], 'credit_required')
            self.assertEqual(self.client.get('/api/v1/bootstrap').json()['purchased_sends_remaining'], 0)

    @override_settings(DEMO_MODE=False, PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='live')
    def test_provider_reference_reuse_cannot_credit_another_purchase(self):
        with patch('core.packages.Zarinpal.request', return_value=PaymentRequest('A'+'a'*20, 'https://www.zarinpal.com/pg/StartPay/A'+'a'*20)):
            self.purchase()
        first = PaymentAttempt.objects.get()
        with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('778899')):
            verify_purchase(first.pk)
        with patch('core.packages.Zarinpal.request', return_value=PaymentRequest('A'+'b'*20, 'https://www.zarinpal.com/pg/StartPay/A'+'b'*20)):
            self.purchase()
        second = PaymentAttempt.objects.exclude(pk=first.pk).get()
        with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('778899')):
            verify_purchase(second.pk)
        self.assertEqual(self.remaining(live=True), 3)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)
        self.assertEqual(FinancialEvent.objects.count(), 1)
        second.refresh_from_db(); self.assertEqual(second.status, 'unknown')

    def test_database_rejects_negative_balance_and_payment_without_target(self):
        for operation in (lambda: Account.objects.filter(user=self.user).update(demo_sends_remaining=-1), lambda: PaymentAttempt.objects.create(amount_toman=10000)):
            with self.assertRaises(IntegrityError), transaction.atomic(): operation()

    def test_live_product_hides_nonlive_purchases_and_never_reuses_their_keys(self):
        key = uuid.uuid4(); result = self.purchase(key)
        self.assertEqual(result.status_code, 200, result.content)
        purchase = CreditPurchase.objects.get()
        with override_settings(DEMO_MODE=False, PROVIDER_ENVIRONMENT='live', PAYMENT_BACKEND='disabled'):
            self.assertEqual(self.client.get('/api/v1/credit-purchases').json()['purchases'], [])
            self.assertEqual(self.client.get(f'/api/v1/credit-purchases/{purchase.pk}').status_code, 404)
            with patch('core.packages.Zarinpal.request') as bank:
                response = self.post('/credit-purchases', {'package_id': self.package.pk, 'package_revision': 0},
                    HTTP_IDEMPOTENCY_KEY=str(key))
                self.assertEqual(response.json()['error']['code'], 'idempotency_conflict'); bank.assert_not_called()
        self.manager.is_superuser = True; self.manager.save()
        self.assertIn(str(purchase.pk), self.post('/manage/records/credit-purchases', {}, self.staff).content.decode())

    def test_nonlive_pending_attempt_does_not_block_live_checkout_or_verify(self):
        from .provider_services import verify_payment
        from .wallet import has_open_checkout
        purchase = CreditPurchase.objects.create(owner=self.user, package=self.package, idempotency_key=uuid.uuid4(),
            package_name=self.package.name, message_count=3, amount_toman=10000, environment='sandbox')
        attempt = PaymentAttempt.objects.create(purchase=purchase, amount_toman=10000, provider='zarinpal', environment='sandbox',
            status='pending', authority='A'+'s'*20, redirect_url='https://sandbox.zarinpal.com/pg/StartPay/A'+'s'*20)
        with override_settings(DEMO_MODE=False, PROVIDER_ENVIRONMENT='live'), patch('core.packages.Zarinpal.verify') as bank:
            self.assertFalse(has_open_checkout(self.user))
            verify_payment(attempt.pk); bank.assert_not_called()
            with patch('core.views.limited') as limit, patch('core.tasks.verify_provider_payment.delay') as queue:
                callback = self.client.get('/api/v1/payments/return/zarinpal', {'Authority': attempt.authority, 'Status': 'OK'})
                self.assertNotIn(str(purchase.pk), callback['Location']); queue.assert_not_called()
            self.assertFalse(CreditEntry.objects.exists()); self.assertFalse(FinancialEvent.objects.exists())


class PackageConcurrencyTests(TransactionTestCase):
    parallel = fixture.PostgreSQLConcurrencyTests.parallel

    def setUp(self):
        if connection.vendor != 'postgresql': self.skipTest('PostgreSQL row-lock integration required')
        from django.core.cache import cache
        cache.clear()
        from .models import SafetyControl
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})
        self.user = get_user_model().objects.create_user('credit-concurrent')
        Account.objects.create(user=self.user, phone_hash='credit-test', phone_cipher='', phone_masked='test', free_sends_remaining=0, demo_sends_remaining=1)
        self.package = MessagePackage.objects.create(name='Concurrent package', message_count=3, price_toman=10000, active=True)
        if settings.PAYMENT_BACKEND == 'zarinpal':
            from .limits import defaults
            limits = defaults(); limits.wallet_enabled = limits.gateway_enabled = True; limits.save()
            ready = patch('core.payment_options.gateway_problem', return_value='')
            ready.start(); self.addCleanup(ready.stop)

    def test_two_simultaneous_orders_cannot_spend_last_credit_twice(self):
        quotes = [Preview.objects.create(owner=self.user, session_key='session', category='appreciation', text='test', moderation_mode='template', price_toman=0, expires_at=timezone.now()+timedelta(minutes=10)) for _ in range(2)]
        submissions = iter([(quotes[i], f'0990123456{i}') for i in range(2)])
        def submit(user):
            quote, phone = next(submissions)
            try:
                create_order(user, 'session', {'preview_id': str(quote.pk), 'recipient_phone': phone}, str(uuid.uuid4()))
                return 'created'
            except APIError as error: return error.code
        self.assertCountEqual(self.parallel(submit), ['created', 'credit_required'])
        self.assertEqual(Account.objects.get(user=self.user).demo_sends_remaining, 0)
        self.assertEqual(Order.objects.count(), 1)

    def test_simultaneous_purchase_retries_grant_once(self):
        key = str(uuid.uuid4())
        data = {'package_id': self.package.pk, 'package_revision': 0}
        results = self.parallel(lambda user: begin_purchase(user, data, key)['id'])
        self.assertEqual(len(set(results)), 1)
        self.assertEqual(Account.objects.get(user=self.user).demo_sends_remaining, 4)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)

    @override_settings(DEMO_MODE=False, PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='live')
    def test_simultaneous_verified_callbacks_grant_once(self):
        from .models import SiteLimits
        from .payment_options import WALLET_TERMS_VERSION
        SiteLimits.objects.update_or_create(pk=1, defaults={'wallet_enabled': True, 'gateway_enabled': True})
        with patch('core.packages.Zarinpal.request', return_value=PaymentRequest('A'+'p'*20, 'https://www.zarinpal.com/pg/StartPay/A'+'p'*20)):
            with patch('core.payment_options.gateway_problem', return_value=''):
                begin_purchase(self.user, {'package_id': self.package.pk, 'package_revision': 0,
                    'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION}, str(uuid.uuid4()))
        attempt = PaymentAttempt.objects.get()
        with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('445566')):
            self.parallel(lambda user: verify_purchase(attempt.pk))
        self.assertEqual(Account.objects.get(user=self.user).purchased_sends_remaining, 3)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)
        self.assertEqual(FinancialEvent.objects.count(), 1)
