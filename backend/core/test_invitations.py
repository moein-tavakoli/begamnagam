import io
import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from . import tests as legacy
from .invitations import CONSENT_VERSION, request_invitation, reward_registration, record_registration, lock_phone
from .invitation_delivery import submit, reconcile
from .models import Account, Invitation, InvitationSend, RecipientGrant, RecipientState, SafetyControl, SpendBudget, OperatorAudit
from .privacy import digest, encrypt, mask, decrypt
from .providers import ProviderUnknown
from .providers.kavenegar import SMSResult
from .services import APIError


class InvitationTests(TestCase):
    post, authenticate = legacy.APITestCase.post, legacy.APITestCase.authenticate

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.user = self.authenticate(free_sends=None)
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})

    def invite(self, phone='09901234567', key=None, client=None):
        with self.captureOnCommitCallbacks(execute=False):
            return self.post('/invitations', {'phone': phone, 'consent': True, 'consent_version': CONSENT_VERSION},
                client, HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))

    def resend(self, invitation, key=None, client=None):
        with self.captureOnCommitCallbacks(execute=False):
            return self.post(f'/invitations/{invitation.pk}/resend', {'consent': True, 'consent_version': CONSENT_VERSION},
                client, HTTP_IDEMPOTENCY_KEY=key or str(uuid.uuid4()))

    def age_sends(self):
        InvitationSend.objects.update(created_at=timezone.now()-timedelta(hours=25))
        RecipientState.objects.update(last_sent_at=timezone.now()-timedelta(hours=25))

    def test_add_is_encrypted_masked_consented_idempotent_and_no_gift_consumed(self):
        key = str(uuid.uuid4())
        response = self.invite('۰۹۹۰۱۲۳۴۵۶۷', key)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self.invite('+989901234567', key).json()['id'], response.json()['id'])
        self.assertEqual(InvitationSend.objects.count(), 1)
        invitation, send = Invitation.objects.get(), InvitationSend.objects.get()
        self.assertEqual(decrypt(invitation.phone_cipher), '09901234567')
        self.assertNotIn('09901234567', response.content.decode())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
        with connection.cursor() as cursor:
            cursor.execute('SELECT full_sms FROM core_invitationsend')
            self.assertTrue(cursor.fetchone()[0].startswith('enc:v1:'))
        self.assertTrue(send.full_sms.startswith('نمیدونم بهت بگم یا نگم؟\n'))
        self.assertLessEqual(len(send.full_sms.encode('utf-16-le'))//2, 201)
        self.assertNotIn('#', send.full_sms)
        self.assertEqual(RecipientGrant.objects.get().invitation_send_id, send.pk)

    def test_no_self_existing_member_or_second_inviter_and_notice_is_explicit(self):
        self.assertEqual(self.invite('09123456789').json()['error']['code'], 'self_invitation')
        other = Client()
        self.authenticate('09901234566', other)
        response = self.invite('09901234566')
        self.assertEqual(response.json()['error']['code'], 'already_registered')
        self.assertIn('قبلاً عضو', response.json()['error']['message'])
        self.assertEqual(self.invite().status_code, 200)
        response = self.invite(client=other)
        self.assertEqual(response.json()['error']['code'], 'already_invited')
        self.assertNotIn(str(self.user.pk), response.json()['error']['message'])
        self.assertEqual(self.invite().json()['error']['code'], 'already_added')
        self.assertEqual(Invitation.objects.count(), 1)

    def test_auth_csrf_consent_ownership_and_no_cross_account_history(self):
        self.assertEqual(Client().get('/api/v1/invitations').status_code, 401)
        self.assertEqual(self.post('/invitations', {'phone': '09901234567'}).status_code, 422)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(self.invite(client=csrf).status_code, 403)
        self.invite()
        other = Client()
        self.authenticate('09901234566', other)
        self.assertEqual(self.resend(Invitation.objects.get(), client=other).status_code, 404)
        self.assertEqual(other.get('/api/v1/invitations').json()['results'], [])
        self.assertEqual(self.client.get('/api/v1/invitations').headers['Cache-Control'], 'no-store')

    def test_three_requests_24_hours_and_no_repeat_while_uncertain(self):
        self.invite()
        invitation = Invitation.objects.get()
        self.assertEqual(self.resend(invitation).json()['error']['code'], 'invitation_pending')
        for ordinal in range(1, 4):
            send = InvitationSend.objects.order_by('ordinal').last()
            submit(send.pk)
            self.assertEqual(InvitationSend.objects.get(pk=send.pk).status, 'delivered_demo')
            if ordinal < 3:
                self.assertEqual(self.resend(invitation).json()['error']['code'], 'invitation_cooldown')
                self.age_sends()
                self.assertEqual(self.resend(invitation).status_code, 200)
        self.assertEqual(self.resend(invitation).json()['error']['code'], 'invitation_limit')
        self.assertEqual(invitation.sends.count(), 3)
        with self.assertRaises(IntegrityError), transaction.atomic():
            InvitationSend.objects.filter(pk=send.pk).update(ordinal=0)

    def test_daily_limit_counts_resends_and_errors_do_not_claim_numbers(self):
        for n in range(5):
            self.assertEqual(self.invite(f'0990123456{n}').status_code, 200)
        self.assertEqual(self.invite('09901234569').status_code, 429)
        self.assertEqual(Invitation.objects.count(), 5)

    def test_verified_first_signup_rewards_inviter_exactly_once_without_codes(self):
        self.invite()
        invitation = Invitation.objects.get()
        other = Client()
        with self.captureOnCommitCallbacks(execute=True):
            self.authenticate('09901234567', other, free_sends=None)
        for _ in range(2): reward_registration(invitation.pk)
        inviter = Account.objects.get(user=self.user)
        invitee = Account.objects.get(phone_hash=invitation.phone_hash)
        self.assertEqual((inviter.free_sends_remaining, inviter.free_sends_earned_total), (6, 3))
        self.assertEqual(invitee.free_sends_remaining, 3)
        self.authenticate('09901234567', other, free_sends=None)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 6)
        self.assertEqual(OperatorAudit.objects.filter(action='invitation_reward').count(), 1)
        result = self.client.get('/api/v1/invitations').json()
        self.assertEqual((result['registered'], result['earned_credits']), (1, 3))
        self.assertEqual(result['results'][0]['reward_credits'], 3)
        self.assertFalse(result['results'][0]['can_resend'])
        self.assertEqual(InvitationSend.objects.get().status, 'cancelled')
        self.assertEqual(self.client.get('/api/v1/bootstrap').json()['free_sends_total'], 6)

    def test_requesting_otp_is_not_registration_and_lost_reward_callback_is_repaired(self):
        self.invite()
        other = Client()
        other.get('/api/v1/bootstrap')
        challenge = self.post('/auth/request-otp', {'phone':'09901234567'}, other).json()
        self.assertIsNone(Invitation.objects.get().registered_at)
        with self.captureOnCommitCallbacks(execute=False):
            self.post('/auth/verify-otp', {'challenge_id':challenge['challenge_id'], 'code':challenge['debug_code']}, other)
        self.assertIsNone(Invitation.objects.get().reward_awarded_at)
        from .tasks import reconcile_outbox
        with patch('core.invitations.publish'):
            reconcile_outbox(); reconcile_outbox()
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 6)

    def test_optout_halt_and_registration_before_dispatch_prevent_submission(self):
        self.invite()
        send = InvitationSend.objects.get()
        RecipientState.objects.filter(phone_hash=Invitation.objects.get().phone_hash).update(blocked=True)
        with patch('core.invitation_delivery.Kavenegar.submit') as wire:
            submit(send.pk)
        wire.assert_not_called()
        self.assertEqual(InvitationSend.objects.get().last_error_code, 'recipient_unavailable')
        self.assertNotIn('لغو', self.client.get('/api/v1/invitations').json()['results'][0]['reason'])

    def test_link_works_with_explicit_stop_and_report_without_sender_identity(self):
        self.invite()
        submit(InvitationSend.objects.get().pk)
        send = InvitationSend.objects.get()
        token = send.full_sms.rsplit('/r/', 1)[-1]
        self.assertTrue(token.isalnum() and token.isascii() and len(token)==8)
        result = self.post('/recipient/actions/inspect', {'token':token})
        self.assertEqual(result.json(), {'active':True, 'can_report':True})
        self.assertEqual(self.post('/recipient/actions/stop', {'token':token}).status_code, 200)
        self.assertTrue(RecipientState.objects.get(phone_hash=Invitation.objects.get().phone_hash).blocked)
        self.age_sends()
        self.assertEqual(self.resend(Invitation.objects.get()).status_code, 409)

    def test_expiry_retention_and_key_rotation_preserve_unique_claim(self):
        self.invite()
        submit(InvitationSend.objects.get().pk)
        Invitation.objects.update(created_at=timezone.now()-timedelta(days=91))
        call_command('rotate_encryption', apply=True, stdout=io.StringIO())
        call_command('prune_private_data', stdout=io.StringIO())
        invitation = Invitation.objects.get()
        self.assertEqual(invitation.phone_cipher, '')
        self.assertEqual(invitation.phone_hash, digest('09901234567'))
        self.assertEqual(InvitationSend.objects.get().full_sms, '')
        self.assertEqual(self.resend(invitation).json()['error']['code'], 'invitation_expired')

    def test_bad_snapshot_rejected_and_queue_expires_without_network(self):
        self.invite()
        InvitationSend.objects.update(full_sms='unreviewed input')
        with patch('core.invitation_delivery.Kavenegar.submit') as wire:
            submit(InvitationSend.objects.get().pk)
        wire.assert_not_called()
        self.assertEqual(InvitationSend.objects.get().status, 'failed')
        InvitationSend.objects.update(status='pending', created_at=timezone.now()-timedelta(hours=49))
        submit(InvitationSend.objects.get().pk)
        self.assertEqual(InvitationSend.objects.get().last_error_code, 'queue_expired')

    def test_feedback_cannot_overtake_pending_invitation(self):
        self.invite()
        preview = legacy.APITestCase.preview(self)
        response = legacy.APITestCase.order(self, preview=preview)
        self.assertEqual(response.json()['error']['code'], 'recipient_unavailable')

    def test_recently_checked_deliveries_cannot_starve_unchecked_invites(self):
        self.invite()
        send = InvitationSend.objects.get()
        invitation = Invitation.objects.get()
        InvitationSend.objects.filter(pk=send.pk).update(provider='kavenegar', status='accepted', checked_at=timezone.now())
        due = InvitationSend.objects.create(invitation=invitation, ordinal=2, idempotency_key=uuid.uuid4(),
            consent_at=timezone.now(), consent_version=CONSENT_VERSION, full_sms='fixed snapshot', provider='kavenegar',
            status='unknown', available_at=timezone.now())
        from .tasks import reconcile_providers
        with patch('core.provider_services.reconcile_payments'), patch('core.invitation_delivery.reconcile') as check:
            reconcile_providers()
        check.assert_called_once_with(due.pk)


class InvitationLiveTests(InvitationTests):
    # Keep base scenarios in demo; only these wire-contract scenarios enable live.
    def live(self):
        return override_settings(DEMO_MODE=False, SMS_BACKEND='kavenegar', PROVIDER_NETWORK_MODE='external',
            SMS_RECIPIENT_POLICY='all', PROVIDER_DAILY_BUDGET_RIAL=100000, SMS_MAX_COST_RIAL=20000, SENDING_WINDOW_ENABLED=False)

    def test_real_adapter_uses_reviewed_snapshot_once_and_shared_budget(self):
        with self.live():
            self.invite()
            send = InvitationSend.objects.get()
            with patch('core.invitation_delivery.Kavenegar.submit', return_value=SMSResult('accepted', '101', 1200)) as wire:
                submit(send.pk); submit(send.pk)
            wire.assert_called_once_with(phone='09901234567', text=send.full_sms, local_id=send.local_id)
            self.assertEqual(SpendBudget.objects.get().reserved_rial, 20000)
            self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
            self.assertEqual(InvitationSend.objects.get().status, 'accepted')
            with patch('core.invitation_delivery.Kavenegar.status', return_value=SMSResult('delivered', '101', 1200)):
                InvitationSend.objects.update(checked_at=None)
                reconcile(send.pk)
            self.assertEqual(InvitationSend.objects.get().status, 'delivered')

    def test_unknown_is_queried_never_resent_or_reopened_by_timeout(self):
        with self.live():
            self.invite()
            send = InvitationSend.objects.get()
            with patch('core.invitation_delivery.Kavenegar.submit', side_effect=ProviderUnknown('timeout')) as wire:
                submit(send.pk); submit(send.pk)
            wire.assert_called_once()
            self.age_sends()
            self.assertEqual(self.resend(Invitation.objects.get()).json()['error']['code'], 'invitation_pending')
            with patch('core.invitation_delivery.Kavenegar.status', side_effect=ProviderUnknown('missing')):
                reconcile(send.pk)
            self.assertEqual(InvitationSend.objects.get().status, 'unknown')

    def test_budget_defers_without_wire_or_disclosing_credit_and_halt_defers(self):
        with self.live(), override_settings(PROVIDER_DAILY_BUDGET_RIAL=10000):
            self.invite()
            with patch('core.invitation_delivery.Kavenegar.submit') as wire:
                submit(InvitationSend.objects.get().pk)
            wire.assert_not_called()
            send = InvitationSend.objects.get()
            self.assertEqual(send.status, 'pending')
            self.assertGreater(send.available_at, timezone.now())
            self.assertIsNone(self.client.get('/api/v1/invitations').json()['results'][0]['reason'])
        SafetyControl.objects.update(halted=True)
        InvitationSend.objects.update(available_at=timezone.now())
        submit(send.pk)
        self.assertEqual(InvitationSend.objects.get().status, 'pending')


class InvitationConcurrencyTests(TransactionTestCase):
    setUp = legacy.PostgreSQLConcurrencyTests.setUp
    parallel = legacy.PostgreSQLConcurrencyTests.parallel

    def test_two_inviters_cannot_claim_one_phone(self):
        other = get_user_model().objects.create_user(username='second-inviter')
        Account.objects.create(user=other, phone_hash=digest('09901234566'), phone_cipher=encrypt('09901234566'), phone_masked=mask('09901234566'))
        users = iter([self.user.pk, other.pk])
        def claim(_):
            try:
                return str(request_invitation(get_user_model().objects.get(pk=next(users)), '09901234567', uuid.uuid4()).pk)
            except APIError as error:
                return error.code
        with patch('core.invitations.publish'):
            results = self.parallel(claim)
        self.assertIn('already_invited', results)
        self.assertEqual(Invitation.objects.count(), 1)
        self.assertEqual(InvitationSend.objects.count(), 1)

    def test_parallel_retries_and_rewards_are_once(self):
        key = uuid.uuid4()
        with patch('core.invitations.publish'):
            self.parallel(lambda user: request_invitation(user, '09901234567', key).pk)
        invitation = Invitation.objects.get()
        self.assertEqual(InvitationSend.objects.count(), 1)
        Invitation.objects.filter(pk=invitation.pk).update(registered_at=timezone.now())
        self.parallel(lambda _: reward_registration(invitation.pk))
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 6)
        self.assertEqual(OperatorAudit.objects.filter(action='invitation_reward').count(), 1)

    def test_registration_and_claim_serialize_on_verified_phone(self):
        actions = iter(['register', 'invite'])
        def race(user):
            action = next(actions)
            if action == 'invite':
                try: return str(request_invitation(user, '09901234567', uuid.uuid4()).pk)
                except APIError as e: return e.code
            with transaction.atomic():
                lock_phone(digest('09901234567'))
                new_user = get_user_model().objects.create_user(username='verified-new')
                account = Account.objects.create(user=new_user, phone_hash=digest('09901234567'), phone_cipher=encrypt('09901234567'), phone_masked=mask('09901234567'))
                record_registration(account)
            return 'registered'
        with patch('core.invitations.publish'):
            results = self.parallel(race)
        self.assertIn('registered', results)
        if Invitation.objects.exists():
            self.assertIsNotNone(Invitation.objects.get().registered_at)
            self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 6)
        else:
            self.assertIn('already_registered', results)
            self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining, 3)
