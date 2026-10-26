import json
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_live_sms as live
from .models import Account, MessageDelivery, Order, Outbox, RecipientState, SafetyControl, SpendBudget
from .provider_delivery import submit_delivery
from .services import APIError, error_response
from .status_reasons import RECIPIENT_LIMIT, REQUEST_UNAVAILABLE
from .tasks import expire_unpaid_orders


class PublicStatusReasonTests(TestCase):
    setUp = live.LiveGiftSMSTests.setUp
    post = live.LiveGiftSMSTests.post
    authenticate = live.LiveGiftSMSTests.authenticate
    preview = live.LiveGiftSMSTests.preview
    make_order = live.LiveGiftSMSTests.make_order
    confirm = live.LiveGiftSMSTests.confirm

    def queue(self):
        order = self.make_order().json()
        self.confirm(order)
        return Order.objects.get(pk=order['id']), Outbox.objects.get(order_id=order['id'])

    def detail(self, order):
        response = self.client.get('/api/v1/orders/' + str(order.pk))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_sender_limits_and_self_recipient_explain_the_correct_action(self):
        response = self.make_order(recipient='09123456789')
        self.assertEqual(response.json()['error']['code'], 'self_recipient')
        order = self.make_order().json()
        Order.objects.filter(pk=order['id']).update(status='accepted', paid_at=timezone.now())
        response = self.make_order()
        self.assertEqual(response.json()['error']['code'], 'pair_cooldown')
        self.assertIn('24', response.json()['error']['message'])
        with override_settings(SENDER_DAILY_LIMIT=1):
            response = self.make_order(recipient='09901234568')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['error']['code'], 'daily_limit')
        self.assertIn('۲۴ ساعت', response.json()['error']['message'])

    def test_receiver_block_cooldown_and_busy_order_have_identical_public_errors(self):
        order = self.make_order().json()
        state = RecipientState.objects.get()
        responses = []
        for blocked, last_sent in [(False, None), (True, None), (False, timezone.now())]:
            # The first case is an existing open order, not a blocked receiver.
            Order.objects.filter(pk=order['id']).update(status='awaiting_payment' if not blocked and last_sent is None else 'failed')
            RecipientState.objects.filter(pk=state.pk).update(blocked=blocked, last_sent_at=last_sent)
            response = self.make_order()
            self.assertEqual(response.status_code, 409)
            responses.append(response.json()['error'])
        self.assertEqual(responses, [{'code': 'recipient_unavailable', 'message': RECIPIENT_LIMIT}] * 3)

    def test_worker_records_account_and_recipient_restrictions_and_returns_credit_once(self):
        for account_blocked in [True, False]:
            with self.subTest(account_blocked=account_blocked):
                order, event = self.queue()
                if account_blocked:
                    Account.objects.filter(user=self.user).update(suspended=True)
                else:
                    RecipientState.objects.filter(phone_hash=order.recipient_hash).update(blocked=True)
                with patch('core.provider_delivery.Kavenegar.submit') as wire:
                    submit_delivery(event.pk)
                    submit_delivery(event.pk)
                wire.assert_not_called()
                result = self.detail(order)
                self.assertEqual(result['status_reason']['code'], 'account_unavailable' if account_blocked else 'recipient_unavailable')
                self.assertEqual(result['financial_status'], 'free_credit_returned')
                self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
                # The historical reason never changes when preferences change.
                RecipientState.objects.filter(phone_hash=order.recipient_hash).update(blocked=False)
                self.assertEqual(self.detail(order)['status_reason'], result['status_reason'])
                Account.objects.filter(user=self.user).update(suspended=False)
                # The next iteration uses the same recipient after a definitive failure.

    def test_content_rejection_is_public_but_budget_failure_is_generic(self):
        order, event = self.queue()
        Order.objects.filter(pk=order.pk).update(text='متن دستکاری‌شده')
        with patch('core.provider_delivery.Kavenegar.submit') as wire:
            submit_delivery(event.pk)
        wire.assert_not_called()
        self.assertEqual(self.detail(order)['status_reason']['code'], 'moderation_rejected')
        order, event = self.queue()
        SpendBudget.objects.update_or_create(day=timezone.localdate(), defaults={'reserved_rial':100000, 'limit_rial':100000})
        with patch('core.provider_delivery.Kavenegar.submit') as wire:
            submit_delivery(event.pk)
        wire.assert_not_called()
        result = self.detail(order)
        self.assertEqual(result['status_reason']['code'], 'send_unavailable')
        self.assertNotIn('اعتبار', result['status_reason']['message'])
        self.assertNotIn('policy_unavailable', json.dumps(result))

    def test_order_and_queue_expiry_are_explained_in_detail_and_history(self):
        order = Order.objects.get(pk=self.make_order().json()['id'])
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now()-timedelta(minutes=16))
        expire_unpaid_orders()
        self.assertEqual(self.detail(order)['status_reason']['code'], 'order_expired')
        queued, event = self.queue()
        Order.objects.filter(pk=queued.pk).update(paid_at=timezone.now()-timedelta(hours=25))
        expire_unpaid_orders()
        self.assertEqual(self.detail(queued)['status_reason']['code'], 'queue_expired')
        history = self.client.get('/api/v1/messages').json()['results']
        self.assertEqual({item['status_reason']['code'] for item in history}, {'order_expired', 'queue_expired'})

    def test_sending_hours_are_explained_and_private_pauses_do_not_keep_stale_reasons(self):
        order, event = self.queue()
        with override_settings(SENDING_WINDOW_ENABLED=True), patch('core.safety.timezone.localtime', return_value=timezone.now().replace(hour=23)):
            submit_delivery(event.pk)
        self.assertEqual(self.detail(order)['status_reason']['code'], 'sending_window')
        SafetyControl.objects.filter(pk=1).update(halted=True)
        Outbox.objects.filter(pk=event.pk).update(available_at=timezone.now())
        submit_delivery(event.pk)
        self.assertIsNone(self.detail(order)['status_reason'])

    def test_internal_codes_never_leak_and_success_does_not_show_stale_failures(self):
        order, event = self.queue()
        for code in ['policy_unavailable', 'sms_disabled', 'provider_rejected', 'provider_terminal_failure', 'daily_budget_exhausted', 'private-upstream-error']:
            Order.objects.filter(pk=order.pk).update(status='failed')
            MessageDelivery.objects.filter(order=order).update(last_error_code=code)
            result = self.detail(order)
            self.assertEqual(result['status_reason']['code'], 'send_unavailable')
            self.assertNotIn(code, json.dumps(result))
        Order.objects.filter(pk=order.pk).update(status='accepted')
        self.assertIsNone(self.detail(order)['status_reason'])
        Order.objects.filter(pk=order.pk).update(status='unknown')
        self.assertEqual(self.detail(order)['status_reason']['code'], 'result_pending')

    def test_system_api_messages_are_sanitized_but_user_errors_are_preserved(self):
        response = error_response(APIError('service_unavailable', 'اعتبار پنل تمام شد / upstream secret', 503, {'detail':'private'}))
        self.assertEqual(json.loads(response.content)['error'], {'code':'service_unavailable', 'message':REQUEST_UNAVAILABLE})
        response = error_response(APIError('daily_limit', 'سقف درخواست‌های شما تکمیل شده', 429))
        self.assertIn('سقف', json.loads(response.content)['error']['message'])
