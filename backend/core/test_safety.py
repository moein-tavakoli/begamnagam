import io
import uuid
from datetime import timedelta
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from . import tests as legacy
from .models import Account, AbuseReport, RecipientGrant, RecipientState, Order, Outbox, FinancialEvent, Refund, PaymentAttempt, SafetyControl, OperatorAudit
from .privacy import digest, decrypt
from .services import APIError
from .safety import operator_action, snapshot
from .tasks import deliver_message


class RecipientSafetyTests(TestCase):
    post, authenticate, preview, order = legacy.APITestCase.post, legacy.APITestCase.authenticate, legacy.APITestCase.preview, legacy.APITestCase.order

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.client = Client()
        self.user = self.authenticate()
        self.quote = self.post('/messages/preview', {'category':'appreciation','text':'ممنون از همراهی تو','recipient_phone':'09901234567'}).json()
        self.token = self.quote['full_sms'].split('/r#')[1]
        self.o = self.order(recipient='09901234567', preview=self.quote).json()

    def deliver(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.post('/orders/'+self.o['id']+'/pay-demo')

    def test_bound_quote_has_256_bit_fragment_capability_and_encrypted_snapshot(self):
        self.assertEqual(len(self.token), 43)
        self.assertEqual(RecipientGrant.objects.get().token_digest, digest('recipient-token:'+self.token))
        with connection.cursor() as cursor:
            cursor.execute('SELECT full_sms FROM core_order WHERE id=%s', [self.o['id']])
            raw = cursor.fetchone()[0]
        self.assertTrue(raw.startswith('enc:v1:'))
        self.assertNotIn(self.token, raw)
        self.assertEqual(Order.objects.get().full_sms, self.quote['full_sms'])
        self.assertLessEqual(self.quote['sms_segments'], 3)

    def test_grant_is_inactive_before_submission_and_get_scanner_cannot_stop(self):
        other = Client()
        self.assertEqual(self.post('/recipient/actions/inspect', {'token':self.token}, other).status_code, 404)
        self.deliver()
        self.assertEqual(other.get('/api/v1/recipient/actions/stop', {'token':self.token}).status_code, 405)
        self.assertFalse(RecipientState.objects.get(phone_hash=digest('09901234567')).blocked)

    def test_anonymous_stop_requires_csrf_and_is_idempotent(self):
        self.deliver()
        other = Client(enforce_csrf_checks=True)
        other.get('/api/v1/bootstrap')
        self.assertEqual(self.post('/recipient/actions/stop', {'token':self.token}, other).status_code, 403)
        headers = {'HTTP_X_CSRFTOKEN':other.cookies['csrftoken'].value}
        for _ in range(2):
            r = self.post('/recipient/actions/stop', {'token':self.token}, other, **headers)
            self.assertEqual(r.json(), {'blocked':True})
            self.assertEqual(r['Referrer-Policy'], 'no-referrer')
            self.assertEqual(r['Cache-Control'], 'no-store')

    def test_inspection_does_not_disclose_either_party_or_private_message(self):
        self.deliver()
        r = self.post('/recipient/actions/inspect', {'token':self.token}, Client())
        self.assertEqual(r.json(), {'active':True, 'can_report':True})
        for private in [self.token, '09901234567', self.user.account.phone_hash, self.o['id']]: self.assertNotIn(private, r.content.decode())

    def test_tampered_expired_or_unknown_grants_have_same_response(self):
        self.deliver()
        wrong = ('x' if self.token[0]!='x' else 'y') + self.token[1:]
        a = self.post('/recipient/actions/stop', {'token':wrong}, Client())
        RecipientGrant.objects.update(stop_expires_at=timezone.now()-timedelta(seconds=1))
        b = self.post('/recipient/actions/stop', {'token':self.token}, Client())
        self.assertEqual(a.json(), b.json())
        self.assertEqual(a.status_code, 404)

    def test_report_duplicate_is_one_encrypted_case_and_stops_globally(self):
        self.deliver()
        payload = {'token':self.token, 'reason':'harassment', 'details':'گزارش مصنوعی بدون اطلاعات واقعی'}
        a = self.post('/recipient/actions/report', payload, Client())
        b = self.post('/recipient/actions/report', payload, Client())
        self.assertEqual(a.json(), b.json())
        self.assertEqual(AbuseReport.objects.count(), 1)
        with connection.cursor() as cursor:
            cursor.execute('SELECT details FROM core_abusereport')
            raw = cursor.fetchone()[0]
        self.assertNotIn(payload['details'], raw)
        self.assertTrue(RecipientState.objects.get(phone_hash=digest('09901234567')).blocked)
        self.assertFalse(self.user.account.suspended)  # Unverified report never auto-punishes a sender.

    def test_report_expiry_does_not_remove_longer_stop_right(self):
        self.deliver()
        RecipientGrant.objects.update(report_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.post('/recipient/actions/report', {'token':self.token,'reason':'unwanted'}, Client()).status_code,404)
        self.assertEqual(self.post('/recipient/actions/stop', {'token':self.token}, Client()).status_code,200)

    def test_old_session_cannot_reenable_receipt_without_fresh_otp(self):
        self.post('/preferences', {'blocked':True})
        session = self.client.session
        session['phone_verified_at'] = 0
        session.save()
        r = self.post('/preferences', {'blocked':False})
        self.assertEqual(r.status_code,403)
        self.assertEqual(r.json()['error']['code'],'reauthentication_required')
        self.assertEqual(self.post('/recipient/actions/unstop', {'token':self.token}).status_code,404)

    def test_deletion_request_is_owned_and_requires_recent_authentication(self):
        r = self.post('/account/deletion', {})
        self.assertEqual(r.status_code,200)
        self.assertTrue(Account.objects.get(user=self.user).deletion_requested_at)
        self.assertEqual(self.order(recipient='09901234568').status_code,403)
        self.assertEqual(self.post('/account/deletion', {}, Client()).status_code,401)

    def test_encryption_key_rotation_preserves_hashes_and_snapshots(self):
        previous = settings.PHONE_ENCRYPTION_KEY
        with override_settings(PHONE_ENCRYPTION_KEY=Fernet.generate_key().decode(), PHONE_ENCRYPTION_FALLBACK_KEYS=[previous]):
            call_command('rotate_encryption', '--apply', stdout=io.StringIO())
            with override_settings(PHONE_ENCRYPTION_FALLBACK_KEYS=[]):
                self.assertEqual(decrypt(Account.objects.get(user=self.user).phone_cipher), '09123456789')
                self.assertEqual(Order.objects.get().full_sms, self.quote['full_sms'])
                self.assertEqual(Account.objects.get(user=self.user).phone_hash, digest('09123456789'))

    def test_retention_dry_run_then_apply_preserves_money_and_suppression(self):
        self.deliver()
        RecipientState.objects.filter(phone_hash=digest('09901234567')).update(blocked=True)
        Order.objects.update(updated_at=timezone.now()-timedelta(days=32))
        Account.objects.filter(user=self.user).update(deletion_requested_at=timezone.now()-timedelta(days=31))
        captures = FinancialEvent.objects.count()
        call_command('prune_private_data', '--dry-run', stdout=io.StringIO())
        self.assertTrue(Order.objects.get().full_sms)
        call_command('prune_private_data', stdout=io.StringIO())
        self.assertEqual(Order.objects.get().full_sms, '')
        self.assertEqual(Order.objects.get().recipient_cipher, '')
        self.assertEqual(Account.objects.get(user=self.user).phone_cipher, '')
        self.assertEqual(FinancialEvent.objects.count(), captures)
        self.assertTrue(RecipientState.objects.get(phone_hash=digest('09901234567')).blocked)

    def test_legal_hold_is_time_limited_and_prevents_content_redaction(self):
        self.deliver()
        self.post('/recipient/actions/report', {'token':self.token,'reason':'unwanted','details':'مصنوعی'}, Client())
        AbuseReport.objects.update(hold_until=timezone.now()+timedelta(days=1))
        Order.objects.update(updated_at=timezone.now()-timedelta(days=32))
        call_command('prune_private_data', stdout=io.StringIO())
        self.assertTrue(Order.objects.get().full_sms)

    def test_halt_defers_existing_queue_and_resume_reuses_same_event(self):
        with self.captureOnCommitCallbacks(execute=False): self.post('/orders/'+self.o['id']+'/pay-demo')
        event = Outbox.objects.get()
        actor = get_user_model().objects.create_superuser(username='test-ops', password=None)
        operator_action(actor, 'halt', 'global', 'synthetic emergency exercise')
        deliver_message(event.pk)
        self.assertEqual(Outbox.objects.get().state,'pending')
        self.assertEqual(Outbox.objects.get().attempts,0)
        self.assertEqual(self.order(recipient='09901234568').status_code,503)
        operator_action(actor, 'resume', 'global', 'synthetic issue resolved')
        Outbox.objects.update(available_at=timezone.now())
        deliver_message(event.pk)
        self.assertEqual(Order.objects.get().status,'delivered_demo')
        self.assertEqual(Outbox.objects.count(),1)
        self.assertEqual(OperatorAudit.objects.count(),2)

    def test_operator_permissions_reason_and_immutable_finance(self):
        actor = get_user_model().objects.create_user(username='ordinary-staff', is_staff=True)
        with self.assertRaises(APIError): operator_action(actor,'suspend',self.user.account.pk,'synthetic complaint')
        call_command('bootstrap_roles',stdout=io.StringIO())
        from django.contrib.auth.models import Group
        actor.groups.add(Group.objects.get(name='content_support'))
        actor = get_user_model().objects.get(pk=actor.pk)
        with self.assertRaises(APIError): operator_action(actor,'suspend',self.user.account.pk,'')
        operator_action(actor,'suspend',self.user.account.pk,'synthetic complaint reviewed')
        self.assertTrue(Account.objects.get(user=self.user).suspended)
        with self.assertRaises(APIError): operator_action(actor,'confirm_refund',uuid.uuid4(),'unapproved finance')
        self.assertEqual(OperatorAudit.objects.count(),1)
        self.assertEqual(Client().get('/api/v1/operations/status').status_code,403)
        self.assertNotIn('phone', str(snapshot()))

    @override_settings(SENDING_WINDOW_ENABLED=True, SENDING_START_HOUR=0, SENDING_END_HOUR=1)
    def test_quiet_hours_defer_without_consuming_delivery_attempt(self):
        from unittest.mock import patch
        with self.captureOnCommitCallbacks(execute=False): self.post('/orders/'+self.o['id']+'/pay-demo')
        with patch('core.safety.timezone.localtime', return_value=timezone.now().replace(hour=12)):
            deliver_message(Outbox.objects.get().pk)
        self.assertEqual(Outbox.objects.get().attempts,0)
        self.assertEqual(Order.objects.get().status,'queued')

    @override_settings(PROVIDER_DAILY_BUDGET_RIAL=10000)
    def test_unexpected_provider_cost_halts_new_spend_and_preserves_observed_charge(self):
        from .budget import reserve_cost, observe_cost
        from .models import SpendReservation, SpendBudget
        from .providers import ProviderDisabled
        reserve_cost('synthetic-overage','sms',1000)
        observe_cost('synthetic-overage',1500)
        observe_cost('synthetic-overage',1500)
        self.assertEqual(SpendBudget.objects.get().reserved_rial,1500)
        self.assertEqual(SpendReservation.objects.get().actual_rial,1500)
        self.assertTrue(SafetyControl.objects.get().halted)
        with self.assertRaises(ProviderDisabled): reserve_cost('synthetic-after-halt','otp',100)

    def test_manual_refund_requires_finance_permission_and_reference(self):
        from .provider_services import request_refund
        self.deliver()
        refund = request_refund(PaymentAttempt.objects.get(), 'synthetic_manual_case')
        call_command('bootstrap_roles', stdout=io.StringIO())
        from django.contrib.auth.models import Group
        actor = get_user_model().objects.create_user(username='finance-staff',is_staff=True)
        actor.groups.add(Group.objects.get(name='finance_operator'))
        actor = get_user_model().objects.get(pk=actor.pk)
        with self.assertRaises(APIError): operator_action(actor,'confirm_refund',refund.pk,'synthetic receipt checked')
        for _ in range(2): operator_action(actor,'confirm_refund',refund.pk,'synthetic receipt checked','synthetic-reference')
        self.assertEqual(FinancialEvent.objects.filter(kind='refund').count(),1)
        self.assertEqual(Refund.objects.get().status,'refunded')
        with self.assertRaises(APIError): operator_action(actor,'suspend',self.user.account.pk,'not content support')

    def test_external_checkout_records_frozen_terms_consent_and_rejects_missing_consent(self):
        quote = self.post('/messages/preview', {'category':'appreciation','text':'تشکر از تو','recipient_phone':'09901234568'}).json()
        with override_settings(PROVIDER_NETWORK_MODE='external',TERMS_VERSION='changed-after-quote'):
            self.assertEqual(self.order(recipient='09901234568',preview=quote).status_code,422)
            result = self.post('/orders', {'preview_id':quote['preview_id'],'recipient_phone':'09901234568','consent':True,'terms_version':quote['terms_version']}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,200)
        order=Order.objects.get(pk=result.json()['id'])
        self.assertTrue(order.consent_at)
        self.assertEqual(order.terms_version,quote['terms_version'])

    def test_cache_outage_pauses_dispatch_when_recipient_controls_cannot_be_used(self):
        from unittest.mock import patch
        with self.captureOnCommitCallbacks(execute=False): self.post('/orders/'+self.o['id']+'/pay-demo')
        with patch('django.core.cache.cache.get',side_effect=ConnectionError('synthetic outage')):
            deliver_message(Outbox.objects.get().pk)
        self.assertEqual(Outbox.objects.get().state,'pending')
        self.assertEqual(Outbox.objects.get().attempts,0)
        self.assertFalse(Refund.objects.exists())

    def test_paid_unsubmitted_queue_expiry_compensates_without_dispatch(self):
        from .tasks import expire_unpaid_orders
        with self.captureOnCommitCallbacks(execute=False): self.post('/orders/'+self.o['id']+'/pay-demo')
        Order.objects.update(paid_at=timezone.now()-timedelta(hours=25))
        expire_unpaid_orders()
        expire_unpaid_orders()
        self.assertEqual(Outbox.objects.get().state,'cancelled')
        self.assertEqual(FinancialEvent.objects.filter(kind='refund').count(),1)
