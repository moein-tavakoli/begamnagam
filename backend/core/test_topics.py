import uuid

from django.core.cache import cache
from django.test import Client, TestCase, override_settings

from . import tests as legacy
from .models import Order, Outbox
from .moderation import CATEGORIES, DIRECT_TEMPLATES, TEMPLATES, moderate, is_reviewed_template
from .tasks import deliver_message


class MessageTopicTests(TestCase):
    post, authenticate = legacy.APITestCase.post, legacy.APITestCase.authenticate

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate(free_sends=None)

    @override_settings(APP_BASE_URL='https://begamnagam.ir')
    def test_all_eighteen_topics_offer_safe_gentle_and_direct_sms_snapshots(self):
        ids = [item['id'] for item in CATEGORIES]
        self.assertEqual(len(ids), 18)
        self.assertEqual(len(set(ids)), 18)
        self.assertEqual(set(ids), set(TEMPLATES))
        self.assertEqual(set(ids), set(DIRECT_TEMPLATES))
        self.assertTrue({'punctuality','listening','conversation','personal_space','phone_etiquette',
            'neighbor','parking','teamwork','apology','good_wishes','environment'}.issubset(ids))
        for item in CATEGORIES:
            moderate(item['example'])
            for text in TEMPLATES[item['id']] + DIRECT_TEMPLATES[item['id']]:
                moderate(text)
                self.assertTrue(is_reviewed_template(item['id'],text))
                snapshot = text + '\nبگم نگم | لغو: begamnagam.ir/r/Ab12Cd34'
                self.assertLessEqual(len(snapshot.encode('utf-16-le'))//2, 201)
            for direct in [False,True]:
                self.user.account.direct_message_tone=direct
                self.user.account.save(update_fields=['direct_message_tone'])
                # A local synthetic contract covers each topic without weakening
                # the real per-user or per-session request limits.
                cache.clear()
                response=self.post('/messages/preview',{'category':item['id'],'text':item['example'],
                    'recipient_phone':'09901234567'})
                self.assertEqual(response.status_code,200,response.content)
                data=response.json()
                self.assertIn(data['rewritten_text'],(DIRECT_TEMPLATES if direct else TEMPLATES)[item['id']])
                self.assertRegex(data['full_sms'].split('لغو: ')[1],r'^begamnagam\.ir/r/[A-Za-z0-9]{8}$')

    def test_new_topic_keeps_moderation_before_and_after_preview(self):
        rejected=self.post('/messages/preview',{'category':'parking','text':'احمق'})
        self.assertEqual(rejected.status_code,422)
        quote=self.post('/messages/preview',{'category':'parking','text':'مسیر را باز بگذاریم',
            'recipient_phone':'09901234567'}).json()
        response=self.post('/orders',{'preview_id':quote['preview_id'],'recipient_phone':'09901234567'},
            HTTP_IDEMPOTENCY_KEY=uuid.uuid4().hex)
        self.assertEqual(response.status_code,200,response.content)
        with self.captureOnCommitCallbacks(execute=False):
            self.assertEqual(self.post('/orders/'+response.json()['id']+'/confirm-free').status_code,200)
        order=Order.objects.get()
        Order.objects.filter(pk=order.pk).update(text='متن بررسی‌نشده')
        deliver_message(Outbox.objects.get().pk)
        order.refresh_from_db()
        self.assertEqual(order.status,'failed')
