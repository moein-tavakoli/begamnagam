import json
import time
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, TransactionTestCase, override_settings
from .ai_config import current
from .freeform import validate_preview
from .gapgpt import GapGPTRejected, GapGPTUnavailable
from .models import AIConfiguration, OperatorAudit, Preview, RewriteUsage
from .moderation import ModerationRejected
from .ollama_rewrite import REVIEW_KEYS, endpoint, rewrite_message, slot
from .test_gapgpt import _Response
from . import test_freeform as freeform_tests
from .services import APIError

BODY = 'لطفاً جلوی در پارک نکن تا مسیر رفت‌وآمد باز بماند.'
SOURCE = 'جلوی در پارک نکن، رفت‌وآمد سخت میشه'
URL = 'http://127.0.0.1:11434/api/chat'


def response(content, **extra):
    return _Response({'done': True, 'done_reason': 'stop', 'message': {
        'role': 'assistant', 'content': json.dumps(content, ensure_ascii=False)}, **extra}, url=URL)


@override_settings(OLLAMA_URL=URL, AI_MODE='template')
class LocalClientTests(TestCase):
    def setUp(self):
        self.config = AIConfiguration(provider='ollama')
        self.opener = Mock()
        self.opener.open.side_effect = [response({'allowed': True, 'message': BODY}),
                                       response({key: True for key in REVIEW_KEYS})]
        self.patcher = patch('core.ollama_rewrite.urllib.request.build_opener', return_value=self.opener)
        self.patcher.start(); self.addCleanup(self.patcher.stop)

    def test_separate_review_is_local_structured_bounded_and_stateless(self):
        self.assertEqual(rewrite_message(SOURCE, max_units=140, config=self.config), BODY)
        self.assertEqual(self.opener.open.call_count, 2)
        for call in self.opener.open.call_args_list:
            request = call.args[0]; data = json.loads(request.data)
            self.assertEqual(request.full_url, URL)
            self.assertIsNone(request.get_header('Authorization'))
            self.assertIs(data['stream'], False); self.assertIs(data['think'], False)
            self.assertEqual(len(data['messages']), 2)
            self.assertEqual(data['options']['num_ctx'], 2048)
            self.assertLessEqual(call.kwargs['timeout'], 20)
        self.assertEqual(json.loads(self.opener.open.call_args_list[1].args[0].data)['format']['required'], list(REVIEW_KEYS))

    def test_negative_or_uncertain_review_never_returns_candidate(self):
        for key in REVIEW_KEYS:
            self.opener.open.side_effect = [response({'allowed': True, 'message': BODY}),
                                           response({name: name != key for name in REVIEW_KEYS})]
            with self.assertRaises(GapGPTRejected):
                rewrite_message(SOURCE, max_units=140, config=self.config)

    def test_refusal_or_bad_output_does_not_proceed_to_review(self):
        for value in [{'allowed': False, 'message': ''}, {'allowed': True, 'message': 'احمق، کنار برو'},
                      {'allowed': True, 'message': 'الف'*141}]:
            self.opener.open.reset_mock(); self.opener.open.side_effect = [response(value)]
            with self.assertRaises((GapGPTRejected, GapGPTUnavailable, ModerationRejected)):
                rewrite_message(SOURCE, max_units=140, config=self.config)
            self.assertEqual(self.opener.open.call_count, 1)

    def test_partial_generation_and_nonboolean_reviews_fail_closed(self):
        for extra in [{'done': False}, {'done_reason': 'length'}]:
            self.opener.open.side_effect = [response({'allowed': True, 'message': BODY}, **extra)]
            with self.assertRaises(GapGPTUnavailable):
                rewrite_message(SOURCE, max_units=140, config=self.config)
        self.opener.open.side_effect = [response({'allowed': True, 'message': BODY}),
                                       response({key: 1 for key in REVIEW_KEYS})]
        with self.assertRaises(GapGPTUnavailable):
            rewrite_message(SOURCE, max_units=140, config=self.config)

    def test_remote_urls_and_cloud_models_are_not_accepted(self):
        for url in ['https://ollama.com/api/chat', 'http://example.com:11434',
                    'http://127.0.0.1:11434/api/chat?token=x', 'http://user:pass@localhost:11434']:
            with self.settings(OLLAMA_URL=url), self.assertRaises(GapGPTUnavailable):
                endpoint()
        from django.core.exceptions import ValidationError
        self.config.ollama_model = 'qwen3:cloud'
        with self.assertRaises(ValidationError): self.config.full_clean()

    def test_timeout_never_calls_gapgpt(self):
        self.opener.open.side_effect = TimeoutError()
        with patch('core.gapgpt.rewrite_message') as remote:
            with self.assertRaises(GapGPTUnavailable):
                rewrite_message(SOURCE, max_units=140, config=self.config)
            remote.assert_not_called()


@override_settings(AI_MODE='template', OLLAMA_URL=URL)
class LocalFlowTests(TestCase):
    post, authenticate = freeform_tests.FreeformTests.post, freeform_tests.FreeformTests.authenticate
    quote, make_order = freeform_tests.FreeformTests.quote, freeform_tests.FreeformTests.make_order

    def setUp(self):
        freeform_tests.FreeformTests.setUp(self)
        AIConfiguration.objects.create(provider='ollama')

    def test_local_preview_is_sealed_and_old_preview_survives_provider_change(self):
        with patch('core.ollama_rewrite.rewrite_message', return_value=BODY) as local, patch('core.gapgpt.rewrite_message') as remote:
            response = self.quote(text='احمق جلوی در پارک نکن، رفت‌وآمد سخت میشه')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn('احمق', local.call_args.args[0]); remote.assert_not_called()
        self.assertEqual(response.json()['moderation_mode'], 'ollama')
        preview = Preview.objects.get(); validate_preview(preview)
        AIConfiguration.objects.filter(pk=1).update(provider='template')
        validate_preview(preview)
        self.assertEqual(self.make_order(response.json()).status_code, 200)
        preview.generated_body = 'لطفاً صدای موسیقی را کم کن.'
        with self.assertRaises(ModerationRejected): validate_preview(preview)

    def test_busy_rejects_immediately_without_using_budget_or_model(self):
        # PostgreSQL advisory locks are reentrant in one session; use fallback
        # locks here. A separate connection concurrency test covers PostgreSQL.
        with patch('core.ollama_rewrite.connection') as db:
            db.vendor = 'sqlite'
            with slot(2), slot(2), patch('core.ollama_rewrite.rewrite_message') as model:
                started = time.monotonic()
                response = self.quote()
                self.assertEqual(response.status_code, 429)
                self.assertEqual(response.json()['error']['code'], 'ai_busy')
                self.assertLess(time.monotonic()-started, 0.5)
                self.assertFalse(RewriteUsage.objects.exists()); model.assert_not_called()

    def test_provider_selection_changes_bootstrap_and_template_mode_calls_no_model(self):
        self.assertEqual(self.client.get('/api/v1/bootstrap').json()['rewrite_mode'], 'ollama')
        AIConfiguration.objects.filter(pk=1).update(provider='template')
        with self.settings(AI_MODE='ollama'), patch('core.moderation.urllib.request.urlopen') as network:
            self.assertEqual(self.client.get('/api/v1/bootstrap').json()['rewrite_mode'], 'template')
            network.assert_not_called()


class AIManagementTests(TestCase):
    def setUp(self):
        cache.clear()
        self.admin = get_user_model().objects.create_superuser('ai-admin', password='test-only')
        self.staff = get_user_model().objects.create_user('ai-staff', is_staff=True)

    def post(self, path, data):
        return self.client.post('/api/v1/manage/ai'+path, json.dumps(data), content_type='application/json')

    def test_permissions_csrf_audit_version_and_no_paid_activation(self):
        self.assertEqual(self.client.get('/api/v1/manage/ai').status_code, 401)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/api/v1/manage/ai').status_code, 403)
        self.client.force_login(self.admin)
        self.assertIn('manage_ai', self.client.get('/api/v1/manage/session').json()['permissions'])
        data = self.client.get('/api/v1/manage/ai').json()
        change = {'values': {'provider': 'ollama'}, 'revision': data['revision'], 'reason': 'local model selection'}
        self.assertEqual(self.post('', change).status_code, 200)
        self.assertEqual(current().provider, 'ollama')
        self.assertEqual(OperatorAudit.objects.get().action, 'update_ai_configuration')
        self.assertEqual(self.post('', change).status_code, 409)
        change.update(revision=1, values={'provider': 'gapgpt'})
        self.assertEqual(self.post('', change).status_code, 422)
        self.assertEqual(current().provider, 'ollama')
        client = Client(enforce_csrf_checks=True); client.force_login(self.admin)
        self.assertEqual(client.post('/api/v1/manage/ai', '{}', content_type='application/json').status_code, 403)

    def test_local_test_sanitizes_input_and_creates_no_sms_or_preview(self):
        self.client.force_login(self.admin)
        with patch('core.ollama_rewrite.rewrite_message', return_value=BODY) as model:
            response = self.post('/test', {'text': 'بیشعور جلوی در پارک نکن، رفت‌وآمد سخت میشه'})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['allowed']); self.assertNotIn('بیشعور', model.call_args.args[0])
        self.assertFalse(Preview.objects.exists()); self.assertFalse(RewriteUsage.objects.exists())
        with patch('core.ollama_rewrite.rewrite_message') as model:
            response = self.post('/test', {'text': 'احمق نفهم'})
            self.assertFalse(response.json()['allowed']); model.assert_not_called()


class AdmissionConcurrencyTests(TransactionTestCase):
    def test_postgres_capacity_is_shared_across_connections_and_never_waits(self):
        from django.db import connection
        from threading import Event, Thread
        if connection.vendor != 'postgresql':
            self.skipTest('Requires independent PostgreSQL sessions')
        ready, release = Event(), Event()
        failures = []
        def hold():
            try:
                with slot(1):
                    ready.set(); release.wait(5)
            except Exception as error:
                failures.append(type(error).__name__)
            finally:
                connection.close()
        thread = Thread(target=hold); thread.start()
        try:
            self.assertTrue(ready.wait(3))
            started = time.monotonic()
            with self.assertRaises(APIError) as error:
                with slot(1): pass
            self.assertEqual(error.exception.code, 'ai_busy')
            self.assertLess(time.monotonic()-started, 0.5)
        finally:
            release.set(); thread.join(5)
        self.assertFalse(failures)
        with slot(1): pass
