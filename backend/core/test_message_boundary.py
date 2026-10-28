"""Direct HTTP attacks and the last provider boundary, independent of the UI."""
import uuid
from contextlib import contextmanager
from unittest.mock import patch
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from . import tests as legacy
from .models import AIConfiguration, Account, Order, Outbox, Preview, SafetyControl
from .provider_delivery import submit_delivery
from .providers.kavenegar import SMSResult

BODY = 'لطفاً جلوی در پارک نکن تا مسیر رفت‌وآمد باز بماند.'
RUDE = 'احمق نفهم بیشعور'


class BoundaryCases:
    post, authenticate = legacy.APITestCase.post, legacy.APITestCase.authenticate

    def setUp(self):
        cache.clear(); self.client = Client()
        self.user = self.authenticate(free_sends=None)
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})
        if self.provider == 'ollama': AIConfiguration.objects.create(provider='ollama')

    @contextmanager
    def live(self):
        with override_settings(DEMO_MODE=False, SMS_BACKEND='kavenegar', PAYMENT_BACKEND='disabled',
                PROVIDER_NETWORK_MODE='external', LIVE_PROVIDERS_ENABLED=True, PROVIDER_ENVIRONMENT='live',
                SMS_RECIPIENT_POLICY='all', SMS_MAX_COST_RIAL=20000, PROVIDER_DAILY_BUDGET_RIAL=100000,
                SENDING_WINDOW_ENABLED=False, TERMS_VERSION='v-boundary-test'):
            yield

    def quote(self):
        with patch('core.'+('ollama_rewrite' if self.provider == 'ollama' else 'gapgpt')+'.rewrite_message', return_value=BODY):
            result = self.post('/messages/preview', {'text': 'احمق جلوی در پارک نکن، رفت‌وآمد سخت میشه',
                'recipient_phone': '09901234567', 'source_mode': 'freeform'})
        self.assertEqual(result.status_code, 200, result.content)
        return result.json()

    def checkout(self, quote, **extra):
        return self.post('/orders', {'preview_id': quote['preview_id'], 'recipient_phone': '09901234567',
            'consent': True, 'terms_version': quote['terms_version'], **extra}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def queue(self, quote):
        result = self.checkout(quote); self.assertEqual(result.status_code, 200, result.content)
        with self.captureOnCommitCallbacks(execute=False):
            confirmed = self.post('/orders/'+result.json()['id']+'/confirm-free')
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        return result.json()

    def test_forged_review_flags_and_raw_insults_cannot_create_a_preview(self):
        with patch('core.ollama_rewrite.rewrite_message') as local, patch('core.gapgpt.rewrite_message') as remote:
            for extra in [{}, {'moderation_mode': 'template', 'safe': True, 'review_signature': 'a'*64}]:
                response = self.post('/messages/preview', {'text': RUDE, 'recipient_phone': '09901234567',
                    'source_mode': 'freeform', **extra})
                self.assertEqual(response.status_code, 422, response.content)
            local.assert_not_called(); remote.assert_not_called()
        self.assertFalse(Preview.objects.exists()); self.assertFalse(Order.objects.exists())

    def test_direct_order_request_requires_a_real_owned_preview(self):
        for preview_id in ['', str(uuid.uuid4())]:
            response = self.post('/orders', {'preview_id': preview_id, 'recipient_phone': '09901234567'},
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
            self.assertIn(response.status_code, [400, 409])
        self.assertFalse(Order.objects.exists()); self.assertFalse(Outbox.objects.exists())

    def test_inspect_or_direct_api_cannot_override_any_outgoing_body_or_verdict(self):
        quote = self.quote()
        for field in ['text', 'body', 'message', 'full_sms', 'generated_body', 'rewritten_text',
                      'original_text', 'review_signature', 'moderation_mode', 'owner_id', 'price_toman']:
            with self.subTest(field=field):
                response = self.checkout(quote, **{field: RUDE})
                self.assertEqual(response.status_code, 422, response.content)
                self.assertEqual(response.json()['error']['code'], 'server_snapshot_required')
        self.assertFalse(Order.objects.exists()); self.assertFalse(Outbox.objects.exists())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_dom_only_changes_never_change_the_exact_sms_sent_by_the_backend(self):
        with self.live():
            quote = self.quote(); original_sms = quote['full_sms']
            # This mirrors editing the displayed preview/JavaScript object. Only
            # the opaque ID, recipient and consent reach the order endpoint.
            quote['full_sms'] = RUDE; quote['rewritten_text'] = RUDE
            self.queue(quote)
            with patch('core.provider_delivery.Kavenegar.submit', return_value=SMSResult('accepted', '801', 1000)) as wire:
                submit_delivery(Outbox.objects.get().pk)
            wire.assert_called_once()
            self.assertEqual(wire.call_args.kwargs['text'], original_sms)
            self.assertNotIn('احمق', wire.call_args.kwargs['text'])

    def test_confirm_requires_consent_and_cannot_accept_replacement_text(self):
        with self.live():
            quote = self.quote()
            response = self.checkout(quote, consent=False)
            self.assertEqual(response.status_code, 422)
            self.assertFalse(Order.objects.exists())
            order = self.checkout(quote).json()
            response = self.post('/orders/'+order['id']+'/confirm-free', {'full_sms': RUDE})
            self.assertEqual(response.status_code, 422)
            self.assertFalse(Outbox.objects.exists())

    def test_tampering_after_order_creation_is_rejected_before_queuing(self):
        quote = self.quote(); order = self.checkout(quote).json()
        Order.objects.filter(pk=order['id']).update(full_sms=RUDE)
        response = self.post('/orders/'+order['id']+'/confirm-free')
        self.assertEqual(response.status_code, 409)
        self.assertFalse(Outbox.objects.exists())
        self.assertIsNone(Order.objects.get().paid_at)

    def test_tampering_between_worker_transactions_is_rejected_at_the_wire(self):
        with self.live():
            self.queue(self.quote())
            def change_after_first_check(*args, **kwargs):
                Order.objects.update(full_sms=RUDE)
            with patch('core.provider_delivery.reserve_cost', side_effect=change_after_first_check), \
                    patch('core.provider_delivery.Kavenegar.submit') as wire:
                submit_delivery(Outbox.objects.get().pk)
            wire.assert_not_called()
            self.assertEqual(Outbox.objects.get().last_error_code, 'moderation_rejected')
            self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_unverified_account_or_missing_csrf_cannot_submit_directly(self):
        anonymous = Client()
        self.assertEqual(self.post('/orders', {}, anonymous).status_code, 401)
        checked = Client(enforce_csrf_checks=True); checked.force_login(self.user)
        response = self.post('/messages/preview', {'text': RUDE}, checked)
        self.assertEqual(response.status_code, 403)


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=100, GAPGPT_USER_DAILY_LIMIT=100, APP_BASE_URL='https://begamnagam.ir')
class GapGPTBoundaryTests(BoundaryCases, TestCase):
    provider = 'gapgpt'


@override_settings(AI_MODE='template', GAPGPT_API_KEY='', GAPGPT_MODEL='', APP_BASE_URL='https://begamnagam.ir')
class OllamaBoundaryTests(BoundaryCases, TestCase):
    provider = 'ollama'
