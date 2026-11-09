import time
from unittest.mock import patch
from django.test import Client, TestCase, override_settings
from . import test_freeform as freeform_tests
from .gapgpt import GapGPTRejected, GapGPTUnavailable
from .models import Account, ModerationAudit, Order, Outbox, Preview, RewriteUsage
from .message_alternatives import MAX_AGE


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5, APP_BASE_URL='https://begamnagam.ir')
class MessageAlternativeTests(TestCase):
    post, authenticate, setUp = freeform_tests.FreeformTests.post, freeform_tests.FreeformTests.authenticate, freeform_tests.FreeformTests.setUp
    quote, make_order = freeform_tests.FreeformTests.quote, freeform_tests.FreeformTests.make_order

    def offer(self):
        with override_settings(AI_MODE='template'):
            response = self.quote('احمق، لطفاً جلوی در پارک نکن', category='parking')
        self.assertEqual(response.status_code, 422, response.content)
        choices = response.json()['error']['details']['alternatives']
        self.assertEqual(len({item['text'] for item in choices}), 2)
        self.assertTrue(all('پارک' in item['text'] for item in choices))
        return choices[-1]

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
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTRejected('review_intent')):
            response = self.quote('رفیق پولدار منی')
        self.assertEqual(response.json()['error']['code'], 'rewrite_intent_changed')
        self.assertNotIn('«', response.json()['error']['message'])
        self.assertNotIn('تهدید', response.json()['error']['message'])
        self.assertEqual(response.json()['error']['details']['alternatives'], [])

    def test_unsafe_purpose_and_private_data_do_not_produce_unrelated_options(self):
        with patch('core.gapgpt.rewrite_message') as model:
            for text in ('اگه جلوی در پارک کنی میکشمت', 'لطفاً به 09123456780 زنگ بزن و جلوی در پارک نکن'):
                response = self.quote(text)
                self.assertEqual(response.status_code, 422, response.content)
                error = response.json()['error']
                self.assertEqual(error['details']['alternatives'], [])
                self.assertNotIn('09123456780', error['message'])
        model.assert_not_called()

    def test_v2_review_failure_offers_two_choices_related_to_safe_intent(self):
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTRejected('review_register')) as model:
            response = self.client.post('/api/v2/message-previews', {
                'source_mode': 'freeform', 'text': 'بیشعور جلوی ورودی پارک نکن',
                'recipient_phone': '09901234567', 'message_tone': 'blunt',
            }, content_type='application/json')
        self.assertEqual(response.status_code, 422, response.content)
        model.assert_called_once()
        error = response.json()['error']
        self.assertIn('زبان', error['message'])
        self.assertEqual(error['code'], 'rewrite_output_rejected')
        choices = error['details']['alternatives']
        self.assertEqual(len({item['id'] for item in choices}), 2)
        self.assertTrue(all('پارک' in item['text'] and item['message_tone'] == 'blunt' for item in choices))
        self.assertFalse(Preview.objects.exists())

    def test_choices_preserve_repayment_and_water_conservation(self):
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTRejected('review_intent')):
            response = self.quote('لطفاً پولم رو پس بده')
            water = self.quote('آب هدر نده').json()['error']['details']['alternatives']
        choices = response.json()['error']['details']['alternatives']
        self.assertEqual(len(choices), 2)
        self.assertTrue(all('پولم' in item['text'] for item in choices))
        self.assertEqual(len(water), 2)
        self.assertTrue(all('آب' in item['text'] and 'زباله' not in item['text'] for item in water))
        selected = self.choose(choices[0])
        self.assertEqual(selected.status_code, 200, selected.content)
        self.assertEqual(selected.json()['rewritten_text'], choices[0]['text'])
        from .freeform import validate_order
        order = self.make_order(selected.json())
        self.assertEqual(order.status_code, 200, order.content)
        validate_order(Order.objects.get(pk=order.json()['id']))

    def test_opposite_reported_and_ambiguous_requests_do_not_produce_choices(self):
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTRejected('review_intent')):
            for draft in ('لطفاً جلوی در پارک کن', 'نگفتم جلوی در پارک نکن، لطفاً همین جا پارک کن',
                          'پولم رو برگردوندم', 'متأسفم که بازی را باختی', 'لباست رو عوض کن'):
                with self.subTest(draft=draft):
                    response = self.quote(draft)
                    self.assertEqual(response.status_code, 422, response.content)
                    self.assertEqual(response.json()['error']['details']['alternatives'], [])

    def test_provider_failure_does_not_silently_offer_or_prepare_a_template(self):
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTUnavailable()):
            response = self.quote('از دوستی با تو خوشحالم')
        self.assertEqual(response.status_code, 503)
        self.assertIn('آماده‌سازی متن', response.json()['error']['message'])
        self.assertNotIn('details', response.json()['error'])
        self.assertFalse(Preview.objects.exists())
