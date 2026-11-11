import io
import json
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings

from .models import KavenegarSettings, OperatorAudit
from .provider_balances import observe
from .providers.http import ProviderRejected
from .providers.kavenegar import Kavenegar


PATH = '/api/v1/manage/sms-template/kavenegar-key'
ENV_KEY = 'synthetic-environment-key'
PANEL_KEY = 'Synthetic_Panel_Key_123'


@override_settings(KAVENEGAR_API_KEY=ENV_KEY, KAVENEGAR_OTP_MODE='sms')
class KavenegarSettingsTests(TestCase):
    def setUp(self):
        self.manager = get_user_model().objects.create_superuser('kavenegar-manager')
        self.client.force_login(self.manager)

    def put_key(self, key, revision=0, *, client=None, **headers):
        return (client or self.client).put(PATH, {'api_key': key, 'revision': revision},
                                           content_type='application/json', **headers)

    def test_only_superuser_can_read_or_write_and_mutation_requires_csrf(self):
        self.assertEqual(Client().get(PATH).status_code, 401)
        staff = get_user_model().objects.create_user('sms-editor', is_staff=True)
        staff.user_permissions.add(Permission.objects.get(codename='manage_site_limits'))
        staff_client = Client()
        staff_client.force_login(staff)
        self.assertEqual(staff_client.get('/api/v1/manage/sms-template').status_code, 200)
        self.assertNotIn('manage_kavenegar_key', staff_client.get('/api/v1/manage/session').json()['permissions'])
        self.assertEqual(staff_client.get(PATH).status_code, 403)
        self.assertEqual(self.put_key(PANEL_KEY, client=staff_client).status_code, 403)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.manager)
        self.assertIn('manage_kavenegar_key', secured.get('/api/v1/manage/session').json()['permissions'])
        self.assertEqual(self.put_key(PANEL_KEY, client=secured).status_code, 403)
        token = secured.cookies['csrftoken'].value
        self.assertEqual(self.put_key(PANEL_KEY, client=secured, HTTP_X_CSRFTOKEN=token).status_code, 200)

    def test_key_is_encrypted_and_only_source_is_returned_or_audited(self):
        before = self.client.get(PATH)
        self.assertEqual(before.json(), {'source': 'environment', 'revision': 0})
        self.assertEqual(before['Cache-Control'], 'no-store')
        with patch('core.providers.kavenegar.post') as send, patch('core.provider_balances._read_json') as balance:
            updated = self.put_key(PANEL_KEY)
        send.assert_not_called()
        balance.assert_not_called()
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json(), {'source': 'panel', 'revision': 1})
        self.assertEqual(self.client.get(PATH).json(), updated.json())
        self.assertNotIn(PANEL_KEY, self.client.get('/api/v1/manage/sms-template').content.decode())
        audit = OperatorAudit.objects.get(action='update_kavenegar_key')
        self.assertEqual(audit.before, before.json())
        self.assertEqual(audit.after, updated.json())
        self.assertNotIn(ENV_KEY, json.dumps([audit.before, audit.after]))
        self.assertEqual(audit.actor, self.manager)

        with connection.cursor() as cursor:
            cursor.execute('SELECT api_key FROM core_kavenegarsettings WHERE id = 1')
            raw, = cursor.fetchone()
        self.assertTrue(raw.startswith('enc:v1:'))
        self.assertNotIn(PANEL_KEY, raw)
        self.assertEqual(KavenegarSettings.objects.get(pk=1).api_key, PANEL_KEY)
        rotated_key = Fernet.generate_key().decode()
        with override_settings(PHONE_ENCRYPTION_KEY=rotated_key,
                               PHONE_ENCRYPTION_FALLBACK_KEYS=[settings.PHONE_ENCRYPTION_KEY]):
            call_command('rotate_encryption', apply=True, stdout=io.StringIO())
        with override_settings(PHONE_ENCRYPTION_KEY=rotated_key, PHONE_ENCRYPTION_FALLBACK_KEYS=[]):
            self.assertEqual(KavenegarSettings.objects.get(pk=1).api_key, PANEL_KEY)

    def test_invalid_keys_and_stale_revisions_do_not_change_the_active_key(self):
        for invalid in ('bad/key', 'key\n', 'key۱', ' ' + PANEL_KEY, 'a' * 257, True):
            with self.subTest(value=invalid):
                response = self.put_key(invalid)
                self.assertEqual(response.status_code, 422, response.content)
                self.assertEqual(response.json()['error']['code'], 'invalid_kavenegar_key')
        self.assertEqual(self.put_key(PANEL_KEY, revision=True).status_code, 422)
        self.assertEqual(self.put_key(PANEL_KEY).status_code, 200)
        self.assertEqual(self.put_key('stale-key').status_code, 409)
        self.assertEqual(self.put_key(PANEL_KEY, revision=1).json()['revision'], 1)
        self.assertEqual(self.client.get(PATH).json(), {'source': 'panel', 'revision': 1})
        self.assertEqual(OperatorAudit.objects.filter(action='update_kavenegar_key').count(), 1)

    def test_active_key_reaches_send_otp_and_status_and_clear_restores_environment(self):
        provider = Kavenegar()
        self.assertEqual(self.put_key(PANEL_KEY).status_code, 200)
        wire_result = {'return': {'status': 200},
                       'entries': [{'messageid': 51, 'localid': 42, 'status': 10, 'cost': 1}]}
        with patch('core.providers.kavenegar.post', return_value=wire_result) as post:
            provider.submit(phone='09901234567', text='پیام آزمون', local_id=42)
            provider.otp(phone='09901234567', code='0123')
            with override_settings(KAVENEGAR_OTP_MODE='lookup', KAVENEGAR_OTP_TEMPLATE='login'):
                provider.otp(phone='09901234567', code='0123')
            provider.status(local_id=42, message_id='51')
            restored = self.put_key('', revision=1)
            self.assertEqual(restored.json(), {'source': 'environment', 'revision': 2})
            provider.status(local_id=42)
        self.assertEqual([call.args[1] for call in post.call_args_list], [
            f'/v1/{PANEL_KEY}/sms/send.json',
            f'/v1/{PANEL_KEY}/sms/send.json',
            f'/v1/{PANEL_KEY}/verify/lookup.json',
            f'/v1/{PANEL_KEY}/sms/status.json',
            f'/v1/{ENV_KEY}/sms/statuslocalmessageid.json',
        ])
        with override_settings(KAVENEGAR_API_KEY=''):
            self.assertEqual(self.client.get(PATH).json(), {'source': 'missing', 'revision': 2})

    def test_manager_can_replace_or_clear_an_unreadable_key(self):
        self.assertEqual(self.put_key(PANEL_KEY).status_code, 200)

        def damage_ciphertext():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE core_kavenegarsettings SET api_key = %s WHERE id = 1', ['enc:v1:unreadable'])

        damage_ciphertext()
        self.assertEqual(self.client.get(PATH).json(), {'source': 'unreadable', 'revision': 1})
        with patch('core.providers.kavenegar.post') as post, patch('core.provider_balances._read_json') as read:
            with self.assertRaises(ProviderRejected):
                Kavenegar().status(local_id=42)
            self.assertEqual(observe('kavenegar')['reason'], 'invalid_configuration')
        post.assert_not_called()
        read.assert_not_called()
        self.assertEqual(self.put_key('Synthetic_Replacement', revision=1).json(), {'source': 'panel', 'revision': 2})
        self.assertEqual(KavenegarSettings.objects.get(pk=1).api_key, 'Synthetic_Replacement')

        damage_ciphertext()
        self.assertEqual(self.put_key('', revision=2).json(), {'source': 'environment', 'revision': 3})
        audit = OperatorAudit.objects.filter(action='update_kavenegar_key', before__source='unreadable')
        self.assertEqual(audit.count(), 2)

    @override_settings(DEMO_MODE=False, PROVIDER_NETWORK_MODE='external', LIVE_PROVIDERS_ENABLED=True,
                       SMS_BACKEND='kavenegar', KAVENEGAR_BASE_URL='https://api.kavenegar.com')
    def test_balance_refresh_uses_the_rotated_key_without_reusing_the_old_balance(self):
        cache.clear()
        responses = [
            {'return': {'status': 200}, 'entries': {'remaincredit': 123}},
            {'return': {'status': 200}, 'entries': {'remaincredit': 456}},
        ]
        with patch('core.provider_balances._read_json', side_effect=responses) as read:
            self.assertEqual(observe('kavenegar')['amount'], '123')
            self.assertEqual(self.put_key(PANEL_KEY).status_code, 200)
            self.assertEqual(observe('kavenegar')['amount'], '456')
            self.assertEqual(observe('kavenegar')['amount'], '456')
        self.assertEqual([call.args[0].full_url for call in read.call_args_list], [
            f'https://api.kavenegar.com/v1/{ENV_KEY}/account/info.json',
            f'https://api.kavenegar.com/v1/{PANEL_KEY}/account/info.json',
        ])
