import json
import uuid
from datetime import timedelta
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from . import tests as legacy
from .models import Order, RecipientState
from .moderation import TEMPLATES
from .privacy import digest


class PhaseTwoTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    preview = legacy.APITestCase.preview
    order = legacy.APITestCase.order

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.client.get('/api/v1/bootstrap')

    def test_recipient_bound_quote_cannot_be_retargeted(self):
        self.authenticate()
        quote = self.post('/messages/preview', {'category':'appreciation', 'text':'تشکر از تو', 'recipient_phone':'09901234567'}).json()
        response = self.order(recipient='09901234568', preview=quote)
        self.assertEqual(response.status_code,409)
        self.assertEqual(Order.objects.count(),0)
        self.assertIn('/r/',quote['full_sms'])

    def test_bound_quote_requires_verified_sender(self):
        result=self.post('/messages/preview',{'category':'appreciation','text':'تشکر از تو','recipient_phone':'09901234567'})
        self.assertEqual(result.status_code,401)

    def test_all_topics_have_three_segment_or_smaller_final_snapshot(self):
        self.authenticate()
        for category in TEMPLATES:
            quote=self.preview(category=category,text='یک پیام محترمانه')
            self.assertLessEqual(quote['sms_segments'],3)
            self.assertTrue(quote['full_sms'].startswith(quote['rewritten_text']))
            self.assertIn('بگم نگم | لغو:',quote['full_sms'])

    def test_pair_limit_survives_global_cooldown_and_cache_loss(self):
        user=self.authenticate()
        old=self.order().json()
        Order.objects.filter(id=old['id']).update(status='delivered_demo', paid_at=timezone.now()-timedelta(hours=23),updated_at=timezone.now()-timedelta(hours=23))
        RecipientState.objects.update(last_sent_at=timezone.now()-timedelta(hours=25))
        cache.clear()
        self.assertEqual(self.order().status_code,409)
        Order.objects.filter(id=old['id']).update(updated_at=timezone.now()-timedelta(hours=25))
        self.assertEqual(self.order().status_code,200)
