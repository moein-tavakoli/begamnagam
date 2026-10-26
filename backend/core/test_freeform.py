import uuid
from datetime import timedelta
from unittest.mock import patch
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from . import tests as legacy
from .freeform import reserve, validate_preview, validate_order
from .models import Account, Preview, Order, Outbox, RewriteBudget, RewriteUsage, SafetyControl
from .moderation import ModerationRejected
from .gapgpt import GapGPTRejected, GapGPTUnavailable
from .privacy import digest, encrypt, mask
from .services import APIError

BODY = 'لطفاً پولی را که قرض گرفته‌اید، در زمان توافق‌شده برگردانید. از توجهتان ممنونم.'


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5, APP_BASE_URL='https://begamnagam.ir')
class FreeformTests(TestCase):
    post, authenticate = legacy.APITestCase.post, legacy.APITestCase.authenticate

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate(free_sends=None)
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted':False})

    def quote(self, text='احمق پولی که قرض گرفتی را به موقع برگردان', category='', phone='09901234567'):
        return self.post('/messages/preview', {'text':text, 'category':category, 'recipient_phone':phone})

    def make_order(self, quote):
        return self.post('/orders', {'preview_id':quote['preview_id'], 'recipient_phone':'09901234567',
            'consent':True, 'terms_version':quote['terms_version']}, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    def test_freeform_ignores_topic_and_filters_insult_before_api_encrypts_only_approved_body(self):
        with patch('core.gapgpt.rewrite_message', return_value=BODY) as model:
            result = self.quote(category='parking')
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(model.call_args.args[0], 'پولی که قرض گرفتی را به موقع برگردان')
        quote, preview = result.json(), Preview.objects.get()
        self.assertEqual(quote['moderation_mode'], 'gapgpt')
        self.assertEqual(quote['rewritten_text'], BODY)
        self.assertEqual(preview.category, 'custom')
        self.assertEqual(preview.text, '')
        self.assertEqual(preview.generated_body, BODY)
        self.assertEqual(len(preview.review_signature), 64)
        self.assertTrue(quote['full_sms'].startswith('نمیدونم بهت بگم یا نگم؟\n'+BODY+'\n'))
        self.assertLessEqual(quote['sms_segments'], 3)
        with connection.cursor() as cursor:
            cursor.execute('SELECT generated_body FROM core_preview')
            self.assertTrue(cursor.fetchone()[0].startswith('enc:v1:'))
        self.assertEqual(RewriteBudget.objects.get().reserved_requests, 1)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
        validate_preview(preview, recipient_hash=digest('09901234567'))

    def test_threat_contact_pure_insult_and_invalid_recipient_never_reach_api_or_budget(self):
        with patch('core.gapgpt.rewrite_message') as model:
            for text in ['می کشمت اگر پولم را ندهی', 'احمق لعنتی', 'به 09123456789 زنگ بزن']:
                self.assertEqual(self.quote(text).status_code, 422)
            self.assertEqual(self.quote(phone='invalid').status_code, 400)
            self.assertEqual(self.quote(phone='09123456789').status_code, 422)
        model.assert_not_called()
        self.assertFalse(RewriteUsage.objects.exists())
        self.assertFalse(Preview.objects.exists())

    def test_anonymous_and_suspended_requests_never_reach_model(self):
        with patch('core.gapgpt.rewrite_message') as model:
            self.assertEqual(Client().post('/api/v1/messages/preview', data='{"text":"یک درخواست تازه"}', content_type='application/json').status_code, 401)
            Account.objects.filter(user=self.user).update(suspended=True)
            self.assertEqual(self.quote().status_code, 403)
        model.assert_not_called()

    def test_invalid_unicode_audit_returns_only_safe_content_error(self):
        response = self.quote('لطفاً\ud800 وسایل را برگردان')
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()['error']['code'], 'moderation_rejected')
        self.assertNotIn('codec', response.content.decode())

    @override_settings(AI_MODE='template')
    def test_explicit_custom_or_edited_suggestion_never_silently_becomes_topic_template(self):
        for mode in ['freeform', 'suggestion']:
            response = self.post('/messages/preview', {'text':'پولم را پس بده', 'category':'parking',
                'recipient_phone':'09901234567', 'source_mode':mode})
            self.assertEqual(response.json()['error']['code'], 'freeform_unavailable')

    def test_report_triage_can_read_generated_body_without_exposing_capability(self):
        from .admin import AbuseReportAdmin
        from .models import AbuseReport, RecipientGrant
        from django.contrib import admin
        with patch('core.gapgpt.rewrite_message', return_value=BODY): self.quote()
        report = AbuseReport.objects.create(grant=RecipientGrant.objects.get(), reason='unwanted')
        self.assertEqual(AbuseReportAdmin(AbuseReport,admin.site).reviewed_text(report), BODY)

    def test_blank_key_and_no_budget_leave_templates_available_without_network(self):
        with patch('core.gapgpt.rewrite_message') as model:
            for config in [{'GAPGPT_API_KEY':''}, {'GAPGPT_MODEL':''}, {'GAPGPT_DAILY_REQUEST_LIMIT':0}]:
                with override_settings(**config):
                    self.assertEqual(self.client.get('/api/v1/bootstrap').json()['rewrite_mode'], 'template')
                    self.assertEqual(self.quote().json()['error']['code'], 'freeform_unavailable')
                    self.assertEqual(self.quote('از همراهی تو ممنونم', category='appreciation').status_code, 200)
        model.assert_not_called()
        self.assertFalse(RewriteUsage.objects.exists())

    def test_bad_model_output_refusal_and_timeout_fail_closed_without_template_fallback(self):
        for failure in [GapGPTRejected(), GapGPTUnavailable()]:
            with patch('core.gapgpt.rewrite_message', side_effect=failure):
                response = self.quote()
            self.assertIn(response.status_code, [422, 503])
        with patch('core.gapgpt.rewrite_message', return_value='احمق پولم را بده'):
            self.assertEqual(self.quote().status_code, 422)
        self.assertFalse(Preview.objects.exists())
        self.assertEqual(RewriteUsage.objects.count(), 3)

    @override_settings(GAPGPT_USER_DAILY_LIMIT=1)
    def test_user_cap_counts_uncertain_calls_and_does_not_spend_sms_budget(self):
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTUnavailable()) as model:
            self.assertEqual(self.quote().status_code, 503)
            response = self.quote()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()['error']['code'], 'rewrite_daily_limit')
        self.assertEqual(model.call_count, 1)
        from .models import SpendReservation
        self.assertFalse(SpendReservation.objects.exists())

    @override_settings(GAPGPT_DAILY_REQUEST_LIMIT=1)
    def test_shared_site_cap_survives_cache_clear_and_failed_request(self):
        with patch('core.gapgpt.rewrite_message', side_effect=GapGPTUnavailable()) as model:
            self.assertEqual(self.quote().status_code, 503)
            cache.clear()
            self.assertEqual(self.quote().status_code, 503)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(RewriteBudget.objects.get().reserved_requests, 1)

    def test_order_and_worker_preserve_confirmed_output_without_another_model_call(self):
        with patch('core.gapgpt.rewrite_message', return_value=BODY) as model:
            quote = self.quote().json()
            order = self.make_order(quote).json()
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.post(f"/orders/{order['id']}/confirm-free").status_code, 200)
        self.assertEqual(model.call_count, 1)
        stored = Order.objects.get()
        self.assertEqual(stored.status, 'delivered_demo')
        self.assertEqual(stored.text, '')
        self.assertEqual(stored.full_sms, quote['full_sms'])
        self.assertEqual(self.client.get('/api/v1/messages').json()['results'][0]['text'], quote['full_sms'])

    def test_tampering_body_sms_recipient_or_signature_prevents_checkout(self):
        with patch('core.gapgpt.rewrite_message', return_value=BODY):
            quote = self.quote().json()
        original = Preview.objects.get()
        for field, value in [('generated_body','لطفاً برای کار دیگری آماده شوید.'), ('full_sms','متن عوض شده'),
                ('review_signature','a'*64), ('recipient_hash',digest('09901234568'))]:
            with self.subTest(field=field):
                before = getattr(original, field)
                Preview.objects.filter(pk=original.pk).update(**{field:value})
                self.assertEqual(self.make_order(quote).status_code, 409)
                Preview.objects.filter(pk=original.pk).update(**{field:before})
        self.assertFalse(Order.objects.exists())

    def test_tampered_queued_snapshot_never_dispatches_and_returns_credit(self):
        with patch('core.gapgpt.rewrite_message', return_value=BODY):
            quote = self.quote().json()
        order = self.make_order(quote).json()
        with self.captureOnCommitCallbacks(execute=False): self.post(f"/orders/{order['id']}/confirm-free")
        Preview.objects.filter(pk=quote['preview_id']).update(generated_body='لطفاً چیز دیگری بفرستید.')
        from .tasks import deliver_message
        deliver_message(Outbox.objects.get().pk)
        self.assertEqual(Order.objects.get().status, 'failed')
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)

    def test_live_adapter_sends_exact_approved_sms_once(self):
        from .provider_delivery import submit_delivery
        from .providers.kavenegar import SMSResult
        with override_settings(DEMO_MODE=False, SMS_BACKEND='kavenegar', PAYMENT_BACKEND='disabled',
                PROVIDER_NETWORK_MODE='external', LIVE_PROVIDERS_ENABLED=True, PROVIDER_ENVIRONMENT='live',
                SMS_RECIPIENT_POLICY='all', SMS_MAX_COST_RIAL=20000, PROVIDER_DAILY_BUDGET_RIAL=100000,
                SENDING_WINDOW_ENABLED=False, TERMS_VERSION='v0.10.0-review'):
            with patch('core.gapgpt.rewrite_message', return_value=BODY): quote = self.quote().json()
            order = self.make_order(quote).json()
            with self.captureOnCommitCallbacks(execute=False): self.post(f"/orders/{order['id']}/confirm-free")
            with patch('core.provider_delivery.Kavenegar.submit', return_value=SMSResult('accepted','101',1000)) as wire:
                submit_delivery(Outbox.objects.get().pk);submit_delivery(Outbox.objects.get().pk)
            wire.assert_called_once()
            self.assertEqual(wire.call_args.kwargs['text'], quote['full_sms'])


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=1, GAPGPT_USER_DAILY_LIMIT=10)
class RewriteConcurrencyTests(TransactionTestCase):
    setUp = legacy.PostgreSQLConcurrencyTests.setUp
    parallel = legacy.PostgreSQLConcurrencyTests.parallel

    def test_parallel_users_cannot_exceed_global_rewrite_budget(self):
        other = get_user_model().objects.create_user(username='other-rewriter')
        Account.objects.create(user=other, phone_hash=digest('09901234566'), phone_cipher=encrypt('09901234566'), phone_masked=mask('09901234566'))
        users = iter([self.user.pk, other.pk])
        def operation(_):
            try: reserve(get_user_model().objects.get(pk=next(users)));return 'reserved'
            except Exception as exc:
                from .moderation import RewriteUnavailable
                if isinstance(exc, RewriteUnavailable): return 'limited'
                raise
        self.assertCountEqual(self.parallel(operation), ['reserved','limited'])
        self.assertEqual(RewriteUsage.objects.count(), 1)
