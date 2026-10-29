import time
from unittest.mock import patch
from django.test import Client, TestCase, override_settings
from . import test_freeform as freeform_tests
from .models import Account, ModerationAudit, Order, Outbox, Preview, RewriteUsage
from .message_alternatives import MAX_AGE


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5, APP_BASE_URL='https://begamnagam.ir')
class MessageAlternativeTests(TestCase):
    post, authenticate, setUp = freeform_tests.FreeformTests.post, freeform_tests.FreeformTests.authenticate, freeform_tests.FreeformTests.setUp
    quote, make_order = freeform_tests.FreeformTests.quote, freeform_tests.FreeformTests.make_order

    def offer(self):
        response = self.quote('میکشمت')
        self.assertEqual(response.status_code, 422, response.content)
        return response.json()['error']['details']['alternatives'][0]

    def choose(self, offer, **extra):
        return self.post('/messages/preview', {'source_mode': 'reviewed_alternative',
            'alternative_token': offer['token'], 'message_tone': offer['message_tone'],
            'recipient_phone': '09901234567', **extra})

    def test_rejection_offers_explicit_reviewed_choice_without_spend_or_sendable_record(self):
        with patch('core.gapgpt.rewrite_message') as model:
            offer = self.offer()
        model.assert_not_called()
        self.assertTrue(offer['text'])
        self.assertFalse(Preview.objects.exists())
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Outbox.objects.exists())
        self.assertFalse(RewriteUsage.objects.exists())
        self.assertEqual(ModerationAudit.objects.get().reason_code, 'unsafe_content')

    def test_chosen_alternative_uses_server_text_and_normal_credits_and_consent(self):
        offer = self.offer()
        with patch('core.gapgpt.rewrite_message') as model:
            response = self.choose(offer)
        self.assertEqual(response.status_code, 200, response.content)
        model.assert_not_called()
        result = response.json();self.assertEqual(result['rewritten_text'], offer['text'])
        self.assertEqual(result['moderation_mode'], 'template')
        item = Preview.objects.get(pk=result['preview_id'])
        self.assertEqual(item.original_text, offer['text'])
        self.assertNotIn('میکشمت', item.full_sms)
        self.assertFalse(RewriteUsage.objects.exists())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
        order = self.make_order(result)
        self.assertEqual(order.status_code, 200, order.content)
        self.assertEqual(Order.objects.get().text, offer['text'])
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 2)

    def test_inspect_cannot_replace_text_or_recipient_or_token(self):
        offer = self.offer()
        for extra in [{'text': 'میکشمت'}, {'category': 'appreciation'},
                      {'recipient_phone': '09901234568'}, {'alternative_token': offer['token']+'x'},
                      {'source_mode': 'freeform'}]:
            with self.subTest(extra=extra):
                self.assertNotEqual(self.choose(offer, **extra).status_code, 200)
        self.assertFalse(Preview.objects.exists())
        self.assertFalse(Order.objects.exists())

    def test_offer_expires_and_cannot_move_to_another_authenticated_session(self):
        offer = self.offer()
        other = Client();other.force_login(self.user);other.get('/api/v1/bootstrap')
        response = self.post('/messages/preview', {'source_mode': 'reviewed_alternative',
            'alternative_token': offer['token'], 'recipient_phone': '09901234567'}, client=other)
        self.assertEqual(response.status_code, 409)
        with patch('django.core.signing.time.time', return_value=time.time()+MAX_AGE+2):
            self.assertEqual(self.choose(offer).status_code, 409)
        self.assertFalse(Preview.objects.exists())

    def test_known_bad_phrase_is_reported_but_model_only_rejection_never_invents_a_word(self):
        response = self.quote('میکشمت')
        self.assertIn('«میکشمت»', response.json()['error']['message'])
        from .gapgpt import GapGPTRejected
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTRejected('review_intent')):
            response = self.quote('رفیق پولدار منی')
        self.assertEqual(response.json()['error']['code'], 'rewrite_intent_changed')
        self.assertNotIn('«', response.json()['error']['message'])
        self.assertNotIn('تهدید', response.json()['error']['message'])

    def test_provider_failure_does_not_silently_offer_or_prepare_a_template(self):
        from .gapgpt import GapGPTUnavailable
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTUnavailable()):
            response = self.quote('از دوستی با تو خوشحالم')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('details', response.json()['error'])
        self.assertFalse(Preview.objects.exists())
