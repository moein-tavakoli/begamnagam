import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from .adapters import AdapterDisabled, payment_adapter, sms_adapter
from .models import FinancialEvent, MessageDelivery, Order, PaymentAttempt, Preview, Refund


class FinancialFoundationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='foundation')
        self.order = self.make_order()

    def make_order(self):
        from .moderation import TEMPLATES
        from .sms import compose_recipient_sms
        reviewed, sms = compose_recipient_sms('appreciation', TEMPLATES['appreciation'][0], 'example.test', '')
        preview = Preview.objects.create(owner=self.user, session_key='synthetic', category='appreciation',
            text=reviewed, full_sms=sms, moderation_mode='template', price_toman=2000,
            expires_at=timezone.now() + timedelta(minutes=15))
        return Order.objects.create(owner=self.user, preview=preview, idempotency_key=uuid.uuid4(),
            recipient_hash='synthetic-hash', recipient_cipher='', recipient_masked='synthetic',
            text=preview.text, full_sms=preview.full_sms, category=preview.category, amount_toman=2000)

    def payment(self, **kwargs):
        return PaymentAttempt.objects.create(order=self.order, amount_toman=2000, **kwargs)

    def assert_constraint(self, operation):
        with self.assertRaises(IntegrityError), transaction.atomic():
            operation()

    def test_pending_payment_cannot_be_applied(self):
        self.assert_constraint(lambda: self.payment(applied_to_order=True))

    def test_only_one_verified_payment_is_applied_but_extra_receipts_can_be_recorded(self):
        self.payment(status='verified', applied_to_order=True)
        self.payment(status='verified', applied_to_order=False)
        self.assert_constraint(lambda: self.payment(status='verified', applied_to_order=True))

    def test_provider_reference_cannot_be_reused(self):
        self.payment(provider_reference='synthetic-provider-id')
        self.assert_constraint(lambda: self.payment(provider_reference='synthetic-provider-id'))

    def test_database_disallows_live_records_and_wrong_units(self):
        self.assert_constraint(lambda: self.payment(environment='live'))
        self.assert_constraint(lambda: self.payment(provider='real'))
        self.assert_constraint(lambda: self.payment(currency='IRR'))
        self.assert_constraint(lambda: MessageDelivery.objects.create(order=self.order, environment='live'))

    def test_positive_financial_amounts_only(self):
        self.assert_constraint(lambda: PaymentAttempt.objects.create(order=self.order, amount_toman=0))
        payment = self.payment()
        self.assert_constraint(lambda: Refund.objects.create(payment=payment, amount_toman=0, reason_code='test'))

    def test_delivery_and_payment_status_are_independent(self):
        payment = self.payment(status='verified', applied_to_order=True)
        delivery = MessageDelivery.objects.create(order=self.order, status='unknown')
        self.assertEqual(payment.status, 'verified')
        self.assertEqual(delivery.status, 'unknown')
        self.assert_constraint(lambda: MessageDelivery.objects.create(order=self.order))

    def test_financial_event_requires_correct_refund_relation_and_unique_capture(self):
        payment = self.payment(status='verified')
        FinancialEvent.objects.create(payment=payment, kind='payment', amount_toman=2000)
        self.assert_constraint(lambda: FinancialEvent.objects.create(payment=payment, kind='payment', amount_toman=2000))
        self.assert_constraint(lambda: FinancialEvent.objects.create(payment=payment, kind='refund', amount_toman=2000))
        refund = Refund.objects.create(payment=payment, amount_toman=2000, reason_code='test')
        FinancialEvent.objects.create(payment=payment, refund=refund, kind='refund', amount_toman=2000)

    def test_demo_adapters_are_repeatable_and_other_adapters_are_disabled(self):
        key = uuid.uuid4()
        self.assertEqual(payment_adapter('demo').verify(attempt_id=key, amount_toman=2000),
            payment_adapter('demo').verify(attempt_id=key, amount_toman=2000))
        self.assertEqual(sms_adapter('demo').submit(submission_id=key).status, 'delivered_demo')
        for name in ['disabled', 'live', 'unknown']:
            with self.assertRaises(AdapterDisabled): payment_adapter(name)
            with self.assertRaises(AdapterDisabled): sms_adapter(name)

    def test_demo_checkout_records_one_capture_delivery_and_compensating_refund(self):
        from .models import RecipientState, Outbox
        from .services import pay_order
        from .tasks import deliver_message
        RecipientState.objects.create(phone_hash=self.order.recipient_hash)
        # A pre-cutover paid receipt, not a new direct checkout.
        attempt = self.payment(status='verified', applied_to_order=True, provider_reference='historical-demo-capture')
        FinancialEvent.objects.create(payment=attempt, kind='payment', amount_toman=2000)
        Order.objects.filter(pk=self.order.pk).update(paid_at=timezone.now(), payment_mode='demo', status='queued')
        MessageDelivery.objects.create(order=self.order, provider='demo', environment='demo', status='queued')
        Outbox.objects.create(order=self.order, available_at=timezone.now())
        pay_order(self.user, self.order.id)
        pay_order(self.user, self.order.id)
        self.assertEqual(PaymentAttempt.objects.filter(order=self.order).count(), 1)
        self.assertEqual(FinancialEvent.objects.filter(payment__order=self.order, kind='payment').count(), 1)
        RecipientState.objects.filter(phone_hash=self.order.recipient_hash).update(blocked=True)
        event = Outbox.objects.get(order=self.order)
        deliver_message(event.id)
        deliver_message(event.id)
        self.assertEqual(Refund.objects.filter(payment__order=self.order, status='refunded').count(), 1)
        self.assertEqual(FinancialEvent.objects.filter(payment__order=self.order, kind='refund').count(), 1)
        self.assertEqual(MessageDelivery.objects.get(order=self.order).status, 'suppressed')
