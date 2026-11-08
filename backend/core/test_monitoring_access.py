"""The IP exception must never become a management login or trust client headers."""
import json
import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError, close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from . import models as m


IP = '203.0.113.42'


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MonitoringAccessTests(TestCase):
    settings_path = '/api/v1/manage/monitoring/settings'
    access_path = '/api/v1/manage/monitoring/access'
    data_path = '/api/v1/manage/monitoring'

    def setUp(self):
        self.owner = get_user_model().objects.create_superuser('monitor-access-owner')
        self.client.force_login(self.owner)

    def save(self, ips, revision=0, client=None):
        return (client or self.client).put(self.settings_path, json.dumps({'ips': ips, 'revision': revision}),
            content_type='application/json')

    def grant(self, ips=None):
        response = self.save(ips if ips is not None else [IP])
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_default_is_empty_and_owner_can_store_exact_ip(self):
        response = self.client.get(self.settings_path, REMOTE_ADDR='198.51.100.4')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ips': [], 'revision': 0, 'current_ip': '198.51.100.4'})
        response = self.client.put(self.settings_path, json.dumps({'ips': ['203.0.113.42'], 'revision': 0}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['ips'], ['203.0.113.42'])
        self.client.logout()
        response = self.client.get(self.data_path, REMOTE_ADDR='203.0.113.42')
        self.assertEqual(response.status_code, 200)

    def test_empty_settings_reads_do_not_create_a_row_and_anonymous_needs_login(self):
        self.assertFalse(m.MonitoringAccessSettings.objects.exists())
        self.client.get(self.settings_path)
        client = Client()
        self.assertEqual(client.get(self.access_path, REMOTE_ADDR=IP).json(), {'allowed': False})
        response = client.get(self.data_path, REMOTE_ADDR=IP)
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'management_login_required')
        self.assertFalse(m.MonitoringAccessSettings.objects.exists())

    def test_only_owner_can_read_and_update_even_with_settings_or_all_app_permissions(self):
        self.grant()
        employee = get_user_model().objects.create_user('all-permissions', is_staff=True)
        employee.user_permissions.set(Permission.objects.filter(content_type__app_label='core'))
        member = get_user_model().objects.create_user('product-user')
        inactive = get_user_model().objects.create_superuser('inactive-owner', is_active=False)
        for user, code in ((None, 401), (member, 403), (employee, 403), (inactive, 401)):
            client = Client()
            if user:
                client.force_login(user)
            for method in ('get', 'put'):
                response = getattr(client, method)(self.settings_path, '{}', content_type='application/json', REMOTE_ADDR=IP) if method == 'put' else client.get(self.settings_path, REMOTE_ADDR=IP)
                self.assertEqual(response.status_code, code, (user, method))
            if user and user != inactive:
                self.assertNotIn('manage_monitoring_access', client.get('/api/v1/manage/session').json().get('permissions', []))
        self.assertIn('manage_monitoring_access', self.client.get('/api/v1/manage/session').json()['permissions'])
        self.assertEqual(m.MonitoringAccessSettings.objects.get().ips, [IP])

    def test_normalizes_new_digits_ipv6_and_mapped_ipv4_without_enabling_a_network(self):
        data = self.grant([' ۲۰۳.۰.۱۱۳.۴۲ ', '2001:0DB8:0:0::42', '192.168.1.179'])
        self.assertCountEqual(data['ips'], ['192.168.1.179', IP, '2001:db8::42'])
        client = Client()
        for address, allowed in ((IP, True), ('::ffff:203.0.113.42', True), ('2001:db8::42', True),
                                 ('192.168.1.179', True), ('203.0.113.41', False), ('2001:db8::43', False)):
            self.assertEqual(client.get(self.access_path, REMOTE_ADDR=address).json(), {'allowed': allowed})

    def test_noop_conflict_and_revocation_are_audited_without_logging_the_ips(self):
        data = self.grant()
        self.assertEqual(data['revision'], 1)
        self.assertEqual(self.save([IP], 1).json()['revision'], 1)
        self.assertEqual(self.save([], 0).status_code, 409)
        self.assertEqual(m.OperatorAudit.objects.filter(action='update_monitoring_access').count(), 1)
        client = Client()
        self.assertEqual(client.get(self.data_path, REMOTE_ADDR=IP).status_code, 200)
        self.assertEqual(self.save([], 1).json()['revision'], 2)
        self.assertEqual(client.get(self.access_path, REMOTE_ADDR=IP).json(), {'allowed': False})
        self.assertEqual(client.get(self.data_path, REMOTE_ADDR=IP).status_code, 401)
        audits = m.OperatorAudit.objects.filter(action='update_monitoring_access').order_by('created_at')
        self.assertEqual(audits.count(), 2)
        self.assertEqual(audits[0].actor, self.owner)
        self.assertEqual(audits[0].before['count'], 0)
        self.assertEqual(audits[0].after['count'], 1)
        self.assertNotEqual(audits[0].before['fingerprint'], audits[0].after['fingerprint'])
        self.assertNotIn(IP, str(list(audits.values('before', 'after', 'reason'))))

    def test_ip_access_is_read_only_and_never_creates_a_staff_or_product_session(self):
        self.grant()
        client = Client()
        with CaptureQueriesContext(connection) as queries:
            response = client.get(self.data_path, REMOTE_ADDR=IP)
            access = client.get(self.access_path, REMOTE_ADDR=IP)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(access.json(), {'allowed': True})
        self.assertEqual([q['sql'] for q in queries if re.match(r'\s*(INSERT|UPDATE|DELETE)', q['sql'], re.I)], [])
        self.assertNotIn(settings.SESSION_COOKIE_NAME, client.cookies)
        self.assertNotIn('permissions', response.json())
        for result in (response, access):
            self.assertIn('no-store', result['Cache-Control'])
            self.assertIn('cookie', result['Vary'].lower())
            for private in (IP, 'current_ip', 'username', 'phone', 'text', 'fingerprint'):
                self.assertNotIn(private, result.content.decode())
        self.assertEqual(client.post(self.data_path, '{}', content_type='application/json', REMOTE_ADDR=IP).status_code, 405)

    def test_ip_exception_does_not_unlock_any_other_management_or_swagger_endpoint(self):
        self.grant()
        client = Client(REMOTE_ADDR=IP)
        for path in ('dashboard', 'limits', 'staff/catalog', 'support/summary', 'monitoring/settings', 'changelog'):
            self.assertEqual(client.get('/api/v1/manage/' + path).status_code, 401, path)
        for path in ('records/accounts', 'records/audit', 'actions'):
            self.assertEqual(client.post('/api/v1/manage/' + path, '{}', content_type='application/json').status_code, 401, path)
        for path in ('/api/v2/document', '/api/v2/schema'):
            self.assertNotEqual(client.get(path).status_code, 200, path)
        self.assertFalse(client.get('/api/v1/bootstrap').json()['authenticated'])

    def test_authenticated_staff_fallback_still_requires_active_operations_permission(self):
        employee = get_user_model().objects.create_user('monitoring-operator', is_staff=True)
        client = Client()
        client.force_login(employee)
        self.assertEqual(client.get(self.data_path, REMOTE_ADDR='198.51.100.4').status_code, 403)
        employee.user_permissions.add(Permission.objects.get(codename='view_operations', content_type__app_label='core'))
        self.assertEqual(client.get(self.access_path, REMOTE_ADDR='198.51.100.4').json(), {'allowed': True})
        self.assertEqual(client.get(self.data_path, REMOTE_ADDR='198.51.100.4').status_code, 200)
        employee.user_permissions.clear()
        self.assertEqual(client.get(self.data_path, REMOTE_ADDR='198.51.100.4').status_code, 403)

    def test_spoofed_headers_cannot_grant_access(self):
        self.grant()
        client = Client()
        for headers in (
            {'HTTP_X_FORWARDED_FOR': IP}, {'HTTP_X_REAL_IP': IP}, {'HTTP_FORWARDED': 'for=' + IP},
            {'HTTP_X_VERIFIED_CLIENT_IP': IP}, {'HTTP_X_FORWARDED_FOR': f'{IP}, 127.0.0.1'},
            {'HTTP_X_FORWARDED_FOR': IP, 'HTTP_X_REAL_IP': IP, 'HTTP_X_VERIFIED_CLIENT_IP': IP},
        ):
            self.assertEqual(client.get(self.data_path, REMOTE_ADDR='198.51.100.4', **headers).status_code, 401)

    @override_settings(TRUSTED_CLIENT_PROXY_IPS={'127.0.0.1', '::1', '192.168.1.6'})
    def test_only_verified_proxy_chain_can_supply_client_ip_and_uses_nearest_untrusted_hop(self):
        with override_settings(MIDDLEWARE=['core.middleware.TrustedProxyClientIP', *settings.MIDDLEWARE]):
            self.grant([IP, '2001:db8::42'])
            client = Client()
            for peer, chain, code in (
                ('127.0.0.1', IP, 200), ('127.0.0.1', f'{IP}, 192.168.1.6', 200),
                ('::1', '2001:db8::42', 200), ('127.0.0.1', f'1.2.3.4, {IP}, 192.168.1.6', 200),
                ('127.0.0.1', f'{IP}, 198.51.100.4, 192.168.1.6', 401),
                ('198.51.100.4', IP, 401), ('127.0.0.1', 'invalid', 401),
                ('127.0.0.1', '', 401), ('127.0.0.1', '::1, 192.168.1.6', 401),
                ('127.0.0.1', IP * 200, 401), ('127.0.0.1', IP + ', invalid', 401),
            ):
                with self.subTest(peer=peer, chain=chain):
                    self.assertEqual(client.get(self.data_path, REMOTE_ADDR=peer, HTTP_X_FORWARDED_FOR=chain).status_code, code)
            current = self.client.get(self.settings_path, REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR=f'{IP}, 192.168.1.6')
            self.assertEqual(current.json()['current_ip'], IP)

    @override_settings(TRUSTED_CLIENT_PROXY_IPS={'192.168.1.6'})
    def test_rejects_invalid_duplicate_broad_and_proxy_ips_without_partial_writes(self):
        invalid = [None, '', [True], [2], [''], ['bad'], ['https://203.0.113.42'], [IP + ':443'],
            ['203.0.113.0/24'], ['203.0.113.*'], ['0.0.0.0'], ['::'], ['127.0.0.1'], ['::1'],
            ['192.168.1.6'], ['::ffff:192.168.1.6'], ['169.254.1.3'], ['224.0.0.1'], ['ff02::1'],
            ['fe80::1%en0'], ['2001:db8::42%en0'], [IP, IP], [IP, '::ffff:' + IP],
            [f'198.51.100.{i}' for i in range(1, 52)]]
        for ips in invalid:
            with self.subTest(ips=ips):
                self.assertEqual(self.save(ips).status_code, 422)
        for revision in (None, True, -1, '0', 2147483647):
            self.assertEqual(self.save([IP], revision).status_code, 422)
        for payload in ({'ips': [IP]}, {'ips': [IP], 'revision': 0, 'is_staff': True}):
            self.assertEqual(self.client.put(self.settings_path, json.dumps(payload), content_type='application/json').status_code, 422)
        self.assertFalse(m.MonitoringAccessSettings.objects.exists())
        self.assertFalse(m.OperatorAudit.objects.filter(action='update_monitoring_access').exists())

    def test_corrupted_settings_and_database_failures_fail_closed(self):
        row = m.MonitoringAccessSettings.objects.create(ips=[IP, 'invalid'])
        client = Client()
        self.assertEqual(client.get(self.access_path, REMOTE_ADDR=IP).json(), {'allowed': False})
        row.ips = IP
        row.save()
        self.assertEqual(client.get(self.data_path, REMOTE_ADDR=IP).status_code, 401)
        with patch('core.monitoring_access.MonitoringAccessSettings.objects.filter', side_effect=DatabaseError):
            self.assertEqual(client.get(self.data_path, REMOTE_ADDR=IP).status_code, 503)

    def test_owner_write_requires_csrf_and_valid_token_can_save(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(self.save([IP], client=client).status_code, 403)
        client.get('/api/v1/manage/session')
        response = client.put(self.settings_path, json.dumps({'ips': [IP], 'revision': 0}),
            content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)

    def test_failed_audit_rolls_back_the_entire_access_grant(self):
        with patch('core.monitoring_access.OperatorAudit.objects.create', side_effect=DatabaseError):
            self.assertEqual(self.save([IP]).status_code, 503)
        self.assertFalse(m.MonitoringAccessSettings.objects.exists())
        self.assertFalse(m.OperatorAudit.objects.filter(action='update_monitoring_access').exists())


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MonitoringAccessConcurrencyTests(TransactionTestCase):
    def test_simultaneous_initial_saves_keep_one_revision_and_one_audit(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Row locking requires PostgreSQL')
        owner = get_user_model().objects.create_superuser('monitoring-race-owner')
        barrier = Barrier(2)

        def save(ip):
            close_old_connections()
            try:
                client = Client()
                client.force_login(get_user_model().objects.get(pk=owner.pk))
                barrier.wait(timeout=10)
                response = client.put(MonitoringAccessTests.settings_path, json.dumps({'ips': [ip], 'revision': 0}),
                    content_type='application/json')
                return response.status_code, ip
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, [IP, '198.51.100.4']))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        winner = next(ip for status, ip in results if status == 200)
        row = m.MonitoringAccessSettings.objects.get()
        self.assertEqual(row.ips, [winner])
        self.assertEqual(row.revision, 1)
        self.assertEqual(m.OperatorAudit.objects.filter(action='update_monitoring_access').count(), 1)
