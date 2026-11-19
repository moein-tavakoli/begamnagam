"""Management table paging contracts, including encrypted phone search."""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from . import models as m
from . import test_user_activity as fixture
from .management_blacklist import blacklist_payload
from .privacy import digest, encrypt, mask


class ManagementPaginationTests(TestCase):
    setUp = fixture.UserActivityTests.setUp
    post = fixture.UserActivityTests.post
    permit = fixture.UserActivityTests.permit

    def alerts(self, count=107):
        m.OperationalAlert.objects.bulk_create([
            m.OperationalAlert(code=f'pagination_{index}', severity='warning')
            for index in range(count)
        ])
        # Deliberately tie the primary ordering field to exercise the PK tie-break.
        m.OperationalAlert.objects.update(updated_at=timezone.now())

    def accounts(self, count=107, *, blocked=False):
        users = get_user_model().objects.bulk_create([
            get_user_model()(username=f'pagination-{index}')
            for index in range(count)
        ])
        accounts = []
        for index, user in enumerate(users):
            phone = f'0955500{index:04d}'
            accounts.append(m.Account(user=user, phone_hash=digest(phone),
                phone_cipher=encrypt(phone), phone_masked=mask(phone)))
        m.Account.objects.bulk_create(accounts)
        m.Account.objects.filter(pk__in=[account.pk for account in accounts]).update(created_at=timezone.now())
        if blocked:
            m.RecipientState.objects.bulk_create([
                m.RecipientState(phone_hash=account.phone_hash, blocked=True)
                for account in accounts
            ])
            m.RecipientState.objects.update(updated_at=timezone.now())
        return accounts

    def assert_pages(self, resource, *, query='', total=107):
        expected_ids = None
        for page_size in (1, 10, 25, 50, 100):
            with self.subTest(resource=resource, query=query, page_size=page_size):
                first = self.post(f'records/{resource}', {'query': query, 'page_size': page_size}).json()
                second = self.post(f'records/{resource}', {'query': query, 'page_size': page_size, 'page': 2}).json()
                self.assertEqual((first['page_size'], second['page_size']), (page_size, page_size))
                self.assertEqual((first['page'], second['page']), (1, 2))
                self.assertEqual((first['total'], second['total']), (total, total))
                self.assertEqual((len(first['rows']), len(second['rows'])), (page_size, min(page_size, total-page_size)))
                ids = [row['record_id'] for row in first['rows'] + second['rows']]
                self.assertEqual(len(ids), len(set(ids)))
                if expected_ids is not None:
                    self.assertEqual(ids[:2], expected_ids)
                else:
                    expected_ids = ids[:2]
                self.assertIn('columns', first)
                self.assertIn('statuses', first)
        beyond = self.post(f'records/{resource}', {'query': query, 'page_size': 100, 'page': 3}).json()
        self.assertEqual((beyond['total'], beyond['page'], beyond['rows']), (total, 3, []))

    def test_generic_tables_use_requested_size_and_stable_pages(self):
        self.permit('view_operationalalert')
        self.alerts()
        self.assert_pages('alerts')

    def test_accounts_use_requested_size_for_plain_and_encrypted_partial_search(self):
        self.permit('view_account')
        self.accounts()
        self.assert_pages('accounts', total=108)
        self.assert_pages('accounts', query='۵۵۵')
        for audit in m.OperatorAudit.objects.filter(action='account_phones_viewed'):
            self.assertNotIn('555', str([audit.reason, audit.before, audit.after]))
            self.assertLessEqual(audit.after['returned'], 100)

    def test_blacklist_uses_requested_size_for_plain_and_encrypted_partial_search(self):
        self.permit('view_account', 'view_recipientstate')
        self.accounts(blocked=True)
        self.assert_pages('blacklist')
        self.assert_pages('blacklist', query='٥٥٥')
        for audit in m.OperatorAudit.objects.filter(action='blacklist_viewed'):
            self.assertNotIn('555', str([audit.reason, audit.before, audit.after]))
            self.assertLessEqual(audit.after['returned'], 100)

    def test_defaults_remain_twenty_five_and_blacklist_direct_calls_are_compatible(self):
        self.permit('view_account', 'view_recipientstate', 'view_operationalalert')
        self.alerts(26)
        self.accounts(26, blocked=True)
        for resource in ('alerts', 'accounts', 'blacklist'):
            with self.subTest(resource=resource):
                result = self.post(f'records/{resource}').json()
                self.assertEqual((result['page'], result['page_size'], len(result['rows'])), (1, 25, 25))
        result = blacklist_payload(self.staff, '', 2)
        self.assertEqual((result['page_size'], len(result['rows'])), (25, 1))

    def test_limit_is_an_alias_and_matching_parameters_are_accepted(self):
        self.permit('view_account', 'view_recipientstate', 'view_operationalalert')
        self.alerts(26)
        self.accounts(26, blocked=True)
        for resource in ('alerts', 'accounts', 'blacklist'):
            for data in ({'limit': 10}, {'limit': 10, 'page_size': 10}, {'limit': '۱۰', 'page_size': '١٠'}):
                with self.subTest(resource=resource, data=data):
                    result = self.post(f'records/{resource}', {**data, 'page': 2}).json()
                    self.assertEqual((result['page_size'], len(result['rows'])), (10, 10))

    def test_invalid_sizes_are_rejected_before_resource_fetch_or_audit(self):
        self.permit('view_account', 'view_recipientstate', 'view_operationalalert')
        invalid = (True, False, '10', '۱٫۵', '۱۰۱', None, 0, -1, 101, 1.5, [], {})
        payloads = [{field: value} for field in ('page_size', 'limit') for value in invalid]
        payloads += [{'page_size': 10, 'limit': 25}, {'page_size': 10, 'limit': True}, {'page_size': False, 'limit': 10}]
        for resource in ('alerts', 'accounts', 'blacklist'):
            for data in payloads:
                with self.subTest(resource=resource, data=data), CaptureQueriesContext(connection) as queries:
                    response = self.post(f'records/{resource}', data)
                    self.assertEqual(response.status_code, 422, response.content)
                    self.assertEqual(response.json()['error']['code'], 'invalid_input')
                    resource_queries = [entry['sql'] for entry in queries if any(
                        f'"core_{table}"' in entry['sql']
                        for table in ('account', 'recipientstate', 'operationalalert', 'operatoraudit')
                    )]
                    self.assertEqual(resource_queries, [])

    def test_page_size_does_not_bypass_resource_permissions(self):
        self.client.force_login(self.member)
        self.assertEqual(self.post('records/accounts', {'page_size': 100}).status_code, 403)
        self.permit('view_recipientstate')
        self.assertEqual(self.post('records/blacklist', {'limit': 100}).status_code, 403)
        self.assertEqual(self.post('records/accounts', {'page_size': 100}).status_code, 403)
