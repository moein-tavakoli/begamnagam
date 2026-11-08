from django.test import TestCase
from . import test_user_activity as fixture
from . import models as m
from .privacy import digest, encrypt


class BlacklistTests(TestCase):
    setUp = fixture.UserActivityTests.setUp
    post = fixture.UserActivityTests.post
    permit = fixture.UserActivityTests.permit
    preview = fixture.UserActivityTests.preview
    order = fixture.UserActivityTests.order

    def test_blacklist_is_permissioned_and_excludes_resumed_recipients(self):
        m.RecipientState.objects.create(
            phone_hash=self.account.phone_hash, blocked=True
        )
        self.client.force_login(self.member)
        self.assertEqual(self.post('records/blacklist').status_code, 403)
        self.permit('view_recipientstate')
        self.assertEqual(self.post('records/blacklist').status_code, 403)
        self.permit('view_account')
        result = self.post('records/blacklist')
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()['rows'][0]['phone'], self.phone)
        self.assertNotIn(self.account.phone_hash, result.content.decode())
        self.assertFalse(
            any(
                key in result.json()['rows'][0]
                for key in ['phone_cipher', 'phone_hash', 'sender', 'owner']
            )
        )
        audit = m.OperatorAudit.objects.get(action='blacklist_viewed')
        self.assertNotIn(self.phone, str(audit.after))
        m.RecipientState.objects.update(blocked=False)
        self.assertEqual(self.post('records/blacklist').json()['total'], 0)

    def test_nonmember_recipient_is_included_and_partial_search_accepts_persian_digits(
        self,
    ):
        order = self.order()
        m.RecipientState.objects.create(phone_hash=order.recipient_hash, blocked=True)
        self.permit('view_account', 'view_recipientstate')
        result = self.post('records/blacklist', {'query': '۹۹۹۹'})
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()['rows'][0]['phone'], '09999999999')
        self.assertEqual(
            self.post('records/blacklist', {'query': '۱۲۳۴'}).json()['total'], 0
        )

    def test_deleted_phone_keeps_entry_without_inventing_identity_or_exposing_hash(
        self,
    ):
        state = m.RecipientState.objects.create(
            phone_hash=digest('09987654321'), blocked=True
        )
        self.permit('view_account', 'view_recipientstate')
        row = self.post('records/blacklist').json()['rows'][0]
        self.assertEqual(row['phone'], 'شماره در سوابق موجود نیست')
        self.assertNotIn(state.phone_hash, str(row))

    def test_inspecting_unsubscribe_link_is_not_a_confirmed_opt_out(self):
        from datetime import timedelta
        from django.utils import timezone
        from . import recipient

        order = self.order()
        m.RecipientState.objects.create(phone_hash=order.recipient_hash, blocked=False)
        token = 'Ab12Cd34'
        m.RecipientGrant.objects.create(
            preview=order.preview,
            recipient_hash=order.recipient_hash,
            token_digest=digest('recipient-token:' + token),
            activated_at=timezone.now(),
            stop_expires_at=timezone.now() + timedelta(days=365),
        )
        self.permit('view_account', 'view_recipientstate')
        self.assertTrue(recipient.inspect(token)['active'])
        self.assertEqual(self.post('records/blacklist').json()['total'], 0)
        recipient.stop(token)
        self.assertEqual(self.post('records/blacklist').json()['total'], 1)

    def test_pagination_is_bounded_and_does_not_drop_second_page(self):
        for index in range(26):
            m.RecipientState.objects.create(
                phone_hash=digest(f'0998000{index:04d}'), blocked=True
            )
        self.permit('view_account', 'view_recipientstate')
        first = self.post('records/blacklist').json()
        second = self.post('records/blacklist', {'page': 2}).json()
        self.assertEqual(first['total'], 26)
        self.assertEqual(len(first['rows']), 25)
        self.assertEqual(len(second['rows']), 1)
        self.assertFalse(
            set(row['record_id'] for row in first['rows'])
            & set(row['record_id'] for row in second['rows'])
        )
