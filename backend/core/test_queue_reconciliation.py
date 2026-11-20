import uuid
from datetime import timedelta
from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import FinancialEvent, Invitation, InvitationSend, MessageDelivery, Order, Outbox, PaymentAttempt, Preview, Refund
from .provider_services import process_refund, reconcile_payments
from .providers import ProviderUnknown
from .safety import operator_action
from .tasks import expire_unpaid_orders, reconcile_providers


class QueueReconciliationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('queue-reconciliation')
        cls.now = timezone.now()
        previews = Preview.objects.bulk_create([
            Preview(owner=cls.owner, price_toman=1000, expires_at=cls.now)
            for _ in range(104)
        ])
        cls.orders = Order.objects.bulk_create([
            Order(owner=cls.owner, preview=preview, idempotency_key=uuid.uuid4(), amount_toman=1000)
            for preview in previews
        ])

    def test_sms_batch_skips_active_leases_and_cooldowns(self):
        deliveries = MessageDelivery.objects.bulk_create([
            MessageDelivery(order=order, provider='kavenegar', environment='live', status='unknown')
            for order in self.orders
        ])
        MessageDelivery.objects.filter(pk__in=[row.pk for row in deliveries[:100]]).update(checked_at=self.now)
        MessageDelivery.objects.filter(pk=deliveries[100].pk).update(lease_until=self.now + timedelta(minutes=1))
        MessageDelivery.objects.filter(pk=deliveries[101].pk).update(status='delivered')
        MessageDelivery.objects.filter(pk=deliveries[102].pk).update(checked_at=self.now - timedelta(minutes=2))

        with (
            patch('core.provider_delivery.reconcile_delivery') as reconcile,
            patch('core.provider_services.reconcile_payments'),
            patch('core.safety.refresh_alerts'),
        ):
            reconcile_providers()

        self.assertEqual(reconcile.call_count, 2)
        self.assertEqual(reconcile.call_args_list, [call(deliveries[102].pk), call(deliveries[103].pk)])

    @override_settings(PROVIDER_ENVIRONMENT='sandbox')
    def test_payment_batch_checks_eligible_attempts_instead_of_cooling_prefix(self):
        attempts = PaymentAttempt.objects.bulk_create([
            PaymentAttempt(order=order, provider='zarinpal', environment='sandbox', status='pending',
                           amount_toman=1000, authority=f'test-authority-{index}')
            for index, order in enumerate(self.orders)
        ])
        PaymentAttempt.objects.filter(pk__in=[row.pk for row in attempts[:100]]).update(
            created_at=self.now - timedelta(minutes=4), checked_at=self.now)
        PaymentAttempt.objects.filter(pk=attempts[100].pk).update(lease_until=self.now + timedelta(minutes=1))
        PaymentAttempt.objects.filter(pk=attempts[101].pk).update(environment='live')
        PaymentAttempt.objects.filter(pk=attempts[102].pk).update(checked_at=self.now - timedelta(minutes=2))

        with patch('core.provider_services.verify_payment') as verify, self.assertNumQueries(1):
            reconcile_payments()

        self.assertEqual(verify.call_count, 2)
        self.assertEqual(verify.call_args_list, [call(attempts[102].pk), call(attempts[103].pk)])

    def test_invitation_batch_prioritizes_longest_wait_since_last_poll(self):
        invitation = Invitation.objects.create(inviter=self.owner, phone_hash='queue-test')
        sends = InvitationSend.objects.bulk_create([
            InvitationSend(invitation=invitation, ordinal=index, idempotency_key=uuid.uuid4(),
                           consent_at=self.now, provider='kavenegar', status='unknown', available_at=self.now)
            for index in range(1, 102)
        ])
        InvitationSend.objects.filter(pk__in=[row.pk for row in sends[:100]]).update(
            created_at=self.now - timedelta(hours=2), checked_at=self.now - timedelta(minutes=6))
        InvitationSend.objects.filter(pk=sends[100].pk).update(created_at=self.now - timedelta(minutes=7))

        with (
            patch('core.invitation_delivery.reconcile') as reconcile,
            patch('core.provider_services.reconcile_payments'),
            patch('core.safety.refresh_alerts'),
        ):
            reconcile_providers()

        self.assertEqual(reconcile.call_count, 100)
        self.assertEqual(reconcile.call_args_list[0], call(sends[100].pk))

    def test_expiry_batch_skips_orders_that_already_entered_submission(self):
        order_ids = [order.pk for order in self.orders]
        old = self.now - timedelta(hours=25)
        Order.objects.filter(pk__in=order_ids).update(status='queued', paid_at=old)
        Outbox.objects.bulk_create([
            Outbox(order=order, state='submitting' if index < 103 else 'pending', available_at=old)
            for index, order in enumerate(self.orders)
        ])
        MessageDelivery.objects.bulk_create([
            MessageDelivery(order=order, status='submitting' if index < 103 else 'queued')
            for index, order in enumerate(self.orders)
        ])

        with patch('core.services.record_demo_refund') as refund:
            expire_unpaid_orders()

        expired = self.orders[-1]
        expired.refresh_from_db()
        self.assertEqual(expired.status, 'cancelled')
        self.assertEqual(expired.outbox.state, 'cancelled')
        self.assertEqual(expired.delivery.status, 'expired')
        refund.assert_called_once_with(expired, 'queue_expired')
        self.assertEqual(Order.objects.filter(pk__in=order_ids, status='queued').count(), 103)

    def make_refund(self):
        attempt = PaymentAttempt.objects.create(order=self.orders[0], provider='zarinpal',
            environment='sandbox', status='verified', amount_toman=1000, authority='fixture-refund')
        return Refund.objects.create(payment=attempt, amount_toman=1000, reason_code='test')

    def test_refund_preserves_operator_confirmation_after_provider_timeout(self):
        refund = self.make_refund()
        operator = get_user_model().objects.create_superuser('queue-operator')

        def confirm_then_timeout(**kwargs):
            operator_action(operator, 'confirm_refund', refund.pk, 'operator reviewed', 'documented')
            raise ProviderUnknown('timeout')

        with patch('core.provider_services.Zarinpal') as provider:
            provider.return_value.reverse.side_effect = confirm_then_timeout
            process_refund(refund.pk)

        refund.refresh_from_db()
        self.assertEqual(refund.status, 'refunded')
        self.assertEqual(refund.provider_reference, 'manual:documented')
        self.assertEqual(FinancialEvent.objects.filter(refund=refund, kind='refund').count(), 1)

    def test_refund_preserves_operator_reference_after_provider_success(self):
        refund = self.make_refund()
        operator = get_user_model().objects.create_superuser('queue-operator')

        with patch('core.provider_services.Zarinpal') as provider:
            provider.return_value.reverse.side_effect = lambda **kwargs: operator_action(
                operator, 'confirm_refund', refund.pk, 'operator reviewed', 'documented')
            process_refund(refund.pk)

        refund.refresh_from_db()
        self.assertEqual(refund.status, 'refunded')
        self.assertEqual(refund.provider_reference, 'manual:documented')
        self.assertEqual(FinancialEvent.objects.filter(refund=refund, kind='refund').count(), 1)

    def test_refund_timeout_cannot_clear_a_newer_processing_claim(self):
        refund = self.make_refund()
        newer_claim = self.now + timedelta(seconds=31)

        def reclaim_then_timeout(**kwargs):
            Refund.objects.filter(pk=refund.pk).update(updated_at=newer_claim)
            raise ProviderUnknown('timeout')

        with patch('core.provider_services.Zarinpal') as provider:
            provider.return_value.reverse.side_effect = reclaim_then_timeout
            process_refund(refund.pk)

        refund.refresh_from_db()
        self.assertEqual(refund.status, 'processing')
        self.assertEqual(refund.updated_at, newer_claim)
        self.assertFalse(FinancialEvent.objects.filter(refund=refund).exists())

    def test_refund_records_proven_reversal_even_after_a_newer_claim(self):
        refund = self.make_refund()

        with patch('core.provider_services.Zarinpal') as provider:
            provider.return_value.reverse.side_effect = lambda **kwargs: Refund.objects.filter(pk=refund.pk).update(
                updated_at=self.now + timedelta(seconds=31))
            process_refund(refund.pk)

        refund.refresh_from_db()
        self.assertEqual(refund.status, 'refunded')
        self.assertEqual(refund.provider_reference, 'reverse-fixture-refund')
        self.assertEqual(FinancialEvent.objects.filter(refund=refund, kind='refund').count(), 1)
