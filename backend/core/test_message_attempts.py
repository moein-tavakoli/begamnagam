import io
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import models, test_freeform as fixture


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5, APP_BASE_URL='https://begamnagam.ir')
class MessageAttemptTests(TestCase):
    post, authenticate = fixture.FreeformTests.post, fixture.FreeformTests.authenticate
    quote = fixture.FreeformTests.quote

    def setUp(self):
        fixture.FreeformTests.setUp(self)

    def attempt_model(self):
        model = getattr(models, 'MessageAttempt', None)
        self.assertIsNotNone(model, 'Preview attempts must persist independently of successful previews')
        return model

    def test_rejected_draft_is_encrypted_and_correlated_without_creating_a_preview(self):
        response = self.quote(text='احمق لعنتی')
        self.assertEqual(response.status_code, 422)
        attempt = self.attempt_model().objects.get()
        self.assertEqual(attempt.owner, self.user)
        self.assertEqual(attempt.original_text, 'احمق لعنتی')
        self.assertEqual(attempt.recipient_phone, '09901234567')
        self.assertEqual(attempt.status, 'rejected')
        self.assertEqual(attempt.reason_code, response.json()['error']['code'])
        self.assertEqual(attempt.moderation_event_id, models.ModerationAudit.objects.get().event_id)
        self.assertIsNone(attempt.preview_id)
        self.assertFalse(models.Preview.objects.exists())
        with connection.cursor() as cursor:
            cursor.execute('SELECT original_text, recipient_phone FROM core_messageattempt')
            stored = cursor.fetchone()
        self.assertTrue(all(value.startswith('enc:v1:') for value in stored))
        self.assertNotIn('احمق لعنتی', str(stored))
        self.assertNotIn('09901234567', str(stored))
        self.assertNotIn('original_text', response.json())

    def test_unavailable_provider_keeps_failed_attempt_and_original_public_error(self):
        with patch('core.gapgpt.rewrite_message', side_effect=fixture.GapGPTUnavailable):
            response = self.quote(text='لطفاً پولم را برگردان')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'rewrite_unavailable')
        attempt = self.attempt_model().objects.get()
        self.assertEqual((attempt.status, attempt.reason_code), ('failed', 'rewrite_unavailable'))
        self.assertEqual(attempt.original_text, 'لطفاً پولم را برگردان')
        self.assertIsNone(attempt.preview_id)

    def test_success_links_sealed_preview_and_normalizes_digits(self):
        with patch('core.gapgpt.rewrite_message', return_value=fixture.BODY):
            response = self.quote(text='پول۱۲تومان را برگردان', phone='۰۹۹۰۱۲۳۴۵۶۷')
        self.assertEqual(response.status_code, 200, response.content)
        attempt = self.attempt_model().objects.get()
        self.assertEqual(attempt.original_text, 'پول12تومان را برگردان')
        self.assertEqual(attempt.recipient_phone, '09901234567')
        self.assertEqual(attempt.status, 'accepted')
        self.assertEqual(str(attempt.preview_id), response.json()['preview_id'])
        self.assertEqual(attempt.message_tone, response.json()['message_tone'])
        self.assertEqual(attempt.moderation_event_id, models.ModerationAudit.objects.get().event_id)

    def test_anonymous_and_unbounded_nontext_requests_do_not_retain_private_input(self):
        anonymous = Client()
        anonymous.post('/api/v1/messages/preview', {'text':'احمق لعنتی'}, content_type='application/json')
        for text in [None, {'value':'private'}, 'x' * 281, '\ud800']:
            self.quote(text=text)
        self.assertFalse(self.attempt_model().objects.exists())

    def test_retention_redacts_attempts_and_account_deletion_without_erasing_metadata(self):
        self.quote(text='احمق لعنتی')
        model = self.attempt_model()
        attempt = model.objects.get()
        model.objects.filter(pk=attempt.pk).update(created_at=timezone.now()-timedelta(days=32))
        call_command('prune_private_data', dry_run=True, stdout=io.StringIO())
        self.assertEqual(model.objects.get(pk=attempt.pk).original_text, 'احمق لعنتی')
        call_command('prune_private_data', stdout=io.StringIO())
        attempt.refresh_from_db()
        self.assertEqual((attempt.original_text, attempt.recipient_phone), ('', ''))
        self.assertEqual((attempt.status, attempt.owner_id), ('rejected', self.user.pk))
        recent = model.objects.create(owner=self.user, original_text='متن تازه', recipient_phone='09901234567', status='failed')
        models.Account.objects.filter(user=self.user).update(deletion_requested_at=timezone.now()-timedelta(days=31))
        call_command('prune_private_data', stdout=io.StringIO())
        recent.refresh_from_db()
        self.assertEqual((recent.original_text, recent.recipient_phone), ('', ''))

    def test_rotation_covers_attempt_text_and_phone(self):
        self.quote(text='احمق لعنتی')
        model = self.attempt_model()
        new_key = Fernet.generate_key().decode()
        with override_settings(PHONE_ENCRYPTION_KEY=new_key, PHONE_ENCRYPTION_FALLBACK_KEYS=[settings.PHONE_ENCRYPTION_KEY]):
            call_command('rotate_encryption', apply=True, stdout=io.StringIO())
        with override_settings(PHONE_ENCRYPTION_KEY=new_key, PHONE_ENCRYPTION_FALLBACK_KEYS=[]):
            attempt = model.objects.get()
            self.assertEqual((attempt.original_text, attempt.recipient_phone), ('احمق لعنتی', '09901234567'))

    def test_history_write_failure_does_not_replace_rejection_or_leak_the_draft(self):
        with patch('core.message_attempts.MessageAttempt.objects.create', side_effect=DatabaseError('private draft')):
            with self.assertLogs('core.message_attempts', level='WARNING') as logs:
                response = self.quote(text='احمق لعنتی')
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('private draft', str(logs.output))
        self.assertNotIn('احمق لعنتی', str(logs.output))
        self.assertEqual(models.ModerationAudit.objects.filter(outcome='rejected').count(), 1)

    def test_success_fails_closed_and_rolls_back_preview_when_history_is_unavailable(self):
        with patch('core.message_attempts.MessageAttempt.objects.create', side_effect=DatabaseError('private draft')):
            with patch('core.gapgpt.rewrite_message', return_value=fixture.BODY):
                with self.assertLogs('core.message_attempts', level='WARNING'):
                    response = self.quote(text='پول قرض گرفته را برگردان')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()['error']['code'], 'service_unavailable')
        self.assertFalse(models.Preview.objects.exists())
        self.assertFalse(models.RecipientGrant.objects.exists())
        self.assertFalse(models.ModerationAudit.objects.filter(outcome='accepted').exists())

    def test_v2_delegation_records_one_attempt_for_each_rejected_and_accepted_preview(self):
        payload = {'source_mode':'freeform', 'recipient_phone':'09901234567', 'text':'احمق لعنتی'}
        response = self.client.post('/api/v2/message-previews', payload, content_type='application/json')
        self.assertEqual(response.status_code, 422, response.content)
        payload['text'] = 'لطفاً پولم را برگردان'
        with patch('core.gapgpt.rewrite_message', return_value=fixture.BODY):
            response = self.client.post('/api/v2/message-previews', payload, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        model = self.attempt_model()
        self.assertEqual(model.objects.filter(status='accepted').count(), 1)
        self.assertEqual(model.objects.filter(status='rejected').count(), 1)

    def test_expired_unused_preview_deletion_preserves_attempt_until_its_retention_deadline(self):
        with patch('core.gapgpt.rewrite_message', return_value=fixture.BODY):
            response = self.quote(text='پولم را برگردان')
        self.assertEqual(response.status_code, 200)
        model = self.attempt_model()
        attempt = model.objects.get()
        models.Preview.objects.filter(pk=attempt.preview_id).update(expires_at=timezone.now()-timedelta(days=2))
        call_command('prune_private_data', stdout=io.StringIO())
        attempt.refresh_from_db()
        self.assertIsNone(attempt.preview_id)
        self.assertEqual(attempt.original_text, 'پولم را برگردان')

    def test_ai_rejection_retains_input_without_dispatchable_preview(self):
        with patch('core.gapgpt.rewrite_message', side_effect=fixture.GapGPTRejected('model_rejected')):
            response = self.quote(text='لطفاً پولم را برگردان')
        self.assertEqual(response.status_code, 422)
        attempt = self.attempt_model().objects.get()
        self.assertEqual(attempt.original_text, 'لطفاً پولم را برگردان')
        self.assertEqual(attempt.status, 'rejected')
        self.assertEqual(attempt.reason_code, response.json()['error']['code'])
        self.assertIsNone(attempt.preview_id)
        self.assertFalse(models.Preview.objects.exists())

    def test_rate_limited_preview_requests_do_not_add_private_history(self):
        model = self.attempt_model()
        for scope in ['preview-session', 'preview-ip-flood', 'preview-user']:
            with self.subTest(scope=scope):
                cache.clear()
                model.objects.all().delete()
                models.RequestLimit.objects.filter(scope__startswith='preview-').delete()
                models.RequestLimit.objects.create(scope=scope, maximum=1, window_seconds=600)
                response = self.quote(text='احمق لعنتی')
                self.assertEqual(response.status_code, 422)
                self.assertEqual(model.objects.count(), 1)
                for text in ['متن خصوصی دوم', 'متن خصوصی سوم', 'متن خصوصی چهارم']:
                    response = self.quote(text=text)
                    self.assertEqual(response.status_code, 429)
                    self.assertEqual(response.json()['error']['code'], 'rate_limited')
                self.assertEqual(model.objects.count(), 1)
                self.assertEqual(model.objects.get().original_text, 'احمق لعنتی')

    def test_invalid_payload_rejected_before_quota_admission_does_not_retain_text(self):
        for _ in range(3):
            response = self.post('/messages/preview', {'text':'متن خصوصی', 'unexpected':True})
            self.assertEqual(response.json()['error']['code'], 'invalid_input')
        self.assertFalse(self.attempt_model().objects.exists())

    def test_invalid_tone_before_account_quota_admission_does_not_retain_text(self):
        response = self.post('/messages/preview', {'text': 'حلالم کن داداش', 'message_tone': 'unknown-tone', 'recipient_phone': '09901234567'})
        self.assertEqual(response.status_code, 422)
        self.assertFalse(self.attempt_model().objects.exists())
