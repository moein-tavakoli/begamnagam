import io
import re
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import tests as legacy
from .models import Account, MessageAttempt, Order, Outbox, Preview, RecipientGrant, SafetyControl
from .moderation import ModerationRejected
from .privacy import decrypt
from .tasks import deliver_message


@override_settings(
    APP_BASE_URL='https://begamnagam.ir', AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key',
    GAPGPT_MODEL='synthetic-model', GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=10,
    RECIPIENT_COOLDOWN_HOURS=0, SENDER_RECIPIENT_COOLDOWN_HOURS=0, SENDER_DAILY_LIMIT=10,
)
class AnonymousReplyTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    first_phone = '09123456789'
    second_phone = '09901234567'
    text = 'ممنونم که برای گفت‌وگو وقت گذاشتی.'

    def setUp(self):
        cache.clear()
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})
        self.other = Client()
        self.sender = self.authenticate(self.first_phone, free_sends=None)
        self.receiver = self.authenticate(self.second_phone, self.other, free_sends=None)

    def preview(self, client, **target):
        with patch('core.gapgpt.rewrite_message', return_value=self.text) as model:
            response = client.post('/api/v2/message-previews', {
                'text': self.text, 'source_mode': 'freeform', 'message_tone': 'firm', **target,
            }, content_type='application/json')
        if response.status_code == 201:
            model.assert_called_once()
            self.assertEqual(model.call_args.kwargs['message_tone'], 'firm')
        else:
            model.assert_not_called()
        return response

    def reserve(self, client, preview, *, key=None, **target):
        return client.post('/api/v2/messages', {
            'preview_id': preview['preview_id'], 'consent': True, 'terms_version': preview['terms_version'], **target,
        }, content_type='application/json', HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))

    def deliver(self, client, order):
        response = self.post(f'/orders/{order["id"]}/confirm-free', {}, client)
        self.assertEqual(response.status_code, 200, response.content)
        deliver_message(Outbox.objects.get(order_id=order['id']).pk)
        self.assertEqual(Order.objects.get(pk=order['id']).status, Order.Status.DELIVERED_DEMO)

    def reply_token(self, preview):
        snapshot = Preview.objects.get(pk=preview['preview_id']).full_sms
        match = re.search(r'پاسخ: begamnagam\.ir/r/([a-z5-9][A-Za-z0-9]{4})', snapshot)
        self.assertIsNotNone(match, snapshot)
        self.assertRegex(snapshot, r'لغو: begamnagam\.ir/r/[A-Z0-4][A-Za-z0-9]{4}$')
        return match.group(1)

    def test_three_reviewed_replies_then_close_the_thread(self):
        initial = self.preview(self.client, recipient_phone=self.second_phone)
        self.assertEqual(initial.status_code, 201, initial.content)
        preview = initial.json()
        token = self.reply_token(preview)
        order = self.reserve(self.client, preview, recipient_phone=self.second_phone).json()
        self.assertEqual(self.preview(self.other, reply_token=token).status_code, 404)
        self.deliver(self.client, order)
        self.assertEqual(self.post('/recipient/actions/reply', {'token': token}, Client()).status_code, 401)
        self.assertEqual(self.post('/recipient/actions/reply', {'token': token}, self.other).json(), {'active': True})
        self.assertEqual(self.preview(self.client, reply_token=token).status_code, 404)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': token}).status_code, 404)

        first_reply_id = None
        for index, (client, hidden) in enumerate(((self.other, self.first_phone),
                                                  (self.client, self.second_phone),
                                                  (self.other, self.first_phone)), start=1):
            response = self.preview(client, reply_token=token)
            self.assertEqual(response.status_code, 201, response.content)
            preview = response.json()
            self.assertTrue(preview['is_reply'])
            self.assertNotIn(hidden, response.content.decode())
            self.assertNotIn('/r/', preview['full_sms'])
            fetched = client.get(f"/api/v2/message-previews/{preview['preview_id']}").json()
            self.assertEqual(fetched, preview)
            forged = self.reserve(client, preview, recipient_phone='09999999999')
            self.assertEqual(forged.status_code, 422, forged.content)
            key = str(uuid.uuid4())
            response = self.reserve(client, preview, key=key)
            self.assertEqual(response.status_code, 200, response.content)
            order = response.json()
            self.assertEqual(self.reserve(client, preview, key=key).json()['id'], order['id'])
            self.assertTrue(order['is_reply'])
            self.assertEqual(order['recipient_phone'], '')
            self.assertEqual(order['recipient_masked'], '')
            self.assertNotIn('/r/', order['text'])
            self.assertEqual(decrypt(Order.objects.get(pk=order['id']).recipient_cipher), hidden)
            self.deliver(client, order)
            self.assertEqual(self.preview(client, reply_token=token).status_code, 404)
            if index == 1:
                first_reply_id = order['id']
            if index == 2:
                Order.objects.filter(pk=first_reply_id).update(updated_at=timezone.now()-timedelta(days=32))
                call_command('prune_private_data', stdout=io.StringIO())
                redacted = Order.objects.get(pk=first_reply_id)
                self.assertEqual(redacted.reply_depth, 1)
                self.assertIsNone(redacted.reply_to_id)
                self.assertIsNone(redacted.preview.reply_to_id)
            if index < 3:
                token = self.reply_token(preview)
            else:
                snapshot = Preview.objects.get(pk=preview['preview_id']).full_sms
                self.assertNotIn('پاسخ:', snapshot)
                self.assertRegex(snapshot, r'لغو: begamnagam\.ir/r/[A-Z0-4][A-Za-z0-9]{4}$')
                self.assertIsNone(RecipientGrant.objects.get(preview_id=preview['preview_id']).reply_token_digest)
        self.assertEqual(Order.objects.count(), 4)
        self.assertEqual(Account.objects.get(user=self.sender).free_sends_remaining, 1)
        self.assertEqual(Account.objects.get(user=self.receiver).free_sends_remaining, 1)

    def test_existing_eight_character_reply_requires_the_original_verified_recipient(self):
        with patch('core.recipient.generate_short_code', side_effect=['Ab12Cd34', 'Ef56Gh78']):
            preview = self.preview(self.client, recipient_phone=self.second_phone).json()
        self.assertIn('begamnagam.ir/r/pEf56Gh78', preview['full_sms'])
        order = self.reserve(self.client, preview, recipient_phone=self.second_phone).json()
        self.deliver(self.client, order)
        self.assertEqual(self.post('/recipient/actions/reply', {'token': 'Ef56Gh78'}, self.client).status_code, 404)
        self.assertEqual(self.post('/recipient/actions/reply', {'token': 'Ef56Gh78'}, self.other).json(), {'active': True})

    def test_rejected_reply_attempt_keeps_server_resolved_destination_for_staff(self):
        preview = self.preview(self.client, recipient_phone=self.second_phone).json()
        order = self.reserve(self.client, preview, recipient_phone=self.second_phone).json()
        self.deliver(self.client, order)
        with patch('core.gapgpt.rewrite_message', side_effect=ModerationRejected('unsafe_content')):
            response = self.other.post('/api/v2/message-previews', {
                'source_mode': 'freeform', 'text': self.text, 'reply_token': self.reply_token(preview),
            }, content_type='application/json')
        self.assertEqual(response.status_code, 422, response.content)
        self.assertNotIn(self.first_phone, response.content.decode())
        attempt = MessageAttempt.objects.get(owner=self.receiver)
        self.assertEqual(attempt.status, 'rejected')
        self.assertEqual(attempt.recipient_phone, self.first_phone)

    def test_two_previews_compete_for_one_turn_and_expired_capability_is_denied(self):
        original = self.preview(self.client, recipient_phone=self.second_phone).json()
        order = self.reserve(self.client, original, recipient_phone=self.second_phone).json()
        self.deliver(self.client, order)
        token = self.reply_token(original)
        grant = RecipientGrant.objects.get(preview_id=original['preview_id'])
        expires = grant.report_expires_at
        RecipientGrant.objects.filter(pk=grant.pk).update(report_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.preview(self.other, reply_token=token).status_code, 404)
        RecipientGrant.objects.filter(pk=grant.pk).update(report_expires_at=expires)
        with override_settings(AI_MODE='template'):
            self.assertEqual(self.preview(self.other, reply_token=token).status_code, 409)
        first = self.preview(self.other, reply_token=token).json()
        second = self.preview(self.other, reply_token=token).json()
        self.assertEqual(self.reserve(self.other, first).status_code, 200)
        self.assertEqual(self.reserve(self.other, second).status_code, 404)
        self.assertEqual(Account.objects.get(user=self.receiver).free_sends_remaining, 2)

    def test_accepted_reply_never_reopens_its_turn_after_late_failure(self):
        original = self.preview(self.client, recipient_phone=self.second_phone).json()
        order = self.reserve(self.client, original, recipient_phone=self.second_phone).json()
        self.deliver(self.client, order)
        token = self.reply_token(original)
        first = self.preview(self.other, reply_token=token).json()
        second = self.preview(self.other, reply_token=token).json()
        reply = self.reserve(self.other, first).json()
        self.deliver(self.other, reply)
        Order.objects.filter(pk=reply['id']).update(status=Order.Status.FAILED)
        self.assertEqual(self.reserve(self.other, second).status_code, 404)
        self.assertEqual(self.preview(self.other, reply_token=token).status_code, 404)

    def test_reply_with_unsafe_content_cannot_be_reserved_or_sent(self):
        original = self.preview(self.client, recipient_phone=self.second_phone).json()
        order = self.reserve(self.client, original, recipient_phone=self.second_phone).json()
        self.deliver(self.client, order)
        with patch('core.gapgpt.rewrite_message') as model:
            response = self.other.post('/api/v2/message-previews', {
                'source_mode': 'freeform', 'reply_token': self.reply_token(original),
                'text': 'می کشمت اگر پولم را ندهی', 'message_tone': 'blunt',
            }, content_type='application/json')
        self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(response.json()['error'].get('details', {}).get('alternatives'))
        model.assert_not_called()
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Preview.objects.count(), 1)

    def test_pending_reservations_do_not_reveal_the_reply_recipient(self):
        original = self.preview(self.client, recipient_phone=self.second_phone).json()
        order = self.reserve(self.client, original, recipient_phone=self.second_phone).json()
        self.deliver(self.client, order)
        token = self.reply_token(original)
        # Inspecting a delivered link reveals no information about the sender's account state.
        Account.objects.filter(user=self.sender).update(suspended=True, deletion_requested_at=timezone.now())
        self.assertEqual(self.post('/recipient/actions/reply', {'token': token}, self.other).status_code, 200)
        reply = self.preview(self.other, reply_token=token).json()
        reserved_reply = self.reserve(self.other, reply)
        self.assertEqual(reserved_reply.status_code, 200, reserved_reply.content)
        ordinary = self.preview(self.other, recipient_phone=self.first_phone).json()
        reserved_ordinary = self.reserve(self.other, ordinary, recipient_phone=self.first_phone)
        self.assertEqual(reserved_ordinary.status_code, 200, reserved_ordinary.content)
        reply_id = reserved_reply.json()['id']
        ordinary_id = reserved_ordinary.json()['id']
        self.assertEqual(self.post(f'/orders/{reply_id}/confirm-free', {}, self.other).status_code, 200)
        response = self.post(f'/orders/{ordinary_id}/confirm-free', {}, self.other)
        self.assertEqual(response.status_code, 409, response.content)
        self.assertEqual(response.json()['error']['code'], 'recipient_unavailable')
        self.assertEqual(Outbox.objects.exclude(order_id=order['id']).count(), 1)

    @override_settings(DEMO_MODE=False, SMS_BACKEND='kavenegar', PROVIDER_NETWORK_MODE='external',
        LIVE_PROVIDERS_ENABLED=True, PROVIDER_ENVIRONMENT='live', SMS_RECIPIENT_POLICY='all',
        SMS_MAX_COST_RIAL=20000, PROVIDER_DAILY_BUDGET_RIAL=100000, SENDING_WINDOW_ENABLED=False)
    def test_live_adapter_uses_the_sealed_reply_and_hidden_destination(self):
        from django.contrib.auth import get_user_model

        from .provider_delivery import submit_delivery
        from .providers.kavenegar import SMSResult

        with patch('core.provider_delivery.Kavenegar.submit', side_effect=[
            SMSResult('accepted', '7001', 1000), SMSResult('accepted', '7002', 1000),
        ]) as wire:
            original = self.preview(self.client, recipient_phone=self.second_phone).json()
            order = self.reserve(self.client, original, recipient_phone=self.second_phone).json()
            self.assertEqual(self.post(f'/orders/{order["id"]}/confirm-free').status_code, 200)
            submit_delivery(Outbox.objects.get(order_id=order['id']).pk)
            editor = Client()
            editor.force_login(get_user_model().objects.create_superuser('sms-editor'))
            saved = editor.put('/api/v1/manage/sms-template', {
                'template': 'متن شما «{{message}}» · {{opt_out}} سپس {{reply}}\nسپاس از همراهی {{reply}}',
                'variables': [], 'revision': 0,
            }, content_type='application/json')
            self.assertEqual(saved.status_code, 200, saved.content)
            with override_settings(SMS_LINK_HOST='bgam.ir', SMS_LINK_ROOT_PATH=True):
                reply = self.preview(self.other, reply_token=self.reply_token(original)).json()
            self.assertNotIn('bgam.ir/', reply['full_sms'])
            self.assertIn('لینک لغو دریافت سپس لینک پاسخ\nسپاس از همراهی لینک پاسخ', reply['full_sms'])
            reserved = self.reserve(self.other, reply).json()
            self.assertEqual(reserved['text'], reply['full_sms'])
            self.assertEqual(self.post(f'/orders/{reserved["id"]}/confirm-free', {}, self.other).status_code, 200)
            event = Outbox.objects.get(order_id=reserved['id'])
            submit_delivery(event.pk)
            submit_delivery(event.pk)
        self.assertEqual(wire.call_count, 2)
        actual = wire.call_args.kwargs
        self.assertEqual(actual['phone'], self.first_phone)
        self.assertEqual(actual['text'], Preview.objects.get(pk=reply['preview_id']).full_sms)
        self.assertRegex(actual['text'], r'لغو: bgam\.ir/[A-Z0-4][A-Za-z0-9]{4} سپس پاسخ: bgam\.ir/[a-z5-9][A-Za-z0-9]{4}')
        self.assertEqual(actual['text'].count('پاسخ: bgam.ir/'), 2)
        self.assertNotIn(self.second_phone, actual['text'])
