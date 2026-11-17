import uuid
import threading
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from . import tests as legacy
from .models import Account, IdentityConsent, IdentityReceipt, OperatorAudit, Order, Outbox, Preview, RecipientGrant, SafetyControl
from .privacy import digest, encrypt
from .tasks import deliver_message


@override_settings(
    APP_BASE_URL='https://begamnagam.ir', AI_MODE='template',
    RECIPIENT_COOLDOWN_HOURS=0, SENDER_RECIPIENT_COOLDOWN_HOURS=0, SENDER_DAILY_LIMIT=20,
)
class IdentityConsentTests(TestCase):
    post, authenticate = legacy.APITestCase.post, legacy.APITestCase.authenticate
    sender_phone = '09123456789'
    recipient_phone = '09901234567'

    def setUp(self):
        self.receipt_ids = {}
        cache.clear()
        SafetyControl.objects.update_or_create(pk=1, defaults={'halted': False})
        self.client, self.recipient, self.third = Client(), Client(), Client()
        self.sender = self.authenticate(self.sender_phone, free_sends=None)
        self.viewer = self.authenticate(self.recipient_phone, self.recipient, free_sends=None)
        self.other = self.authenticate('09211234567', self.third, free_sends=None)
        self.order, self.token = self.send(self.client, self.recipient_phone)

    def send(self, client, phone, *, deliver=True):
        preview = self.post('/messages/preview', {
            'category': 'appreciation', 'text': 'ممنونم از کمکت', 'recipient_phone': phone,
        }, client)
        self.assertEqual(preview.status_code, 200, preview.content)
        quote = preview.json()
        order = self.post('/orders', {
            'preview_id': quote['preview_id'], 'recipient_phone': phone,
            'consent': True, 'terms_version': quote['terms_version'],
        }, client, HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(order.status_code, 200, order.content)
        order = Order.objects.get(pk=order.json()['id'])
        if deliver:
            with self.captureOnCommitCallbacks(execute=False):
                self.assertEqual(self.post(f'/orders/{order.pk}/confirm-free', client=client).status_code, 200)
            deliver_message(Outbox.objects.get(order=order).pk)
        return order, Preview.objects.get(pk=quote['preview_id']).full_sms.rsplit('/r/', 1)[1]

    def request_identity(self, client=None, token=None, **extra):
        return self.post('/recipient/actions/identity', {'token': token or self.token, **extra}, client or self.recipient)

    def action(self, row, action, client=None, **extra):
        return self.post(f"/identity-requests/{row['id']}", {
            'action': action, 'revision': row['revision'], **extra,
        }, client)

    def phone(self, row, client=None):
        receipt_id = self.receipt_ids.get(row['id'], row['id'])
        return (client or self.recipient).get(f"/api/v1/identity-requests/{receipt_id}/phone")

    def create_request(self):
        response = self.request_identity()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['status'], 'pending')
        receipt = IdentityReceipt.objects.get(pk=response.json()['id'])
        row = next(row for row in self.client.get('/api/v1/identity-requests').json()['results'] if row['id'] == str(receipt.consent.decision_id))
        self.receipt_ids[row['id']] = response.json()['id']
        return row

    def test_feature_is_closed_by_default_for_bootstrap_and_direct_requests(self):
        self.assertFalse(self.client.get('/api/v1/bootstrap').json().get('identity_requests_enabled', False))
        self.assertEqual(self.request_identity().status_code, 404)
        self.assertEqual(self.client.get('/api/v1/identity-requests').status_code, 404)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_request_requires_the_verified_recipient_and_delivered_message(self):
        self.assertTrue(self.recipient.get('/api/v1/bootstrap').json().get('identity_requests_enabled'))
        self.assertEqual(self.request_identity(Client()).status_code, 401)
        self.assertEqual(self.request_identity(self.third).status_code, 404)
        self.assertEqual(self.request_identity(self.client).status_code, 404)
        row = self.create_request()
        self.assertEqual(self.request_identity().json()['id'], self.receipt_ids[row['id']])
        self.assertEqual(self.request_identity(phone=self.sender_phone).status_code, 422)
        _, token = self.send(self.client, '09211234567', deliver=False)
        self.assertEqual(self.request_identity(self.third, token).status_code, 404)
        self.assertEqual(self.phone(row).status_code, 404)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_only_the_subject_can_approve_and_only_the_requester_can_read_phone(self):
        row = self.create_request()
        self.assertEqual(self.action(row, 'approve', self.third, consent=True).status_code, 404)
        self.assertEqual(self.action(row, 'approve', self.recipient, consent=True).status_code, 404)
        self.assertEqual(self.action(row, 'approve').status_code, 422)
        accepted = self.action(row, 'approve', consent=True)
        self.assertEqual(accepted.status_code, 200, accepted.content)
        self.assertEqual(accepted.json()['status'], 'approved')
        shown = self.phone(row)
        self.assertEqual(shown.json(), {'phone': self.sender_phone})
        self.assertEqual(shown['Cache-Control'], 'no-store')
        self.assertEqual(shown['Referrer-Policy'], 'no-referrer')
        self.assertEqual(self.phone(row, self.third).status_code, 404)
        self.assertEqual(self.phone(row, self.client).status_code, 404)
        for client, direction in [(self.client, 'incoming'), (self.recipient, 'outgoing')]:
            response = client.get('/api/v1/identity-requests', {'direction': direction})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(self.sender_phone, response.content.decode())
            self.assertNotIn(self.recipient_phone, response.content.decode())

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_approval_is_directional_and_never_grants_another_recipient(self):
        row = self.create_request()
        self.assertEqual(self.action(row, 'approve', consent=True).status_code, 200)
        _, other_token = self.send(self.client, '09211234567')
        other = self.request_identity(self.third, other_token).json()
        self.assertEqual(other['status'], 'pending')
        self.assertEqual(self.phone(other, self.third).status_code, 404)
        _, reverse_token = self.send(self.recipient, self.sender_phone)
        reverse = self.request_identity(self.client, reverse_token).json()
        self.assertEqual(reverse['status'], 'pending')
        self.assertEqual(self.phone(reverse, self.client).status_code, 404)
        self.assertEqual(self.phone(row).json(), {'phone': self.sender_phone})

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_revoke_blocks_future_reads_and_stale_approval_cannot_reopen_it(self):
        row = self.create_request()
        approved = self.action(row, 'approve', consent=True).json()
        self.assertEqual(self.phone(row).status_code, 200)
        revoked = self.action(approved, 'revoke')
        self.assertEqual(revoked.status_code, 200, revoked.content)
        self.assertEqual(revoked.json()['status'], 'revoked')
        self.assertEqual(self.client.get('/api/v1/identity-requests').json()['count'], 0)
        self.assertEqual(self.phone(row).status_code, 404)
        stale = self.action(row, 'approve', consent=True)
        self.assertEqual(stale.status_code, 409)
        pending_again = self.create_request()
        self.assertNotEqual(pending_again['id'], row['id'])
        self.assertEqual(pending_again['revision'], 0)
        self.assertEqual(self.phone(row).status_code, 404)
        self.assertEqual(self.action(approved, 'approve', consent=True).status_code, 404)
        self.assertEqual(self.action(pending_again, 'approve', consent=True).status_code, 200)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_disabling_feature_hides_existing_approvals_and_still_allows_revocation(self):
        row = self.create_request()
        approved = self.action(row, 'approve', consent=True).json()
        with override_settings(IDENTITY_REQUESTS_ENABLED=False):
            self.assertEqual(self.phone(row).status_code, 404)
            self.assertEqual(self.client.get('/api/v1/identity-requests').status_code, 404)
            self.assertEqual(self.action(approved, 'revoke').status_code, 200)
        self.assertEqual(self.phone(row).status_code, 404)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_only_explicit_csrf_protected_actions_change_consent(self):
        row = self.create_request()
        checked = Client(enforce_csrf_checks=True)
        checked.force_login(self.sender)
        self.assertEqual(self.action(row, 'approve', checked, consent=True).status_code, 403)
        self.assertEqual(checked.get(f"/api/v1/identity-requests/{row['id']}").status_code, 405)
        self.assertEqual(self.phone(row).status_code, 404)
        with patch('core.providers.kavenegar.Kavenegar.submit') as wire:
            self.assertEqual(self.action(row, 'approve', consent=True).status_code, 200)
        wire.assert_not_called()

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_deleted_or_suspended_subject_never_discloses_phone(self):
        row = self.create_request()
        self.assertEqual(self.action(row, 'approve', consent=True).status_code, 200)
        Account.objects.filter(user=self.sender).update(suspended=True)
        self.assertEqual(self.phone(row).status_code, 404)
        Account.objects.filter(user=self.sender).update(suspended=False)
        self.assertEqual(self.post('/account/deletion').status_code, 200)
        self.assertEqual(self.phone(row).status_code, 404)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_decline_does_not_disclose_and_repeated_pending_requests_are_idempotent(self):
        row = self.create_request()
        self.assertEqual(self.action(row, 'decline').json()['status'], 'declined')
        self.assertEqual(self.phone(row).status_code, 404)
        new_request = self.create_request()
        self.assertEqual(self.request_identity().json()['id'], self.receipt_ids[new_request['id']])
        self.assertEqual(self.action(row, 'approve', consent=True).status_code, 404)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_hidden_message_never_opens_a_new_request_or_exposes_its_context(self):
        row = self.create_request()
        self.assertEqual(self.client.delete(f'/api/v1/messages/{self.order.pk}').status_code, 200)
        self.assertEqual(self.request_identity().status_code, 404)
        for client, direction in [(self.client, 'incoming'), (self.recipient, 'outgoing')]:
            result = client.get('/api/v1/identity-requests', {'direction': direction}).json()['results'][0]
            self.assertEqual(result['id'], row['id'] if direction == 'incoming' else self.receipt_ids[row['id']])
            self.assertIsNone(result['message_created_at'])
            self.assertNotIn('text', result)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_visibility_and_link_expiry_are_rechecked_after_admission(self):
        from .identity_consent import lock_actor

        def hide_after_initial_read(*args):
            parties = lock_actor(*args)
            Order.objects.filter(pk=self.order.pk).update(owner_hidden_at=timezone.now())
            return parties

        with patch('core.identity_consent.lock_actor', side_effect=hide_after_initial_read):
            self.assertEqual(self.request_identity().status_code, 404)
        self.assertFalse(IdentityConsent.objects.exists())
        Order.objects.filter(pk=self.order.pk).update(owner_hidden_at=None)

        def expire_after_initial_read(*args):
            parties = lock_actor(*args)
            RecipientGrant.objects.filter(preview=self.order.preview).update(stop_expires_at=timezone.now()-timedelta(seconds=1))
            return parties

        with patch('core.identity_consent.lock_actor', side_effect=expire_after_initial_read):
            self.assertEqual(self.request_identity().status_code, 404)
        self.assertFalse(IdentityConsent.objects.exists())

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_expired_links_and_staff_without_verified_account_have_no_access(self):
        staff = get_user_model().objects.create_user(username='identity-staff', is_staff=True)
        staff_client = Client()
        staff_client.force_login(staff)
        self.assertEqual(self.request_identity(staff_client).status_code, 401)
        self.assertEqual(staff_client.get('/api/v1/identity-requests').status_code, 401)
        RecipientGrant.objects.filter(preview=self.order.preview).update(stop_expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.request_identity().status_code, 404)
        self.assertFalse(IdentityConsent.objects.exists())

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_attempts_are_limited_even_for_wrong_capabilities(self):
        for _ in range(30):
            self.assertEqual(self.request_identity(self.third).status_code, 404)
        self.assertEqual(self.request_identity(self.third).status_code, 429)
        self.assertFalse(IdentityConsent.objects.exists())

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_account_deletion_revokes_permanently_and_audits_contain_no_phones(self):
        row = self.create_request()
        self.assertEqual(self.action(row, 'approve', consent=True).status_code, 200)
        self.assertEqual(self.post('/account/deletion').status_code, 200)
        Account.objects.filter(user=self.sender).update(deletion_requested_at=None)
        self.assertEqual(self.phone(row).status_code, 404)
        self.assertEqual(IdentityConsent.objects.get(decision_id=row['id']).status, 'revoked')
        for event in OperatorAudit.objects.filter(action__startswith='identity_'):
            self.assertNotIn(self.sender_phone, str(event.after))
            self.assertNotIn(self.recipient_phone, str(event.after))

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_public_receipts_never_link_separate_anonymous_sources_or_reuse_revoked_handles(self):
        first = self.request_identity().json()
        _, second_token = self.send(self.client, self.recipient_phone)
        second = self.request_identity(token=second_token).json()
        self.assertNotEqual(first['id'], second['id'])
        self.assertIsNone(second['message_created_at'])
        self.assertNotEqual(first['requested_at'], second['requested_at'])
        self.assertEqual((first['revision'], second['revision']), (0, 0))
        pair = self.client.get('/api/v1/identity-requests').json()['results'][0]
        listing = self.recipient.get('/api/v1/identity-requests?direction=outgoing').json()
        self.assertEqual(listing['count'], 2)
        self.assertNotIn(pair['id'], str(listing))
        approved = self.action(pair, 'approve', consent=True).json()
        self.assertEqual(self.phone(first).status_code, 200)
        self.assertEqual(self.action(approved, 'revoke').status_code, 200)
        _, third_token = self.send(self.client, self.recipient_phone)
        fresh = self.request_identity(token=third_token).json()
        self.assertNotIn(fresh['id'], [first['id'], second['id']])
        self.assertIsNone(fresh['message_created_at'])
        self.assertEqual(self.phone(fresh).status_code, 404)
        pair = self.client.get('/api/v1/identity-requests').json()['results'][0]
        self.assertEqual(self.action(pair, 'approve', consent=True).status_code, 200)
        self.assertEqual(self.phone(fresh).status_code, 200)
        self.assertEqual(self.phone(first).status_code, 404)

    @override_settings(IDENTITY_REQUESTS_ENABLED=True)
    def test_unapproved_denials_remain_neutral_and_environment_cannot_bypass_permissions(self):
        row = self.create_request()
        public_id = self.receipt_ids[row['id']]
        self.assertEqual(self.action(row, 'decline').status_code, 200)
        outgoing = self.recipient.get('/api/v1/identity-requests?direction=outgoing').json()['results'][0]
        self.assertEqual(outgoing['id'], public_id)
        self.assertEqual(outgoing['status'], 'pending')
        row = self.create_request()
        self.assertEqual(self.receipt_ids[row['id']], public_id)
        approved = self.action(row, 'approve', consent=True).json()
        with override_settings(DEMO_MODE=False, PROVIDER_ENVIRONMENT='live'):
            self.assertEqual(self.phone(row).status_code, 404)
            self.assertEqual(self.recipient.get('/api/v1/identity-requests?direction=outgoing').json()['count'], 0)
            self.assertEqual(self.action(approved, 'revoke').status_code, 404)
        for malformed in [[], {}, 1, None]:
            self.assertEqual(self.action(approved, malformed).status_code, 422)


@override_settings(IDENTITY_REQUESTS_ENABLED=True)
class IdentityConsentConcurrencyTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_phone_read_waits_for_committing_revocation_and_returns_no_number(self):
        from .identity_consent import phone
        users = [get_user_model().objects.create_user(username=name) for name in ('identity-subject', 'identity-requester')]
        accounts = [Account.objects.create(user=user, phone_hash=digest(number), phone_cipher=encrypt(number))
                    for user, number in zip(users, ('09123456789', '09901234567'))]
        row = IdentityConsent.objects.create(subject=accounts[0], requester=accounts[1], environment='demo', status='approved')
        receipt = IdentityReceipt.objects.create(consent=row, generation=0, status='approved', approved_once=True)
        locked, read_started, release, done = [threading.Event() for _ in range(4)]
        results, errors = [], []

        def revoke():
            close_old_connections()
            try:
                with transaction.atomic():
                    record = IdentityConsent.objects.select_for_update().get(pk=row.pk)
                    record.status = 'revoked'
                    record.revision += 1
                    record.save()
                    locked.set()
                    if not release.wait(5):
                        raise AssertionError('Timed out waiting for the concurrent read')
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        def read():
            close_old_connections()
            try:
                request = RequestFactory().get('/api/v1/identity-requests/phone')
                request.user = get_user_model().objects.get(pk=users[1].pk)
                read_started.set()
                results.append(phone(request, receipt.pk))
            except Exception as exc:
                errors.append(exc)
            finally:
                done.set()
                close_old_connections()

        writer, reader = threading.Thread(target=revoke), threading.Thread(target=read)
        writer.start()
        try:
            self.assertTrue(locked.wait(5))
            reader.start()
            self.assertTrue(read_started.wait(5))
            self.assertFalse(done.wait(0.15), 'A phone read bypassed the in-flight revocation lock')
        finally:
            release.set()
            writer.join(5)
            if reader.ident is not None:
                reader.join(5)
        self.assertFalse(errors, errors)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status_code, 404)
        self.assertNotIn(b'09123456789', results[0].content)
