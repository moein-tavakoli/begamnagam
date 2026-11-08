"""Full display phones remain confined to existing owner and staff boundaries."""
import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import support, tests as fixture
from .models import Account, Invitation, Order, Preview, SupportConversation
from .privacy import digest, encrypt, mask


@override_settings(DEMO_MODE=True, OTP_BACKEND='demo', SMS_BACKEND='console',
                   PROVIDER_NETWORK_MODE='disabled', PAYMENT_BACKEND='demo', AI_MODE='template')
class FullPhoneViewTests(TestCase):
    post = fixture.APITestCase.post
    authenticate = fixture.APITestCase.authenticate

    def setUp(self):
        cache.clear()
        self.client = Client()
        self.client.get('/api/v1/bootstrap')

    def make_order(self, user, phone='09901234567', *, pruned=False):
        preview = Preview.objects.create(owner=user, session_key=self.client.session.session_key,
            category='appreciation', text='سپاس از همراهی', moderation_mode='template', price_toman=0,
            expires_at=timezone.now() + timedelta(minutes=10))
        return Order.objects.create(owner=user, preview=preview, idempotency_key=uuid.uuid4(),
            recipient_hash=digest(phone), recipient_cipher='' if pruned else encrypt(phone),
            recipient_masked=mask(phone), text='سپاس از همراهی', category='appreciation',
            amount_toman=0, is_free=True)

    def make_invitation(self, user, phone='09901234561', *, pruned=False):
        return Invitation.objects.create(inviter=user, phone_hash=digest(phone),
            phone_cipher='' if pruned else encrypt(phone), phone_masked=mask(phone))

    def test_login_and_bootstrap_return_only_verified_accounts_full_phone(self):
        anonymous = self.client.get('/api/v1/bootstrap').json()
        self.assertNotIn('phone', anonymous)
        self.assertNotIn('me', self.client.get('/api/v2/bootstrap').json())
        challenge = self.post('/auth/request-otp', {'phone': '۰۹۱۲۳۴۵۶۷۸۹'}).json()
        verified = self.post('/auth/verify-otp', {
            'challenge_id': challenge['challenge_id'], 'code': challenge['debug_code']}).json()
        self.assertEqual(verified.get('phone'), '09123456789')
        self.assertEqual(verified['phone_masked'], '091•••••789')
        self.assertEqual(self.client.get('/api/v1/bootstrap').json().get('phone'), '09123456789')
        self.assertEqual(self.client.get('/api/v2/me').json().get('phone'), '09123456789')
        self.assertEqual(self.client.get('/api/v2/bootstrap').json()['me'].get('phone'), '09123456789')
        staff = get_user_model().objects.create_user('staff-without-product-account', is_staff=True)
        staff_client = Client(); staff_client.force_login(staff)
        self.assertNotIn('phone', staff_client.get('/api/v1/bootstrap').json())
        self.assertNotIn('me', staff_client.get('/api/v2/bootstrap').json())
        self.assertEqual(staff_client.get('/api/v2/me').status_code, 401)

    def test_history_and_receipt_return_recipient_only_to_order_owner(self):
        user = self.authenticate()
        order = self.make_order(user)
        for path in (f'/api/v1/orders/{order.pk}', f'/api/v2/messages/{order.pk}'):
            value = self.client.get(path).json()
            self.assertEqual(value.get('recipient_phone'), '09901234567')
            self.assertEqual(value['recipient_masked'], '099•••••567')
            self.assertNotIn('09123456789', str(value))
            self.assertNotIn('recipient_cipher', value)
        for path in ('/api/v1/messages', '/api/v2/messages'):
            self.assertEqual(self.client.get(path).json()['results'][0].get('recipient_phone'), '09901234567')
        other = Client(); self.authenticate('09901234562', other)
        for path in (f'/api/v1/orders/{order.pk}', f'/api/v2/messages/{order.pk}'):
            response = other.get(path)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn('09901234567', response.content.decode())
            self.assertEqual(Client().get(path).status_code, 401)
        for path in ('/api/v1/messages', '/api/v2/messages'):
            self.assertEqual(other.get(path).json()['results'], [])

    def test_invitations_return_full_phone_only_for_inviter(self):
        user = self.authenticate()
        self.make_invitation(user)
        for path in ('/api/v1/invitations', '/api/v2/invitations'):
            value = self.client.get(path).json()['results'][0]
            self.assertEqual(value.get('phone'), '09901234561')
            self.assertNotIn('phone_cipher', value)
            self.assertEqual(Client().get(path).status_code, 401)
        other = Client(); self.authenticate('09901234562', other)
        for path in ('/api/v1/invitations', '/api/v2/invitations'):
            self.assertEqual(other.get(path).json()['results'], [])

    def test_support_customer_phone_is_staff_only_and_staff_identity_stays_private(self):
        user = self.authenticate()
        support.send(user, {'text': 'راهنمایی می‌خواهم'}, uuid.uuid4())
        thread = SupportConversation.objects.get(account__user=user)
        staff_user = get_user_model().objects.create_user('private-staff', is_staff=True)
        Account.objects.create(user=staff_user, phone_hash=digest('09901234563'),
            phone_cipher=encrypt('09901234563'), phone_masked=mask('09901234563'))
        staff = Client(); staff.force_login(staff_user)
        inbox = self.post('/manage/support/inbox', {'filter': 'all'}, staff).json()
        self.assertEqual(inbox['conversations'][0].get('phone'), '09123456789')
        page = staff.get(f'/api/v1/manage/support/{thread.pk}/messages').json()
        self.assertEqual(page['thread'].get('phone'), '09123456789')
        self.assertNotIn('phone_cipher', str(page))
        support.send(staff_user, {'text': 'پاسخ پشتیبانی', 'reply_to_sequence': 1},
            uuid.uuid4(), thread_id=thread.pk, staff=True)
        for path in ('/api/v1/support/messages', '/api/v2/support/messages'):
            value = self.client.get(path).json()
            self.assertNotIn('phone', value['thread'])
            self.assertNotIn('phone_masked', value['thread'])
            self.assertNotIn('09901234563', str(value))
            self.assertNotIn('private-staff', str(value))
        other = Client(); self.authenticate('09901234562', other)
        self.assertIsNone(other.get('/api/v1/support/messages').json()['thread'])
        for client in (self.client, other, Client()):
            response = client.get(f'/api/v1/manage/support/{thread.pk}/messages')
            self.assertIn(response.status_code, (401, 403))
            self.assertNotIn('09123456789', response.content.decode())

    def test_pruned_cipher_returns_empty_phone_without_mask_reconstruction(self):
        user = self.authenticate()
        order = self.make_order(user, pruned=True)
        self.make_invitation(user, pruned=True)
        Account.objects.filter(user=user).update(phone_cipher='')
        for path in ('/api/v1/bootstrap', '/api/v2/me'):
            self.assertEqual(self.client.get(path).json().get('phone'), '')
        for path in (f'/api/v1/orders/{order.pk}', f'/api/v2/messages/{order.pk}'):
            self.assertEqual(self.client.get(path).json().get('recipient_phone'), '')
        for path in ('/api/v1/invitations', '/api/v2/invitations'):
            self.assertEqual(self.client.get(path).json()['results'][0].get('phone'), '')
        thread = SupportConversation.objects.create(account=Account.objects.get(user=user))
        self.assertEqual(support.thread_data(thread, staff=True).get('phone'), '')
