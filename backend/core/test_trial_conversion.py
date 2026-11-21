import json
import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (Account, CreditEntry, CreditPurchase, FinancialEvent, MessageAttempt,
                     PaymentAttempt, Preview, Refund, WalletEntry)
from .payment_options import WALLET_TERMS_VERSION
from .test_manual_payments import ManualFixture


class TrialConversionTests(ManualFixture, TestCase):
    def report(self, *args):
        out = StringIO()
        call_command('conversion_report', 'text-trial', *args, stdout=out)
        return json.loads(out.getvalue())['trial_conversion']

    def test_staff_dashboard_shows_only_live_aggregates_and_missing_rate(self):
        url = '/api/v1/manage/dashboard'
        self.assertNotEqual(self.client.get(url).status_code, 200)
        self.client.force_login(get_user_model().objects.create_superuser('trial-staff'))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['live_trial_conversion'], self.report())
        self.assertIsNone(response.json()['live_trial_conversion']['linked_purchase_rate'])

    @override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='gpt-6-luna',
                       GAPGPT_DAILY_REQUEST_LIMIT=12, GAPGPT_USER_DAILY_LIMIT=5)
    def test_verified_trial_and_its_two_checkout_methods_retain_attribution_after_pruning(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=0)
        with patch('core.gapgpt.rewrite_message', return_value='ممنونم که کمک کردی.'):
            response = self.post('/messages/text-trials', {'text':'ممنونم که کمک کردی.'})
        self.assertEqual(response.status_code, 200, response.content)
        tid = response.json()['trial_id']
        self.assertEqual(MessageAttempt.objects.get(preview_id=tid).trial_environment, 'demo')
        self.assertEqual(self.post('/messages/text-trials/'+tid+'/bind', {'recipient_phone':'09901234567'}).status_code, 200)
        def buy(method):
            payload = {'resume_preview_id': tid, 'package_id':self.package.pk, 'package_revision':self.package.revision,
                       'payment_method':method, 'wallet_consent':True, 'wallet_terms_version':WALLET_TERMS_VERSION}
            return self.post('/credit-purchases', payload, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).json()
        card = buy('card')
        self.assertTrue(CreditPurchase.objects.get(pk=card['id']).from_measured_text_trial)
        self.post('/credit-purchases/'+card['id']+'/cancel-card', {})
        paid = buy('gateway')
        self.assertEqual(paid['status'], 'credited')
        Preview.objects.filter(pk=tid).update(expires_at=timezone.now()-timedelta(days=3))
        call_command('prune_private_data', stdout=StringIO())
        purchase = CreditPurchase.objects.get(pk=paid['id'])
        self.assertIsNone(purchase.resume_preview_id)
        self.assertTrue(purchase.from_measured_text_trial)
        self.assertEqual(self.report()['trial_senders'], 0)
        self.assertIsNone(self.report()['linked_purchase_rate'])

    def test_only_mature_first_triers_and_confirmed_linked_live_purchases_count(self):
        now = timezone.now()
        start = now - timedelta(days=10)
        def enroll(name, when=start, environment='live', status='accepted'):
            user, _ = get_user_model().objects.get_or_create(username=name)
            account, _ = Account.objects.get_or_create(user=user, defaults={'phone_hash':name})
            attempt = MessageAttempt.objects.create(owner=user, status=status, trial_environment=environment)
            MessageAttempt.objects.filter(pk=attempt.pk).update(created_at=when)
            return account
        def sale(account, offset=1, *, linked=True, credited=True, environment='live', refund=0, grant=False, method='gateway', refund_day=None):
            when = start + timedelta(days=offset)
            purchase = CreditPurchase.objects.create(owner=account.user, package=self.package, idempotency_key=uuid.uuid4(),
                amount_toman=10000, message_count=3, environment=environment, from_measured_text_trial=linked,
                credited_at=when if credited else None, payment_method='card' if grant else method, wallet_refund_consent=not grant)
            CreditPurchase.objects.filter(pk=purchase.pk).update(created_at=when)
            payment = PaymentAttempt.objects.create(purchase=purchase, provider='manual' if grant or method == 'card' else 'zarinpal',
                environment=environment, status='verified' if credited else 'pending', amount_toman=10000)
            if credited:
                CreditEntry.objects.create(account=account, purchase=purchase, units=3, environment=environment, kind='purchase')
                FinancialEvent.objects.create(payment=payment, kind='payment', amount_toman=10000)
            if refund:
                row = Refund.objects.create(payment=payment, amount_toman=refund, status='refunded')
                event = FinancialEvent.objects.create(payment=payment, refund=row, kind='refund', amount_toman=refund)
                FinancialEvent.objects.filter(pk=event.pk).update(created_at=start+timedelta(days=refund_day) if refund_day else when)
            return purchase
        buyer = enroll('returns')
        enroll('returns', start+timedelta(hours=10))
        sale(buyer)
        sale(buyer, 2)
        nonbuyer = enroll('other')
        sale(nonbuyer, linked=False)
        sale(nonbuyer, credited=False)
        sale(nonbuyer, environment='sandbox')
        sale(nonbuyer, 7)
        sale(nonbuyer, -1)
        sale(nonbuyer, refund=10000)
        sale(nonbuyer, grant=True)
        enroll('recent', now)
        enroll('demo', environment='demo')
        enroll('legacy', environment='')
        enroll('rejected', status='rejected')
        earlier = enroll('earlier', start-timedelta(days=12))
        enroll('earlier', start+timedelta(hours=1))
        sale(earlier)
        # Each additional buyer has exactly one qualifying on-path sale.
        sale(enroll('partial-refund'), refund=1000)
        sale(enroll('late-refund'), refund=10000, refund_day=8)
        sale(enroll('customer-card'), method='card')
        wallet = enroll('wallet')
        debit = sale(wallet, method='wallet')
        WalletEntry.objects.create(account=wallet, purchase=debit, kind='package_debit', amount_toman=10000,
                                  balance_after_toman=0, environment='live')
        sale(nonbuyer, method='wallet')  # No matching balance debit.
        result = self.report('--since', start.date().isoformat())
        self.assertEqual(result['trial_senders'], 7)
        self.assertEqual(result['eligible_senders_with_full_window'], 6)
        self.assertEqual(result['awaiting_full_window'], 1)
        self.assertEqual(result['confirmed_linked_buyers'], 5)
        self.assertEqual(result['linked_purchase_rate'], 0.8333)
