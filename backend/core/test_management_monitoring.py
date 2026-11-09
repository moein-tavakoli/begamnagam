"""Monitoring aggregates use real rows without revealing or modifying them."""
import re
import uuid
from datetime import datetime, timedelta, timezone as datetime_timezone
from zoneinfo import ZoneInfo
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext

from . import models as m
from .privacy import digest, encrypt, mask
from .safety import snapshot


NOW = datetime(2026, 11, 8, 9, 17, tzinfo=datetime_timezone.utc)  # Tehran 12:47
START = datetime(2026, 11, 7, 9, 30, tzinfo=datetime_timezone.utc)  # Tehran 13:00


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ManagementMonitoringTests(TestCase):
    path = '/api/v1/manage/monitoring'

    def setUp(self):
        self.staff = get_user_model().objects.create_user('monitor-staff', is_staff=True)
        self.staff.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='view_operations'))
        self.member = get_user_model().objects.create_user('monitor-member')
        self.client.force_login(self.staff)

    def account(self, at):
        user = get_user_model().objects.create_user('account-' + uuid.uuid4().hex)
        phone = '09123456789'
        value = m.Account.objects.create(user=user, phone_hash=digest(uuid.uuid4().hex),
            phone_cipher=encrypt(phone), phone_masked=mask(phone))
        m.Account.objects.filter(pk=value.pk).update(created_at=at)
        return value

    def order(self, at):
        preview = m.Preview.objects.create(owner=self.member, session_key='private-session', category='appreciation',
            text='private-preview-text', generated_body='private-reviewed-text', price_toman=2000,
            moderation_mode='template', expires_at=NOW + timedelta(minutes=5))
        value = m.Order.objects.create(owner=self.member, preview=preview, idempotency_key=uuid.uuid4(),
            recipient_hash=digest('09999999999'), recipient_cipher=encrypt('09999999999'),
            recipient_masked=mask('09999999999'), text='private-order-text', full_sms='private-order-sms',
            category='appreciation', amount_toman=2000)
        m.Order.objects.filter(pk=value.pk).update(created_at=at)
        return value

    def get_data(self):
        with patch('django.utils.timezone.now', return_value=NOW):
            response = self.client.get(self.path)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_requires_active_staff_with_operations_permission(self):
        limited = get_user_model().objects.create_user('monitor-limited', is_staff=True)
        inactive = get_user_model().objects.create_user('monitor-inactive', is_staff=True, is_active=False)
        inactive.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='view_operations'))
        for user, expected in ((None, 401), (self.member, 403), (limited, 403), (inactive, 401), (self.staff, 200)):
            with self.subTest(user=user):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                self.assertEqual(self.client.get(self.path).status_code, expected)
        self.assertEqual(self.client.post(self.path, {}, content_type='application/json').status_code, 405)

    def test_empty_window_has_24_zero_filled_tehran_hours_and_private_cache_headers(self):
        data = self.get_data()
        self.assertEqual(set(data), {'generated_at', 'window', 'totals', 'hourly', 'delivery', 'moderation',
                                     'queue', 'operations', 'alerts', 'environment'})
        self.assertEqual(data['window'], {'start': '2026-11-07T13:00:00+03:30',
            'end': '2026-11-08T12:47:00+03:30', 'timezone': 'Asia/Tehran'})
        self.assertEqual(data['totals'], {'accounts_new': 0, 'accounts_today': 0, 'accounts_total': 0, 'requests': 0, 'delivered': 0, 'support_unanswered': 0, 'blacklist_total': 0})
        self.assertEqual(len(data['hourly']), 24)
        self.assertEqual(data['hourly'][0], {'at': '2026-11-07T13:00:00+03:30', 'accounts': 0, 'requests': 0})
        self.assertEqual(data['hourly'][-1], {'at': '2026-11-08T12:00:00+03:30', 'accounts': 0, 'requests': 0})
        self.assertTrue(all(row['accounts'] == row['requests'] == 0 for row in data['hourly']))
        self.assertEqual(data['delivery'], [])
        self.assertEqual(data['moderation'], [])
        self.assertEqual(data['queue'], [])
        response = self.client.get(self.path)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertIn('cookie', response['Vary'].lower())

    def test_account_and_order_creation_window_includes_lower_boundary_excludes_now(self):
        for at in (START - timedelta(microseconds=1), START, START + timedelta(minutes=45),
                   NOW - timedelta(microseconds=1), NOW, NOW + timedelta(seconds=1)):
            self.account(at)
            self.order(at)
        data = self.get_data()
        self.assertEqual(data['totals']['accounts_new'], 3)
        self.assertEqual(data['totals']['requests'], 3)
        self.assertEqual(data['hourly'][0]['accounts'], 2)
        self.assertEqual(data['hourly'][0]['requests'], 2)
        self.assertEqual(data['hourly'][-1]['accounts'], 1)
        self.assertEqual(sum(row['accounts'] for row in data['hourly']), 3)
        self.assertEqual(sum(row['requests'] for row in data['hourly']), 3)

    def test_today_accounts_use_tehran_midnight_and_total_includes_all_accounts(self):
        midnight = NOW.astimezone(ZoneInfo('Asia/Tehran')).replace(hour=0, minute=0, second=0, microsecond=0)
        for at in (midnight - timedelta(microseconds=1), midnight,
                   NOW - timedelta(microseconds=1), NOW + timedelta(seconds=1)):
            self.account(at)
        data = self.get_data()
        self.assertEqual(data['totals'].get('accounts_today'), 2)
        self.assertEqual(data['totals'].get('accounts_total'), 4)
        self.assertEqual(data['totals']['accounts_new'], 3)

    def test_today_accounts_reset_at_tehran_midnight_without_losing_total(self):
        midnight = NOW.astimezone(ZoneInfo('Asia/Tehran')).replace(hour=0, minute=0, second=0, microsecond=0)
        self.account(midnight - timedelta(microseconds=1))
        with patch('django.utils.timezone.now', return_value=midnight):
            data = self.client.get(self.path).json()
        self.assertEqual(data['totals'].get('accounts_today'), 0)
        self.assertEqual(data['totals'].get('accounts_total'), 1)

    def test_blacklist_counts_only_active_opt_outs_including_without_accounts(self):
        for number, blocked in [('09901234567', True), ('09901234568', True), ('09901234569', False)]:
            m.RecipientState.objects.create(phone_hash=digest(number), blocked=blocked)
        totals = self.get_data()['totals']
        self.assertEqual(totals.get('blacklist_total'), 2)

    def test_delivery_partition_uses_delivery_creation_cohort_not_order_or_resolution(self):
        for created, status in ((START - timedelta(microseconds=1), 'delivered'), (START, 'delivered'),
                                (NOW - timedelta(seconds=1), 'delivered_demo'),
                                (NOW - timedelta(seconds=1), 'failed'), (NOW, 'delivered')):
            delivery = m.MessageDelivery.objects.create(order=self.order(START - timedelta(days=2)),
                status=status, resolved_at=NOW - timedelta(minutes=1), provider_reference='private-provider-' + uuid.uuid4().hex)
            m.MessageDelivery.objects.filter(pk=delivery.pk).update(created_at=created)
        data = self.get_data()
        self.assertEqual(data['totals']['requests'], 0)
        self.assertEqual(data['totals']['delivered'], 1)
        self.assertEqual(data['delivery'], [{'status': 'delivered', 'count': 1},
            {'status': 'delivered_demo', 'count': 1}, {'status': 'failed', 'count': 1}])
        self.assertEqual(sum(row['count'] for row in data['delivery']), 3)

    def test_moderation_partition_is_creation_bounded(self):
        for at, status in ((START - timedelta(microseconds=1), 'reject'), (START, 'allow'),
                           (NOW - timedelta(microseconds=1), 'reject'), (NOW, 'allow')):
            audit = m.ModerationAudit.objects.create(owner=self.member, outcome=status,
                reason_code='private-moderation-reason', content_digest='private-content-digest')
            m.ModerationAudit.objects.filter(pk=audit.pk).update(created_at=at)
        self.assertEqual(self.get_data()['moderation'], [{'status': 'allow', 'count': 1}, {'status': 'reject', 'count': 1}])

    def test_queue_is_current_across_old_message_and_invitation_rows(self):
        invitation = m.Invitation.objects.create(inviter=self.member, phone_hash=digest('09120000000'),
            phone_cipher=encrypt('09120000000'), phone_masked=mask('09120000000'))
        for ordinal, status in enumerate(('pending', 'submitting', 'unknown', 'done', 'failed'), 1):
            outbox = m.Outbox.objects.create(order=self.order(START - timedelta(days=1)), state=status, available_at=NOW)
            send = m.InvitationSend.objects.create(invitation=invitation, ordinal=ordinal, idempotency_key=uuid.uuid4(),
                consent_version='v1', consent_at=NOW, full_sms='private-invitation-sms', provider='demo', status=status, available_at=NOW)
            for obj in (outbox, send):
                type(obj).objects.filter(pk=obj.pk).update(created_at=NOW - timedelta(hours=30))
        data = self.get_data()
        self.assertEqual(data['queue'], [
            {'kind': 'messages', 'status': 'pending', 'count': 1},
            {'kind': 'messages', 'status': 'submitting', 'count': 1},
            {'kind': 'messages', 'status': 'unknown', 'count': 1},
            {'kind': 'invitations', 'status': 'pending', 'count': 1},
            {'kind': 'invitations', 'status': 'submitting', 'count': 1},
            {'kind': 'invitations', 'status': 'unknown', 'count': 1}])
        self.assertEqual(data['operations']['oldest_queue_seconds'], 108000)
        self.assertEqual(data['operations']['outbox_pending'], 2)

    def test_support_counts_unanswered_conversations_and_alerts_are_active_bounded_ordered(self):
        for answered, last in ((0, 2), (2, 2), (0, 0)):
            m.SupportConversation.objects.create(account=self.account(START), last_sequence=last,
                last_customer_sequence=last, answered_customer_sequence=answered)
        for code, severity, active, minutes in (('warning-old', 'warning', True, 10),
                ('critical-old', 'critical', True, 9), ('high-old', 'high', True, 8),
                ('high-new', 'high', True, 1), ('warning-new', 'warning', True, 2),
                ('warning-extra', 'warning', True, 20), ('critical-inactive', 'critical', False, 0)):
            alert = m.OperationalAlert.objects.create(code=code, severity=severity, active=active, count=3)
            m.OperationalAlert.objects.filter(pk=alert.pk).update(updated_at=NOW - timedelta(minutes=minutes))
        data = self.get_data()
        self.assertEqual(data['totals']['support_unanswered'], 1)
        self.assertEqual(data['alerts'], [{'code': code, 'severity': severity, 'count': 3} for code, severity in (
            ('critical-old', 'critical'), ('high-new', 'high'), ('high-old', 'high'),
            ('warning-new', 'warning'), ('warning-old', 'warning'))])

    def test_read_is_private_and_has_no_database_writes_even_without_safety_control(self):
        order = self.order(START)
        account = self.account(START)
        m.MessageDelivery.objects.create(order=order, provider_reference='private-provider-reference')
        self.assertFalse(m.SafetyControl.objects.exists())
        with CaptureQueriesContext(connection) as queries:
            data = self.get_data()
        self.assertFalse(m.SafetyControl.objects.exists())
        writes = [query['sql'] for query in queries if re.match(r'\s*(INSERT|UPDATE|DELETE)', query['sql'], re.I)]
        self.assertEqual(writes, [])
        self.assertLess(len(queries), 35)
        encoded = str(data)
        for private in ('09123456789', '09999999999', 'private-', str(order.pk), str(order.preview_id),
                        account.phone_hash, account.phone_cipher, 'phone', 'text', 'username', 'provider_reference'):
            self.assertNotIn(private, encoded)
        self.assertEqual(set(data['environment']), {'demo', 'sms', 'otp', 'payment', 'paid_enabled'})
        m.SafetyControl.objects.create(pk=1, halted=True)
        with patch('django.utils.timezone.now', return_value=NOW):
            expected = snapshot()
        self.assertEqual(self.get_data()['operations'], expected)
