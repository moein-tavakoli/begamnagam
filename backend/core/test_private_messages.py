import io
from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import test_freeform as fixture
from .freeform import validate_preview
from .models import AIConfiguration, AbuseReport, OperatorAudit, Order, Preview, RecipientGrant

ORIGINAL = '  احمق پولی که قرض گرفتی را به موقع برگردان  '


@override_settings(AI_MODE='gapgpt', GAPGPT_API_KEY='synthetic-key', GAPGPT_MODEL='synthetic-model',
    GAPGPT_DAILY_REQUEST_LIMIT=20, GAPGPT_USER_DAILY_LIMIT=5, APP_BASE_URL='https://begamnagam.ir')
class PrivateMessageTests(TestCase):
    post, authenticate = fixture.FreeformTests.post, fixture.FreeformTests.authenticate
    quote, make_order = fixture.FreeformTests.quote, fixture.FreeformTests.make_order

    def setUp(self):
        fixture.FreeformTests.setUp(self)

    def prepared(self):
        with patch('core.gapgpt.rewrite_message', return_value=fixture.BODY) as provider:
            response = self.quote(text=ORIGINAL)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn('احمق', provider.call_args.args[0])
        return response

    def ordered(self):
        preview = self.prepared().json()
        response = self.make_order(preview)
        self.assertEqual(response.status_code, 200, response.content)
        return Order.objects.get(pk=response.json()['id'])

    def private_post(self, client, order, reason='Review message pair'):
        return client.post(f'/api/v1/manage/orders/{order.pk}/texts', {'reason': reason}, content_type='application/json')

    def test_original_and_approved_output_are_separate_encrypted_and_not_public(self):
        response = self.prepared()
        preview = Preview.objects.get()
        self.assertEqual(preview.original_text, ORIGINAL)
        self.assertEqual(preview.generated_body, fixture.BODY)
        self.assertEqual(preview.text, '')
        self.assertNotIn(ORIGINAL, response.content.decode())
        self.assertNotIn('original_text', response.json())
        with connection.cursor() as cursor:
            cursor.execute('SELECT original_text, generated_body FROM core_preview')
            stored = cursor.fetchone()
        self.assertTrue(all(value.startswith('enc:v1:') for value in stored))
        self.assertNotIn(ORIGINAL, str(stored))
        validate_preview(preview)
        order_response = self.make_order(response.json())
        self.assertEqual(order_response.status_code, 200)
        order = Order.objects.get()
        for path in (f'/api/v1/orders/{order.pk}', '/api/v1/messages'):
            content = self.client.get(path)
            self.assertNotIn(ORIGINAL, content.content.decode())
            self.assertNotIn('original_text', content.content.decode())
            self.assertIn(fixture.BODY, content.content.decode())
        self.assertEqual(order.text, '')
        self.assertNotIn('احمق', order.full_sms)

    def test_ollama_also_preserves_exact_original_and_filters_model_input(self):
        AIConfiguration.objects.create(provider='ollama')
        with patch('core.ollama_rewrite.rewrite_message', return_value=fixture.BODY) as provider:
            response = self.quote(text=ORIGINAL)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('احمق', provider.call_args.args[0])
        preview = Preview.objects.get()
        self.assertEqual(preview.original_text, ORIGINAL)
        self.assertEqual(preview.generated_body, fixture.BODY)
        validate_preview(preview)

    @override_settings(AI_MODE='template')
    def test_template_suggestions_keep_the_initial_wording_separate(self):
        response = self.quote(text='از کمک و توجهت ممنونم', category='appreciation')
        self.assertEqual(response.status_code, 200)
        preview = Preview.objects.get()
        self.assertEqual(preview.original_text, 'از کمک و توجهت ممنونم')
        self.assertNotEqual(preview.text, preview.original_text)

    def test_rejected_or_failed_rewrites_do_not_retain_a_raw_draft(self):
        with patch('core.gapgpt.rewrite_message') as provider:
            self.assertEqual(self.quote(text='احمق لعنتی').status_code, 422)
            provider.assert_not_called()
        with patch('core.gapgpt.rewrite_message', side_effect=fixture.GapGPTUnavailable):
            self.assertEqual(self.quote(text=ORIGINAL).status_code, 503)
        self.assertEqual(Preview.objects.count(), 0)

    def test_only_staff_with_both_permissions_can_review_and_every_read_is_audited(self):
        order = self.ordered()
        self.assertEqual(self.private_post(Client(), order).status_code, 401)
        self.assertEqual(self.private_post(self.client, order).status_code, 403)
        staff = get_user_model().objects.create_user(username='text-reviewer', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_order'))
        client = Client(); client.force_login(staff)
        self.assertEqual(self.private_post(client, order).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='view_private_message_text'))
        self.assertEqual(self.private_post(client, order, reason='').status_code, 422)
        response = self.private_post(client, order)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['original_text'], ORIGINAL)
        self.assertEqual(response.json()['final_text'], fixture.BODY)
        self.assertTrue(response.json()['original_available'])
        self.assertEqual(response['Cache-Control'], 'no-store')
        audit = OperatorAudit.objects.get(action='message_text_viewed')
        self.assertEqual((audit.actor, audit.object_id), (staff, str(order.pk)))
        self.assertEqual((audit.before, audit.after), ({}, {}))
        listed = client.post('/api/v1/manage/records/orders', {}, content_type='application/json')
        self.assertNotIn(ORIGINAL, listed.content.decode())
        client = Client(enforce_csrf_checks=True); client.force_login(staff)
        self.assertEqual(self.private_post(client, order).status_code, 403)

    def test_custom_permission_alone_is_insufficient_and_legacy_text_is_not_invented(self):
        order = self.ordered()
        Preview.objects.filter(pk=order.preview_id).update(original_text='')
        staff = get_user_model().objects.create_user(username='text-only-reviewer', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_private_message_text'))
        client = Client(); client.force_login(staff)
        self.assertEqual(self.private_post(client, order).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='view_order'))
        response = self.private_post(client, order)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['original_available'])
        self.assertEqual(response.json()['original_text'], '')

    def test_django_admin_enforces_same_permission_and_records_view(self):
        order = self.ordered()
        staff = get_user_model().objects.create_user(username='django-text-reviewer', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='view_order'))
        client = Client(); client.force_login(staff)
        path = reverse('admin:core_order_change', args=[order.pk])
        self.assertNotContains(client.get(path), ORIGINAL.strip())
        staff.user_permissions.add(Permission.objects.get(codename='view_private_message_text'))
        self.assertContains(client.get(path), ORIGINAL.strip())
        self.assertEqual(OperatorAudit.objects.filter(action='message_text_viewed').count(), 1)

    def test_key_rotation_and_retention_cover_original_text(self):
        order = self.ordered()
        with override_settings(PHONE_ENCRYPTION_KEY=Fernet.generate_key().decode(), PHONE_ENCRYPTION_FALLBACK_KEYS=[settings.PHONE_ENCRYPTION_KEY]):
            call_command('rotate_encryption', apply=True, stdout=io.StringIO())
            self.assertEqual(Preview.objects.get(pk=order.preview_id).original_text, ORIGINAL)
            Order.objects.filter(pk=order.pk).update(status='cancelled', updated_at=timezone.now()-timedelta(days=32))
            grant = RecipientGrant.objects.get(preview_id=order.preview_id)
            report = AbuseReport.objects.create(grant=grant, reason='other', hold_until=timezone.now()+timedelta(days=1))
            call_command('prune_private_data', stdout=io.StringIO())
            self.assertEqual(Preview.objects.get(pk=order.preview_id).original_text, ORIGINAL)
            AbuseReport.objects.filter(pk=report.pk).update(hold_until=timezone.now()-timedelta(seconds=1))
            call_command('prune_private_data', stdout=io.StringIO())
            self.assertEqual(Preview.objects.get(pk=order.preview_id).original_text, '')
            self.assertEqual(Preview.objects.get(pk=order.preview_id).generated_body, '')
