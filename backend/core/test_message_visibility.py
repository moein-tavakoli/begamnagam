"""Website revocation must survive retries, sessions and retention, not cancel SMS."""
import io
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import Account, Order, Outbox
from .tasks import deliver_message
from . import test_api_v2 as integration


@override_settings(DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console',
                   PROVIDER_NETWORK_MODE='disabled', PAYMENT_BACKEND='demo', AI_MODE='template')
class MessageVisibilityTests(TestCase):
    setUp = integration.IntegrationAPITests.setUp
    session = integration.IntegrationAPITests.session
    mutate = integration.IntegrationAPITests.mutate
    login = integration.IntegrationAPITests.login
    make_preview = integration.IntegrationAPITests.make_preview
    reserve = integration.IntegrationAPITests.reserve

    def remove(self, identifier):
        response = self.client.delete('/api/v1/messages/' + identifier,
                                      HTTP_X_CSRFTOKEN=self.tokens[id(self.client)])
        self.assertEqual(response.status_code, 200, response.content)

    def test_hidden_message_cannot_be_reopened_by_retry_or_submission(self):
        owner = self.login()
        preview = self.make_preview()
        key = uuid.uuid4()
        message = self.reserve(preview, key=key).json()
        credits = Account.objects.get(user=owner).free_sends_remaining
        self.remove(message['id'])
        repeated = self.reserve(preview, key=key)
        self.assertEqual(repeated.status_code, 404, repeated.content)
        for suffix in ('confirm-free', 'confirm-credit', 'pay-demo', 'pay-wallet', 'payments'):
            with self.subTest(suffix=suffix):
                response = self.client.post(f'/api/v1/orders/{message["id"]}/{suffix}', {},
                    content_type='application/json', HTTP_X_CSRFTOKEN=self.tokens[id(self.client)])
                self.assertEqual(response.status_code, 404, response.content)
                self.assertNotIn(preview['rewritten_text'], response.content.decode())
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(Account.objects.get(user=owner).free_sends_remaining, credits)

    def test_hidden_queued_message_still_delivers_and_only_staff_can_read_record(self):
        owner = self.login()
        message = self.reserve().json()
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.mutate(f'/messages/{message["id"]}/submission', method='PUT').status_code, 200)
        self.remove(message['id'])
        event = Outbox.objects.get(order_id=message['id'])
        deliver_message(event.pk)
        order = Order.objects.get(pk=message['id'])
        self.assertEqual(order.status, Order.Status.DELIVERED_DEMO)
        hidden_at = order.owner_hidden_at
        fresh = Client()
        fresh.force_login(owner)
        self.assertEqual(fresh.get('/api/v1/messages').json()['results'], [])
        self.assertEqual(fresh.get('/api/v1/orders/' + message['id']).status_code, 404)

        self.assertEqual(fresh.post(f'/api/v1/manage/orders/{message["id"]}/texts', {}, content_type='application/json').status_code, 403)
        staff = Client()
        staff.force_login(get_user_model().objects.create_superuser('visibility-admin'))
        response = staff.post(f'/api/v1/manage/orders/{message["id"]}/texts', {}, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['final_text'])
        Order.objects.filter(pk=order.pk).update(updated_at=timezone.now()-timedelta(days=40))
        call_command('prune_private_data', stdout=io.StringIO())
        order.refresh_from_db()
        self.assertEqual(order.owner_hidden_at, hidden_at)
        self.assertEqual(fresh.get('/api/v1/messages').json()['results'], [])
        self.assertEqual(fresh.get('/api/v1/orders/' + message['id']).status_code, 404)

    def test_serializer_cannot_restore_a_stale_loaded_message(self):
        from .services import APIError, serialize_order, serialize_orders
        self.login()
        message = self.reserve().json()
        stale = Order.objects.get(pk=message['id'])
        self.remove(message['id'])
        with self.assertRaises(APIError) as raised:
            serialize_order(stale)
        self.assertEqual(raised.exception.status, 404)
        self.assertEqual(serialize_orders([stale]), [])

    def test_website_visibility_revision_is_account_scoped_and_survives_new_session(self):
        owner = self.login()
        other = Client(enforce_csrf_checks=True)
        self.login('09123456788', other)
        initial = self.client.get('/api/v1/bootstrap').json()
        other_initial = other.get('/api/v1/bootstrap').json()
        self.assertIn('message_visibility_revision', initial)
        message = self.reserve().json()
        self.remove(message['id'])
        changed = self.client.get('/api/v1/bootstrap').json()
        self.assertNotEqual(changed['message_visibility_revision'], initial['message_visibility_revision'])
        self.assertEqual(changed['session_identity'], initial['session_identity'])
        self.assertEqual(other.get('/api/v1/bootstrap').json()['message_visibility_revision'], other_initial['message_visibility_revision'])
        self.remove(message['id'])
        self.assertEqual(self.client.get('/api/v1/bootstrap').json()['message_visibility_revision'], changed['message_visibility_revision'])
        fresh = Client()
        fresh.force_login(owner)
        self.assertEqual(fresh.get('/api/v1/bootstrap').json()['message_visibility_revision'], changed['message_visibility_revision'])
        self.assertNotIn('message_visibility_revision', Client().get('/api/v1/bootstrap').json())
