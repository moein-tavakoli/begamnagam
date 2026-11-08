"""Exercise rejected AI input from public consumers through staff text review."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import Client, TestCase, override_settings

from . import models, test_freeform as fixture
from .gapgpt import GapGPTRejected, GapGPTUnavailable
from .test_bot_conversations import BotHelpers


AI_SETTINGS = dict(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key',
    GAPGPT_MODEL='synthetic-model', GAPGPT_DAILY_REQUEST_LIMIT=20,
    GAPGPT_USER_DAILY_LIMIT=5, APP_BASE_URL='https://begamnagam.ir')


class StaffHistoryAssertions:
    def assert_staff_can_read_attempt(self, account, original, *, status, reason):
        attempt = models.MessageAttempt.objects.get(owner_id=account.user_id, status=status)
        self.assertEqual(attempt.original_text, original)
        self.assertEqual(attempt.recipient_phone, '09901234567')
        self.assertEqual(attempt.reason_code, reason)
        self.assertIsNone(attempt.preview_id)
        with connection.cursor() as cursor:
            cursor.execute('SELECT original_text, recipient_phone FROM core_messageattempt WHERE id = %s', [attempt.pk])
            encrypted = cursor.fetchone()
        self.assertTrue(all(value.startswith('enc:v1:') for value in encrypted))
        self.assertNotIn(original, str(encrypted))
        self.assertFalse(models.Preview.objects.exists())
        self.assertFalse(models.Order.objects.exists())
        self.assertFalse(models.Outbox.objects.exists())

        staff = get_user_model().objects.create_user('history-reader-' + str(attempt.pk), is_staff=True)
        staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='core',
            codename__in=['view_account', 'view_order']))
        client = Client(enforce_csrf_checks=True)
        client.force_login(staff)
        token = client.get('/api/v2/session').json()['csrf_token']
        base = f'/api/v1/manage/users/{account.pk}'
        activity = client.post(base + '/activity', {'section': 'messages'}, content_type='application/json',
            HTTP_X_CSRFTOKEN=token)
        self.assertEqual(activity.status_code, 200, activity.content)
        # The correlated moderation audit must not duplicate the rejected input.
        rows = activity.json()['rows']
        self.assertEqual(sum(row['id'] == str(attempt.pk) for row in rows), 1)
        self.assertEqual(len(rows), models.MessageAttempt.objects.filter(owner_id=account.user_id).count())
        self.assertNotIn(original, activity.content.decode())
        path = base + f'/attempts/{attempt.pk}/texts'
        self.assertEqual(client.post(path, {}, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='view_private_message_text'))
        self.assertEqual(client.post(path, {}, content_type='application/json').status_code, 403)
        reviewed = client.post(path, {}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(reviewed.status_code, 200, reviewed.content)
        self.assertEqual(reviewed.json()['original_text'], original)
        self.assertTrue(reviewed.json()['original_available'])
        self.assertIsNone(reviewed.json()['reviewed_text'])
        self.assertEqual(reviewed['Cache-Control'], 'no-store')
        audit = models.OperatorAudit.objects.get(action='message_attempt_text_viewed', object_id=str(attempt.pk))
        self.assertEqual(audit.actor_id, staff.pk)
        self.assertNotIn(original, json.dumps([audit.reason, audit.before, audit.after]))


@override_settings(**AI_SETTINGS)
class PublicMessageHistoryTests(StaffHistoryAssertions, TestCase):
    post, authenticate = fixture.FreeformTests.post, fixture.FreeformTests.authenticate
    setUp = fixture.FreeformTests.setUp

    def test_v2_auth_csrf_schema_and_quota_denials_do_not_store_private_text(self):
        endpoint = '/api/v2/message-previews'
        payload = {'source_mode': 'freeform', 'recipient_phone': '09901234567', 'text': 'لطفاً پولم را برگردان'}
        self.assertEqual(Client().post(endpoint, payload, content_type='application/json').status_code, 401)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(endpoint, payload, content_type='application/json').status_code, 403)
        models.RequestLimit.objects.create(scope='api-v2-account', maximum=1, window_seconds=60)
        invalid = self.client.post(endpoint, {**payload, 'unexpected': True}, content_type='application/json')
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()['error']['code'], 'invalid_input')
        limited = self.client.post(endpoint, payload, content_type='application/json')
        self.assertEqual(limited.status_code, 429)
        self.assertFalse(models.MessageAttempt.objects.exists())
        self.assertFalse(models.ModerationAudit.objects.exists())
        self.assertFalse(models.RewriteUsage.objects.exists())

    def test_website_and_v2_ai_failures_are_discoverable_and_readable_only_by_authorized_staff(self):
        for endpoint in ['/api/v1/messages/preview', '/api/v2/message-previews']:
            for failure, status, expected in [(GapGPTRejected('review_intent'), 'rejected', 422),
                                               (GapGPTUnavailable(), 'failed', 503)]:
                with self.subTest(endpoint=endpoint, status=status):
                    models.MessageAttempt.objects.all().delete()
                    models.ModerationAudit.objects.all().delete()
                    with patch('core.gapgpt.rewrite_message', side_effect=failure):
                        response = self.client.post(endpoint, {'source_mode': 'freeform',
                            'recipient_phone': '۰۹۹۰۱۲۳۴۵۶۷', 'text': 'لطفاً پول۱۲تومان را برگردان'},
                            content_type='application/json')
                    self.assertEqual(response.status_code, expected, response.content)
                    self.assert_staff_can_read_attempt(self.user.account, 'لطفاً پول12تومان را برگردان',
                        status=status, reason=response.json()['error']['code'])


@override_settings(**AI_SETTINGS, DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console',
    PROVIDER_NETWORK_MODE='disabled', PAYMENT_BACKEND='demo', API_DOCUMENTATION_ENABLED=False)
class BotMessageHistoryTests(StaffHistoryAssertions, BotHelpers, TestCase):
    def test_bot_owned_session_keeps_rejected_and_failed_ai_text_for_staff_history(self):
        self.resume()
        account = self.login()
        for failure, status, expected in [(GapGPTRejected('review_intent'), 'rejected', 422),
                                         (GapGPTUnavailable(), 'failed', 503)]:
            with self.subTest(status=status):
                with patch('core.gapgpt.rewrite_message', side_effect=failure):
                    response = self.mutate('/message-previews', {'source_mode': 'freeform',
                        'recipient_phone': '09901234567', 'text': 'لطفاً پولم را برگردان'})
                self.assertEqual(response.status_code, expected, response.content)
                self.assert_staff_can_read_attempt(account, 'لطفاً پولم را برگردان',
                    status=status, reason=response.json()['error']['code'])
