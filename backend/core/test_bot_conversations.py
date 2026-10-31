import io
import importlib.util
import json
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from pathlib import Path
from unittest.mock import patch

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.management import call_command, CommandError
from django.db import close_old_connections, connection
from django.test import Client, LiveServerTestCase, SimpleTestCase, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from core.bot_conversations import new_credential
from core.models import Account, BotConversation, BotConversationEvent, BotIntegration, OTPChallenge, Outbox, Preview
from core.privacy import digest


class BotHelpers:
    def setUp(self):
        cache.clear()
        self.integration = BotIntegration(platform='telegram', bot_id='123456')
        self.key = new_credential(self.integration)
        self.integration.save()
        self.client = Client(enforce_csrf_checks=True)
        self.tokens = {}

    def get(self, path, client=None, key=None):
        return (client or self.client).get('/api/v2' + path, HTTP_X_BOT_KEY=key or self.key)

    def mutate(self, path, data=None, method='POST', client=None, key=None, csrf=True):
        client = client or self.client
        if id(client) not in self.tokens:
            self.tokens[id(client)] = self.get('/session', client, key).json()['csrf_token']
        headers = {'HTTP_X_BOT_KEY': key or self.key}
        if csrf:
            headers['HTTP_X_CSRFTOKEN'] = self.tokens[id(client)]
        response = client.generic(method, '/api/v2' + path, data=json.dumps(data if data is not None else {}),
            content_type='application/json', **headers)
        if response.status_code < 400:
            payload = response.json()
            if 'csrf_token' in payload:
                self.tokens[id(client)] = payload['csrf_token']
            elif 'session' in payload:
                self.tokens[id(client)] = payload['session']['csrf_token']
        return response

    def resume(self, user='777', chat='777', client=None, key=None):
        response = self.mutate('/bot/conversations/resolutions',
            {'user_id': user, 'chat_id': chat, 'chat_type': 'private'}, client=client, key=key)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def login(self, phone='09123456789', client=None, key=None):
        challenge = self.mutate('/auth/otp-challenges', {'phone': phone}, client=client, key=key)
        self.assertEqual(challenge.status_code, 201, challenge.content)
        response = self.mutate('/auth/sessions', {'challenge_id': challenge.json()['challenge_id'],
            'code': challenge.json()['debug_code']}, client=client, key=key)
        self.assertEqual(response.status_code, 201, response.content)
        return Account.objects.get(phone_hash=digest(phone))

    def checkpoint(self, conversation, *, revision=None, event=None, data=None, step='awaiting_recipient', client=None, key=None):
        return self.mutate('/bot/conversations/' + conversation['id'] + '/state', {
            'expected_revision': conversation['revision'] if revision is None else revision,
            'event_id': event or str(uuid.uuid4()), 'step': step, 'data': data or {}},
            method='PUT', client=client, key=key)


SETTINGS = dict(DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console', AI_MODE='template',
    PROVIDER_NETWORK_MODE='disabled', PAYMENT_BACKEND='demo', API_DOCUMENTATION_ENABLED=False)


@override_settings(**SETTINGS)
class BotConversationTests(BotHelpers, TestCase):
    def test_restart_discovery_is_bounded_scoped_and_contains_no_private_draft_or_session(self):
        first = self.resume()['conversation']
        self.checkpoint(first, data={'recipient_phone': '09901234567', 'text': 'متن خصوصی'}, step='awaiting_text')
        self.resume(user='888', chat='888', client=Client(enforce_csrf_checks=True))
        service = Client(enforce_csrf_checks=True)
        listed = self.get('/bot/conversations?limit=1', service).json()
        self.assertTrue(listed['has_more'])
        self.assertEqual(len(listed['results']), 1)
        following = self.get('/bot/conversations?limit=1&cursor=' + listed['next_cursor'], service).json()
        self.assertFalse(following['has_more'])
        self.assertNotEqual(listed['results'][0]['id'], following['results'][0]['id'])
        self.assertNotIn('09901234567', json.dumps(following))
        self.assertNotIn('data', following['results'][0])
        self.assertNotIn('session_key', following['results'][0])
        self.assertEqual(self.get('/bot/conversations?step=awaiting_text', service).json()['results'][0]['id'], first['id'])
        self.assertEqual(self.get('/bot/conversations?step=menu&cursor=' + listed['next_cursor'], service).status_code, 422)
        integration = BotIntegration(platform='bale', bot_id='123456')
        key = new_credential(integration)
        integration.save()
        self.assertEqual(self.get('/bot/conversations', service, key).json()['results'], [])
        self.assertEqual(self.get('/bot/conversations?cursor=' + listed['next_cursor'], service, key).status_code, 422)
        self.assertEqual(self.get('/bot/conversations?limit=51', service).status_code, 422)
        self.assertEqual(service.get('/api/v2/bot/conversations').status_code, 401)

    def test_restart_restores_same_session_account_and_private_draft(self):
        initial = self.resume()
        account = self.login()
        conversation = self.get('/bot/conversations/' + initial['conversation']['id']).json()
        self.assertEqual(conversation['account_id'], str(account.pk))
        draft = {'recipient_phone': '+۹۸۹۹۰۱۲۳۴۵۶۷', 'text': 'متن ۱۲۳', 'message_tone': 'polite'}
        saved = self.checkpoint(conversation, data=draft)
        self.assertEqual(saved.status_code, 200, saved.content)
        restarted = Client(enforce_csrf_checks=True)
        restored = self.resume(client=restarted)
        self.assertTrue(restored['session_restored'])
        self.assertTrue(restored['session']['authenticated'])
        self.assertEqual(restored['conversation']['id'], conversation['id'])
        self.assertEqual(restored['conversation']['data']['recipient_phone'], '09901234567')
        self.assertEqual(restored['conversation']['data']['text'], 'متن 123')
        self.assertEqual(self.get('/me', restarted).json()['id'], str(account.pk))
        # Fresh CSRF from resolution also works on normal product endpoints.
        self.assertEqual(self.mutate('/recipients/validations', {'phone': '09901234567'}, client=restarted).status_code, 200)

    def test_restart_during_otp_reuses_challenge_without_a_new_sms(self):
        conversation = self.resume()['conversation']
        challenge = self.mutate('/auth/otp-challenges', {'phone': '09123456789'}).json()
        self.assertEqual(self.checkpoint(conversation, step='awaiting_otp', data={'challenge_id': challenge['challenge_id']}).status_code, 200)
        restarted = Client(enforce_csrf_checks=True)
        resumed = self.resume(client=restarted)
        self.assertEqual(resumed['conversation']['step'], 'awaiting_otp')
        self.assertEqual(resumed['conversation']['resume_action'], 'enter_otp')
        response = self.mutate('/auth/sessions', {'challenge_id': challenge['challenge_id'],
            'code': challenge['debug_code']}, client=restarted)
        self.assertEqual(response.status_code, 201, response.content)
        state = self.get('/bot/conversations/' + conversation['id'], restarted).json()
        self.assertEqual(state['step'], 'menu')
        self.assertEqual(state['data'], {})

    def test_expired_challenge_requires_new_authentication(self):
        conversation = self.resume()['conversation']
        challenge = self.mutate('/auth/otp-challenges', {'phone': '09123456789'}).json()
        self.checkpoint(conversation, step='awaiting_otp', data={'challenge_id': challenge['challenge_id']})
        OTPChallenge.objects.filter(pk=challenge['challenge_id']).update(expires_at=timezone.now()-timedelta(seconds=1))
        restarted = self.resume(client=Client(enforce_csrf_checks=True))
        self.assertEqual(restarted['conversation']['resume_action'], 'authenticate')

    def test_preview_and_send_recovery_preserve_snapshot_key_and_single_credit_charge(self):
        initial = self.resume()['conversation']
        account = self.login()
        conversation = self.get('/bot/conversations/' + initial['id']).json()
        example = next(item for item in self.get('/catalog').json()['examples'] if item['topic'] == 'appreciation')
        preview = self.mutate('/message-previews', {'recipient_phone': '09901234567', 'source_mode': 'suggestion',
            'category': example['topic'], 'text': example['text']}).json()
        key = str(uuid.uuid4())
        data = {'recipient_phone': '09901234567', 'preview_id': preview['preview_id'], 'idempotency_key': key}
        self.assertEqual(self.checkpoint(conversation, data=data, step='submitting').status_code, 200)
        restarted = Client(enforce_csrf_checks=True)
        resumed = self.resume(client=restarted)
        self.assertEqual(resumed['conversation']['resume_action'], 'reconcile_message')
        self.assertEqual(self.get('/message-previews/' + preview['preview_id'], restarted).json()['full_sms'], preview['full_sms'])
        body = {'preview_id': preview['preview_id'], 'recipient_phone': '09901234567',
                'consent': True, 'terms_version': preview['terms_version']}
        response = restarted.post('/api/v2/messages', data=json.dumps(body), content_type='application/json',
            HTTP_X_BOT_KEY=self.key, HTTP_X_CSRFTOKEN=self.tokens[id(restarted)], HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, 200, response.content)
        message_id = response.json()['id']
        # Simulate a lost reservation response and another process restart.
        third = Client(enforce_csrf_checks=True)
        self.resume(client=third)
        retry = third.post('/api/v2/messages', data=json.dumps(body), content_type='application/json',
            HTTP_X_BOT_KEY=self.key, HTTP_X_CSRFTOKEN=self.tokens[id(third)], HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(retry.json()['id'], message_id)
        for _ in range(2):
            with self.captureOnCommitCallbacks(execute=True):
                submitted = self.mutate('/messages/' + message_id + '/submission', method='PUT', client=third)
            self.assertEqual(submitted.status_code, 200, submitted.content)
        account.refresh_from_db()
        self.assertEqual(account.free_sends_remaining, 2)
        self.assertEqual(Outbox.objects.count(), 1)
        state = self.get('/bot/conversations/' + conversation['id'], third).json()
        self.assertEqual(self.checkpoint(state, step='receipt', data={'message_id': message_id}, client=third).status_code, 200)

    def test_expired_preview_is_reported_as_refresh_without_a_new_ai_call(self):
        conversation = self.resume()['conversation']
        self.login()
        conversation = self.get('/bot/conversations/' + conversation['id']).json()
        example = next(item for item in self.get('/catalog').json()['examples'] if item['topic'] == 'appreciation')
        preview = self.mutate('/message-previews', {'recipient_phone': '09901234567', 'source_mode': 'suggestion',
            'category': example['topic'], 'text': example['text']}).json()
        response = self.checkpoint(conversation, data={'preview_id': preview['preview_id'], 'recipient_phone': '09901234567'},
            step='awaiting_confirmation')
        self.assertEqual(response.status_code, 200, response.content)
        Preview.objects.filter(pk=preview['preview_id']).update(expires_at=timezone.now()-timedelta(seconds=1))
        resumed = self.resume(client=Client(enforce_csrf_checks=True))
        self.assertEqual(resumed['conversation']['resume_action'], 'refresh_preview')

    def test_handled_provider_failure_preserves_otp_challenge_and_spend_reservation(self):
        from core.providers import ProviderDisabled
        self.resume()
        with override_settings(OTP_BACKEND='kavenegar', OTP_MAX_COST_RIAL=100), \
             patch('core.providers.Kavenegar.otp', side_effect=ProviderDisabled('test-disabled')), \
             patch('core.budget.reserve_cost') as reserve:
            # A DB write inside the spend service must survive the handled 503.
            from core.models import OperatorAudit
            reserve.side_effect = lambda *args: OperatorAudit.objects.create(action='test_cost_reserved', reason='isolated', before={}, after={})
            response = self.mutate('/auth/otp-challenges', {'phone': '09123456789'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(OTPChallenge.objects.count(), 1)
        self.assertEqual(OperatorAudit.objects.filter(action='test_cost_reserved').count(), 1)

    def test_platforms_and_bots_isolate_identities_but_share_verified_credit(self):
        telegram = self.resume()
        first = self.login()
        for platform, bot_id in [('bale', '123456'), ('telegram', '654321')]:
            integration = BotIntegration(platform=platform, bot_id=bot_id)
            key = new_credential(integration)
            integration.save()
            client = Client(enforce_csrf_checks=True)
            other = self.resume(client=client, key=key)
            self.assertNotEqual(other['conversation']['id'], telegram['conversation']['id'])
            self.assertFalse(other['session']['authenticated'])
            self.assertEqual(self.login(client=client, key=key).pk, first.pk)
            self.assertEqual(self.get('/me/credits', client, key).json()['gift_remaining'], 3)
        self.assertEqual(Account.objects.count(), 1)

    def test_chat_ids_do_not_authenticate_and_cookie_jar_cannot_switch_identity(self):
        conversation = self.resume()['conversation']
        self.assertIsNone(conversation['account_id'])
        self.assertEqual(self.get('/me').status_code, 401)
        bad = self.mutate('/bot/conversations/resolutions', {'user_id': '888', 'chat_id': '888', 'chat_type': 'private'})
        self.assertEqual(bad.status_code, 409)
        other = Client(enforce_csrf_checks=True)
        self.assertEqual(self.get('/bot/conversations/' + conversation['id'], other).status_code, 404)

    def test_private_identity_validation_and_no_arbitrary_account_binding(self):
        for data in [{'user_id': '777', 'chat_id': '-777', 'chat_type': 'group'},
                     {'user_id': '۷۷۷', 'chat_id': '777', 'chat_type': 'private'},
                     {'user_id': '777', 'chat_id': '777', 'chat_type': 'private', 'account_id': '1'},
                     {'user_id': 777, 'chat_id': '777', 'chat_type': 'private'}]:
            self.assertEqual(self.mutate('/bot/conversations/resolutions', data).status_code, 422)
        self.assertEqual(BotConversation.objects.count(), 0)

    def test_chat_collision_is_a_conflict_without_reassigning_owner(self):
        self.resume()
        other = Client(enforce_csrf_checks=True)
        response = self.mutate('/bot/conversations/resolutions',
            {'user_id': '888', 'chat_id': '777', 'chat_type': 'private'}, client=other)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(BotConversation.objects.count(), 1)

    def test_every_mutation_requires_csrf_including_resolution_and_checkpoint(self):
        data = {'user_id': '777', 'chat_id': '777', 'chat_type': 'private'}
        self.assertEqual(self.mutate('/bot/conversations/resolutions', data, csrf=False).status_code, 403)
        conversation = self.resume()['conversation']
        path = '/bot/conversations/' + conversation['id']
        for suffix, method in [('/state', 'PUT'), ('/state', 'DELETE'), ('/account', 'DELETE')]:
            self.assertEqual(self.mutate(path + suffix, {}, method, csrf=False).status_code, 403)

    def test_bad_key_revocation_and_bot_cookie_scope(self):
        self.assertEqual(self.mutate('/bot/conversations/resolutions',
            {'user_id': '777', 'chat_id': '777', 'chat_type': 'private'}, key='invalid').status_code, 401)
        self.resume()
        self.login()
        self.assertEqual(self.client.get('/api/v2/me').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/messages', HTTP_X_BOT_KEY=self.key).status_code, 403)
        self.assertEqual(self.client.get('/api/v2/document', HTTP_X_BOT_KEY=self.key).status_code, 403)
        self.integration.active = False
        self.integration.save()
        self.assertEqual(self.get('/me').status_code, 401)
        self.integration.active = True
        new = new_credential(self.integration)
        self.integration.save()
        self.assertEqual(self.get('/me').status_code, 401)
        self.assertEqual(self.get('/me', key=new).status_code, 200)

    def test_checkpoint_conflicts_and_duplicate_events_never_rewind_newer_stage(self):
        conversation = self.resume()['conversation']
        first = self.checkpoint(conversation, event='update-1')
        self.assertTrue(first.json()['applied'])
        self.assertEqual(self.checkpoint(conversation, event='other').status_code, 409)
        second = self.checkpoint(first.json()['conversation'], event='update-2', step='awaiting_text')
        repeated = self.checkpoint(conversation, event='update-1')
        self.assertFalse(repeated.json()['applied'])
        self.assertEqual(repeated.json()['conversation'], second.json()['conversation'])
        self.assertEqual(self.checkpoint(conversation, event='update-1', step='menu').status_code, 409)
        self.assertEqual(BotConversationEvent.objects.count(), 2)

    def test_checkpoint_has_closed_data_and_never_accepts_otp_cookies_or_raw_credentials(self):
        conversation = self.resume()['conversation']
        for data in [{'otp': '1234'}, {'code': '1234'}, {'cookies': 'secret'}, {'account_id': '1'}, {'token': 'secret'}, {'history': []}]:
            self.assertEqual(self.checkpoint(conversation, data=data).status_code, 422)
        self.assertEqual(BotConversationEvent.objects.count(), 0)

    def test_saved_resources_must_belong_to_current_account_and_session(self):
        conversation = self.resume()['conversation']
        self.assertEqual(self.checkpoint(conversation, data={'message_id': str(uuid.uuid4())}).status_code, 401)
        self.login()
        conversation = self.get('/bot/conversations/' + conversation['id']).json()
        for field in ['preview_id', 'message_id', 'challenge_id']:
            response = self.checkpoint(conversation, data={field: str(uuid.uuid4())})
            self.assertEqual(response.status_code, 409)

    def test_expired_authentication_requires_otp_and_removes_account_private_draft(self):
        conversation = self.resume()['conversation']
        self.login()
        conversation = self.get('/bot/conversations/' + conversation['id']).json()
        self.checkpoint(conversation, data={'text': 'متن خصوصی'})
        stored = BotConversation.objects.get(pk=conversation['id'])
        Session.objects.filter(session_key=stored.session_key).update(expire_date=timezone.now()-timedelta(seconds=1))
        resumed = self.resume(client=Client(enforce_csrf_checks=True))
        self.assertFalse(resumed['session']['authenticated'])
        self.assertIsNone(resumed['conversation']['account_id'])
        self.assertEqual(resumed['conversation']['data'], {})
        self.assertEqual(resumed['conversation']['step'], 'awaiting_phone')

    def test_logout_and_unlink_survive_restart_without_affecting_other_platform(self):
        conversation = self.resume()['conversation']
        self.login()
        self.assertEqual(self.mutate('/session', method='DELETE').status_code, 200)
        resumed = self.resume(client=Client(enforce_csrf_checks=True))
        self.assertFalse(resumed['session']['authenticated'])
        self.assertIsNone(resumed['conversation']['account_id'])
        self.login()
        unlinked = self.mutate('/bot/conversations/' + conversation['id'] + '/account', method='DELETE')
        self.assertFalse(unlinked.json()['session']['authenticated'])
        self.assertIsNone(unlinked.json()['conversation']['account_id'])
        self.assertEqual(self.get('/me').status_code, 401)

    def test_different_account_login_replaces_link_and_drops_old_draft(self):
        conversation = self.resume()['conversation']
        first = self.login()
        conversation = self.get('/bot/conversations/' + conversation['id']).json()
        self.checkpoint(conversation, data={'text': 'متن حساب قبلی'})
        second = self.login('09123456780')
        current = self.get('/bot/conversations/' + conversation['id']).json()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(current['account_id'], str(second.pk))
        self.assertEqual(current['data'], {})

    def test_state_expiry_reset_and_encryption_at_rest(self):
        conversation = self.resume()['conversation']
        saved = self.checkpoint(conversation, data={'recipient_phone': '09901234567', 'text': 'متن خصوصی'})
        self.assertEqual(saved.status_code, 200, saved.content)
        with connection.cursor() as cursor:
            cursor.execute('SELECT user_id, chat_id, session_key, data FROM core_botconversation')
            self.assertTrue(all(value.startswith('enc:v1:') for value in cursor.fetchone()))
        BotConversation.objects.filter(pk=conversation['id']).update(state_expires_at=timezone.now()-timedelta(seconds=1))
        expired = self.get('/bot/conversations/' + conversation['id']).json()
        self.assertEqual(expired['data'], {})
        self.assertGreater(expired['revision'], saved.json()['conversation']['revision'])
        reset = self.mutate('/bot/conversations/' + conversation['id'] + '/state',
            {'expected_revision': expired['revision'], 'event_id': 'reset-1'}, method='DELETE')
        self.assertTrue(reset.json()['applied'])

    def test_inactive_account_does_not_resume_authenticated_or_keep_old_draft(self):
        conversation = self.resume()['conversation']
        account = self.login()
        account.user.is_active = False
        account.user.save()
        resumed = self.resume(client=Client(enforce_csrf_checks=True))
        self.assertFalse(resumed['session']['authenticated'])
        self.assertIsNone(resumed['conversation']['account_id'])
        account.user.is_active = True
        account.user.save()
        self.assertFalse(self.resume(client=Client(enforce_csrf_checks=True))['session']['authenticated'])

    def test_password_revocation_still_leaves_a_resumable_anonymous_bot_identity(self):
        conversation = self.resume()['conversation']
        account = self.login()
        account.user.set_unusable_password()
        account.user.save()
        restarted = Client(enforce_csrf_checks=True)
        restored = self.resume(client=restarted)
        self.assertFalse(restored['session']['authenticated'])
        self.assertIsNone(restored['conversation']['account_id'])
        self.assertEqual(self.login(client=restarted).pk, account.pk)
        rebound = self.get('/bot/conversations/' + conversation['id'], restarted)
        self.assertEqual(rebound.json()['account_id'], str(account.pk))

    def test_key_limiter_fails_closed(self):
        # Bootstrap a CSRF cookie first so this exercises authentication.
        self.tokens[id(self.client)] = self.get('/session').json()['csrf_token']
        with patch('core.services.cache.add', side_effect=ConnectionError):
            response = self.mutate('/bot/conversations/resolutions', {'user_id': '777', 'chat_id': '777', 'chat_type': 'private'})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(BotConversation.objects.count(), 0)

    def test_provision_rotate_and_disable_never_store_or_reprint_plain_secret(self):
        output = io.StringIO()
        call_command('manage_bot_integration', platform='bale', bot_id='111', stdout=output)
        issued = json.loads(output.getvalue())
        stored = BotIntegration.objects.get(pk=issued['id'])
        self.assertNotIn(issued['api_key'].split('.')[1], stored.secret_digest)
        with self.assertRaises(CommandError):
            call_command('manage_bot_integration', platform='bale', bot_id='111', stdout=io.StringIO())
        rotated = io.StringIO()
        call_command('manage_bot_integration', platform='bale', bot_id='111', rotate=True, stdout=rotated)
        self.assertNotEqual(json.loads(rotated.getvalue())['api_key'], issued['api_key'])
        call_command('manage_bot_integration', platform='bale', bot_id='111', disable=True, stdout=io.StringIO())
        stored.refresh_from_db()
        self.assertFalse(stored.active)

    def test_retention_clears_drafts_events_and_inactive_identities_with_dry_run(self):
        conversation = self.resume()['conversation']
        self.checkpoint(conversation, data={'text': 'متن خصوصی'})
        BotConversation.objects.filter(pk=conversation['id']).update(last_seen_at=timezone.now()-timedelta(days=31))
        call_command('prune_private_data', dry_run=True, stdout=io.StringIO())
        self.assertEqual(BotConversation.objects.count(), 1)
        call_command('prune_private_data', stdout=io.StringIO())
        self.assertEqual(BotConversation.objects.count(), 0)
        self.assertEqual(BotConversationEvent.objects.count(), 0)

    def test_retention_expires_active_draft_and_deletes_identity_of_redacted_account(self):
        conversation = self.resume()['conversation']
        self.login()
        conversation = self.get('/bot/conversations/' + conversation['id']).json()
        self.checkpoint(conversation, data={'text': 'متن خصوصی'})
        BotConversation.objects.filter(pk=conversation['id']).update(state_expires_at=timezone.now()-timedelta(seconds=1))
        call_command('prune_private_data', stdout=io.StringIO())
        stored = BotConversation.objects.get(pk=conversation['id'])
        self.assertEqual(stored.data, '{}')
        self.assertEqual(stored.step, 'menu')
        Account.objects.filter(pk=stored.account_id).update(deletion_requested_at=timezone.now()-timedelta(days=31))
        call_command('prune_private_data', stdout=io.StringIO())
        self.assertFalse(BotConversation.objects.exists())
        self.assertFalse(Session.objects.filter(session_key=stored.session_key).exists())


@override_settings(**SETTINGS)
class BotConcurrencyTests(BotHelpers, TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_simultaneous_checkpoints_have_one_winner_and_one_revision_conflict(self):
        conversation = self.resume()['conversation']
        cookies = self.client.cookies.copy()
        token = self.tokens[id(self.client)]
        barrier = Barrier(2)

        def run(event):
            close_old_connections()
            client = Client(enforce_csrf_checks=True)
            client.cookies = cookies.copy()
            barrier.wait(timeout=10)
            try:
                return client.put('/api/v2/bot/conversations/' + conversation['id'] + '/state',
                    data=json.dumps({'expected_revision': conversation['revision'], 'event_id': event,
                        'step': 'awaiting_text', 'data': {}}), content_type='application/json',
                    HTTP_X_BOT_KEY=self.key, HTTP_X_CSRFTOKEN=token).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(run, ['first', 'second'])), [200, 409])
        self.assertEqual(BotConversationEvent.objects.count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_first_contact_race_creates_one_identity_and_one_resumable_session(self):
        clients = [Client(enforce_csrf_checks=True), Client(enforce_csrf_checks=True)]
        tokens = [self.get('/session', client).json()['csrf_token'] for client in clients]
        barrier = Barrier(2)

        def run(index):
            close_old_connections()
            barrier.wait(timeout=10)
            try:
                response = clients[index].post('/api/v2/bot/conversations/resolutions',
                    data=json.dumps({'user_id': '999', 'chat_id': '999', 'chat_type': 'private'}),
                    content_type='application/json', HTTP_X_BOT_KEY=self.key, HTTP_X_CSRFTOKEN=tokens[index])
                return response.status_code, response.json()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(run, [0, 1]))
        self.assertEqual([result[0] for result in results], [200, 200], results)
        self.assertEqual(results[0][1]['conversation']['id'], results[1][1]['conversation']['id'])
        self.assertEqual(BotConversation.objects.count(), 1)
        self.assertEqual(clients[0].cookies['sessionid'].value, clients[1].cookies['sessionid'].value)


def client_module():
    path = Path(__file__).parent / 'api_v2/integration/client.py'
    spec = importlib.util.spec_from_file_location('durable_bot_api_client', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProviderUpdateIdentityTests(SimpleTestCase):
    def test_both_platforms_extract_sender_and_chat_separately_for_messages_and_callbacks(self):
        parser = client_module().private_update_identity
        for platform in ['telegram', 'bale']:
            message = {'from': {'id': 777}, 'chat': {'id': 999, 'type': 'private'}, 'message_id': 123}
            expected = {'user_id': '777', 'chat_id': '999', 'update_id': '0', 'message_id': '123'}
            self.assertEqual(parser(platform, {'update_id': 0, 'message': message}), expected)
            self.assertEqual(parser(platform, {'update_id': 0, 'callback_query': {'from': {'id': 777},
                'message': {key: value for key, value in message.items() if key != 'from'}}}), expected)
            for update in [{'update_id': 0, 'message': {**message, 'chat': {'id': -123, 'type': 'group'}}},
                           {'update_id': True, 'message': message}, {'update_id': 0, 'edited_message': message},
                           {'update_id': 0, 'message': {**message, 'from': {'id': 777, 'is_bot': True}}}]:
                with self.assertRaises(ValueError):
                    parser(platform, update)


@override_settings(**SETTINGS)
class DurableBotClientTests(BotHelpers, LiveServerTestCase):
    def test_fresh_python_client_restores_both_platforms_using_real_http_without_saved_cookies(self):
        module = client_module()
        for platform in ['telegram', 'bale']:
            if platform == 'bale':
                integration = BotIntegration(platform=platform, bot_id='123456')
                key = new_credential(integration)
                integration.save()
            else:
                key = self.key
            first = module.BotAPI(self.live_server_url + '/api/v2', bot_key=key, require_real_otp=False)
            conversation = first.resume_conversation(777, 777)['conversation']
            first.save_state(revision=conversation['revision'], event_id='update-1', step='awaiting_phone', data={})
            challenge = first.request_otp('09123456789')
            first.verify_otp(challenge['challenge_id'], challenge['debug_code'])
            # An entirely new OS process has no access to the original jar or
            # Python objects. Its only durable inputs are the adapter credential
            # and the provider identity, passed privately through stdin.
            code = '''import importlib.util,json,sys
p=json.load(sys.stdin)
s=importlib.util.spec_from_file_location('api',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
c=m.BotAPI(p['url'],bot_key=p['key']);before=len(c.jar)
r=c.resume_conversation(777,777)
print(json.dumps({'empty_jar_before':before==0,'authenticated':r['session']['authenticated'],'account_id':c.getme()['id']}))
'''
            process = subprocess.run([sys.executable, '-c', code, str(Path(__file__).parent/'api_v2/integration/client.py')],
                input=json.dumps({'url': self.live_server_url + '/api/v2', 'key': key}),
                capture_output=True, text=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr)
            recovered = json.loads(process.stdout)
            self.assertTrue(recovered['empty_jar_before'])
            self.assertTrue(recovered['authenticated'])
            self.assertEqual(recovered['account_id'], first.getme()['id'])
            restarted = module.BotAPI(self.live_server_url + '/api/v2', bot_key=key)
            self.assertEqual(len(restarted.jar), 0)
            result = restarted.resume_conversation(777, 777)
            self.assertTrue(result['session']['authenticated'])
            self.assertEqual(first.getme()['id'], restarted.getme()['id'])
            self.assertEqual(restarted.credits()['gift_remaining'], 3)
            state = restarted.conversation()
            self.assertEqual(len(restarted.conversations()['results']), 1)
            restarted.reset_state(revision=state['revision'], event_id='reset-1')
            restarted.unlink_account()
            self.assertFalse(restarted.refresh_session()['authenticated'])
