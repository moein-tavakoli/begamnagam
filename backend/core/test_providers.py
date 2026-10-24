import uuid
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from .tests import APITestCase
from .models import PaymentAttempt, FinancialEvent, MessageDelivery, Outbox, Refund, SpendBudget, Order
from .provider_fixture import LocalProviders
from .providers import Kavenegar, Zarinpal, ProviderDisabled, ProviderUnknown, ProviderRejected
from .provider_services import begin_payment, verify_payment, process_refund, request_refund
from .provider_delivery import submit_delivery, reconcile_delivery
from .budget import reserve_cost
from .services import APIError


class ProviderContracts(TestCase):
    post, authenticate, preview, order = APITestCase.post, APITestCase.authenticate, APITestCase.preview, APITestCase.order

    def setUp(self):
        from django.core.cache import cache
        from django.test import Client
        cache.clear()
        self.client = Client()
        self.fixture = LocalProviders().__enter__()
        self.config = override_settings(PROVIDER_NETWORK_MODE='local', PROVIDER_TIMEOUT_SECONDS=1,
            KAVENEGAR_BASE_URL=self.fixture.url, ZARINPAL_BASE_URL=self.fixture.url,
            ZARINPAL_REDIRECT_BASE=self.fixture.url, KAVENEGAR_API_KEY='synthetic-key',
            ZARINPAL_MERCHANT_ID='synthetic-merchant', KAVENEGAR_OTP_TEMPLATE='test',
            PAYMENT_BACKEND='zarinpal', PROVIDER_ENVIRONMENT='sandbox', PROVIDER_DAILY_BUDGET_RIAL=10000,
            OTP_MAX_COST_RIAL=500, SMS_MAX_COST_RIAL=2000)
        self.config.enable()
        self.user = self.authenticate()
        self.o = self.order(recipient='09901234567').json()

    def tearDown(self):
        self.config.disable()
        self.fixture.__exit__()

    def pay(self):
        result = begin_payment(self.user, self.o['id'], uuid.uuid4())
        attempt = PaymentAttempt.objects.get(pk=result['attempt_id'])
        self.fixture.payments[attempt.authority]['status'] = 'PAID'
        with self.captureOnCommitCallbacks(execute=False):
            verify_payment(attempt.pk)
        return attempt

    def test_payment_request_integer_rial_redirect_and_repeated_attempt(self):
        result = begin_payment(self.user, self.o['id'], uuid.uuid4())
        repeated = begin_payment(self.user, self.o['id'], uuid.uuid4())
        self.assertEqual(result, repeated)
        a = PaymentAttempt.objects.get()
        self.assertEqual(self.fixture.payments[a.authority]['amount'], 20000)
        self.assertEqual(self.fixture.calls.count('request'), 1)

    def test_forged_callback_does_not_prove_payment(self):
        result = begin_payment(self.user, self.o['id'], uuid.uuid4())
        with self.captureOnCommitCallbacks(execute=False):
            verify_payment(result['attempt_id'])
        self.assertFalse(FinancialEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        response = self.client.get('/api/v1/payments/return/zarinpal?Authority=FAKE&Status=OK')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(FinancialEvent.objects.exists())

    def test_verification_duplicate_101_creates_one_capture_and_outbox(self):
        attempt = self.pay()
        verify_payment(attempt.pk)
        self.assertEqual(FinancialEvent.objects.filter(kind='payment').count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)
        self.assertEqual(MessageDelivery.objects.get().status, 'queued')

    def test_wrong_amount_never_captures_or_queues(self):
        r = begin_payment(self.user, self.o['id'], uuid.uuid4())
        a = PaymentAttempt.objects.get(pk=r['attempt_id'])
        self.fixture.payments[a.authority]['status'] = 'PAID'
        self.fixture.modes['verify'] = 'wrong_amount'
        verify_payment(a.pk)
        self.assertFalse(FinancialEvent.objects.exists())
        self.assertFalse(Outbox.objects.exists())

    def test_request_lost_after_accept_not_retried(self):
        self.fixture.modes['request'] = 'drop_after_accept'
        for _ in range(2):
            with self.assertRaises(APIError): begin_payment(self.user, self.o['id'], uuid.uuid4())
        self.assertEqual(self.fixture.calls.count('request'), 1)
        self.assertEqual(PaymentAttempt.objects.get().status, 'unknown')

    def test_verify_lost_after_accept_can_be_reconciled(self):
        r = begin_payment(self.user, self.o['id'], uuid.uuid4())
        a = PaymentAttempt.objects.get(pk=r['attempt_id'])
        self.fixture.payments[a.authority]['status'] = 'PAID'
        self.fixture.modes['verify'] = 'drop_after_accept'
        verify_payment(a.pk)
        self.assertFalse(Outbox.objects.exists())
        self.fixture.modes.clear()
        with self.captureOnCommitCallbacks(execute=False): verify_payment(a.pk)
        self.assertEqual(FinancialEvent.objects.count(), 1)
        self.assertEqual(Outbox.objects.count(), 1)

    def test_late_success_records_refund_without_sms(self):
        r = begin_payment(self.user, self.o['id'], uuid.uuid4())
        a = PaymentAttempt.objects.get(pk=r['attempt_id'])
        self.fixture.payments[a.authority]['status'] = 'PAID'
        Order.objects.filter(pk=self.o['id']).update(created_at=timezone.now()-timedelta(hours=1))
        verify_payment(a.pk)
        self.assertEqual(FinancialEvent.objects.count(), 1)
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(Refund.objects.count(), 1)
        process_refund(Refund.objects.get().pk)
        self.assertEqual(Refund.objects.get().status, 'refunded')

    @override_settings(SMS_BACKEND='kavenegar')
    def test_sms_lost_after_accept_is_queried_never_sent_twice(self):
        self.pay()
        e = Outbox.objects.get()
        self.fixture.modes['send'] = 'drop_after_accept'
        submit_delivery(e.pk)
        submit_delivery(e.pk)
        d = MessageDelivery.objects.get()
        self.assertEqual(d.status, 'unknown')
        self.assertEqual(self.fixture.calls.count('send'), 1)
        self.fixture.modes.clear()
        self.fixture.messages[str(d.local_id)]['status'] = 10
        reconcile_delivery(d.pk)
        self.assertEqual(MessageDelivery.objects.get().status, 'delivered')
        self.assertEqual(self.fixture.calls.count('send'), 1)

    @override_settings(SMS_BACKEND='kavenegar')
    def test_dead_worker_submission_lease_queries_instead_of_resends(self):
        self.pay()
        d = MessageDelivery.objects.get()
        d.status = 'submitting'
        d.lease_until = timezone.now()-timedelta(minutes=1)
        d.save()
        Outbox.objects.update(state='submitting')
        reconcile_delivery(d.pk)
        self.assertEqual(self.fixture.calls.count('send'), 0)
        self.assertEqual(MessageDelivery.objects.get().status, 'unknown')

    def test_reverse_lost_response_reconciles_without_second_mutation(self):
        a = self.pay()
        refund = request_refund(a, 'synthetic')
        self.fixture.modes['reverse'] = 'drop_after_accept'
        process_refund(refund.pk)
        self.assertEqual(Refund.objects.get().status, 'unknown')
        self.fixture.modes.clear()
        process_refund(refund.pk)
        process_refund(refund.pk)
        self.assertEqual(self.fixture.calls.count('reverse'), 1)
        self.assertEqual(FinancialEvent.objects.filter(kind='refund').count(), 1)

    def test_budget_gross_cap_and_repeat_reservation(self):
        reserve_cost('synthetic:1', 'sms', 6000)
        reserve_cost('synthetic:1', 'sms', 6000)
        with self.assertRaises(ProviderDisabled): reserve_cost('synthetic:2', 'sms', 6000)
        self.assertEqual(SpendBudget.objects.get().reserved_rial, 6000)

    def test_external_network_and_redirects_cannot_escape_local_contract(self):
        with override_settings(KAVENEGAR_BASE_URL='https://api.kavenegar.com'):
            with self.assertRaises(ProviderDisabled): Kavenegar().otp(phone='09901234567', code='123456')
        self.fixture.modes['lookup'] = 'redirect'
        with self.assertRaises(ProviderUnknown): Kavenegar().otp(phone='09901234567', code='123456')
        self.assertEqual(self.fixture.calls.count('lookup'), 1)

    @override_settings(OTP_BACKEND='kavenegar')
    def test_real_otp_protocol_never_exposes_debug_code(self):
        response = self.post('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('debug_code', response.json())
        self.assertIn('09911234567', self.fixture.codes)

    @override_settings(SMS_BACKEND='kavenegar')
    def test_aged_uncertain_sms_still_creates_refund_when_status_endpoint_is_down(self):
        self.pay()
        d = MessageDelivery.objects.get()
        MessageDelivery.objects.filter(pk=d.pk).update(status='unknown', created_at=timezone.now()-timedelta(hours=25))
        Outbox.objects.update(state='unknown')
        self.fixture.modes['statuslocalmessageid'] = 'malformed'
        reconcile_delivery(d.pk)
        self.assertEqual(Refund.objects.count(), 1)
        self.assertEqual(self.fixture.calls.count('send'), 0)

    def test_settled_refund_stays_open_until_proven_reversed(self):
        a = self.pay()
        PaymentAttempt.objects.filter(pk=a.pk).update(created_at=timezone.now()-timedelta(hours=1))
        refund = request_refund(a, 'delivery_unavailable')
        process_refund(refund.pk)
        self.assertEqual(Refund.objects.get().status, 'unknown')
        self.assertEqual(self.fixture.calls.count('reverse'), 0)
        self.assertFalse(FinancialEvent.objects.filter(kind='refund').exists())

    def test_very_late_receipt_after_private_redaction_is_still_captured_and_refunded(self):
        r = begin_payment(self.user, self.o['id'], uuid.uuid4())
        a = PaymentAttempt.objects.get(pk=r['attempt_id'])
        self.fixture.payments[a.authority]['status'] = 'PAID'
        Order.objects.filter(pk=self.o['id']).update(status='cancelled', recipient_hash='', recipient_cipher='', created_at=timezone.now()-timedelta(days=32))
        verify_payment(a.pk)
        self.assertEqual(FinancialEvent.objects.filter(kind='payment').count(),1)
        self.assertEqual(Refund.objects.count(),1)
        self.assertEqual(self.client.get('/api/v1/orders/'+self.o['id']).json()['financial_status'],'refund_pending')
        self.assertFalse(Outbox.objects.exists())
