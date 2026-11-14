import json
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import models as m
from .privacy import digest, encrypt, mask


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UserActivityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = get_user_model().objects.create_user('activity-staff', is_staff=True)
        self.member = get_user_model().objects.create_user('activity-member')
        self.other = get_user_model().objects.create_user('activity-other')
        self.phone = '09123456789'
        self.account = m.Account.objects.create(user=self.member, phone_hash=digest(self.phone),
            phone_cipher=encrypt(self.phone), phone_masked=mask(self.phone))

    def permit(self, *names):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label='core', codename__in=names))
        self.client.force_login(self.staff)

    def post(self, path, data=None, client=None):
        return (client or self.client).post('/api/v1/manage/' + path, json.dumps(data or {}), content_type='application/json')

    def preview(self, owner=None):
        return m.Preview.objects.create(owner=owner or self.member, session_key='test-activity', category='appreciation',
            original_text='private source', text='private reviewed', generated_body='private reviewed', price_toman=2000,
            moderation_mode='template', expires_at=timezone.now()+timedelta(minutes=5))

    def order(self, owner=None, recipient_phone='09999999999', *, status=m.Order.Status.FAILED):
        owner = owner or self.member
        return m.Order.objects.create(owner=owner, preview=self.preview(owner), idempotency_key=uuid.uuid4(),
            recipient_hash=digest(recipient_phone), recipient_cipher=encrypt(recipient_phone), recipient_masked=mask(recipient_phone),
            text='private reviewed', category='appreciation', amount_toman=2000, status=status)

    def activity(self, section='messages', page=1):
        return self.post(f'users/{self.account.pk}/activity', {'section': section, 'page': page})

    def test_accounts_expose_full_phone_only_to_authorized_staff_and_audit_without_search(self):
        self.client.force_login(self.member)
        self.assertEqual(self.post('records/accounts').status_code, 403)
        self.permit('view_order')
        self.assertEqual(self.post('records/accounts').status_code, 403)
        self.permit('view_account')
        response = self.post('records/accounts', {'query': '۴۵۶۷'})
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['title'], 'کاربران')
        self.assertEqual(result['rows'][0]['phone'], self.phone)
        self.assertEqual(result['rows'][0]['phone_masked'], mask(self.phone))
        self.assertNotIn('phone_cipher', response.content.decode())
        self.assertNotIn(digest(self.phone), response.content.decode())
        audit = m.OperatorAudit.objects.get(action='account_phones_viewed')
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertNotIn('4567', json.dumps([audit.reason, audit.before, audit.after]))
        self.assertNotIn(self.phone, json.dumps([audit.reason, audit.before, audit.after]))

    def test_partial_phone_results_are_paginated_and_canonical(self):
        self.permit('view_account')
        for i in range(26):
            phone = f'0955500{i:04d}'
            user = get_user_model().objects.create_user(f'partial-{i}')
            m.Account.objects.create(user=user, phone_hash=digest(phone), phone_cipher=encrypt(phone), phone_masked=mask(phone))
        first = self.post('records/accounts', {'query': '۵۵۵'}).json()
        second = self.post('records/accounts', {'query': '٥٥٥', 'page': 2}).json()
        self.assertEqual((first['total'], second['total']), (26, 26))
        self.assertEqual((len(first['rows']), len(second['rows'])), (25, 1))
        self.assertFalse({row['id'] for row in first['rows']} & {row['id'] for row in second['rows']})
        self.assertEqual(self.client.get('/api/v1/manage/records/accounts?query=555').status_code, 405)

    def test_activity_requires_account_and_section_permission_and_csrf(self):
        self.permit('view_account')
        self.assertEqual(self.activity().status_code, 403)
        self.assertEqual(self.activity('invitations').status_code, 403)
        self.permit('view_order')
        self.assertEqual(self.activity().status_code, 200)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(self.post(f'users/{self.account.pk}/activity', {'section': 'messages'}, client).status_code, 403)
        for data in ({'section': 'unknown'}, {'section': []}, {'section': 'messages', 'page': True}, {'section': 'messages', 'page': 0}):
            self.assertEqual(self.post(f'users/{self.account.pk}/activity', data).status_code, 422)
        self.assertEqual(self.post('users/99999999/activity', {'section': 'messages'}).status_code, 404)

    def test_message_activity_scopes_orders_and_historic_rejections_and_excludes_raw_text(self):
        self.permit('view_account', 'view_order')
        order = self.order()
        foreign = self.order(self.other, recipient_phone='09999999997')
        rejected = m.ModerationAudit.objects.create(owner=self.member, category='appreciation', outcome='rejected',
            reason_code='unsafe', content_digest='private-digest')
        m.ModerationAudit.objects.create(owner=self.other, category='appreciation', outcome='rejected', reason_code='unsafe', content_digest='other')
        response = self.activity()
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['account']['phone'], self.phone)
        self.assertEqual(result['total'], 2)
        self.assertEqual({row['kind'] for row in result['rows']}, {'order', 'moderation'})
        self.assertEqual({row['id'] for row in result['rows']}, {str(order.pk), str(rejected.event_id)})
        self.assertEqual({row['kind']: row['recipient_phone'] for row in result['rows']},
            {'order': '09999999999', 'moderation': ''})
        self.assertEqual(response['Cache-Control'], 'no-store')
        audit = m.OperatorAudit.objects.get(action='user_activity_viewed')
        self.assertEqual(audit.after, {'section': 'messages'})
        self.assertNotIn('09999999999', json.dumps([audit.reason, audit.before, audit.after]))
        for secret in ('private source', 'private reviewed', 'private-digest', str(foreign.pk), '09999999997',
                       order.recipient_cipher, order.recipient_hash, order.recipient_masked):
            self.assertNotIn(secret, response.content.decode())

    def test_message_activity_leaves_a_cleared_order_recipient_unavailable(self):
        self.permit('view_account', 'view_order')
        order = self.order()
        m.Order.objects.filter(pk=order.pk).update(recipient_cipher='')

        response = self.activity()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rows'][0]['recipient_phone'], '')
        self.assertNotIn(order.recipient_masked, response.content.decode())

    @override_settings(DEMO_MODE=False)
    def test_received_messages_match_the_users_phone_and_confirmed_sends(self):
        self.permit('view_account', 'view_order')
        sender_phone = '09351234567'
        sender = m.Account.objects.create(user=self.other, phone_hash=digest(sender_phone),
            phone_cipher=encrypt(sender_phone), phone_masked=mask(sender_phone))
        sent = self.order()
        self_send = self.order(recipient_phone=self.phone, status=m.Order.Status.DELIVERED)
        delivered = self.order(self.other, self.phone, status=m.Order.Status.DELIVERED)
        accepted = self.order(self.other, self.phone, status=m.Order.Status.ACCEPTED)
        for state in (m.Order.Status.AWAITING_PAYMENT, m.Order.Status.QUEUED, m.Order.Status.UNKNOWN,
                      m.Order.Status.FAILED, m.Order.Status.CANCELLED, m.Order.Status.DELIVERED_DEMO):
            self.order(self.other, self.phone, status=state)
        self.order(self.other, '09999999997', status=m.Order.Status.DELIVERED)
        m.MessageAttempt.objects.create(owner=self.other, recipient_phone=self.phone, status='accepted',
            reason_code='preview_accepted', original_text='private input for target')

        response = self.activity()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        payload = response.json()
        self.assertEqual(payload['total'], 4)
        orders = {row['id']: row for row in payload['rows']}
        self.assertEqual({identifier: row['direction'] for identifier, row in orders.items()}, {
            str(sent.pk): 'sent', str(self_send.pk): 'sent',
            str(delivered.pk): 'received', str(accepted.pk): 'received',
        })
        self.assertEqual(orders[str(delivered.pk)]['recipient_phone'], self.phone)
        self.assertEqual(orders[str(delivered.pk)]['sender_phone'], sender_phone)
        self.assertEqual(orders[str(accepted.pk)]['sender_phone'], sender_phone)
        self.assertNotIn('sender_phone', orders[str(sent.pk)])
        self.assertEqual(orders[str(delivered.pk)]['order_id'], str(delivered.pk))
        self.assertEqual(orders[str(delivered.pk)]['created_at'], DjangoJSONEncoder().default(delivered.created_at))
        for private in (self.other.username, 'private source', 'private reviewed',
                        'private input for target', delivered.recipient_cipher, delivered.recipient_hash,
                        sender.phone_cipher, sender.phone_hash, sender.phone_masked):
            self.assertNotIn(private, response.content.decode())
        audit = m.OperatorAudit.objects.get(action='user_activity_viewed')
        self.assertEqual(audit.after, {'section': 'messages'})
        self.assertNotIn(self.phone, json.dumps([audit.reason, audit.before, audit.after]))
        self.assertNotIn(sender_phone, json.dumps([audit.reason, audit.before, audit.after]))

        path = f'orders/{delivered.pk}/texts'
        self.assertEqual(self.post(path).status_code, 403)
        self.permit('view_private_message_text')
        self.assertEqual(self.post(path).json()['final_text'], 'private reviewed')
        audit = m.OperatorAudit.objects.get(action='message_text_viewed')
        self.assertEqual(audit.object_id, str(delivered.pk))
        self.assertNotIn('private reviewed', json.dumps([audit.reason, audit.before, audit.after]))

    def test_received_rows_keep_missing_or_redacted_sender_numbers_unavailable(self):
        self.permit('view_account', 'view_order')
        self.order(self.other, self.phone, status=m.Order.Status.DELIVERED)
        row, = self.activity().json()['rows']
        self.assertEqual(row['sender_phone'], '')

        phone = '09351234567'
        m.Account.objects.create(user=self.other, phone_hash=digest(phone), phone_cipher='', phone_masked='حذف‌شده')
        row, = self.activity().json()['rows']
        self.assertEqual(row['sender_phone'], '')

    def test_received_messages_are_ordered_by_provider_receipt_time(self):
        self.permit('view_account', 'view_order')
        confirmed = self.order(self.other, self.phone, status=m.Order.Status.DELIVERED)
        accepted = self.order(self.other, self.phone, status=m.Order.Status.ACCEPTED)
        sent = self.order()
        now = timezone.now().replace(microsecond=0) + timedelta(hours=1)
        m.MessageDelivery.objects.create(order=confirmed, status=m.MessageDelivery.Status.DELIVERED,
            accepted_at=now - timedelta(minutes=2), resolved_at=now, provider='kavenegar', environment='live')
        m.MessageDelivery.objects.create(order=accepted, status=m.MessageDelivery.Status.ACCEPTED,
            accepted_at=now - timedelta(minutes=1), provider='kavenegar', environment='live')

        rows = self.activity().json()['rows']

        self.assertEqual([row['id'] for row in rows], [str(confirmed.pk), str(accepted.pk), str(sent.pk)])
        self.assertEqual(rows[0]['created_at'], now.isoformat().replace('+00:00', 'Z'))

    @override_settings(DEMO_MODE=True)
    def test_demo_receipt_remains_labelled_as_simulated(self):
        self.permit('view_account', 'view_order')
        order = self.order(self.other, self.phone, status=m.Order.Status.DELIVERED_DEMO)

        row, = self.activity().json()['rows']

        self.assertEqual(row['id'], str(order.pk))
        self.assertEqual(row['direction'], 'received')
        self.assertEqual(row['status'], 'delivered_demo')

    def test_redacted_accounts_or_cleared_recipient_hashes_do_not_match(self):
        self.permit('view_account', 'view_order')
        order = self.order(self.other, self.phone, status=m.Order.Status.DELIVERED)
        m.Account.objects.filter(pk=self.account.pk).update(phone_cipher='')
        self.assertEqual(self.activity().json()['rows'], [])

        m.Account.objects.filter(pk=self.account.pk).update(phone_hash='', phone_cipher=self.account.phone_cipher)
        m.Order.objects.filter(pk=order.pk).update(recipient_hash='', recipient_cipher='')

        self.assertEqual(self.activity().json()['rows'], [])

    def test_invitations_include_only_selected_user_and_recent_send_state(self):
        self.permit('view_account', 'view_invitation')
        invitation = m.Invitation.objects.create(inviter=self.member, phone_hash=digest('09999999998'),
            phone_cipher=encrypt('09999999998'), phone_masked=mask('09999999998'))
        m.Invitation.objects.create(inviter=self.other, phone_hash=digest('09999999997'),
            phone_cipher=encrypt('09999999997'), phone_masked=mask('09999999997'))
        m.InvitationSend.objects.create(invitation=invitation, ordinal=1, idempotency_key=uuid.uuid4(), consent_version='test',
            consent_at=timezone.now(), full_sms='private invitation', provider='demo', available_at=timezone.now(), status='failed', last_error_code='unavailable')
        result = self.activity('invitations').json()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rows'][0]['id'], str(invitation.pk))
        self.assertEqual(result['rows'][0]['phone'], '09999999998')
        self.assertEqual(result['rows'][0]['status'], 'failed')
        self.assertEqual(result['rows'][0]['reason_code'], 'unavailable')

    def test_missing_reason_is_generated_but_explicit_malformed_reason_stays_invalid(self):
        self.permit('suspend_account')
        response = self.post('actions', {'action': 'suspend', 'object_id': str(self.account.pk)})
        self.assertEqual(response.status_code, 200)
        audit = m.OperatorAudit.objects.get(action='suspend')
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertGreaterEqual(len(audit.reason), 3)
        for reason in ('', None, [], 'x', 'x'*201):
            self.assertGreaterEqual(self.post('actions', {'action': 'unsuspend', 'object_id': str(self.account.pk), 'reason': reason}).status_code, 400)

    def test_other_audited_management_settings_accept_omitted_reason(self):
        self.permit('manage_ai', 'manage_message_packages', 'manage_message_examples', 'manage_manual_payments')
        settings = [
            ('ai', {'timeout_seconds': 4}),
            ('packages', {'name': 'بستهٔ آزمون', 'message_count': 3, 'price_toman': 10000, 'active': True, 'sort_order': 0}),
            ('message-examples/groups', {'name': 'دستهٔ آزمون', 'active': True, 'sort_order': 0}),
            ('manual-payment-settings', {'enabled': False, 'bank_name': 'بانک آزمون', 'card_number': '', 'card_holder': '',
                'bale_username': '', 'telegram_username': ''}),
        ]
        for path, values in settings:
            with self.subTest(path=path):
                response = self.post(path, {'revision': 0, 'values': values})
                self.assertEqual(response.status_code, 200, response.content)
        audits = m.OperatorAudit.objects.filter(actor=self.staff)
        self.assertEqual(audits.count(), 4)
        self.assertTrue(all(len(audit.reason) >= 3 for audit in audits))

    def test_account_header_is_available_without_order_permission(self):
        path = f'/api/v1/manage/users/{self.account.pk}'
        self.assertEqual(self.client.get(path).status_code, 401)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.permit('view_account')
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['account'], {'id': self.account.pk, 'phone': self.phone,
            'phone_masked': mask(self.phone), 'suspended': False})
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(m.OperatorAudit.objects.get(action='user_activity_viewed').object_id, str(self.account.pk))

    def test_attempt_activity_deduplicates_converted_previews_and_moderation_events(self):
        self.permit('view_account', 'view_order')
        order = self.order()
        event = m.ModerationAudit.objects.create(owner=self.member, category='appreciation', outcome='rejected',
            reason_code='unsafe', content_digest='private-digest')
        rejected = m.MessageAttempt.objects.create(owner=self.member, original_text='private rejected source',
            recipient_phone='09999999998', status='rejected', reason_code='unsafe', message_tone='firm', moderation_event_id=event.event_id)
        m.MessageAttempt.objects.create(owner=self.member, preview=order.preview, original_text='private accepted source',
            status='accepted', reason_code='preview_accepted', message_tone='polite')
        failed = m.MessageAttempt.objects.create(owner=self.member, original_text='private failed source',
            status='failed', reason_code='ai_unavailable', message_tone='blunt')
        pending = m.MessageAttempt.objects.create(owner=self.member, preview=self.preview(), original_text='private pending source',
            status='accepted', reason_code='preview_accepted', message_tone='firm')
        foreign = m.MessageAttempt.objects.create(owner=self.other, original_text='private foreign source',
            recipient_phone='09999999997', status='failed', reason_code='ai_unavailable')
        response = self.activity()
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['total'], 4)
        self.assertEqual({row['id'] for row in result['rows']}, {str(row.pk) for row in (order, rejected, failed, pending)})
        self.assertEqual(next(row for row in result['rows'] if row['id'] == str(rejected.pk))['reason_code'], 'unsafe')
        self.assertEqual(next(row for row in result['rows'] if row['id'] == str(order.pk))['order_id'], str(order.pk))
        self.assertEqual({row['id']: row['recipient_phone'] for row in result['rows']},
            {str(order.pk): '09999999999', str(rejected.pk): '09999999998', str(failed.pk): '', str(pending.pk): ''})
        for secret in ('private rejected source', 'private accepted source', 'private failed source', 'private pending source',
                       'private foreign source', str(foreign.pk), '09999999997', 'private-digest', 'enc:v1:'):
            self.assertNotIn(secret, response.content.decode())

    def test_message_pagination_covers_multiple_kinds_without_gaps(self):
        self.permit('view_account', 'view_order')
        order = self.order()
        received = self.order(self.other, self.phone, status=m.Order.Status.DELIVERED)
        m.MessageAttempt.objects.bulk_create([m.MessageAttempt(owner=self.member, status='failed', reason_code='ai_unavailable',
            original_text='private attempt') for _ in range(15)])
        m.ModerationAudit.objects.bulk_create([m.ModerationAudit(owner=self.member, outcome='rejected', reason_code='unsafe',
            content_digest='private-digest') for _ in range(15)])
        first, second = self.activity().json(), self.activity(page=2).json()
        self.assertEqual(first['total'], 32)
        self.assertEqual((len(first['rows']), len(second['rows'])), (25, 7))
        ids = [row['record_id'] for row in first['rows'] + second['rows']]
        self.assertEqual(len(set(ids)), 32)
        self.assertIn(str(order.pk), ids)
        self.assertIn(str(received.pk), ids)
        self.assertTrue(first['pagination']['has_next'])
        self.assertFalse(second['pagination']['has_next'])
        self.assertEqual(self.activity(page=3).json()['rows'], [])

    def test_attempt_texts_are_owner_scoped_permissioned_and_audited_without_content(self):
        attempt = m.MessageAttempt.objects.create(owner=self.member, original_text='private rejected source',
            status='rejected', reason_code='unsafe')
        path = f'users/{self.account.pk}/attempts/{attempt.pk}/texts'
        self.permit('view_account', 'view_order')
        self.assertEqual(self.post(path).status_code, 403)
        self.permit('view_private_message_text')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(self.post(path, client=client).status_code, 403)
        response = self.post(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['original_text'], 'private rejected source')
        self.assertTrue(response.json()['original_available'])
        self.assertIsNone(response.json()['reviewed_text'])
        audit = m.OperatorAudit.objects.get(action='message_attempt_text_viewed')
        self.assertEqual(audit.actor_id, self.staff.pk)
        self.assertEqual(audit.object_id, str(attempt.pk))
        self.assertNotIn('private rejected source', json.dumps([audit.reason, audit.before, audit.after]))
        foreign = m.MessageAttempt.objects.create(owner=self.other, original_text='private foreign source', status='failed', reason_code='ai_unavailable')
        self.assertEqual(self.post(f'users/{self.account.pk}/attempts/{foreign.pk}/texts').status_code, 404)
        self.assertEqual(self.post(path, {'reason': ''}).status_code, 422)
        self.assertEqual(m.OperatorAudit.objects.filter(action='message_attempt_text_viewed').count(), 1)
        m.MessageAttempt.objects.filter(pk=attempt.pk).update(original_text='')
        self.assertFalse(self.post(path).json()['original_available'])
