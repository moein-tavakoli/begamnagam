import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from threading import Barrier
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from .freeform import validate_order, validate_preview
from .gapgpt import GapGPTRejected
from .moderation import ModerationRejected
from .models import (Account, AIConfiguration, CreditPurchase, MessageAttempt, Order, Outbox,
                     Preview, RecipientGrant, RecipientState, RewriteUsage, SMSTemplateSettings)
from .payment_options import WALLET_TERMS_VERSION
from .privacy import digest, encrypt
from .recipient_codes import SAMPLE_ACTION_CODE, SAMPLE_STOP_CODE
from .test_gapgpt import BODY, SOURCE, VERDICT, _Response, _completion
from .test_manual_payments import ManualFixture


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='gpt-6-luna',
                   GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5)
class TextTrialTests(ManualFixture, TestCase):
    path = '/messages/text-trials'
    phone = '09901234567'

    def trial(self):
        with patch('core.gapgpt.rewrite_message', return_value=BODY):
            result = self.post(self.path, {'text': SOURCE})
        self.assertEqual(result.status_code, 200, result.content)
        return result.json()

    def bind(self, trial_id, phone=None, client=None, **extra):
        return self.post(f'{self.path}/{trial_id}/bind', {'recipient_phone': phone or self.phone, **extra}, client)

    def order(self, preview_id, client=None, consent=True, key=None):
        from django.conf import settings
        return self.post('/orders', {'preview_id': preview_id, 'recipient_phone': self.phone, 'consent': consent,
                         'terms_version': settings.TERMS_VERSION}, client, HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()))

    def buy(self, preview_id):
        return self.post('/credit-purchases', {'resume_preview_id': preview_id, 'package_id': self.package.pk,
            'package_revision': self.package.revision, 'payment_method': 'gateway', 'wallet_consent': True,
            'wallet_terms_version': WALLET_TERMS_VERSION}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def test_both_review_stages_without_destination_or_transaction(self):
        initial_recipient_states = RecipientState.objects.count()
        opener = Mock()
        opener.open.side_effect = [_Response(_completion({'allowed': True, 'message': BODY})),
                                  _Response(_completion({**VERDICT, 'tone_matched': True}))]
        with patch('core.gapgpt.urllib.request.build_opener', return_value=opener):
            response = self.post(self.path, {'text': SOURCE})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(opener.open.call_count, 2)
        trial = response.json()
        self.assertEqual(set(trial), {'trial_id', 'full_sms', 'expires_at'})
        self.assertIn(BODY, trial['full_sms'])
        self.assertIn(SAMPLE_ACTION_CODE, trial['full_sms'])
        preview = Preview.objects.get(pk=trial['trial_id'])
        self.assertEqual(preview.message_tone, self.client.get('/api/v1/bootstrap').json()['default_message_tone'])
        self.assertEqual(preview.recipient_hash, '')
        with self.assertRaises(ModerationRejected):
            validate_preview(preview)
        self.assertEqual(MessageAttempt.objects.get().recipient_phone, '')
        self.assertEqual(RewriteUsage.objects.count(), 1)
        with connection.cursor() as cursor:
            cursor.execute('SELECT original_text, generated_body, full_sms FROM core_preview')
            self.assertTrue(all(value.startswith('enc:v1:') for value in cursor.fetchone()))
        self.assertGreaterEqual(self.order(trial['trial_id']).status_code, 400)
        self.assertGreaterEqual(self.buy(trial['trial_id']).status_code, 400)
        self.assertGreaterEqual(self.client.get('/api/v2/message-previews/' + trial['trial_id']).status_code, 400)
        self.assertFalse(RecipientGrant.objects.exists())
        self.assertEqual(RecipientState.objects.count(), initial_recipient_states)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(CreditPurchase.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_both_routes_require_verified_session_and_csrf(self):
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        for url, data in [(self.path, {'text': SOURCE}), (f'{self.path}/{uuid.uuid4()}/bind', {'recipient_phone': self.phone})]:
            self.assertEqual(self.post(url, data, Client()).status_code, 401)
            self.assertEqual(self.post(url, data, csrf).status_code, 403)
        with patch('core.gapgpt.rewrite_message') as model:
            self.assertEqual(self.post(self.path, {'text': SOURCE, 'recipient_phone': self.phone}).status_code, 422)
            self.assertEqual(self.post(self.path, {'text': SOURCE, 'message_tone': 'angry'}).status_code, 422)
            Account.objects.filter(user=self.user).update(suspended=True)
            self.assertEqual(self.post(self.path, {'text': SOURCE}).status_code, 403)
        model.assert_not_called()

    def test_no_fallback_and_existing_safety_accounting(self):
        with override_settings(AI_MODE='template'), patch('core.gapgpt.rewrite_message') as model:
            self.assertEqual(self.post(self.path, {'text': SOURCE}).json()['error']['code'], 'freeform_unavailable')
            model.assert_not_called()
        with patch('core.gapgpt.rewrite_message') as model:
            self.assertEqual(self.post(self.path, {'text': 'به 09123456789 زنگ بزن'}).status_code, 422)
            model.assert_not_called()
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTRejected('review_unsafe')):
            response = self.post(self.path, {'text': SOURCE})
        self.assertEqual(response.status_code, 422)
        self.assertFalse(response.json()['error']['details']['alternatives'])
        self.assertEqual(MessageAttempt.objects.filter(status='rejected').count(), 2)
        Account.objects.filter(user=self.user).update(rewrite_daily_limit=1)
        self.assertEqual(self.post(self.path, {'text': SOURCE}).status_code, 429)
        self.assertEqual(RewriteUsage.objects.count(), 1)
        self.assertFalse(Preview.objects.exists())

    def test_site_layout_can_repeat_the_text_and_remove_replies_but_must_show_the_trial_body(self):
        layout = SMSTemplateSettings.objects.create(template='{{brand}}\n{{message}}\n{{message}}\n{{opt_out}}',
            variables=[{'name': 'brand', 'value': 'درود'}], legacy_reply_footer=False)
        trial = self.trial()
        self.assertTrue(trial['full_sms'].startswith(f'درود\n{BODY}\n{BODY}\n'))
        self.assertTrue(trial['full_sms'].endswith(SAMPLE_STOP_CODE))
        bound = self.bind(trial['trial_id']).json()['full_sms']
        self.assertEqual(bound, trial['full_sms'].replace(SAMPLE_STOP_CODE, bound.split('/')[-1]))
        self.assertIsNone(RecipientGrant.objects.get().reply_token_digest)
        layout.template = 'درود\n{{opt_out}}'
        layout.save()
        with patch('core.gapgpt.rewrite_message') as model:
            self.assertEqual(self.post(self.path, {'text': SOURCE}).json()['error']['code'], 'sms_template_unavailable')
            model.assert_not_called()
        self.assertEqual(RewriteUsage.objects.count(), 1)

    def test_bind_once_requires_same_owner_session_and_explicit_gift_confirmation(self):
        trial = self.trial()
        trial_id = trial['trial_id']
        other_session = Client()
        other_session.force_login(self.user)
        stranger = Client()
        self.authenticate('09901234568', stranger)
        with patch('core.gapgpt.rewrite_message') as model:
            for client in (other_session, stranger):
                self.assertEqual(self.bind(trial_id, client=client).status_code, 404)
            self.assertEqual(self.bind(trial_id, phone='invalid').status_code, 400)
            self.assertEqual(self.bind(trial_id, phone='09123456789').status_code, 422)
            self.assertEqual(self.bind(trial_id, text='جایگزین').status_code, 422)
            response = self.bind(trial_id)
            self.assertEqual(response.status_code, 200, response.content)
            quote = response.json()
            self.assertEqual(quote['expires_at'], trial['expires_at'])
            self.assertTrue(quote['is_free'])
            self.assertEqual(quote['rewritten_text'], BODY)
            token = quote['full_sms'].split('/')[-1]
            self.assertEqual(quote['full_sms'], trial['full_sms'].replace(SAMPLE_ACTION_CODE, token))
            self.assertEqual(self.bind(trial_id).json(), quote)
            self.assertEqual(self.bind(trial_id, phone='09901234569').status_code, 409)
            self.assertEqual(self.order(quote['preview_id'], other_session).status_code, 404)
            self.assertEqual(other_session.get('/api/v2/message-previews/' + quote['preview_id']).status_code, 404)
            model.assert_not_called()
        self.assertEqual(RecipientGrant.objects.count(), 1)
        self.assertIsNone(RecipientGrant.objects.get().activated_at)
        self.assertEqual(MessageAttempt.objects.get().recipient_phone, self.phone)
        self.assertEqual(RewriteUsage.objects.count(), 1)
        validate_preview(Preview.objects.get(pk=quote['preview_id']), recipient_hash=digest(self.phone))
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(self.order(quote['preview_id'], consent=False).status_code, 422)
        RecipientState.objects.create(phone_hash=digest(self.phone), blocked=True)
        self.assertEqual(self.order(quote['preview_id']).json()['error']['code'], 'recipient_unavailable')
        RecipientState.objects.filter(pk=digest(self.phone)).update(blocked=False)
        key = uuid.uuid4()
        self.assertEqual(self.order(quote['preview_id'], key=key).status_code, 200)
        self.assertEqual(self.order(quote['preview_id'], other_session, key=key).status_code, 404)
        self.assertEqual(self.bind(trial_id).status_code, 409)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 2)
        self.assertFalse(Outbox.objects.exists())

    def test_expired_tampered_or_changed_snapshot_cannot_be_bound(self):
        trial_id = self.trial()['trial_id']
        preview = Preview.objects.filter(pk=trial_id)
        with override_settings(TERMS_VERSION='changed'):
            self.assertEqual(self.bind(trial_id).status_code, 409)
        config = AIConfiguration.objects.create(tone_firm_enabled=False, provider='gapgpt')
        self.assertEqual(self.bind(trial_id).status_code, 409)
        config.delete()
        layout = SMSTemplateSettings.objects.create(template='درود\n{{message}}\n{{reply}}', variables=[])
        self.assertEqual(self.bind(trial_id).status_code, 409)
        layout.delete()
        preview.update(generated_body='صبح شما بخیر')
        self.assertEqual(self.bind(trial_id).status_code, 409)
        preview.update(expires_at=timezone.now()-timedelta(days=2))
        self.assertEqual(self.bind(trial_id).status_code, 409)
        self.assertFalse(RecipientGrant.objects.exists())
        call_command('prune_private_data', stdout=StringIO())
        self.assertFalse(preview.exists())

    def test_bound_signature_survives_session_key_retention_for_a_pending_order(self):
        quote = self.bind(self.trial()['trial_id']).json()
        self.order(quote['preview_id'])
        preview = Preview.objects.get(pk=quote['preview_id'])
        with patch('core.management.commands.prune_private_data.timezone.now', return_value=timezone.now() + timedelta(days=2)):
            call_command('prune_private_data', stdout=StringIO())
        preview.refresh_from_db()
        self.assertEqual(preview.session_key, '')
        validate_preview(preview, recipient_hash=digest(self.phone))
        order = Order.objects.get(preview=preview)
        validate_order(order)
        order.recipient_cipher = encrypt('09901234568')
        with self.assertRaises(ModerationRejected):
            validate_order(order)

    @override_settings(CONVERSION_EXPERIMENT='preview')
    def test_zero_credit_trial_becomes_checkout_resume_only_after_binding(self):
        Account.objects.filter(user=self.user).update(free_sends_remaining=0)
        trial = self.trial()
        exposure = {'experiment': 'preview', 'surface': 'preview', 'preview_id': trial['trial_id']}
        self.assertFalse(self.post('/conversion-exposures', exposure).json()['recorded'])
        self.assertGreaterEqual(self.buy(trial['trial_id']).status_code, 400)
        response = self.bind(trial['trial_id'])
        self.assertEqual(response.status_code, 200, response.content)
        quote = response.json()
        self.assertTrue(self.post('/conversion-exposures', exposure).json()['recorded'])
        self.assertFalse(quote['is_free'])
        self.assertGreaterEqual(self.order(quote['preview_id']).status_code, 400)
        checkout = self.buy(quote['preview_id'])
        self.assertEqual(checkout.status_code, 200, checkout.content)
        self.assertEqual(checkout.json()['resume_status'], 'ready')
        resumed = self.client.get('/api/v1/messages/preview/' + quote['preview_id'])
        self.assertEqual(resumed.json()['full_sms'], quote['full_sms'])
        self.assertEqual(RewriteUsage.objects.count(), 1)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Outbox.objects.exists())


@skipUnlessDBFeature('has_select_for_update')
@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
                   GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5)
class ConcurrentTextTrialTests(ManualFixture, TransactionTestCase):
    def test_concurrent_binds_cannot_select_two_targets(self):
        with patch('core.gapgpt.rewrite_message', return_value=BODY):
            trial = self.post('/messages/text-trials', {'text': SOURCE}).json()
        path = f"/messages/text-trials/{trial['trial_id']}/bind"
        start = Barrier(2)

        def bind_target(phone):
            client = Client()
            client.cookies = self.client.cookies.copy()
            try:
                start.wait(timeout=10)
                return self.post(path, {'recipient_phone': phone}, client).status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(bind_target, ['09901234567', '09901234568']))
        self.assertCountEqual(outcomes, [200, 409])
        grant = RecipientGrant.objects.get()
        self.assertEqual(grant.recipient_hash, digest(MessageAttempt.objects.get().recipient_phone))
        self.assertEqual(RewriteUsage.objects.count(), 1)
        self.assertFalse(Order.objects.exists())
