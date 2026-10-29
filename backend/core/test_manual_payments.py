import uuid
from io import StringIO
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.management import call_command
from datetime import timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from . import tests as fixture
from .models import Account, CreditEntry, CreditPurchase, FinancialEvent, ManualPayment, ManualPaymentSettings, MessagePackage, OperatorAudit, PaymentAttempt, Outbox, SafetyControl
from .manual_payments import approve, begin_purchase, grant_package, save_settings, valid_card
from .packages import purchase_data
from .payment_options import WALLET_TERMS_VERSION
from .services import APIError

CARD='6037991234567890'  # synthetic, checksum-corrected below; never a real transfer
CARD=CARD[:-1]+next(str(n) for n in range(10) if valid_card(CARD[:-1]+str(n)))


class ManualFixture:
    post, authenticate = fixture.APITestCase.post, fixture.APITestCase.authenticate

    def setUp(self):
        fixture.APITestCase.setUp(self)
        self.user=self.authenticate(free_sends=3)
        Account.objects.filter(user=self.user).update(demo_sends_remaining=0)
        SafetyControl.objects.update_or_create(pk=1,defaults={'halted':False})
        self.package=MessagePackage.objects.create(name='بستهٔ آزمون',message_count=3,price_toman=10000,active=True)
        self.actor=get_user_model().objects.create_user('bank-reviewer',is_staff=True)
        self.actor.user_permissions.add(*Permission.objects.filter(codename__in=['manage_manual_payments','approve_manual_payments']))
        self.staff=Client();self.staff.force_login(self.actor)
        ManualPaymentSettings.objects.update_or_create(pk=1,defaults={'enabled':True,'card_number':CARD,'card_holder':'پشتیبان آزمون','bank_name':'بانک آزمون','bale_username':'test_support','telegram_username':'test_support'})

    def create(self,key=None,**extra):
        return begin_purchase(self.user,{'package_id':self.package.pk,'package_revision':self.package.revision,'payment_method':'card','wallet_consent':True,'wallet_terms_version':WALLET_TERMS_VERSION,**extra},key or uuid.uuid4())

    def proof(self,reference='BANK123456',**extra):
        return {'reason':'واریز با بانک تطبیق داده شد','bank_verified':True,'amount_toman':10000,'bank_reference':reference,'paid_date':timezone.localdate().isoformat(),**extra}

    def balance(self):return Account.objects.get(user=self.user).demo_sends_remaining


class ManualPaymentTests(ManualFixture,TestCase):
    def test_seeded_four_proportional_packages_and_three_gifts(self):
        catalog=self.client.get('/api/v1/bootstrap').json()
        pairs={(p['message_count'],p['price_toman']) for p in catalog['message_packages']}
        self.assertTrue({(3,10000),(9,30000),(30,100000),(90,300000)}<=pairs)
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,3)

    def test_claim_never_credits_and_approval_is_atomic_and_idempotent(self):
        purchase=self.create();manual=purchase.manual_payment
        result=self.post(f'/credit-purchases/{purchase.pk}/receipt',{'receipt_sent':True,'reference':'12345678'})
        self.assertEqual(result.status_code,200,result.content);self.assertEqual(result.json()['status'],'awaiting_review')
        self.assertEqual(self.balance(),0);self.assertFalse(CreditEntry.objects.exists());self.assertFalse(FinancialEvent.objects.exists())
        for _ in range(2):
            result=self.post(f'/manage/manual-payments/{manual.pk}/approve',self.proof(),self.staff)
            self.assertEqual(result.status_code,200,result.content);self.assertEqual(result.json()['status'],'credited')
        self.assertEqual(self.balance(),3)
        self.assertEqual((CreditEntry.objects.count(),FinancialEvent.objects.count()),(1,1))
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,3)
        self.assertFalse(Outbox.objects.exists())
        self.assertEqual(OperatorAudit.objects.filter(action='approve_manual_payment').count(),1)

    def test_receipt_owner_login_and_csrf_protected(self):
        purchase=self.create();other=Client();self.authenticate('09901234561',other)
        self.assertEqual(self.post(f'/credit-purchases/{purchase.pk}/receipt',{'receipt_sent':True},other).status_code,404)
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.user)
        self.assertEqual(self.post(f'/credit-purchases/{purchase.pk}/receipt',{'receipt_sent':True},csrf).status_code,403)
        for data in ({},{'receipt_sent':False},{'receipt_sent':True,'credited_at':'now'}):
            self.assertEqual(self.post(f'/credit-purchases/{purchase.pk}/receipt',data).status_code,422)
        self.assertEqual(self.balance(),0)

    def test_admin_mutations_require_csrf_and_public_bootstrap_has_no_card(self):
        purchase=self.create()
        self.assertNotIn(CARD,Client().get('/api/v1/bootstrap').content.decode())
        csrf=Client(enforce_csrf_checks=True);csrf.force_login(self.actor)
        for path,data in [(f'/manage/manual-payments/{purchase.manual_payment.pk}/approve',self.proof()),
            (f'/manage/manual-payments/{purchase.manual_payment.pk}/reject',{'reason':'بررسی آزمون'}),
            ('/manage/manual-payments/grant',{}),('/manage/manual-payment-settings',{})]:
            self.assertEqual(self.post(path,data,csrf).status_code,403)
        self.assertEqual(self.post('/manage/manual-payments/grant',{}).status_code,403)
        self.assertEqual(self.balance(),0)

    def test_price_units_status_and_revision_cannot_be_forged(self):
        for extra in ({'amount_toman':1},{'message_count':1000},{'status':'approved'},{'package_revision':99},{'wallet_consent':False}):
            with self.subTest(extra=extra),self.assertRaises(APIError):self.create(**extra)
        self.assertFalse(CreditPurchase.objects.exists())

    def test_approval_needs_scoped_permission_and_actual_bank_match(self):
        purchase=self.create()
        with self.assertRaises(APIError):approve(self.user,purchase.manual_payment.pk,self.proof())
        for extra in ({'amount_toman':9999},{'amount_toman':True},{'bank_verified':False},{'bank_reference':''},{'paid_date':'no'},{'paid_date':(timezone.localdate()+timedelta(days=1)).isoformat()},{'reason':''},{'units':1000}):
            with self.subTest(extra=extra),self.assertRaises(APIError):approve(self.actor,purchase.manual_payment.pk,self.proof(**extra))
        self.assertEqual(self.balance(),0);self.assertFalse(CreditEntry.objects.exists());self.assertFalse(FinancialEvent.objects.exists())

    def test_same_bank_proof_cannot_grant_different_purchase(self):
        first=self.create();approve(self.actor,first.manual_payment.pk,self.proof())
        second=self.create()
        with self.assertRaises(APIError) as caught:approve(self.actor,second.manual_payment.pk,self.proof())
        self.assertEqual(caught.exception.code,'receipt_used');self.assertEqual(self.balance(),3)
        self.assertEqual(CreditEntry.objects.count(),1)
        self.assertEqual(PaymentAttempt.objects.get(purchase=second).status,'pending')

    def test_bank_proof_normalized_and_different_receipt_cannot_change_approved_purchase(self):
        purchase=self.create();approve(self.actor,purchase.manual_payment.pk,self.proof(reference='۱۲۳۴-۵۶۷۸'))
        approve(self.actor,purchase.manual_payment.pk,self.proof(reference='12345678'))
        with self.assertRaises(APIError):approve(self.actor,purchase.manual_payment.pk,self.proof(reference='OTHER123'))
        self.assertEqual(self.balance(),3)

    def test_snapshot_survives_package_and_merchant_edits(self):
        purchase=self.create()
        MessagePackage.objects.filter(pk=self.package.pk).update(message_count=1000,price_toman=2000000,active=False)
        ManualPaymentSettings.objects.filter(pk=1).update(card_holder='فرد جدید',bank_name='بانک جدید',bale_username='other_support')
        data=purchase_data(purchase)
        self.assertEqual(data['amount_toman'],10000);self.assertEqual(data['card']['holder'],'پشتیبان آزمون');self.assertEqual(data['card']['bank_name'],'بانک آزمون')
        self.assertEqual(data['receipt_channels'][0]['url'],'https://ble.ir/test_support')
        approve(self.actor,purchase.manual_payment.pk,self.proof());self.assertEqual(self.balance(),3)

    def test_card_intent_idempotency_and_cross_method_open_checkout(self):
        key=uuid.uuid4();purchase=self.create(key)
        self.assertEqual(self.create(key).pk,purchase.pk)
        with self.assertRaises(APIError) as pending:self.create()
        self.assertEqual(pending.exception.code,'payment_reconciliation')
        gateway=self.post('/credit-purchases',{'package_id':self.package.pk,'package_revision':0},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(gateway.json()['error']['code'],'payment_reconciliation')
        self.assertEqual(PaymentAttempt.objects.count(),1)

    def test_cancellation_only_before_claim_and_rejection_never_mints_credit(self):
        purchase=self.create()
        self.assertEqual(self.post(f'/credit-purchases/{purchase.pk}/cancel-card',{}).json()['status'],'cancelled')
        with self.assertRaises(APIError):approve(self.actor,purchase.manual_payment.pk,self.proof())
        purchase=self.create();self.post(f'/credit-purchases/{purchase.pk}/receipt',{'receipt_sent':True})
        self.assertEqual(self.post(f'/credit-purchases/{purchase.pk}/cancel-card',{}).status_code,409)
        result=self.post(f'/manage/manual-payments/{purchase.manual_payment.pk}/reject',{'reason':'واریز در حساب تأیید نشد'},self.staff)
        self.assertEqual(result.json()['status'],'rejected');self.assertEqual(self.balance(),0)
        self.assertFalse(FinancialEvent.objects.exists())

    def test_admin_direct_grant_uses_same_ledger_proof_and_stable_key(self):
        data={**self.proof(),'account_id':Account.objects.get(user=self.user).pk,'package_id':self.package.pk,'package_revision':0}
        key=uuid.uuid4()
        for _ in range(2):
            result=self.post('/manage/manual-payments/grant',data,self.staff,HTTP_IDEMPOTENCY_KEY=str(key))
            self.assertEqual(result.status_code,200,result.content);self.assertEqual(result.json()['status'],'credited')
        self.assertEqual(self.balance(),3);self.assertEqual(CreditPurchase.objects.count(),1)
        result=self.post('/manage/manual-payments/grant',data,self.staff,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.json()['error']['code'],'receipt_used');self.assertEqual(CreditPurchase.objects.count(),1)

    def test_credit_capacity_or_suspended_account_rolls_back_approval(self):
        purchase=self.create()
        Account.objects.filter(user=self.user).update(suspended=True)
        with self.assertRaises(APIError):approve(self.actor,purchase.manual_payment.pk,self.proof())
        self.assertFalse(CreditEntry.objects.exists());self.assertFalse(FinancialEvent.objects.exists())
        self.assertEqual(PaymentAttempt.objects.get(purchase=purchase).status,'pending')
        purchase.refresh_from_db();self.assertIsNone(purchase.credited_at)

    def test_live_gift_profile_cannot_enable_paid_card_or_use_demo_credit(self):
        purchase=self.create()
        with override_settings(DEMO_MODE=False,PROVIDER_ENVIRONMENT='live',PROVIDER_NETWORK_MODE='external',LIVE_PROVIDERS_ENABLED=True,PROVIDER_DAILY_BUDGET_UNLIMITED=True):
            self.assertFalse(self.client.get('/api/v1/bootstrap').json()['payment_options']['card_enabled'])
            self.assertEqual(self.client.get(f'/api/v1/credit-purchases/{purchase.pk}').status_code,404)
            with self.assertRaises(APIError):self.create()
            with self.assertRaises(APIError):approve(self.actor,purchase.manual_payment.pk,self.proof())
        self.assertEqual(self.balance(),0)
        approve(self.actor,purchase.manual_payment.pk,self.proof())
        with override_settings(DEMO_MODE=False,PROVIDER_ENVIRONMENT='live'):
            with self.assertRaises(APIError):approve(self.actor,purchase.manual_payment.pk,self.proof())
        self.assertEqual(self.balance(),3)

    def test_manual_path_makes_no_gateway_or_sms_network_calls(self):
        with patch('core.packages.Zarinpal.request') as request,patch('core.packages.Zarinpal.verify') as verify:
            purchase=self.create();approve(self.actor,purchase.manual_payment.pk,self.proof())
            from .packages import verify_purchase
            verify_purchase(PaymentAttempt.objects.get(purchase=purchase).pk)
            request.assert_not_called();verify.assert_not_called()
        self.assertFalse(Outbox.objects.exists())

    def test_settings_revision_permissions_validation_and_safe_audit(self):
        values={'enabled':True,'card_number':CARD,'card_holder':'نام آزمون','bank_name':'بانک آزمون','bale_username':'@test_support','telegram_username':''}
        data={'values':values,'revision':0,'reason':'تنظیم کارت مقصد'}
        with self.assertRaises(APIError):save_settings(self.user,data)
        self.assertEqual(save_settings(self.actor,data)['values']['bale_username'],'test_support')
        with self.assertRaises(APIError):save_settings(self.actor,data)
        data['revision']=1
        for key,value in [('card_number','1111111111111111'),('bale_username','https://evil.test'),('telegram_username','@xx'),('enabled','yes')]:
            with self.subTest(key=key),self.assertRaises(APIError):save_settings(self.actor,{**data,'values':{**values,key:value}})
        audit=OperatorAudit.objects.get(action='manual_payment_settings')
        self.assertNotIn(CARD,str(audit.before)+str(audit.after))
        self.assertFalse(Client().get('/api/v1/bootstrap').json()['authenticated'])
        self.assertEqual(self.client.get('/api/v1/manage/manual-payment-settings').status_code,403)

    def test_bank_data_encrypted_at_rest_and_not_in_records_or_audit(self):
        purchase=self.create();approve(self.actor,purchase.manual_payment.pk,self.proof())
        with connection.cursor() as cursor:
            cursor.execute('SELECT card_number, confirmed_reference FROM core_manualpayment WHERE purchase_id=%s',[purchase.pk])
            card,reference=cursor.fetchone();self.assertNotIn(CARD,card);self.assertNotIn('BANK123456',reference)
        response=self.post('/manage/records/manual-payments',{},self.staff)
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['rows'][0]['record_id'],str(purchase.manual_payment.pk))
        records=response.content.decode()
        self.assertNotIn(CARD,records);self.assertNotIn('BANK123456',records)
        self.assertNotIn('BANK123456',str(list(OperatorAudit.objects.values('before','after'))))
        old_key=settings.PHONE_ENCRYPTION_KEY
        with override_settings(PHONE_ENCRYPTION_KEY=Fernet.generate_key().decode(),PHONE_ENCRYPTION_FALLBACK_KEYS=[old_key]):
            call_command('rotate_encryption',apply=True,stdout=StringIO())
            with override_settings(PHONE_ENCRYPTION_FALLBACK_KEYS=[]):
                self.assertEqual(ManualPaymentSettings.objects.get(pk=1).card_number,CARD)
                manual=ManualPayment.objects.get(purchase=purchase)
                self.assertEqual(manual.card_number,CARD);self.assertEqual(manual.confirmed_reference,'BANK123456')



class ManualPaymentConcurrencyTests(ManualFixture,TransactionTestCase):
    def test_concurrent_approvals_credit_once(self):
        if connection.vendor!='postgresql':self.skipTest('requires PostgreSQL row locks')
        purchase=self.create();manual_id=purchase.manual_payment.pk;actor_id=self.actor.pk;proof=self.proof()
        def run(_):
            connections.close_all()
            try:return str(approve(get_user_model().objects.get(pk=actor_id),manual_id,proof).pk)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(results,[str(purchase.pk)]*2);self.assertEqual(self.balance(),3)
        self.assertEqual((CreditEntry.objects.count(),FinancialEvent.objects.count()),(1,1))

    def test_concurrent_reused_bank_receipt_on_different_accounts_rolls_back_loser(self):
        if connection.vendor!='postgresql':self.skipTest('requires PostgreSQL unique-index contention')
        first=self.create()
        other_client=Client();other=self.authenticate('09901234561',other_client)
        Account.objects.filter(user=other).update(demo_sends_remaining=0)
        second=begin_purchase(other,{'package_id':self.package.pk,'package_revision':0,'payment_method':'card','wallet_consent':True,'wallet_terms_version':WALLET_TERMS_VERSION},uuid.uuid4())
        from threading import Barrier
        from .packages import _apply_verified
        barrier=Barrier(2)
        def synchronized(*args,**kwargs):
            barrier.wait(timeout=10)
            return _apply_verified(*args,**kwargs)
        actor_id=self.actor.pk;proof=self.proof()
        def run(identifier):
            connections.close_all()
            try:
                approve(get_user_model().objects.get(pk=actor_id),identifier,proof)
                return 'credited'
            except APIError as error:return error.code
            finally:connections.close_all()
        with patch('core.manual_payments._apply_verified',side_effect=synchronized),ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(run,[first.manual_payment.pk,second.manual_payment.pk]))
        self.assertCountEqual(results,['credited','receipt_used'])
        self.assertEqual(sum(Account.objects.filter(user__in=[self.user,other]).values_list('demo_sends_remaining',flat=True)),3)
        self.assertEqual((CreditEntry.objects.count(),FinancialEvent.objects.count()),(1,1))
        self.assertEqual(ManualPayment.objects.filter(status='approved').count(),1)
