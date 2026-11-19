import secrets
import io
from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import tests as legacy
from .models import Order, Preview, RecipientGrant, RecipientState, SMSTemplateSettings
from .privacy import digest


class ShortRecipientLinkTests(TestCase):
    post = legacy.APITestCase.post
    authenticate = legacy.APITestCase.authenticate
    preview = legacy.APITestCase.preview
    order = legacy.APITestCase.order

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate()

    def quote(self):
        return self.post('/messages/preview', {'category': 'body', 'text': 'بوی بدن',
            'recipient_phone': '09901234567'})

    def deliver(self, quote):
        order = self.order(preview=quote).json()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.post('/orders/'+order['id']+'/pay-demo').status_code, 200)
        self.assertEqual(Order.objects.get(pk=order['id']).status, 'delivered_demo')
        return order

    @override_settings(APP_BASE_URL='https://begamnagam.ir')
    def test_single_action_still_uses_a_bare_domain_and_typed_cancel_code(self):
        SMSTemplateSettings.objects.create(template='{{message}}\n{{opt_out}}', legacy_reply_footer=False)
        response = self.quote()
        self.assertEqual(response.status_code, 200, response.content)
        quote = response.json()
        link = quote['full_sms'].split('لغو: ')[1]
        self.assertRegex(link, r'^begamnagam\.ir/r/c[A-Za-z0-9]{5}$')
        old_link = 'https://begamnagam.ir/r#' + 'A'*43
        self.assertEqual(len(old_link) - len(link), 45)
        self.assertLessEqual(quote['sms_segments'], 3)
        self.deliver(quote)
        token = link.rsplit('/', 1)[1]
        public = Client(enforce_csrf_checks=True)
        public.get('/api/v1/bootstrap')
        headers = {'HTTP_X_CSRFTOKEN': public.cookies['csrftoken'].value}
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token}, public).status_code, 403)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': token}, public, **headers).json(),
                         {'active': True, 'can_report': True})
        missing = self.post('/recipient/actions/stop', {'token': token}, public, **headers)
        self.assertEqual(missing.json()['error']['code'], 'recipient_confirmation_required')
        wrong = self.post('/recipient/actions/stop', {'token': token, 'phone': '09901234568'}, public, **headers)
        self.assertEqual(wrong.status_code, 404)
        self.assertFalse(RecipientState.objects.get(phone_hash=digest('09901234567')).blocked)
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token, 'phone': '۰۹۹۰ ۱۲۳۴۵۶۷'},
                                   public, **headers).json(), {'blocked': True})
        self.assertTrue(RecipientState.objects.get(phone_hash=digest('09901234567')).blocked)

    @override_settings(APP_BASE_URL='https://begamnagam.ir', SMS_LINK_HOST='bgam.ir', SMS_LINK_ROOT_PATH=True)
    def test_short_domain_sends_one_code_for_reply_and_opt_out(self):
        response = self.quote()
        self.assertEqual(response.status_code, 200, response.content)
        quote = response.json()
        self.assertRegex(quote['full_sms'], r'\nپاسخ یا لغو: bgam\.ir/a[A-Za-z0-9]{5}$')
        self.assertEqual(quote['full_sms'].count('bgam.ir/'), 1)
        token = quote['full_sms'].rsplit('/', 1)[1]
        self.assertRegex(token, r'[0-9]')
        grant = RecipientGrant.objects.get(preview_id=quote['preview_id'])
        self.assertEqual(grant.token_digest, digest('recipient-token:'+token))
        self.assertEqual(grant.reply_token_digest, digest('reply-token:'+token))
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': token}, Client()).status_code, 404)
        self.deliver(quote)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': token}, Client()).json(),
                         {'active': True, 'can_report': True})
        self.assertEqual(self.post('/recipient/actions/reply', {'token': token}).status_code, 404)
        receiver = Client()
        self.authenticate('09901234567', receiver)
        self.assertEqual(self.post('/recipient/actions/reply', {'token': token}, receiver).json(), {'active': True})
        public = Client(enforce_csrf_checks=True)
        public.get('/api/v1/bootstrap')
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token}, public).status_code, 403)
        headers = {'HTTP_X_CSRFTOKEN': public.cookies['csrftoken'].value}
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token}, public, **headers).status_code, 422)
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token, 'phone': '09901234568'},
                                   public, **headers).status_code, 404)
        report = self.post('/recipient/actions/report', {'token': token, 'reason': 'unwanted', 'phone': '09901234567'},
                           public, **headers)
        self.assertEqual(report.status_code, 200)
        self.assertTrue(report.json()['blocked'])

    @override_settings(APP_BASE_URL='https://begamnagam.ir')
    def test_existing_long_links_and_frozen_snapshots_remain_valid(self):
        quote = self.quote().json()
        legacy = secrets.token_urlsafe(32)
        old_sms = quote['rewritten_text'] + '\nبگم نگم | لغو: https://begamnagam.ir/r#' + legacy
        Preview.objects.filter(pk=quote['preview_id']).update(full_sms=old_sms)
        RecipientGrant.objects.filter(preview_id=quote['preview_id']).update(token_digest=digest('recipient-token:'+legacy))
        self.deliver(quote)
        self.assertEqual(self.post('/recipient/actions/stop', {'token': legacy}, Client()).json(), {'blocked': True})
        self.assertEqual(Preview.objects.get(pk=quote['preview_id']).full_sms, old_sms)
        self.assertEqual(Order.objects.get().full_sms, old_sms)

    def test_existing_short_fragment_links_still_stop_receiving(self):
        SMSTemplateSettings.objects.create(template='{{message}}\n{{opt_out}}', legacy_reply_footer=False)
        with patch('core.recipient.generate_short_code', return_value='Ef56Gh78'):
            quote = self.quote().json()
        token = quote['full_sms'].rsplit('/', 1)[1]
        old_sms = quote['full_sms'].split('\n', 1)[1].replace('/r/'+token, '/r#'+token)
        Preview.objects.filter(pk=quote['preview_id']).update(full_sms=old_sms)
        self.deliver(quote)
        self.assertEqual(self.post('/recipient/actions/stop', {'token':token}, Client()).json(), {'blocked':True})
        self.assertEqual(Order.objects.get().full_sms, old_sms)

    def test_previous_five_character_stop_link_still_confirms_the_phone(self):
        SMSTemplateSettings.objects.create(template='{{message}}\n{{opt_out}}', legacy_reply_footer=False)
        token = 'A1Cd2'
        with patch('core.recipient.generate_short_code', return_value=token):
            quote = self.quote().json()
        self.deliver(quote)
        public = Client()
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token}, public).status_code, 422)
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token, 'phone': '09901234567'},
                                   public).json(), {'blocked': True})

    def test_collision_retries_without_replacing_an_existing_grant(self):
        with patch('core.recipient.generate_short_code', return_value='a1Cd2x'):
            first = self.quote().json()
        original = RecipientGrant.objects.get(preview_id=first['preview_id'])
        with patch('core.recipient.generate_short_code', side_effect=['a1Cd2x', 'ay9Q2x']) as generate:
            second = self.quote()
        self.assertEqual(second.status_code, 200, second.content)
        self.assertTrue(second.json()['full_sms'].endswith('/r/ay9Q2x'))
        self.assertEqual(generate.call_count, 2)
        original.refresh_from_db()
        self.assertEqual(original.token_digest, digest('recipient-token:a1Cd2x'))
        self.assertEqual(original.reply_token_digest, digest('reply-token:a1Cd2x'))
        self.assertEqual(RecipientGrant.objects.count(), 2)

    def test_exhausted_collisions_fail_closed_and_roll_back_preview(self):
        with patch('core.recipient.generate_short_code', return_value='a1Cd2x'):
            self.assertEqual(self.quote().status_code, 200)
            failed = self.quote()
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(Preview.objects.count(), 1)
        self.assertEqual(RecipientGrant.objects.count(), 1)

    def test_expired_delivered_codes_are_not_reassigned_after_private_data_cleanup(self):
        quote = self.quote().json()
        token = quote['full_sms'].rsplit('/r/', 1)[1]
        self.deliver(quote)
        RecipientGrant.objects.update(stop_expires_at=timezone.now()-timedelta(days=1),
                                      report_expires_at=timezone.now()-timedelta(days=1))
        call_command('prune_private_data', stdout=io.StringIO())
        original = RecipientGrant.objects.get()
        self.assertEqual(original.recipient_hash, '')
        self.assertEqual(original.token_digest, digest('recipient-token:'+token))
        with patch('core.recipient.generate_short_code', side_effect=[token, 'a2sh1a']):
            response = self.quote()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['full_sms'].endswith('/r/a2sh1a'))
        self.assertEqual(self.post('/recipient/actions/stop', {'token': token, 'phone': '09901234567'},
                                   Client()).status_code, 404)

    def test_invalid_lengths_or_symbols_are_rejected_and_rotating_sessions_do_not_skip_ip_limit(self):
        for token in ['a'*4, 'a'*6, 'a'*7, 'a'*9, 'Abcd_123', 'Abcd-123', 'ABCde', 'r3PLy']:
            self.assertEqual(self.post('/recipient/actions/inspect', {'token': token}, Client()).status_code, 404)
        # Fresh sessions and changing candidate codes must share the IP budget.
        cache.clear()
        for index in range(120):
            response = self.post('/recipient/actions/inspect', {'token': f'{index:08d}'}, Client())
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': 'Qwer1234'}, Client()).status_code, 429)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': 'Qwer1234'}, Client(), REMOTE_ADDR='198.51.100.9').status_code, 404)

    def test_old_and_new_short_codes_share_the_tighter_ip_budget(self):
        for index in range(30):
            prefix = 'a' if index % 2 else 'c'
            self.assertEqual(self.post('/recipient/actions/inspect', {'token': f'{prefix}{index:05d}'}, Client()).status_code, 404)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': 'Z1234'}, Client()).status_code, 429)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': 'OldT1234'}, Client()).status_code, 404)
        self.assertEqual(self.post('/recipient/actions/inspect', {'token': 'Z1234'}, Client(), REMOTE_ADDR='198.51.100.9').status_code, 404)
