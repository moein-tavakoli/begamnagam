import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.test import TestCase
from . import test_runtime_limits as runtime, test_live_sms as live
from .account_options import update_account_options
from .models import Account, CreditEntry, OperatorAudit, Order, PaymentAttempt, SiteLimits
from .services import APIError, release_free_credit


class SponsoredSendingTests(TestCase):
    post, preview = runtime.RuntimeLimitsTests.post, runtime.RuntimeLimitsTests.preview
    order, configure = runtime.RuntimeLimitsTests.order, runtime.RuntimeLimitsTests.configure

    def setUp(self):
        runtime.RuntimeLimitsTests.setUp(self)
        self.configure(sender_limit=0, recipient_cooldown_hours=0, pair_cooldown_hours=0)
        self.actor = get_user_model().objects.create_user(username='sponsor-operator', is_staff=True)
        self.actor.user_permissions.add(Permission.objects.get(codename='manage_free_sending'))
        self.account = Account.objects.get(user=self.user)

    def set_sponsored(self, enabled):
        return update_account_options(self.actor, self.account.pk, {'unlimited_free_sends': enabled}, 'تغییر مجوز ارسال رایگان')

    def test_sends_without_gifts_or_package_credit_and_preserves_balances(self):
        Account.objects.filter(pk=self.account.pk).update(free_sends_remaining=0, demo_sends_remaining=7, purchased_sends_remaining=9)
        self.set_sponsored(True)
        for _ in range(4):
            response = self.order()
            self.assertEqual(response.status_code, 200, response.content)
            order = Order.objects.get(pk=response.json()['id'])
            self.assertTrue(order.is_free and order.is_sponsored)
            self.assertFalse(order.uses_purchased_credit)
            order.status = 'delivered_demo';order.save(update_fields=['status'])
        self.account.refresh_from_db()
        self.assertEqual((self.account.free_sends_remaining, self.account.demo_sends_remaining, self.account.purchased_sends_remaining), (0, 7, 9))
        self.assertFalse(CreditEntry.objects.exists())
        self.assertFalse(PaymentAttempt.objects.exists())
        self.assertTrue(self.client.get('/api/v1/bootstrap').json()['unlimited_free_sends'])
        self.assertTrue(self.client.get('/api/v2/me/credits').json()['unlimited_free_sends'])

    def test_grant_requires_requote_instead_of_charging_package_for_old_preview(self):
        Account.objects.filter(pk=self.account.pk).update(free_sends_remaining=0, demo_sends_remaining=7)
        quote=self.preview(category='appreciation',text='تشکر از تو')
        self.assertFalse(quote['is_free'])
        self.set_sponsored(True)
        response=self.post('/orders',{'preview_id':quote['preview_id'],'recipient_phone':'09901234567','consent':True,'terms_version':quote['terms_version']},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.json()['error']['code'],'free_quota_changed')
        self.account.refresh_from_db();self.assertEqual(self.account.demo_sends_remaining,7)
        self.assertFalse(Order.objects.exists())
        self.assertEqual(self.order().status_code,200)
        self.account.refresh_from_db();self.assertEqual(self.account.demo_sends_remaining,7)

    def test_revoke_blocks_old_unconsumed_preview_but_existing_order_retry_is_idempotent(self):
        Account.objects.filter(pk=self.account.pk).update(free_sends_remaining=0)
        self.set_sponsored(True)
        quote = self.preview(category='appreciation', text='تشکر از تو')
        body = {'preview_id': quote['preview_id'], 'recipient_phone':'09901234567', 'consent':True, 'terms_version':quote['terms_version']}
        self.set_sponsored(False)
        response = self.post('/orders',body,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.json()['error']['code'],'free_quota_changed')
        self.set_sponsored(True)
        key=str(uuid.uuid4());response=self.post('/orders',body,HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code,200,response.content)
        self.set_sponsored(False)
        retry=self.post('/orders',body,HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(retry.json()['id'],response.json()['id'])
        with transaction.atomic():
            order=Order.objects.select_for_update().get(pk=response.json()['id'])
            release_free_credit(order);release_free_credit(order)
        self.account.refresh_from_db();self.assertEqual(self.account.free_sends_remaining,0)
        self.assertIsNone(Order.objects.get().free_credit_released_at)

    def test_daily_count_permission_cannot_grant_free_sending_and_changes_are_audited(self):
        actor=get_user_model().objects.create_user(username='count-operator',is_staff=True)
        actor.user_permissions.add(Permission.objects.get(codename='manage_account_limits'))
        with self.assertRaises(APIError):
            update_account_options(actor,self.account.pk,{'unlimited_free_sends':True},'تغییر سقف تعداد')
        self.set_sponsored(True)
        audit=OperatorAudit.objects.get(action='account_send_options')
        self.assertEqual(audit.before,{'unlimited_free_sends':False})
        self.assertEqual(audit.after,{'unlimited_free_sends':True})
        self.client.force_login(actor)
        response=self.post('/manage/actions',{'action':'free_sending','object_id':str(self.account.pk),'value':False,'reason':'بازگشت به اعتبار محدود'})
        self.assertEqual(response.status_code,403)

    def test_management_action_requires_boolean_reason_and_exposes_current_flag(self):
        self.client.force_login(self.actor)
        base={'action':'free_sending','object_id':str(self.account.pk),'reason':'اعطای ارسال رایگان'}
        for bad in ['true', 1, None]:
            self.assertEqual(self.post('/manage/actions',{**base,'value':bad}).status_code,403)
        self.assertEqual(self.post('/manage/actions',{**base,'value':True,'reason':''}).status_code,400)
        self.assertEqual(self.post('/manage/actions',{**base,'value':True}).status_code,200)
        self.account.refresh_from_db();self.assertTrue(self.account.unlimited_free_sends)
        self.assertIn('manage_free_sending',self.client.get('/api/v1/manage/session').json()['permissions'])

    def test_limits_suspension_and_client_injected_flag_still_apply(self):
        self.set_sponsored(True);SiteLimits.objects.filter(pk=1).update(sender_limit=1)
        response=self.order();self.assertEqual(response.status_code,200,response.content)
        Order.objects.update(status='delivered_demo')
        self.assertEqual(self.order().json()['error']['code'],'daily_limit')
        SiteLimits.objects.filter(pk=1).update(sender_limit=0)
        Account.objects.filter(pk=self.account.pk).update(suspended=True)
        self.assertEqual(self.order().status_code,403)
        Account.objects.filter(pk=self.account.pk).update(suspended=False)
        quote=self.preview(category='appreciation',text='تشکر از تو')
        response=self.post('/orders',{'preview_id':quote['preview_id'],'recipient_phone':'09901234567','unlimited_free_sends':True},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(response.json()['error']['code'],'server_snapshot_required')


class LiveSponsoredSendingTests(TestCase):
    setUp = live.LiveGiftSMSTests.setUp
    post, authenticate, preview = live.LiveGiftSMSTests.post, live.LiveGiftSMSTests.authenticate, live.LiveGiftSMSTests.preview
    make_order, confirm = live.LiveGiftSMSTests.make_order, live.LiveGiftSMSTests.confirm

    def test_real_profile_sponsored_order_keeps_budget_and_provider_idempotency(self):
        from unittest.mock import patch
        from .providers.kavenegar import SMSResult
        from .provider_delivery import submit_delivery
        from .models import MessageDelivery, Outbox, SpendBudget
        Account.objects.filter(user=self.user).update(unlimited_free_sends=True,free_sends_remaining=0)
        quote=self.preview(category='appreciation',text='تشکر از تو')
        response=self.make_order(quote=quote);self.assertEqual(response.status_code,200,response.content)
        self.confirm(response.json())
        with patch('core.provider_delivery.Kavenegar.submit',return_value=SMSResult('accepted','synthetic-sponsored',1000)) as wire:
            submit_delivery(Outbox.objects.get().pk);submit_delivery(Outbox.objects.get().pk)
        self.assertEqual(wire.call_count,1)
        self.assertEqual(MessageDelivery.objects.get().environment,'live')
        self.assertGreater(SpendBudget.objects.get().reserved_rial,0)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,0)

    def test_optout_definitive_failure_does_not_create_gift_or_call_provider(self):
        from unittest.mock import patch
        from .models import Outbox, RecipientState
        from .provider_delivery import submit_delivery
        Account.objects.filter(user=self.user).update(unlimited_free_sends=True,free_sends_remaining=0)
        response=self.make_order();self.assertEqual(response.status_code,200,response.content)
        self.confirm(response.json())
        RecipientState.objects.update(blocked=True)
        with patch('core.provider_delivery.Kavenegar.submit') as wire:
            submit_delivery(Outbox.objects.get().pk)
        wire.assert_not_called()
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,0)
        self.assertEqual(Order.objects.get().status,'cancelled')
