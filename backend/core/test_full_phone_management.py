"""Unmasked management displays retain their staff and page boundaries."""
import json
import uuid
from unittest.mock import patch

from django.test import Client, TestCase

from . import models as m
from . import test_user_activity as fixture
from .privacy import digest, encrypt, mask


class FullPhoneManagementTests(TestCase):
    setUp = fixture.UserActivityTests.setUp
    post = fixture.UserActivityTests.post
    permit = fixture.UserActivityTests.permit

    def invitation(self, phone='09999999998', *, owner=None, cipher=None):
        return m.Invitation.objects.create(inviter=owner or self.member, phone_hash=digest(phone),
            phone_cipher=encrypt(phone) if cipher is None else cipher, phone_masked=mask(phone))

    def manual_payment(self, *, owner=None):
        package = m.MessagePackage.objects.create(name='آزمون', message_count=3, price_toman=10000, active=True)
        purchase = m.CreditPurchase.objects.create(owner=owner or self.member, idempotency_key=uuid.uuid4(),
            package=package, package_name='آزمون', message_count=3, amount_toman=10000, environment='demo')
        return m.ManualPayment.objects.create(purchase=purchase, card_number='private-card', card_holder='test')

    def test_generic_invitation_and_manual_payment_columns_show_full_phones(self):
        invitation = self.invitation()
        self.manual_payment()
        self.permit('view_invitation', 'approve_manual_payments')
        for resource, field, phone, cipher in (
            ('invitations', 'phone', '09999999998', invitation.phone_cipher),
            ('manual-payments', 'purchase__owner__account__phone', self.phone, self.account.phone_cipher),
        ):
            with self.subTest(resource=resource):
                response = self.post('records/' + resource)
                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertIn(field, [column['key'] for column in payload['columns']])
                self.assertEqual(payload['rows'][0][field], phone)
                self.assertFalse(any('masked' in column['key'] for column in payload['columns']))
                for secret in (cipher, 'phone_cipher', 'phone_hash', 'private-card', self.member.username):
                    self.assertNotIn(secret, response.content.decode())

    def test_generic_phone_decryption_stays_inside_selected_page(self):
        self.invitation('09999999991', cipher='pruned-invalid-cipher')
        selected = self.invitation('09999999992')
        self.invitation('09999999993', cipher='pruned-invalid-cipher')
        self.permit('view_invitation')
        payload = self.post('records/invitations', {'page_size': 1, 'page': 2}).json()
        self.assertEqual(payload['total'], 3)
        self.assertEqual([row['record_id'] for row in payload['rows']], [str(selected.pk)])
        self.assertEqual(payload['rows'][0].get('phone'), '09999999992')
        self.assertEqual(self.post('records/invitations', {'page_size': 1, 'page': 4}).json()['rows'], [])

    def test_manual_payment_phone_decryption_stays_inside_selected_page_and_search_works(self):
        self.manual_payment()
        self.permit('approve_manual_payments')
        response = self.post('records/manual-payments', {'query': self.account.phone_masked})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['rows'][0].get('purchase__owner__account__phone'), self.phone)
        m.Account.objects.filter(pk=self.account.pk).update(phone_cipher='invalid-off-page-cipher')
        self.assertEqual(self.post('records/manual-payments', {'page_size': 1, 'page': 2}).json()['rows'], [])

    def test_pruned_phone_values_are_empty_instead_of_masked_fallbacks(self):
        self.invitation(cipher='')
        self.manual_payment()
        m.Account.objects.filter(pk=self.account.pk).update(phone_cipher='')
        self.permit('view_invitation', 'approve_manual_payments')
        for resource, key in (('invitations', 'phone'), ('manual-payments', 'purchase__owner__account__phone')):
            with self.subTest(resource=resource):
                self.assertEqual(self.post('records/' + resource).json()['rows'][0].get(key), '')

    def test_generic_phone_guards_reject_before_decryption(self):
        self.invitation()
        self.manual_payment()
        with patch('core.management_api.decrypt', side_effect=AssertionError('unauthorized decryption')):
            for user, status in ((None, 401), (self.member, 403), (self.staff, 403)):
                self.client.logout()
                if user:
                    self.client.force_login(user)
                for resource in ('invitations', 'manual-payments'):
                    self.assertEqual(self.post('records/' + resource).status_code, status)
            self.permit('view_invitation', 'approve_manual_payments')
            client = Client(enforce_csrf_checks=True)
            client.force_login(self.staff)
            self.assertEqual(self.post('records/invitations', client=client).status_code, 403)
            self.assertEqual(self.post('records/invitations', {'page_size': 101}).status_code, 422)

    def test_user_invitation_activity_full_phone_stays_owner_scoped_and_audited_without_phone(self):
        self.invitation()
        self.invitation('09999999997', owner=self.other)
        self.permit('view_account', 'view_invitation')
        response = self.post(f'users/{self.account.pk}/activity', {'section': 'invitations'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['phone'] for row in response.json()['rows']], ['09999999998'])
        self.assertNotIn('09999999997', response.content.decode())
        self.assertNotIn('phone_cipher', response.content.decode())
        audit = m.OperatorAudit.objects.get(action='user_activity_viewed')
        metadata = json.dumps([audit.reason, audit.before, audit.after])
        self.assertNotIn(self.phone, metadata)
        self.assertNotIn('09999999998', metadata)

    def test_django_account_and_invitation_admin_render_full_readonly_phone(self):
        invitation = self.invitation()
        self.permit('view_account', 'view_invitation')
        for model, obj, phone in (('account', self.account, self.phone), ('invitation', invitation, '09999999998')):
            for suffix in ('', f'{obj.pk}/change/'):
                with self.subTest(model=model, suffix=suffix):
                    response = self.client.get(f'/admin/core/{model}/{suffix}')
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, phone)
                    self.assertNotContains(response, obj.phone_masked)
                    self.assertNotContains(response, obj.phone_cipher)
                    self.assertNotContains(response, 'name="phone_cipher"')

    def test_django_admin_pruned_phone_has_unavailable_label_and_no_masked_fallback(self):
        invitation = self.invitation(cipher='')
        m.Account.objects.filter(pk=self.account.pk).update(phone_cipher='')
        self.permit('view_account', 'view_invitation')
        for model, obj in (('account', self.account), ('invitation', invitation)):
            response = self.client.get(f'/admin/core/{model}/{obj.pk}/change/')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'شماره در سوابق موجود نیست')
            self.assertNotContains(response, obj.phone_masked)

    def test_django_admin_rejects_without_model_permission(self):
        self.invitation()
        self.client.force_login(self.staff)
        for model in ('account', 'invitation'):
            self.assertEqual(self.client.get(f'/admin/core/{model}/').status_code, 403)
