import uuid
from datetime import timedelta
from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.management import call_command
from django.db import connections
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from .models import Account, CreditEntry, CreditPurchase, MessageAttempt, Order, Outbox, Preview
from .payment_options import WALLET_TERMS_VERSION
from .privacy import decrypt, mask
from .providers.zarinpal import PaymentRequest, VerifiedPayment
from .test_manual_payments import ManualFixture


class PurchaseResumeTests(ManualFixture, TestCase):
    phone = '09901234567'

    def setUp(self):
        super().setUp()
        Account.objects.filter(user=self.user).update(free_sends_remaining=0)

    def preview(self, **target):
        response = self.post('/messages/preview', {
            'category': 'appreciation', 'text': 'از همراهی‌ات ممنونم!', **(target or {'recipient_phone': self.phone}),
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def resume(self, preview, client=None):
        return (client or self.client).get('/api/v1/messages/preview/' + preview['preview_id'])

    def buy(self, preview=None, method='gateway', key=None, client=None):
        data = {'package_id': self.package.pk, 'package_revision': self.package.revision, 'payment_method': method,
                'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION}
        if preview:
            data['resume_preview_id'] = preview['preview_id']
        return self.post('/credit-purchases', data, client, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def order(self, preview, key=None, client=None, **changes):
        return self.post('/orders', {'preview_id': preview['preview_id'], 'terms_version': preview['terms_version'],
                         'consent': True, **changes}, client, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def detail(self, purchase, client=None):
        return (client or self.client).get('/api/v1/credit-purchases/' + purchase['id']).json()

    def test_verified_purchase_returns_the_exact_review_for_explicit_confirmation(self):
        preview = self.preview()
        self.assertGreaterEqual(self.order(preview).status_code, 400)
        purchase = self.buy(preview)
        self.assertEqual(purchase.status_code, 200, purchase.content)
        self.assertEqual((purchase.json()['resume_status'], purchase.json()['resume_preview_id']),
                         ('ready', preview['preview_id']))
        result = self.resume(preview)
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertEqual(result.json(), {**preview, 'recipient_masked': mask(self.phone), 'is_shared_destination': False})
        self.assertNotIn(self.phone, result.content.decode())
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(self.order(preview, consent=False).json()['error']['code'], 'consent_required')
        explicit = self.order(preview, consent=False, recipient_phone=self.phone)
        self.assertEqual(explicit.json()['error']['code'], 'consent_required')
        self.assertEqual(self.order(preview, terms_version='old').json()['error']['code'], 'consent_required')
        key = uuid.uuid4()
        first = self.order(preview, key=key)
        self.assertEqual(first.status_code, 200, first.content)
        item = Order.objects.get(pk=first.json()['id'])
        self.assertEqual(decrypt(item.recipient_cipher), self.phone)
        self.assertEqual(item.full_sms, Preview.objects.get(pk=preview['preview_id']).full_sms)
        self.assertTrue(item.consent_at)
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(self.order(preview, key=key).json()['id'], first.json()['id'])
        self.assertEqual(CreditEntry.objects.filter(kind='reserve').count(), 1)
        self.assertEqual(self.resume(preview).status_code, 409)
        self.assertEqual(self.detail(purchase.json())['resume_status'], 'unavailable')
        self.assertIsNone(self.detail(purchase.json())['resume_preview_id'])

    def test_other_sessions_and_accounts_cannot_attach_or_reopen_the_preview(self):
        preview = self.preview()
        purchase = self.buy(preview)
        self.assertEqual(purchase.status_code, 200, purchase.content)
        self.assertEqual(self.resume(preview, Client()).status_code, 401)
        fresh_session = Client()
        fresh_session.force_login(self.user)
        stranger = Client()
        self.authenticate('09901234568', stranger)
        for client in (fresh_session, stranger):
            self.assertEqual(self.resume(preview, client).status_code, 404)
            self.assertEqual(self.buy(preview, client=client).status_code, 404)
            self.assertGreaterEqual(self.order(preview, client=client).status_code, 400)
        v2_preview = '/api/v2/message-previews/' + preview['preview_id']
        self.assertEqual(fresh_session.get(v2_preview).status_code, 404)
        v2_order = fresh_session.post('/api/v2/messages', {
            'preview_id': preview['preview_id'], 'recipient_phone': self.phone, 'terms_version': preview['terms_version'],
            'consent': True}, content_type='application/json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(v2_order.status_code, 404)
        self.assertIsNone(self.detail(purchase.json(), fresh_session)['resume_preview_id'])
        self.assertFalse(Order.objects.exists())
        self.assertEqual(CreditPurchase.objects.count(), 1)
        Account.objects.filter(user=self.user).update(deletion_requested_at=timezone.now(), suspended=True)
        self.assertGreaterEqual(self.resume(preview).status_code, 400)
        self.assertIsNone(self.detail(purchase.json())['resume_preview_id'])

    def test_expiry_cleanup_keeps_payment_and_idempotent_retry_but_retires_target(self):
        preview = self.preview()
        key = uuid.uuid4()
        purchase = self.buy(preview, key=key)
        self.assertEqual(purchase.status_code, 200, purchase.content)
        another = self.preview()
        self.assertEqual(self.buy(another, key=key).json()['error']['code'], 'idempotency_conflict')
        Preview.objects.filter(pk=preview['preview_id']).update(expires_at=timezone.now()-timedelta(days=2))
        self.assertEqual(self.resume(preview).status_code, 409)
        self.assertEqual(self.buy(preview).status_code, 409)
        call_command('prune_private_data', stdout=StringIO())
        self.assertFalse(Preview.objects.filter(pk=preview['preview_id']).exists())
        details = self.detail(purchase.json())
        self.assertEqual((details['status'], details['resume_status'], details['resume_preview_id']),
                         ('credited', 'unavailable', None))
        self.assertEqual(self.buy(preview, key=key).json()['id'], purchase.json()['id'])
        self.assertEqual(self.buy(another, key=key).json()['error']['code'], 'idempotency_conflict')
        self.assertEqual(CreditEntry.objects.count(), 1)
        unlinked = self.buy()
        self.assertEqual(unlinked.status_code, 200, unlinked.content)
        self.assertIsNone(unlinked.json()['resume_status'])

    def test_gift_preview_cannot_start_a_bound_purchase(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=1)
        gift = self.preview()
        self.assertTrue(gift['is_free'])
        for method in ('card', 'gateway'):
            self.assertEqual(self.buy(gift, method).status_code, 409)
        self.assertFalse(CreditPurchase.objects.exists())

    def test_open_card_is_reused_and_cancelled_card_can_be_replaced(self):
        preview = self.preview()
        purchase = self.buy(preview, 'card').json()
        self.assertEqual(self.buy(preview, 'card').json()['id'], purchase['id'])
        self.assertEqual(self.buy(preview).json()['error']['code'], 'payment_reconciliation')
        self.assertEqual(self.post('/credit-purchases/' + purchase['id'] + '/cancel-card', {}).status_code, 200)
        paid = self.buy(preview).json()
        self.assertEqual(paid['status'], 'credited')
        self.assertEqual(self.buy(preview).json()['id'], paid['id'])
        self.assertEqual(CreditPurchase.objects.count(), 2)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)

    def test_card_receipt_unlocks_return_only_after_staff_approval(self):
        preview = self.preview()
        key = uuid.uuid4()
        response = self.buy(preview, 'card', key)
        self.assertEqual(response.status_code, 200, response.content)
        purchase = response.json()
        self.assertIsNone(purchase['resume_preview_id'])
        self.assertEqual(self.buy(preview, 'card', key).json()['id'], purchase['id'])
        self.assertEqual(self.buy(self.preview(), 'card', key).json()['error']['code'], 'idempotency_conflict')
        self.assertGreaterEqual(self.order(preview).status_code, 400)
        submitted = self.post('/credit-purchases/' + purchase['id'] + '/receipt', {'receipt_sent': True})
        self.assertIsNone(submitted.json()['resume_preview_id'])
        approved = self.post('/manage/manual-payments/' + purchase['manual_payment_id'] + '/approve',
                             self.proof(), self.staff)
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertFalse(approved.json().get('resume_preview_id'))
        self.assertEqual(self.detail(purchase)['resume_preview_id'], preview['preview_id'])
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Outbox.objects.exists())

    def test_gateway_callback_returns_to_receipt_and_independent_verification_unlocks_resume(self):
        from .models import PaymentAttempt, SiteLimits
        from .packages import verify_purchase
        preview = self.preview()
        authority = 'A' + 'a' * 20
        with override_settings(PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='sandbox'):
            SiteLimits.objects.update_or_create(pk=1, defaults={'gateway_enabled': True, 'wallet_enabled': True})
            with patch('core.payment_options.gateway_problem', return_value=''), patch(
                    'core.packages.Zarinpal.request', return_value=PaymentRequest(authority, 'https://example.test/pay')):
                result = self.buy(preview)
            self.assertEqual(result.status_code, 200, result.content)
            purchase = result.json()
            self.assertEqual(purchase['status'], 'pending')
            self.assertIsNone(purchase['resume_preview_id'])
            with patch('core.tasks.verify_provider_payment.delay'):
                callback = Client().get('/api/v1/payments/return/zarinpal', {'Authority': authority, 'Status': 'OK'})
            self.assertTrue(callback['Location'].endswith('/credits?purchase=' + purchase['id']))
            self.assertNotIn(preview['preview_id'], callback['Location'])
            self.assertIsNone(self.detail(purchase)['resume_preview_id'])
            with patch('core.packages.Zarinpal.verify', return_value=VerifiedPayment('fixture-reference')):
                verify_purchase(PaymentAttempt.objects.get(purchase_id=purchase['id']).pk)
            self.assertEqual(self.detail(purchase)['resume_preview_id'], preview['preview_id'])
            self.assertFalse(Order.objects.exists())
            self.assertFalse(Outbox.objects.exists())

    def test_share_resume_hides_private_numbers_and_rechecks_revocation(self):
        destination = Client()
        self.authenticate(self.phone, destination)
        token = self.post('/personal-share', client=destination).json()['url'].split('#')[1]
        preview = self.preview(share_token=token)
        purchase = self.buy(preview)
        self.assertEqual(purchase.status_code, 200, purchase.content)
        result = self.resume(preview)
        self.assertEqual(result.status_code, 200, result.content)
        self.assertTrue(result.json()['is_shared_destination'])
        self.assertEqual(result.json()['recipient_masked'], '')
        for private in (self.phone, token):
            self.assertNotIn(private, result.content.decode())
        different_session = Client()
        different_session.force_login(self.user)
        self.assertEqual(self.order(preview, client=different_session).status_code, 404)
        destination.delete('/api/v1/personal-share')
        self.assertGreaterEqual(self.resume(preview).status_code, 400)
        self.assertIsNone(self.detail(purchase.json())['resume_preview_id'])
        self.assertGreaterEqual(self.order(preview).status_code, 400)
        self.assertFalse(Order.objects.exists())

    @override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
                       GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5)
    def test_tampered_sealed_copy_and_changed_direct_recipient_cannot_resume(self):
        with patch('core.gapgpt.rewrite_message', return_value='ممنونم که به حرفم گوش دادی.') as rewrite:
            preview = self.preview(recipient_phone=self.phone, source_mode='freeform')
            purchase = self.buy(preview)
            self.assertEqual(purchase.status_code, 200, purchase.content)
            self.assertEqual(self.resume(preview).status_code, 200)
            rewrite.assert_called_once()
        MessageAttempt.objects.filter(preview_id=preview['preview_id']).update(recipient_phone='09901234568')
        self.assertEqual(self.resume(preview).status_code, 409)
        self.assertIsNone(self.detail(purchase.json())['resume_preview_id'])
        MessageAttempt.objects.filter(preview_id=preview['preview_id']).update(recipient_phone=self.phone)
        Preview.objects.filter(pk=preview['preview_id']).update(review_signature='changed')
        self.assertEqual(self.resume(preview).status_code, 409)
        self.assertEqual(self.order(preview).status_code, 409)
        self.assertFalse(Order.objects.exists())


@skipUnlessDBFeature('has_select_for_update')
class BoundCheckoutConcurrencyTests(ManualFixture, TransactionTestCase):
    def test_two_tabs_with_distinct_keys_share_one_purchase(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=0)
        sealed = self.post('/messages/preview', {
            'category': 'appreciation', 'text': 'از همراهی‌ات ممنونم!', 'recipient_phone': '09901234567',
        }).json()
        data = {'package_id': self.package.pk, 'package_revision': self.package.revision,
                'payment_method': 'gateway', 'resume_preview_id': sealed['preview_id'],
                'wallet_consent': True, 'wallet_terms_version': WALLET_TERMS_VERSION}
        barrier = Barrier(2)
        def purchase(_):
            tab = Client()
            tab.cookies = self.client.cookies.copy()
            try:
                barrier.wait(timeout=10)
                response = self.post('/credit-purchases', data, tab, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
                self.assertEqual(response.status_code, 200, response.content)
                return response.json()['id']
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(purchase, range(2)))
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(CreditPurchase.objects.count(), 1)
        self.assertEqual(CreditEntry.objects.filter(kind='purchase').count(), 1)
        self.assertEqual(self.balance(), self.package.message_count)
