import uuid
import json
import os
import subprocess
import sys
import ssl
import socket
import urllib.error
from urllib.parse import parse_qs
from unittest.mock import patch
from datetime import timedelta
from django.conf import settings
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
from .privacy import digest


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
            ZARINPAL_MERCHANT_ID='synthetic-merchant', KAVENEGAR_SENDER='10000000',
            KAVENEGAR_OTP_MODE='sms', KAVENEGAR_OTP_TEMPLATE='',
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
        self.assertEqual(PaymentAttempt.objects.get(pk=a.pk).status,'unknown')
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
        self.fixture.modes['send'] = 'redirect'
        with self.assertRaises(ProviderUnknown): Kavenegar().otp(phone='09901234567', code='123456')
        self.assertEqual(self.fixture.calls.count('send'), 1)

    @override_settings(OTP_BACKEND='kavenegar')
    def test_real_otp_protocol_never_exposes_debug_code(self):
        response = self.post('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('debug_code', response.json())
        self.assertFalse(response.json()['demo_mode'])
        self.assertEqual(self.fixture.calls.count('send'), 1)
        self.assertNotIn('lookup', self.fixture.calls)
        payload = self.fixture.otp_requests[0]
        code = self.fixture.codes['09911234567']
        self.assertEqual(payload['sender'], '10000000')
        self.assertEqual(payload['hide'], '1')
        self.assertNotIn('template', payload)
        self.assertEqual(payload['message'], f'بگم نگم\nکد ورود: {code}\nاعتبار: ۵ دقیقه\nکد را در اختیار کسی نگذارید.')
        verified = self.post('/auth/verify-otp', {'challenge_id':response.json()['challenge_id'], 'code':code})
        self.assertEqual(verified.status_code, 200)

    @override_settings(KAVENEGAR_OTP_MODE='lookup', KAVENEGAR_OTP_TEMPLATE='approved-login')
    def test_lookup_remains_explicit_and_uses_approved_template(self):
        result = Kavenegar().otp(phone='09911234567', code='012345')
        self.assertEqual(result.status, 'accepted')
        self.assertEqual(self.fixture.calls.count('lookup'), 1)
        self.assertNotIn('send', self.fixture.calls)
        self.assertEqual(self.fixture.otp_requests[0]['template'], 'approved-login')
        self.assertEqual(self.fixture.codes['09911234567'], '012345')

    def test_invalid_otp_input_or_configuration_does_not_dispatch(self):
        for code in ('12345', '1234567', '123456\nمتن اضافی', '۱۲۳۴۵۶', None):
            with self.assertRaises(ProviderRejected):
                Kavenegar().otp(phone='09911234567', code=code)
        for mode in ('lookup', 'invalid'):
            with override_settings(KAVENEGAR_OTP_MODE=mode, KAVENEGAR_OTP_TEMPLATE=''):
                with self.assertRaises(ProviderRejected):
                    Kavenegar().otp(phone='09911234567', code='123456')
        self.assertFalse(self.fixture.calls)

    @override_settings(OTP_BACKEND='kavenegar')
    def test_lost_ordinary_otp_response_does_not_repeat_or_expose_code(self):
        self.fixture.modes['send'] = 'drop_after_accept'
        response = self.post('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('debug_code', response.json())
        self.assertEqual(response.json()['delivery_status'], 'unknown')
        self.assertEqual(self.fixture.calls.count('send'), 1)
        verified = self.post('/auth/verify-otp', {'challenge_id':response.json()['challenge_id'],
            'code': self.fixture.codes['09911234567']})
        self.assertEqual(verified.status_code, 200)

    @override_settings(OTP_BACKEND='kavenegar')
    def test_rejected_ordinary_otp_cannot_be_verified(self):
        from .models import OTPChallenge
        self.fixture.modes['send'] = 'reject'
        response = self.post('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('debug_code', response.json())
        self.assertIsNotNone(OTPChallenge.objects.latest('created_at').consumed_at)
        self.assertEqual(self.fixture.calls.count('send'), 1)

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

    @override_settings(SMS_BACKEND='kavenegar')
    def test_halt_between_submission_intent_and_wire_call_defers_safely(self):
        from unittest.mock import patch
        from .budget import reserve_cost as original
        from .models import SafetyControl
        self.pay()
        def reserve_then_halt(*args,**kwargs):
            result=original(*args,**kwargs)
            SafetyControl.objects.update(halted=True)
            return result
        with patch('core.provider_delivery.reserve_cost',side_effect=reserve_then_halt):
            submit_delivery(Outbox.objects.get().pk)
        self.assertEqual(self.fixture.calls.count('send'),0)
        self.assertEqual(Outbox.objects.get().state,'pending')
        self.assertEqual(MessageDelivery.objects.get().status,'queued')


class LocalRealOTPTests(TestCase):
    post, preview, order = APITestCase.post, APITestCase.preview, APITestCase.order

    def setUp(self):
        from django.core.cache import cache
        from django.test import Client
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.config = override_settings(DEMO_MODE=True, LOCAL_REAL_OTP_ENABLED=True,
            OTP_TEST_RECIPIENT_HASHES={digest('09911234567')}, OTP_BACKEND='kavenegar',
            SMS_BACKEND='console', PAYMENT_BACKEND='demo', PROVIDER_NETWORK_MODE='disabled',
            LIVE_PROVIDERS_ENABLED=False, KAVENEGAR_BASE_URL='https://api.kavenegar.com',
            KAVENEGAR_API_KEY='synthetic-key', KAVENEGAR_SENDER='10000000',
            KAVENEGAR_OTP_MODE='sms', KAVENEGAR_OTP_TEMPLATE='',
            APP_BASE_URL='http://localhost:3000', PROVIDER_DAILY_BUDGET_RIAL=1000, OTP_MAX_COST_RIAL=500)
        self.config.enable()
        self.addCleanup(self.config.disable)
        self.wire = patch('core.providers.http.urllib.request.build_opener').start()
        self.addCleanup(patch.stopall)
        self.wire.return_value.open.return_value.read.return_value = json.dumps(
            {'return': {'status': 200}, 'entries': [{'messageid':700, 'status':1, 'cost':500}]}).encode()
        self.client.get('/api/v1/bootstrap')

    def submit(self, path, data=None, **headers):
        return self.post(path, data, HTTP_X_CSRFTOKEN=self.client.cookies['csrftoken'].value, **headers)

    def request_code(self):
        response = self.submit('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['demo_mode'])
        self.assertEqual(response.json()['delivery_status'], 'accepted')
        self.assertNotIn('debug_code', response.json())
        request = self.wire.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.kavenegar.com/v1/synthetic-key/sms/send.json')
        payload = parse_qs(request.data.decode())
        code = payload['message'][0].split('\n')[1].split(': ')[1]
        return response.json()['challenge_id'], code

    def test_real_otp_login_keeps_checkout_and_delivery_simulated(self):
        bootstrap = self.client.get('/api/v1/bootstrap').json()
        self.assertTrue(bootstrap['demo_mode'])
        self.assertTrue(bootstrap['otp_is_real'])
        self.assertEqual(bootstrap['payment_backend'], 'demo')
        challenge, code = self.request_code()
        verified = self.submit('/auth/verify-otp', {'challenge_id':challenge, 'code':code})
        self.assertEqual(verified.status_code, 200)
        preview = self.submit('/messages/preview', {'category':'appreciation','text':'از همراهی شما ممنونم.'}).json()
        order = self.submit('/orders', {'preview_id':preview['preview_id'],'recipient_phone':'09901234567'},
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).json()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit('/orders/'+order['id']+'/pay-demo')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.get(pk=order['id']).status, 'delivered_demo')
        self.assertTrue(Order.objects.get(pk=order['id']).is_free)
        self.assertFalse(FinancialEvent.objects.exists())
        self.assertEqual(self.wire.return_value.open.call_count, 1)
        self.assertEqual(SpendBudget.objects.get().reserved_rial, 500)

    def test_other_numbers_are_blocked_without_challenge_budget_or_network(self):
        from .models import OTPChallenge
        response = self.submit('/auth/request-otp', {'phone':'09911234568'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'otp_unavailable')
        self.assertFalse(OTPChallenge.objects.exists())
        self.assertFalse(SpendBudget.objects.exists())
        self.wire.assert_not_called()
        with self.assertRaises(ProviderRejected):
            Kavenegar().otp(phone='09911234568', code='123456')
        self.wire.assert_not_called()

    def test_csrf_and_daily_budget_apply_before_real_network(self):
        response = self.post('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 403)
        self.wire.assert_not_called()
        self.request_code()
        self.request_code()
        response = self.submit('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.wire.return_value.open.call_count, 2)

    def test_general_sms_payment_status_and_redirects_remain_blocked(self):
        from .providers.http import endpoint
        with self.assertRaises(ProviderDisabled):
            Kavenegar().submit(phone='09911234567', text='Do not send', local_id=1)
        with self.assertRaises(ProviderDisabled):
            Kavenegar().status(local_id=1)
        with self.assertRaises(ProviderDisabled):
            endpoint('https://sandbox.zarinpal.com', '/pg/v4/payment/request.json', {'sandbox.zarinpal.com'})
        with self.assertRaises(ProviderDisabled):
            endpoint('https://api.kavenegar.com', '/v1/synthetic-key/sms/status.json', {'api.kavenegar.com'}, otp=True)
        with override_settings(KAVENEGAR_BASE_URL='https://example.invalid'):
            with self.assertRaises(ProviderDisabled):
                Kavenegar().otp(phone='09911234567', code='123456')
        self.wire.assert_not_called()
        from .providers.http import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, '', {}, 'https://example.invalid'))

    def test_expired_and_replayed_real_codes_cannot_authenticate(self):
        from .models import OTPChallenge
        challenge, code = self.request_code()
        OTPChallenge.objects.filter(pk=challenge).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.submit('/auth/verify-otp', {'challenge_id':challenge,'code':code}).status_code, 400)
        challenge, code = self.request_code()
        self.assertEqual(self.submit('/auth/verify-otp', {'challenge_id':challenge,'code':code}).status_code, 200)
        self.assertEqual(self.submit('/auth/verify-otp', {'challenge_id':challenge,'code':code}).status_code, 400)

    def test_startup_accepts_only_isolated_bounded_test_configuration(self):
        env = dict(os.environ, DEMO_MODE='1', DEBUG='1', PROVIDER_NETWORK_MODE='disabled',
            LIVE_PROVIDERS_ENABLED='0', LOCAL_REAL_OTP_ENABLED='1', OTP_BACKEND='kavenegar',
            SMS_BACKEND='console', PAYMENT_BACKEND='demo', KAVENEGAR_API_KEY='synthetic-key',
            KAVENEGAR_SENDER='10000000', KAVENEGAR_BASE_URL='https://api.kavenegar.com',
            KAVENEGAR_OTP_MODE='sms', KAVENEGAR_OTP_TEMPLATE='',
            OTP_TEST_RECIPIENT_HASHES='a'*64, PROVIDER_DAILY_BUDGET_RIAL='1000',
            OTP_MAX_COST_RIAL='500', APP_BASE_URL='http://localhost:3000')
        command = [sys.executable,'-c',"import runpy; runpy.run_path('config/settings.py')"]
        self.assertEqual(subprocess.run(command,env=env,capture_output=True).returncode, 0)
        for invalid in ({'SMS_BACKEND':'kavenegar'}, {'PAYMENT_BACKEND':'zarinpal'},
                {'OTP_TEST_RECIPIENT_HASHES':''}, {'OTP_MAX_COST_RIAL':'0'},
                {'OTP_MAX_COST_RIAL':'1001'}, {'KAVENEGAR_API_KEY':''},
                {'APP_BASE_URL':'https://example.invalid'}, {'PROVIDER_NETWORK_MODE':'external'},
                {'KAVENEGAR_BASE_URL':'https://api.kavenegar.com/extra'}):
            with self.subTest(fields=tuple(invalid)):
                self.assertNotEqual(subprocess.run(command,env=dict(env,**invalid),capture_output=True).returncode, 0)

    def test_certificate_failure_is_definite_and_logged_without_private_data(self):
        from .models import OTPChallenge
        sensitive = 'https://api.kavenegar.com/v1/synthetic-key/sms/send.json?phone=09911234567&code=123456'
        error = urllib.error.URLError(ssl.SSLCertVerificationError(1, sensitive))
        self.wire.return_value.open.side_effect = error
        with self.assertLogs('core.views', level='WARNING') as logs:
            response = self.submit('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('challenge_id', response.json())
        self.assertNotIn('debug_code', response.json())
        self.assertIn('tls_certificate_verification_failed', '\n'.join(logs.output))
        for private in ('synthetic-key', '09911234567', '123456', 'https://'):
            self.assertNotIn(private, '\n'.join(logs.output))
            self.assertNotIn(private, response.content.decode())
        self.assertIsNotNone(OTPChallenge.objects.latest('created_at').consumed_at)
        self.assertEqual(self.wire.return_value.open.call_count, 1)

    def test_dns_failure_and_uncertain_timeout_have_distinct_outcomes(self):
        self.wire.return_value.open.side_effect = urllib.error.URLError(socket.gaierror('synthetic lookup failure'))
        response = self.submit('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 503)
        self.wire.return_value.open.side_effect = urllib.error.URLError(TimeoutError('synthetic timeout'))
        response = self.submit('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['delivery_status'], 'unknown')
        self.assertNotIn('debug_code', response.json())
        self.assertEqual(self.wire.return_value.open.call_count, 2)

    def test_provider_failed_status_does_not_claim_accepted(self):
        self.wire.return_value.open.return_value.read.return_value = json.dumps(
            {'return': {'status': 200}, 'entries': [{'messageid':700, 'status':6, 'cost':500}]}).encode()
        response = self.submit('/auth/request-otp', {'phone':'09911234567'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(self.wire.return_value.open.call_count, 1)
