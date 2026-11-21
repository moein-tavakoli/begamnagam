import io
import json
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .conversion_experiments import split
from .models import (Account, ConversionExposure, CreditPurchase, FinancialEvent, MessageDelivery,
                     MessagePackage, Order, PaymentAttempt, Preview, Refund, SafetyControl, SpendBudget, SpendReservation)


@override_settings(DEMO_MODE=True, PAYMENT_BACKEND='demo')
class ConversionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user('participant')
        self.account = Account.objects.create(user=self.user, phone_hash='participant', free_sends_remaining=0)
        self.client.force_login(self.user)
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted':False})
        self.offer = MessagePackage.objects.get(price_experiment_only=True)
        self.base = MessagePackage.objects.filter(active=True, message_count=9, price_toman=30000).first()

    def bootstrap(self, client=None):
        return (client or self.client).get('/api/v1/bootstrap').json()

    def expose(self, key, surface, **extra):
        return self.client.post('/api/v1/conversion-exposures', {'experiment':key, 'surface':surface, **extra},
            content_type='application/json')

    def buy(self, key, **extra):
        return self.client.post('/api/v1/credit-purchases', {'package_id': self.offer.pk,
            'package_revision':self.offer.revision, **extra}, HTTP_IDEMPOTENCY_KEY=str(key), content_type='application/json')

    def preview(self):
        return Preview.objects.create(owner=self.user, session_key=self.client.session.session_key,
            price_toman=0, expires_at=timezone.now()+timedelta(minutes=5))

    def test_split_is_reproducible_and_both_arms_are_used(self):
        self.assertEqual(split(24,'live','price'), split(24,'live','price'))
        self.assertEqual({split(i,'live','price') for i in range(40)}, {'control','treatment'})

    @override_settings(CONVERSION_EXPERIMENT='off')
    def test_default_features_have_no_exposure_or_price_offer(self):
        startup = self.bootstrap()
        self.assertEqual(startup['conversion_experiment'], {'key':'off','variant':None,'inline_checkout':True,'show_examples':True})
        self.assertNotIn(self.offer.pk, [row['id'] for row in startup['message_packages']])
        self.assertFalse(self.expose('price','pricing').json()['recorded'])
        self.assertEqual(self.buy(uuid.uuid4()).json()['error']['code'], 'package_changed')
        self.assertFalse(ConversionExposure.objects.exists())

    @override_settings(CONVERSION_EXPERIMENT='examples')
    def test_samples_use_same_prices_and_only_one_verified_visible_impression(self):
        guest = self.bootstrap(Client())
        self.assertFalse(guest['conversion_experiment']['show_examples'])
        self.assertIsNone(guest['conversion_experiment']['variant'])
        for variant in ('control','treatment'):
            with patch('core.conversion_experiments.split', return_value=variant):
                data = self.bootstrap()
                self.assertEqual(data['conversion_experiment']['show_examples'], variant == 'treatment')
                self.assertEqual(guest['message_packages'], data['message_packages'])
        self.assertFalse(ConversionExposure.objects.exists())
        self.assertEqual(self.expose('examples','credits').status_code,422)
        self.assertEqual(self.expose('examples','pricing',text='private').status_code,422)
        self.assertTrue(self.expose('examples','pricing').json()['recorded'])
        self.assertFalse(self.expose('examples','pricing').json()['recorded'])
        self.assertEqual(ConversionExposure.objects.count(),1)
        with override_settings(CONVERSION_EXPERIMENT='price'):
            self.assertIsNone(self.bootstrap()['conversion_experiment']['variant'])
        self.client.logout()
        self.assertEqual(self.expose('examples','pricing').status_code,401)

    @override_settings(CONVERSION_EXPERIMENT='preview')
    def test_exhausted_current_session_preview_only_and_first_exposure_is_preserved(self):
        first, other = self.preview(), self.preview()
        self.assertEqual(self.expose('preview','preview',preview_id='bad').status_code,422)
        Preview.objects.filter(pk=other.pk).update(session_key='other-session')
        self.assertFalse(self.expose('preview','preview',preview_id=str(other.pk)).json()['recorded'])
        for field in ('free_sends_remaining', 'demo_sends_remaining'):
            Account.objects.filter(pk=self.account.pk).update(**{field:1})
            self.assertFalse(self.expose('preview','preview',preview_id=str(first.pk)).json()['recorded'])
            Account.objects.filter(pk=self.account.pk).update(**{field:0})
        self.assertTrue(self.expose('preview','preview',preview_id=str(first.pk)).json()['recorded'])
        self.assertFalse(self.expose('preview','preview',preview_id=str(self.preview().pk)).json()['recorded'])
        self.assertEqual(ConversionExposure.objects.get().preview_id, first.pk)

    @override_settings(CONVERSION_EXPERIMENT='price')
    def test_price_enforced_at_checkout_and_existing_retries_survive_gate_closure(self):
        with patch('core.conversion_experiments.split', return_value='control'):
            self.assertNotIn(self.offer.pk,[p['id'] for p in self.bootstrap()['message_packages']])
            self.assertEqual(self.buy(uuid.uuid4()).json()['error']['code'], 'package_changed')
        with patch('core.conversion_experiments.split', return_value='treatment'):
            self.assertNotIn(self.offer.pk,[p['id'] for p in self.bootstrap(Client())['message_packages']])
            offers = self.bootstrap()['message_packages']
            self.assertIn(self.base.pk,[p['id'] for p in offers])
            displayed = next(p for p in offers if p['id'] == self.offer.pk)
            self.assertTrue(displayed['active'] and displayed['experiment_only'])
            self.assertTrue(self.expose('price','credits').json()['recorded'])
            key = uuid.uuid4()
            purchase = self.buy(key).json()
            self.assertEqual((purchase['message_count'],purchase['amount_toman'],purchase['status']), (8,25000,'credited'))
            self.assertIsNone(self.bootstrap()['conversion_experiment']['variant'])
            self.assertEqual(self.buy(uuid.uuid4()).json()['error']['code'], 'package_changed')
        with override_settings(CONVERSION_EXPERIMENT='off'):
            self.assertEqual(self.buy(key).json()['id'], purchase['id'])

    @override_settings(CONVERSION_EXPERIMENT='price')
    def test_unavailable_methods_halt_or_missing_comparator_do_not_enroll(self):
        with override_settings(PAYMENT_BACKEND='disabled'):
            self.assertIsNone(self.bootstrap()['conversion_experiment']['variant'])
            self.assertFalse(self.expose('price','pricing').json()['recorded'])
        SafetyControl.objects.update(halted=True)
        self.assertIsNone(self.bootstrap()['conversion_experiment']['variant'])
        SafetyControl.objects.update(halted=False)
        self.base.active = False
        self.base.save()
        self.assertIsNone(self.bootstrap()['conversion_experiment']['variant'])

    def test_live_report_counts_mature_eligible_users_and_only_actual_post_exposure_outcomes(self):
        now = timezone.now()
        start = now - timedelta(days=10)
        first_preview = self.preview()
        def enroll(account, *, variant='treatment', environment='live', when=start):
            item = ConversionExposure.objects.create(account=account, experiment='preview', variant=variant,
                environment=environment, surface='preview', preview_id=first_preview.pk)
            ConversionExposure.objects.filter(pk=item.pk).update(exposed_at=when)
        enroll(self.account)
        enroll(self.account, environment='demo')
        for i, (variant, at) in enumerate([('treatment', start), ('control', start), ('control', now)]):
            user = get_user_model().objects.create_user('p'+str(i))
            enroll(Account.objects.create(user=user, phone_hash=user.username), variant=variant, when=at)
        def sale(created, credited, environment='live', **extra):
            obj = CreditPurchase.objects.create(owner=self.user, package=self.base, idempotency_key=uuid.uuid4(),
                environment=environment, credited_at=credited, amount_toman=30000, message_count=9, **extra)
            CreditPurchase.objects.filter(pk=obj.pk).update(created_at=created)
            return obj
        sale(start-timedelta(hours=1), start+timedelta(hours=1))
        sale(start,start,environment='demo')
        sale(start,start+timedelta(days=8))
        sale(start,None)
        sale(start,start, payment_method='card', wallet_refund_consent=False)
        first = sale(start, start+timedelta(hours=2))
        sale(start, start+timedelta(days=1))
        order = Order.objects.create(owner=self.user, preview=first_preview, idempotency_key=uuid.uuid4(),
            uses_purchased_credit=True, payment_mode='credit_live', paid_at=start+timedelta(days=1), amount_toman=0)
        payment = PaymentAttempt.objects.create(purchase=first, environment='live', provider='zarinpal', amount_toman=30000)
        refund = Refund.objects.create(payment=payment, amount_toman=1000)
        event = FinancialEvent.objects.create(payment=payment, kind='refund', refund=refund, amount_toman=1000)
        FinancialEvent.objects.filter(pk=event.pk).update(created_at=start+timedelta(days=2))
        delivery = MessageDelivery.objects.create(order=order, environment='live', provider='kavenegar', attempts=1)
        budget = SpendBudget.objects.create(day=start.date(), limit_rial=500)
        SpendReservation.objects.create(operation_key='sms:'+str(delivery.submission_key), budget=budget, kind='sms',
            amount_rial=500, actual_rial=120)
        out = io.StringIO()
        call_command('conversion_report', 'preview', '--treatment-cost-toman', '3000', stdout=out)
        arms = json.loads(out.getvalue())['arms']
        self.assertEqual(arms['control']['awaiting_full_window'],1)
        self.assertIsNone(arms['control']['net_contribution_per_eligible_user_toman'])
        arm = arms['treatment']
        self.assertEqual(arm['eligible_users_with_full_window'],2)
        self.assertEqual(arm['first_purchase_rate'],0.5)
        self.assertEqual(arm['first_purchase_mix_units_per_toman'], {'9/30000':1})
        self.assertEqual(arm['credited_package_revenue_toman'],60000)
        self.assertEqual(arm['recorded_refunds_toman'],1000)
        self.assertEqual(arm['net_contribution_per_eligible_user_toman'],28000)
        self.assertEqual(arm['known_order_sms_cost_rial'],120)
        self.assertEqual(arm['same_preview_confirmed_after_first_purchase'],1)
