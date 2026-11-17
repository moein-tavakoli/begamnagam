import uuid
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import tests as legacy
from .models import Account, Order, Outbox, Preview, RecipientState
from .privacy import decrypt, digest, mask


@override_settings(APP_BASE_URL='https://begamnagam.ir', AI_MODE='template')
class PersonalShareTests(TestCase):
    post, authenticate = legacy.APITestCase.post, legacy.APITestCase.authenticate
    target_phone = '09901234567'

    def setUp(self):
        cache.clear()
        self.owner_client, self.client = Client(), Client()
        self.owner = self.authenticate(self.target_phone, self.owner_client, free_sends=None)
        self.sender = self.authenticate(free_sends=None)

    def create_link(self):
        response = self.post('/personal-share', client=self.owner_client)
        self.assertEqual(response.status_code, 200, response.content)
        url = response.json()['url']
        parsed = urlsplit(url)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path, parsed.query), ('https', 'begamnagam.ir', '/send', ''))
        self.assertRegex(parsed.fragment, r'^[0-9a-f]{32}$')
        self.assertNotIn(self.target_phone, url)
        return url, parsed.fragment

    def preview(self, token, client=None, **extra):
        return self.post('/messages/preview', {
            'category': 'appreciation', 'text': 'از همراهی‌ات ممنونم!', 'share_token': token, **extra,
        }, client)

    def reserve(self, quote, key=None, client=None, **extra):
        return self.post('/orders', {
            'preview_id': quote['preview_id'], 'consent': True,
            'terms_version': quote['terms_version'], **extra,
        }, client, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def test_opt_in_link_is_stable_and_only_owner_can_revoke_it(self):
        self.assertEqual(self.owner_client.get('/api/v1/personal-share').json(), {'url': None})
        url, token = self.create_link()
        self.assertEqual(self.create_link()[0], url)
        self.assertEqual(self.client.get('/api/v1/personal-share').json(), {'url': None})
        self.assertEqual(self.client.delete('/api/v1/personal-share').status_code, 200)
        self.assertEqual(self.owner_client.get('/api/v1/personal-share').json(), {'url': url})
        self.assertEqual(self.owner_client.delete('/api/v1/personal-share').json(), {'url': None})
        self.assertNotEqual(self.create_link()[0], url)
        self.assertEqual(self.post('/personal-share/resolve', {'share_token': token}).status_code, 404)

    def test_phone_verification_and_csrf_gate_link_actions(self):
        _, token = self.create_link()
        guest = Client(enforce_csrf_checks=True)
        guest.get('/api/v1/bootstrap')
        data = {'share_token': token}
        self.assertEqual(self.post('/personal-share/resolve', data, guest).status_code, 403)
        csrf = guest.cookies['csrftoken'].value
        response = self.post('/personal-share/resolve', data, guest, HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.preview(token, Client()).status_code, 401)
        staff = get_user_model().objects.create_user(username='share-staff', is_staff=True)
        guest.force_login(staff)
        self.assertEqual(guest.get('/api/v1/personal-share').status_code, 401)
        self.assertEqual(self.post('/personal-share/resolve', data, self.owner_client).json()['error']['code'], 'self_recipient')

    def test_shared_destination_is_masked_from_resolution_to_history_and_survives_retry(self):
        _, token = self.create_link()
        selected = self.post('/personal-share/resolve', {'share_token': token})
        self.assertEqual(selected.status_code, 200, selected.content)
        self.assertEqual(selected.json(), {'recipient_masked': mask(self.target_phone)})
        self.assertEqual(selected['Cache-Control'], 'no-store')
        quote = self.preview(token)
        self.assertEqual(quote.status_code, 200, quote.content)
        self.assertNotIn('begamnagam.ir/', quote.json()['full_sms'])
        key = uuid.uuid4()
        created = self.reserve(quote.json(), key=key)
        self.assertEqual(created.status_code, 200, created.content)
        order_id = created.json()['id']
        order = Order.objects.get(pk=order_id)
        self.assertEqual(decrypt(order.recipient_cipher), self.target_phone)
        self.assertEqual(order.recipient_hash, digest(self.target_phone))
        self.assertEqual(self.reserve(quote.json(), key=key).json()['id'], order_id)
        self.assertEqual(Account.objects.get(user=self.sender).free_sends_remaining, 2)
        with self.captureOnCommitCallbacks(execute=False):
            confirmed = self.post(f'/orders/{order_id}/confirm-free')
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        self.assertTrue(Outbox.objects.filter(order=order).exists())
        for record in [created.json(), confirmed.json(),
                       self.client.get(f'/api/v1/orders/{order_id}').json(),
                       self.client.get('/api/v1/messages').json()['results'][0],
                       self.client.get(f'/api/v2/messages/{order_id}').json(),
                       self.client.get('/api/v2/messages').json()['results'][0]]:
            self.assertEqual(record['recipient_phone'], '')
            self.assertEqual(record['recipient_masked'], mask(self.target_phone))
            self.assertNotIn('begamnagam.ir/', record['text'])
        self.owner_client.delete('/api/v1/personal-share')
        self.assertEqual(self.post(f'/orders/{order_id}/confirm-free').json()['status'], 'queued')

    def test_preview_is_bound_to_its_link_and_cannot_be_retargeted(self):
        _, token = self.create_link()
        self.assertEqual(self.preview(token, recipient_phone='09901234568').status_code, 422)
        self.assertEqual(self.preview(token, reply_token='some-reply-token').status_code, 422)
        quote = self.preview(token).json()
        self.assertEqual(self.reserve(quote, recipient_phone=self.target_phone).status_code, 422)
        self.assertEqual(self.reserve(quote, client=self.owner_client).status_code, 404)
        self.owner_client.delete('/api/v1/personal-share')
        self.create_link()
        self.assertEqual(self.reserve(quote).json()['error']['code'], 'share_link_unavailable')
        self.assertFalse(Order.objects.exists())

    def test_revocation_prevents_confirmation_of_an_unsubmitted_order(self):
        _, token = self.create_link()
        order_id = self.reserve(self.preview(token).json()).json()['id']
        self.owner_client.delete('/api/v1/personal-share')
        denied = self.post(f'/orders/{order_id}/confirm-free')
        self.assertEqual(denied.json()['error']['code'], 'share_link_unavailable')
        self.assertFalse(Outbox.objects.exists())

    def test_shared_link_preserves_opt_out_and_has_no_invitation_reward(self):
        _, token = self.create_link()
        RecipientState.objects.update_or_create(phone_hash=digest(self.target_phone), defaults={'blocked': True})
        self.assertEqual(self.post('/personal-share/resolve', {'share_token': token}).status_code, 200)
        rejected = self.reserve(self.preview(token).json())
        self.assertEqual(rejected.json()['error']['code'], 'recipient_unavailable')
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Account.objects.get(user=self.owner).free_sends_earned_total, 0)

    def test_suspended_link_is_unavailable_without_requesting_a_rewrite(self):
        _, token = self.create_link()
        Account.objects.filter(user=self.owner).update(suspended=True)
        self.assertTrue(self.owner_client.get('/api/v1/personal-share').json().get('paused'))
        self.assertEqual(self.post('/personal-share/resolve', {'share_token': token}).status_code, 404)
        with patch('core.views.rewrite') as rewrite:
            self.assertEqual(self.preview(token).json()['error']['code'], 'share_link_unavailable')
        rewrite.assert_not_called()

    def test_shared_recipient_conflicts_use_the_standard_unavailable_response(self):
        _, token = self.create_link()
        order_id = self.reserve(self.preview(token).json()).json()['id']
        Order.objects.filter(pk=order_id).update(status=Order.Status.DELIVERED_DEMO)
        for destination in [{'share_token': token}, {'recipient_phone': self.target_phone}]:
            with self.subTest(shared='share_token' in destination):
                result = self.post('/messages/preview', {
                    'text': 'ممنونم از کمکت', 'category': 'appreciation', **destination,
                })
                added_phone = {key: value for key, value in destination.items() if key == 'recipient_phone'}
                response = self.reserve(result.json(), **added_phone)
                self.assertEqual(response.json()['error']['code'], 'recipient_unavailable')

    def test_retention_removes_link_reference_from_order_history(self):
        url, token = self.create_link()
        quote = self.preview(token).json()
        order_id = self.reserve(quote).json()['id']
        Order.objects.filter(pk=order_id).update(
            status=Order.Status.DELIVERED_DEMO, updated_at=timezone.now()-timedelta(days=32),
        )
        call_command('prune_private_data', stdout=StringIO())
        self.assertIsNone(Preview.objects.get(pk=quote['preview_id']).personal_share_token)
        self.assertEqual(self.owner_client.get('/api/v1/personal-share').json(), {'url': url})
        receipt = self.client.get(f'/api/v1/orders/{order_id}').json()
        self.assertTrue(receipt['is_shared_destination'])
        self.assertEqual(receipt['recipient_phone'], '')

    def test_deletion_request_removes_the_owners_active_link(self):
        _, token = self.create_link()
        self.assertEqual(self.post('/account/deletion', client=self.owner_client).status_code, 200)
        self.assertEqual(self.owner_client.get('/api/v1/personal-share').json(), {'url': None})
        self.assertEqual(self.post('/personal-share/resolve', {'share_token': token}).status_code, 404)

    @override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
                       GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5)
    def test_reviewed_share_preview_keeps_its_destination_and_signature_after_queueing(self):
        _, token = self.create_link()
        body = 'از کمکت ممنونم!'
        with patch('core.gapgpt.rewrite_message', return_value=body) as review:
            response = self.preview(token, source_mode='freeform', text=body)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(review.call_args.args[0], body)
        preview = Preview.objects.get(pk=response.json()['preview_id'])
        self.assertEqual(preview.generated_body, body)
        self.assertEqual(preview.recipient_hash, digest(self.target_phone))
        order_id = self.reserve(response.json()).json()['id']
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.post(f'/orders/{order_id}/confirm-free').status_code, 200)
        self.owner_client.delete('/api/v1/personal-share')
        from .freeform import validate_order
        validate_order(Order.objects.get(pk=order_id))
