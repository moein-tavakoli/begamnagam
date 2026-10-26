from unittest.mock import patch

from django.test import TestCase, override_settings

from . import test_live_sms as live
from .models import Order, Outbox, Preview, RecipientGrant
from .moderation import TEMPLATES, ModerationRejected
from .provider_delivery import submit_delivery
from .providers.kavenegar import SMSResult
from .sms import compose_recipient_sms


class SMSIntroTests(TestCase):
    setUp = live.LiveGiftSMSTests.setUp
    post = live.LiveGiftSMSTests.post
    authenticate = live.LiveGiftSMSTests.authenticate
    preview = live.LiveGiftSMSTests.preview
    make_order = live.LiveGiftSMSTests.make_order
    confirm = live.LiveGiftSMSTests.confirm

    @override_settings(APP_BASE_URL='https://begamnagam.ir')
    def test_intro_and_newline_are_in_the_reviewed_preview_and_exact_provider_payload(self):
        quote = self.preview(category='appreciation', text='ممنون از همراهی تو')
        self.assertEqual(quote['full_sms'].split('\n')[0], 'نمیدونم بهت بگم یا نگم؟')
        self.assertEqual(quote['full_sms'].split('\n')[1], quote['rewritten_text'])
        order = self.make_order(quote=quote).json()
        self.confirm(order)
        with patch('core.provider_delivery.Kavenegar.submit', return_value=SMSResult('accepted', '701', 1000)) as wire:
            submit_delivery(Outbox.objects.get().pk)
            submit_delivery(Outbox.objects.get().pk)
        self.assertEqual(wire.call_count, 1)
        self.assertEqual(wire.call_args.kwargs['text'], quote['full_sms'])
        self.assertEqual(Order.objects.get().full_sms, quote['full_sms'])

    @override_settings(APP_BASE_URL='https://begamnagam.ir')
    def test_long_reviewed_model_choice_uses_a_fitting_reviewed_body_without_truncating(self):
        long_body = max(TEMPLATES['body'], key=len)
        with patch('core.views.rewrite', return_value=(long_body, 'ollama_curated')):
            response = self.post('/messages/preview', {'category':'body', 'text':'یک یادآوری دوستانه', 'recipient_phone':'09901234567'})
        self.assertEqual(response.status_code, 200, response.content)
        quote = response.json()
        self.assertNotEqual(quote['rewritten_text'], long_body)
        self.assertIn(quote['rewritten_text'], TEMPLATES['body'])
        self.assertIn('\n'+quote['rewritten_text']+'\n', quote['full_sms'])
        self.assertLessEqual(len(quote['full_sms'].encode('utf-16-le'))//2, 201)
        self.assertLessEqual(quote['sms_segments'], 3)
        self.assertEqual(Preview.objects.get().text, quote['rewritten_text'])
        with self.assertRaises(ModerationRejected):
            compose_recipient_sms('body', 'متن بررسی‌نشده', 'begamnagam.ir', 'Ab12Cd34')

    def test_previously_reviewed_preview_is_dispatched_unchanged_without_new_intro(self):
        quote = self.preview(category='appreciation', text='ممنون از تو')
        old_sms = quote['full_sms'].split('\n', 1)[1]
        Preview.objects.filter(pk=quote['preview_id']).update(full_sms=old_sms)
        order = self.make_order(quote=quote).json()
        self.confirm(order)
        with patch('core.provider_delivery.Kavenegar.submit', return_value=SMSResult('accepted', '702', 1000)) as wire:
            submit_delivery(Outbox.objects.get().pk)
        self.assertEqual(wire.call_args.kwargs['text'], old_sms)

    @override_settings(APP_BASE_URL='https://'+'a'*200+'.ir')
    def test_unfittable_sms_rolls_back_preview_and_grant(self):
        response = self.post('/messages/preview', {'category':'appreciation', 'text':'ممنون از تو', 'recipient_phone':'09901234567'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error']['code'], 'message_too_long')
        self.assertFalse(Preview.objects.exists())
        self.assertFalse(RecipientGrant.objects.exists())
