import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings

from . import models as m


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StaffRolesTests(TestCase):
    base = '/api/v1/manage/staff/'

    def setUp(self):
        cache.clear()
        self.owner = get_user_model().objects.create_superuser('staff-owner', password='Owner-only-test-23!')
        self.legacy = get_user_model().objects.create_user('legacy-employee', is_staff=True)
        self.client.force_login(self.owner)

    def request(self, method, path, data=None, client=None):
        return getattr(client or self.client, method)(self.base + path,
            json.dumps(data or {}), content_type='application/json')

    def role(self, sections, name=None):
        response = self.request('post', 'roles', {'name': name or 'نقش ' + uuid.uuid4().hex[:8], 'sections': sections})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def employee(self, role, username='new-employee'):
        response = self.request('post', 'employees', {'username': username, 'display_name': 'کارمند ۱۲',
            'password': 'Strong-private-test-42!', 'role_id': role['id'], 'is_active': True})
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def edit_employee(self, employee, **changes):
        return self.request('patch', f"employees/{employee['id']}", {
            'display_name': employee['display_name'], 'role_id': employee['role']['id'] if employee['role'] else None,
            'is_active': employee['is_active'], 'revision': employee['revision'], **changes})

    def test_catalog_is_private_owner_only_and_has_six_explained_sections(self):
        response = self.client.get(self.base + 'catalog')
        self.assertEqual(response.status_code, 200)
        sections = response.json()['sections']
        self.assertEqual([s['key'] for s in sections], ['support', 'finance', 'operations', 'users', 'content', 'settings'])
        self.assertTrue(all(s['label'] and s['description'] for s in sections))
        self.assertEqual(response['Cache-Control'], 'no-store')
        for actor, status in ((None, 401), (self.legacy, 403)):
            self.client.logout()
            if actor:
                self.client.force_login(actor)
            self.assertEqual(self.client.get(self.base + 'catalog').status_code, status)

    def test_seeded_roles_assign_no_existing_users_and_exclude_auth_privileges(self):
        response = self.client.get(self.base + 'roles').json()
        self.assertEqual({r['name'] for r in response['rows']}, {'پشتیبانی', 'مالی', 'عملیات', 'ادمین'})
        self.assertFalse(m.StaffMembership.objects.exists())
        self.assertFalse(self.legacy.groups.exists())
        for role in m.StaffRole.objects.select_related('group'):
            self.assertFalse(role.group.permissions.exclude(content_type__app_label='core').exists())
            self.assertFalse(role.group.permissions.filter(codename__in=['change_staffrole', 'add_staffmembership']).exists())
        self.assertEqual(m.StaffRole.objects.get(name='پشتیبانی').group.permissions.count(), 2)

    def test_owner_only_all_endpoints_even_for_application_admin(self):
        role = self.role(['support', 'finance', 'operations', 'users', 'content', 'settings'])
        employee = self.employee(role)
        member = get_user_model().objects.create_user('normal-member')
        for actor, expected in ((None, 401), (member, 403), (get_user_model().objects.get(pk=employee['id']), 403)):
            client = Client()
            if actor:
                client.force_login(actor)
            for path in ('catalog', 'roles', 'employees'):
                self.assertEqual(client.get(self.base + path).status_code, expected)
            for method, path, payload in (
                ('post', 'roles', {'name': 'forged', 'sections': ['support']}),
                ('patch', f"roles/{role['id']}", {'name': 'forged', 'sections': ['support'], 'revision': 0}),
                ('delete', f"roles/{role['id']}", {'revision': 0}),
                ('post', 'employees', {}), ('patch', f"employees/{employee['id']}", {})):
                self.assertEqual(self.request(method, path, payload, client).status_code, expected)

    def test_role_create_edit_revision_duplicate_and_assigned_deletion(self):
        role = self.role(['support', 'users'], 'نقش ۱۲')
        self.assertEqual(role['name'], 'نقش 12')
        self.assertEqual(role['revision'], 0)
        self.assertEqual(role['member_count'], 0)
        path = f"roles/{role['id']}"
        payload = {'name': 'نقش تازه', 'sections': ['finance'], 'revision': 0}
        updated = self.request('patch', path, payload)
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()['revision'], 1)
        self.assertEqual(self.request('patch', path, payload).status_code, 409)
        self.assertEqual(self.request('delete', path, {'revision': 0}).status_code, 409)
        self.assertEqual(self.request('post', 'roles', {'name': 'نقش تازه', 'sections': ['support']}).status_code, 409)
        self.employee(updated.json())
        self.assertEqual(self.request('delete', path, {'revision': 1}).status_code, 409)
        self.assertEqual(self.client.get(self.base + 'roles', {'query': 'تازه'}).json()['rows'][0]['member_count'], 1)
        unused = self.role(['support'])
        group_id = m.StaffRole.objects.get(pk=unused['id']).group_id
        self.assertEqual(self.request('delete', f"roles/{unused['id']}", {'revision': 0}).json(), {'ok': True})
        self.assertFalse(Group.objects.filter(pk=group_id).exists())

    def test_role_payloads_reject_privilege_injection_and_invalid_sections(self):
        for payload in (
            {'name': 'bad', 'sections': ['support'], 'permissions': ['auth.change_user']},
            {'name': 'bad', 'sections': ['support'], 'group_id': 1},
            {'name': '', 'sections': ['support']}, {'name': 'x' * 81, 'sections': ['support']},
            {'name': 'bad', 'sections': []}, {'name': 'bad', 'sections': ['unknown']},
            {'name': 'bad', 'sections': ['support', 'support']}, {'name': 'bad', 'sections': 'support'},
            {'name': 'bad', 'sections': [True]}, {'name': 3, 'sections': ['support']}):
            with self.subTest(payload=payload):
                self.assertEqual(self.request('post', 'roles', payload).status_code, 422)
        role = self.role(['support'])
        for revision in (None, True, -1, '0'):
            self.assertEqual(self.request('patch', f"roles/{role['id']}", {
                'name': role['name'], 'sections': ['support'], 'revision': revision}).status_code, 422)

    def test_employee_password_is_hashed_and_creation_has_no_product_side_effects(self):
        employee = self.employee(self.role(['finance']))
        user = get_user_model().objects.get(pk=employee['id'])
        self.assertTrue(user.check_password('Strong-private-test-42!'))
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(employee['display_name'], 'کارمند 12')
        self.assertEqual(employee['revision'], 0)
        self.assertEqual(set(employee), {'id', 'username', 'display_name', 'role', 'is_active', 'is_owner', 'revision'})
        for model in (m.Account, m.OTPChallenge, m.Outbox, m.MessageDelivery):
            self.assertFalse(model.objects.exists())
        audit = m.OperatorAudit.objects.get(action='staff_employee_created')
        self.assertEqual(audit.actor_id, self.owner.pk)
        self.assertEqual(audit.after, {'role_id': employee['role']['id'], 'is_active': True})
        self.assertNotIn('Strong-private-test-42!', json.dumps(audit.after))
        self.assertNotIn('password', json.dumps(employee))

    def test_employee_assignment_replaces_legacy_groups_and_direct_permissions(self):
        old_group = Group.objects.create(name='legacy-wide-permissions')
        old_group.permissions.add(Permission.objects.get(content_type__app_label='auth', codename='change_user'))
        self.legacy.groups.add(old_group)
        self.legacy.user_permissions.add(Permission.objects.get(content_type__app_label='core', codename='manage_ai'))
        row = next(r for r in self.client.get(self.base + 'employees').json()['rows'] if r['id'] == self.legacy.pk)
        self.assertIsNone(row['role'])
        self.assertEqual(row['revision'], 0)
        role = self.role(['support'])
        response = self.edit_employee(row, role_id=role['id'], display_name='کارمند قدیمی')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['revision'], 1)
        self.legacy.refresh_from_db()
        self.assertEqual(list(self.legacy.groups.values_list('pk', flat=True)), [m.StaffRole.objects.get(pk=role['id']).group_id])
        self.assertFalse(self.legacy.user_permissions.exists())
        self.assertFalse(self.legacy.has_perm('auth.change_user'))
        self.assertFalse(self.legacy.has_perm('core.manage_ai'))
        self.assertTrue(self.legacy.has_perm('core.add_supportmessage'))
        self.assertEqual(self.edit_employee(row, role_id=role['id'], display_name='کارمند قدیمی').status_code, 409)

    def test_employee_updates_conflict_password_reset_and_inactive_session_revocation(self):
        employee = self.employee(self.role(['support']))
        client = Client()
        user = get_user_model().objects.get(pk=employee['id'])
        client.force_login(user)
        self.assertEqual(client.get('/api/v1/manage/support/summary').status_code, 200)
        response = self.edit_employee(employee, password='Replacement-private-test-81!', is_active=False)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['revision'], 1)
        self.assertEqual(self.edit_employee(employee).status_code, 409)
        user.refresh_from_db()
        self.assertTrue(user.check_password('Replacement-private-test-81!'))
        self.assertEqual(client.get('/api/v1/manage/support/summary').status_code, 401)

    def test_employee_payloads_reject_privileges_product_users_and_owner_mutation(self):
        role = self.role(['support'])
        data = {'username': 'valid-new-user', 'display_name': 'نام', 'password': 'Strong-private-test-42!',
            'role_id': role['id'], 'is_active': True}
        for changes in ({'is_superuser': True}, {'is_staff': False}, {'groups': []}, {'user_permissions': []},
            {'username': 'x' * 151}, {'username': 'bad username'}, {'password': '123'}, {'password': ''},
            {'role_id': True}, {'role_id': None}, {'is_active': 1}, {'display_name': 'x' * 151}):
            with self.subTest(fields=list(changes)):
                self.assertEqual(self.request('post', 'employees', {**data, **changes}).status_code, 422)
        self.assertEqual(self.request('post', 'employees', {**data, 'username': self.legacy.username}).status_code, 409)
        nonstaff = get_user_model().objects.create_user('product-user')
        for target, expected in ((self.owner, 403), (nonstaff, 404)):
            response = self.request('patch', f'employees/{target.pk}', {'display_name': 'تغییر',
                'role_id': role['id'], 'is_active': False, 'revision': 0})
            self.assertEqual(response.status_code, expected)
        employee = self.employee(role)
        self.assertEqual(self.edit_employee(employee, username='renamed').status_code, 422)
        self.assertEqual(self.request('delete', f"employees/{employee['id']}").status_code, 405)

    def test_management_csrf_enforced_for_post_patch_delete(self):
        role = self.role(['support'])
        employee = self.employee(role)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        for method, path, payload in (
            ('post', 'roles', {'name': 'csrf', 'sections': ['support']}),
            ('patch', f"roles/{role['id']}", {'name': 'csrf', 'sections': ['support'], 'revision': 0}),
            ('delete', f"roles/{role['id']}", {'revision': 0}),
            ('post', 'employees', {}), ('patch', f"employees/{employee['id']}", {})):
            self.assertEqual(self.request(method, path, payload, client).status_code, 403)

    def test_lists_search_pagination_bounds_and_exclude_product_users(self):
        get_user_model().objects.create_user('hidden-product-user')
        get_user_model().objects.bulk_create([get_user_model()(username=f'employee-{n:03}', is_staff=True) for n in range(30)])
        first = self.client.get(self.base + 'employees', {'page_size': 10}).json()
        second = self.client.get(self.base + 'employees', {'page': 2, 'page_size': 10}).json()
        self.assertEqual((first['total'], first['page_size'], len(first['rows'])), (32, 10, 10))
        self.assertFalse({r['id'] for r in first['rows']} & {r['id'] for r in second['rows']})
        self.assertEqual(self.client.get(self.base + 'employees', {'query': 'employee-00'}).json()['total'], 10)
        self.assertEqual(self.client.get(self.base + 'employees', {'page': 100}).json()['rows'], [])
        for path in ('roles', 'employees'):
            for filters in ({'page': 0}, {'page_size': 101}, {'page_size': 'true'}, {'page': '1.5'},
                {'query': 'x' * 101}, {'unknown': 'field'}, {'page': ['1', '2']}):
                self.assertEqual(self.client.get(self.base + path, filters).status_code, 422)

    def test_search_preserves_opaque_username_digits_and_normalizes_human_names(self):
        employee = self.employee(self.role(['support'], name='نقش ۱۲'), username='operator۱۲')
        response = self.client.get(self.base + 'employees', {'query': 'operator۱۲'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['rows']], [employee['id']])
        self.assertEqual(response.json()['rows'][0]['username'], 'operator۱۲')
        by_name = self.client.get(self.base + 'employees', {'query': 'کارمند ۱۲'}).json()
        self.assertEqual([row['id'] for row in by_name['rows']], [employee['id']])
        by_role = self.client.get(self.base + 'roles', {'query': 'نقش ۱۲'}).json()
        self.assertEqual([row['id'] for row in by_role['rows']], [employee['role']['id']])

    def test_managed_support_and_changelog_require_sections_and_revoke_next_request(self):
        finance = self.role(['finance'])
        employee = self.employee(finance)
        client = Client()
        client.force_login(get_user_model().objects.get(pk=employee['id']))
        for path in ('support/summary', 'changelog'):
            self.assertEqual(client.get('/api/v1/manage/' + path).status_code, 403)
        self.assertEqual(client.post('/api/v1/manage/support/inbox', '{}', content_type='application/json').status_code, 403)
        self.assertEqual(client.get('/api/v1/manage/limits').status_code, 403)
        permissions = client.get('/api/v1/manage/session').json()['permissions']
        self.assertNotIn('support_chat', permissions)
        self.assertNotIn('manage_staff', permissions)
        self.assertNotIn('view_changelog', permissions)
        updated = self.request('patch', f"roles/{finance['id']}", {'name': finance['name'],
            'sections': ['support', 'settings'], 'revision': 0})
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(client.get('/api/v1/manage/support/summary').status_code, 200)
        self.assertEqual(client.get('/api/v1/manage/changelog').status_code, 200)
        self.assertEqual(client.post('/api/v1/manage/records/payments', '{}', content_type='application/json').status_code, 403)
        permissions = client.get('/api/v1/manage/session').json()['permissions']
        self.assertIn('support_chat', permissions)
        self.assertIn('view_changelog', permissions)
        self.assertNotIn('manage_staff', permissions)
        self.assertIn('manage_staff', self.client.get('/api/v1/manage/session').json()['permissions'])
        self.assertEqual(m.OperatorAudit.objects.get(action='staff_role_updated').after['sections'], ['support', 'settings'])

    def test_legacy_staff_support_and_changelog_access_is_preserved(self):
        self.client.force_login(self.legacy)
        self.assertEqual(self.client.get('/api/v1/manage/support/summary').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/manage/changelog').status_code, 200)
        context = self.client.get('/api/v1/manage/session').json()
        self.assertIn('support_chat', context['permissions'])
        self.assertIn('view_changelog', context['permissions'])
        self.assertNotIn('manage_staff', context['permissions'])

    def test_each_bundle_enforces_its_actual_section_endpoints(self):
        endpoints = {
            'support': ('get', '/api/v1/manage/support/summary'),
            'finance': ('post', '/api/v1/manage/records/manual-payments'),
            'operations': ('get', '/api/v1/manage/monitoring'),
            'users': ('post', '/api/v1/manage/records/accounts'),
            'content': ('get', '/api/v1/manage/message-examples'),
            'settings': ('get', '/api/v1/manage/limits'),
        }
        for section in endpoints:
            employee = self.employee(self.role([section]), username='section-' + section)
            client = Client()
            client.force_login(get_user_model().objects.get(pk=employee['id']))
            for requested, (method, path) in endpoints.items():
                allowed = requested == section or (section == 'content' and requested == 'users')
                response = client.get(path) if method == 'get' else client.post(path, '{}', content_type='application/json')
                self.assertEqual(response.status_code, 200 if allowed else 403, (section, requested, response.content))
            if section != 'support':
                thread = uuid.uuid4()
                for suffix, data in (('messages', {'text': 'پاسخ', 'reply_to_sequence': 1}),
                    ('read', {'through_sequence': 0}), ('close', {'last_sequence': 0})):
                    response = client.post(f'/api/v1/manage/support/{thread}/{suffix}', json.dumps(data), content_type='application/json')
                    self.assertEqual(response.status_code, 403)
            private = client.post(f'/api/v1/manage/orders/{uuid.uuid4()}/texts', '{}', content_type='application/json')
            self.assertEqual(private.status_code, 404 if section == 'content' else 403)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class StaffRoleConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Row-lock concurrency requires PostgreSQL')
        from .staff_roles import create_role
        self.owner = get_user_model().objects.create_superuser('concurrency-owner', password='Owner-test-93!')
        self.user = get_user_model().objects.create_user('concurrent-legacy', is_staff=True, first_name='کارمند')
        self.role = create_role(self.owner, {'name': 'نقش همزمان', 'sections': ['support']})

    def race(self, actions):
        barrier = Barrier(len(actions))

        def run(action):
            close_old_connections()
            try:
                client = Client()
                client.force_login(get_user_model().objects.get(pk=self.owner.pk))
                barrier.wait(timeout=10)
                method, path, data = action
                return getattr(client, method)('/api/v1/manage/staff/' + path,
                    json.dumps(data), content_type='application/json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(actions)) as executor:
            return list(executor.map(run, actions))

    def test_concurrent_first_assignment_is_serialized_and_stale_edit_conflicts(self):
        data = {'display_name': 'نام', 'role_id': self.role['id'], 'is_active': True, 'revision': 0}
        statuses = self.race([('patch', f'employees/{self.user.pk}', data)] * 2)
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(m.StaffMembership.objects.get(user=self.user).revision, 1)
        self.assertEqual(self.user.groups.count(), 1)
        self.assertEqual(m.OperatorAudit.objects.filter(action='staff_employee_updated').count(), 1)

    def test_concurrent_role_updates_keep_one_revision_and_matching_permissions(self):
        statuses = self.race([('patch', f"roles/{self.role['id']}", {
            'name': self.role['name'], 'sections': [section], 'revision': 0}) for section in ('support', 'finance')])
        self.assertEqual(sorted(statuses), [200, 409])
        role = m.StaffRole.objects.get(pk=self.role['id'])
        self.assertEqual(role.revision, 1)
        has_support = role.group.permissions.filter(codename='add_supportmessage').exists()
        has_finance = role.group.permissions.filter(codename='approve_manual_payments').exists()
        self.assertEqual((has_support, has_finance), (role.sections == ['support'], role.sections == ['finance']))

    def test_deleting_a_role_racing_assignment_cannot_leave_dangling_membership(self):
        statuses = self.race([
            ('delete', f"roles/{self.role['id']}", {'revision': 0}),
            ('patch', f'employees/{self.user.pk}', {'display_name': 'نام', 'role_id': self.role['id'],
                'is_active': True, 'revision': 0}),
        ])
        self.assertEqual(statuses.count(200), 1)
        self.assertTrue(404 in statuses or 409 in statuses, statuses)
        if m.StaffRole.objects.filter(pk=self.role['id']).exists():
            self.assertTrue(m.StaffMembership.objects.filter(user=self.user, role_id=self.role['id']).exists())
        else:
            self.assertFalse(m.StaffMembership.objects.filter(user=self.user).exists())
