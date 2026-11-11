from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings

from . import models as m
from . import test_live_sms as live
from .provider_delivery import submit_delivery
from .providers.kavenegar import SMSResult


PATH = '/api/v1/manage/sms-template'
TEMPLATE = '{{intro}}\n{{message}}\n{{opt_out}}'
VARIABLES = [{'name': 'intro', 'value': 'درود از بگم نگم'}]


def save_template(client, *, template=TEMPLATE, variables=VARIABLES, revision=0, sender=None, **headers):
    payload = {'template': template, 'variables': variables, 'revision': revision}
    if sender is not None:
        payload['sender'] = sender
    return client.put(PATH, payload, content_type='application/json', **headers)


@override_settings(APP_BASE_URL='https://begamnagam.ir')
class SMSTemplateSettingsTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user('sms-settings', is_staff=True)
        self.actor.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='manage_site_limits'))
        self.client.force_login(self.actor)

    def test_default_and_draft_preview_leave_settings_and_queue_untouched(self):
        response = self.client.get(PATH)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('Cookie', response['Vary'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        settings = response.json()
        self.assertEqual(settings['revision'], 0)
        self.assertTrue(settings['preview']['full_sms'].startswith('نمیدونم بهت بگم یا نگم؟\n'))
        preview = self.client.post(PATH + '/preview', {'template': TEMPLATE, 'variables': VARIABLES},
                                   content_type='application/json')
        self.assertEqual(preview.status_code, 200, preview.content)
        sample = preview.json()
        self.assertTrue(sample['full_sms'].startswith('درود از بگم نگم\n'))
        self.assertTrue(sample['full_sms'].endswith('\nلغو: begamnagam.ir/r/Sample-X'))
        self.assertEqual(sample['sms_units'], len(sample['full_sms'].encode('utf-16-le')) // 2)
        self.assertFalse(m.SMSTemplateSettings.objects.exists())
        self.assertFalse(m.RecipientGrant.objects.exists())
        self.assertFalse(m.Outbox.objects.exists())

    def test_requires_staff_settings_permission_and_csrf(self):
        anonymous = Client()
        self.assertEqual(anonymous.get(PATH).status_code, 401)
        support = get_user_model().objects.create_user('sms-support', is_staff=True)
        anonymous.force_login(support)
        self.assertEqual(anonymous.get(PATH).status_code, 403)
        self.assertEqual(save_template(anonymous).status_code, 403)
        self.assertEqual(anonymous.post(PATH + '/preview', {}, content_type='application/json').status_code, 403)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.actor)
        secured.get('/api/v1/manage/session')
        self.assertEqual(save_template(secured).status_code, 403)
        self.assertEqual(secured.post(PATH + '/preview', {}, content_type='application/json').status_code, 403)
        result = save_template(secured, HTTP_X_CSRFTOKEN=secured.cookies['csrftoken'].value)
        self.assertEqual(result.status_code, 200, result.content)

    def test_unsafe_or_unusable_templates_are_rejected_without_saving(self):
        cases = [
            ('{{message}}', []),
            ('{{message}}\n{{opt_out}}\nپایان', []),
            ('متن {{message}}\n{{opt_out}}', []),
            ('{{message}}\n{{message}}\n{{opt_out}}', []),
            ('{{message}}\n{{opt_out}} {{opt_out}}', []),
            ('{{user.phone}}\n{{message}}\n{{opt_out}}', []),
            ('{{unknown}}\n{{message}}\n{{opt_out}}', []),
            (TEMPLATE, [{'name': 'message', 'value': 'سلام'}]),
            (TEMPLATE, VARIABLES * 2),
            (TEMPLATE, [{'name': 'intro', 'value': 'تماس با ۰۹۱۲۳۴۵۶۷۸۹'}]),
            (TEMPLATE, [{'name': 'intro', 'value': 'example.org'}]),
            (TEMPLATE, [{'name': 'intro', 'value': 'example.test'}]),
            (TEMPLATE, [{'name': 'intro', 'value': 'tel:1234'}]),
            (TEMPLATE, [{'name': 'intro', 'value': 'سلام\u2028از بگم نگم'}]),
            (TEMPLATE, [{'name': 'intro', 'value': '{{opt_out}}'}]),
            ('\u202eپیام\n{{message}}\n{{opt_out}}', []),
        ]
        for template, variables in cases:
            with self.subTest(template=template, variables=variables):
                response = save_template(self.client, template=template, variables=variables)
                self.assertEqual(response.status_code, 422, response.content)
        self.assertFalse(m.SMSTemplateSettings.objects.exists())
        self.assertFalse(m.OperatorAudit.objects.filter(action='update_sms_template').exists())

    def test_long_template_warns_and_saves(self):
        template = 'نکته‌ای کوتاه و دوستانه برای شما ' * 24 + '\n{{message}}\n{{opt_out}}'
        response = save_template(self.client, template=template, variables=[])
        self.assertEqual(response.status_code, 200, response.content)
        preview = response.json()['preview']
        self.assertTrue(preview['length_warning'])
        self.assertGreater(preview['sms_segments'], 3)
        self.assertIn('پاسخ:', preview['full_sms'])
        self.assertEqual(m.SMSTemplateSettings.objects.get().template, template.replace(' \n', '\n'))

    def test_save_normalizes_digits_and_conflicts_preserve_last_saved_template(self):
        localized = [{'name': 'intro', 'value': 'پیام شمارهٔ ۱۲'}]
        saved = save_template(self.client, variables=localized)
        self.assertEqual(saved.status_code, 200, saved.content)
        result = saved.json()
        self.assertEqual(result['revision'], 1)
        self.assertEqual(result['variables'], [{'name': 'intro', 'value': 'پیام شمارهٔ 12'}])
        self.assertEqual(self.client.get(PATH).json(), result)
        self.assertEqual(save_template(self.client, variables=localized, revision=1).json()['revision'], 1)
        conflict = save_template(self.client, revision=0)
        self.assertEqual(conflict.status_code, 409, conflict.content)
        self.assertEqual(self.client.get(PATH).json(), result)
        audit = m.OperatorAudit.objects.get(action='update_sms_template')
        self.assertEqual(audit.actor, self.actor)
        self.assertEqual((audit.before['revision'], audit.after['revision']), (0, 1))
        self.assertNotIn('پیام شمارهٔ', str(audit.after))

    @override_settings(KAVENEGAR_SENDER='10000000')
    def test_sender_can_change_independently_and_legacy_edits_preserve_it(self):
        initial = self.client.get(PATH).json()
        self.assertEqual(initial['sender'], '')
        self.assertEqual(initial['default_sender'], '10000000')
        layout = {'template': initial['template'], 'variables': initial['variables']}
        saved = save_template(self.client, **layout, sender=' ۰۳۰۰ ١٥٠٠ ')
        self.assertEqual(saved.status_code, 200, saved.content)
        result = saved.json()
        self.assertEqual((result['sender'], result['revision']), ('03001500', 1))
        self.assertEqual(result['preview'], initial['preview'])
        self.assertEqual(self.client.get(PATH).json(), result)
        audit = m.OperatorAudit.objects.get(action='update_sms_template')
        self.assertNotEqual(audit.before['fingerprint'], audit.after['fingerprint'])
        self.assertNotIn('03001500', str(audit.after))

        conflict = save_template(self.client, **layout, sender='20000000')
        self.assertEqual(conflict.status_code, 409, conflict.content)
        legacy = save_template(self.client, revision=1)
        self.assertEqual(legacy.status_code, 200, legacy.content)
        self.assertEqual(legacy.json()['sender'], '03001500')
        reset = save_template(self.client, revision=legacy.json()['revision'], sender='')
        self.assertEqual(reset.status_code, 200, reset.content)
        self.assertEqual(reset.json()['sender'], '')
        self.assertEqual(reset.json()['default_sender'], '10000000')

    def test_invalid_sender_does_not_save_settings(self):
        for sender in (30000000, '30000000,20000000', '+30000000', '3' * 21):
            with self.subTest(sender=sender):
                response = save_template(self.client, sender=sender)
                self.assertEqual(response.status_code, 422, response.content)
                self.assertIn('sender', response.json()['error']['fields'])
        self.assertFalse(m.SMSTemplateSettings.objects.exists())


@override_settings(APP_BASE_URL='https://begamnagam.ir')
class SMSTemplateFlowTests(TestCase):
    setUp = live.LiveGiftSMSTests.setUp
    post = live.LiveGiftSMSTests.post
    authenticate = live.LiveGiftSMSTests.authenticate
    preview = live.LiveGiftSMSTests.preview
    make_order = live.LiveGiftSMSTests.make_order
    confirm = live.LiveGiftSMSTests.confirm

    @override_settings(KAVENEGAR_API_KEY='synthetic-key', KAVENEGAR_SENDER='10000000')
    def test_queued_order_uses_sender_active_at_submission(self):
        quote = self.preview(category='appreciation', text='ممنون از همراهی تو')
        order = self.make_order(quote=quote).json()
        self.confirm(order)
        outbox = m.Outbox.objects.get(order_id=order['id'])
        delivery = m.MessageDelivery.objects.get(order_id=order['id'])
        editor = Client()
        editor.force_login(get_user_model().objects.create_superuser('sms-editor'))
        saved = save_template(editor, sender='30001500')
        self.assertEqual(saved.status_code, 200, saved.content)

        accepted = {'return': {'status': 200}, 'entries': [{'messageid': 700, 'status': 1, 'cost': 1000}]}
        with patch('core.providers.kavenegar.post', return_value=accepted) as wire:
            submit_delivery(outbox.pk)
            submit_delivery(outbox.pk)
        wire.assert_called_once()
        payload = wire.call_args.args[2]
        self.assertEqual(payload['sender'], '30001500')
        self.assertEqual(payload['message'], quote['full_sms'])
        self.assertEqual(payload['localid'], delivery.local_id)
        self.assertEqual(m.Order.objects.get(pk=order['id']).status, 'accepted')

    def test_change_applies_to_new_previews_and_delivers_exact_old_and_new_snapshots(self):
        first = self.preview(category='appreciation', text='ممنون از همراهی تو')
        editor = Client()
        editor.force_login(get_user_model().objects.create_superuser('sms-editor'))
        intro = ('درود از بگم نگم و آرزوی یک روز آرام برای شما. ' * 14).strip()
        response = save_template(editor, variables=[{'name': 'intro', 'value': intro}])
        self.assertEqual(response.status_code, 200, response.content)
        examples = self.client.get('/api/v2/catalog').json()['examples']
        example = next(item for item in examples if item['topic'] == 'appreciation')
        new = self.client.post('/api/v2/message-previews', {'category': example['topic'], 'text': example['text'],
            'recipient_phone': '09901234568', 'source_mode': 'suggestion'}, content_type='application/json')
        self.assertEqual(new.status_code, 201, new.content)
        second = new.json()
        self.assertTrue(second['full_sms'].startswith(intro + '\n' + second['rewritten_text'] + '\n'))
        self.assertGreater(second['sms_segments'], 3)
        self.assertRegex(second['full_sms'], r'\nلغو: begamnagam\.ir/r/[A-Za-z0-9]{8}$')
        self.assertEqual(m.Preview.objects.get(pk=first['preview_id']).full_sms, first['full_sms'])
        for phone, quote in [('09901234567', first), ('09901234568', second)]:
            order = self.make_order(recipient=phone, quote=quote).json()
            self.confirm(order)
            outbox = m.Outbox.objects.get(order_id=order['id'])
            with patch('core.provider_delivery.Kavenegar.submit', return_value=SMSResult('accepted', f'70{phone[-1]}', 1000)) as wire:
                submit_delivery(outbox.pk)
            self.assertEqual(wire.call_args.kwargs['text'], quote['full_sms'])
