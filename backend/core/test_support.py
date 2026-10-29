import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from . import support, tests as fixture
from .models import Account, CreditEntry, FinancialEvent, OperatorAudit, Outbox, RequestLimit, SupportConversation, SupportMessage
from .services import APIError


class SupportFixture:
    post, authenticate = fixture.APITestCase.post, fixture.APITestCase.authenticate
    def setUp(self):
        fixture.APITestCase.setUp(self)
        self.user=self.authenticate(free_sends=3)
        self.manager=get_user_model().objects.create_user('support-admin',is_staff=True)
        self.staff=Client();self.staff.force_login(self.manager)
    def send(self,text='سلام؛ دربارهٔ بستهٔ پیام سؤال دارم',key=None):
        return support.send(self.user,{'text':text},key or uuid.uuid4())
    def reply(self,thread,text='سلام، شناسهٔ خرید را بفرست',sequence=None,key=None):
        return support.send(self.manager,{'text':text,'reply_to_sequence':sequence or thread.last_customer_sequence},key or uuid.uuid4(),thread_id=thread.pk,staff=True)


class SupportTests(SupportFixture,TestCase):
    def test_staff_login_is_not_customer_phone_auth_and_members_cannot_read_admin_inbox(self):
        self.assertEqual(self.staff.get('/api/v1/support/messages').status_code,401)
        self.assertEqual(self.client.get('/api/v1/manage/support/summary').status_code,403)
        self.assertEqual(self.post('/manage/support/inbox',{}).status_code,403)
        self.assertEqual(Client().get('/api/v1/support/summary').status_code,401)
        self.assertEqual(self.staff.get('/api/v1/manage/support/summary').status_code,200)
        self.assertEqual(self.post('/manage/support/inbox',{},self.staff).status_code,200)
        self.assertFalse(SupportConversation.objects.exists())

    def test_empty_get_creates_no_thread_and_sending_never_changes_message_credits_or_finance(self):
        self.assertEqual(self.client.get('/api/v1/support/messages').json()['messages'],[])
        self.assertFalse(SupportConversation.objects.exists())
        result=self.post('/support/messages',{'text':'راهنمایی می‌خواهم'},HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
        self.assertEqual(result.status_code,200,result.content)
        self.assertEqual(result.json()['message']['role'],'customer')
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,3)
        self.assertFalse(Outbox.objects.exists());self.assertFalse(CreditEntry.objects.exists());self.assertFalse(FinancialEvent.objects.exists())

    def test_thread_is_private_and_owner_cannot_forge_another_thread_or_staff_identity(self):
        result=self.send();thread=SupportConversation.objects.get()
        other=Client();self.authenticate('09901234561',other)
        self.assertEqual(other.get('/api/v1/support/messages').json()['messages'],[])
        self.assertEqual(self.post(f'/manage/support/{thread.pk}/messages',{'text':'forged','reply_to_sequence':1},other,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,403)
        self.assertEqual(self.post('/support/messages',{'text':'fake','role':'staff','thread_id':str(thread.pk)},other,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,422)
        self.assertEqual(SupportMessage.objects.count(),1)
        self.assertEqual(self.post('/support/read',{'through_sequence':1},other).status_code,404)
        self.assertEqual(self.client.get('/api/v1/support/messages').json()['messages'][0]['id'],result['message']['id'])

    def test_any_active_staff_can_reply_without_additional_role_and_identity_stays_generic(self):
        self.send();thread=SupportConversation.objects.get();reply=self.reply(thread)
        result=self.client.get('/api/v1/support/messages').json()
        self.assertEqual(result['messages'][-1]['role'],'staff')
        self.assertNotIn('support-admin',str(result));self.assertNotIn('author',str(result));self.assertNotIn('client_key',result['messages'][-1])
        self.assertEqual(support.customer_summary(self.user)['unread_count'],1)
        other=get_user_model().objects.create_user('another-admin',is_staff=True)
        current_identity=self.staff.get('/api/v1/manage/session').json()['session_identity']
        other_client=Client();other_client.force_login(other)
        self.assertNotEqual(current_identity,other_client.get('/api/v1/manage/session').json()['session_identity'])
        support.send(other,{'text':'پاسخ تکمیلی','reply_to_sequence':1},uuid.uuid4(),thread_id=thread.pk,staff=True)
        self.assertEqual(SupportMessage.objects.filter(role='staff').count(),2)
        self.manager.is_active=False
        with self.assertRaises(APIError):self.reply(thread)

    def test_csrf_required_for_customer_admin_send_read_inbox_and_close(self):
        self.send();thread=SupportConversation.objects.get()
        for actor,paths in [(self.user,[('/support/messages',{'text':'سلام'}),('/support/read',{'through_sequence':1})]),(self.manager,[('/manage/support/inbox',{}),(f'/manage/support/{thread.pk}/messages',{'text':'پاسخ','reply_to_sequence':1}),(f'/manage/support/{thread.pk}/read',{'through_sequence':1}),(f'/manage/support/{thread.pk}/close',{'last_sequence':1})])]:
            csrf=Client(enforce_csrf_checks=True);csrf.force_login(actor)
            for path,data in paths:self.assertEqual(self.post(path,data,csrf).status_code,403)
        self.assertEqual(SupportMessage.objects.count(),1)

    def test_only_plain_text_and_bounded_length_are_accepted(self):
        for data in ({'text':''},{'text':'x'*2001},{'text':['bad']},{'text':'\u200c\u200c'},{'text':'bad\x00text'},{'text':'bad\u202etext'},{'text':'سلام','file':'data:image/png'}, {'text':'hi','attachment_url':'https://evil.test'}):
            with self.subTest(data_type=type(data.get('text'))):
                self.assertEqual(self.post('/support/messages',data,HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())).status_code,422)
        self.assertEqual(self.client.post('/api/v1/support/messages',{'text':'سلام'}).status_code,415)
        self.assertFalse(SupportMessage.objects.exists())
        text='<script>alert("x")</script>\nپیام با نیم‌فاصله'
        result=self.send(text);self.assertEqual(result['message']['text'],text)

    def test_retry_key_is_bound_to_author_and_exact_normalized_text(self):
        key=uuid.uuid4();first=self.send(' سلام\r\nپشتیبانی ',key);again=self.send('سلام\nپشتیبانی',key)
        self.assertEqual(first['message']['id'],again['message']['id']);self.assertEqual(SupportMessage.objects.count(),1)
        with self.assertRaises(APIError) as conflict:self.send('پیام متفاوت',key)
        self.assertEqual(conflict.exception.code,'idempotency_conflict')
        thread=SupportConversation.objects.get();reply_key=uuid.uuid4()
        first=self.reply(thread,key=reply_key);again=self.reply(thread,key=reply_key)
        self.assertEqual(first['message']['id'],again['message']['id']);self.assertEqual(SupportMessage.objects.count(),2)

    def test_viewing_is_not_answering_and_badge_clears_only_after_reply_and_read(self):
        self.send();thread=SupportConversation.objects.get()
        self.assertEqual(support.staff_summary(self.manager),{'attention_count':1,'waiting_count':1})
        self.staff.get(f'/api/v1/manage/support/{thread.pk}/messages')
        self.assertEqual(support.staff_summary(self.manager)['waiting_count'],1)
        self.post(f'/manage/support/{thread.pk}/read',{'through_sequence':1},self.staff)
        self.assertEqual(support.staff_summary(self.manager)['attention_count'],1)
        self.reply(thread)
        self.assertEqual(support.staff_summary(self.manager),{'attention_count':0,'waiting_count':0})
        self.assertEqual(support.customer_summary(self.user)['unread_count'],1)
        self.post('/support/read',{'through_sequence':2});self.assertEqual(support.customer_summary(self.user)['unread_count'],0)
        self.post('/support/read',{'through_sequence':0});self.assertEqual(SupportConversation.objects.get().customer_read_sequence,2)
        self.assertEqual(self.post('/support/read',{'through_sequence':99}).status_code,422)

    def test_stale_admin_reply_does_not_answer_new_customer_message(self):
        self.send('سؤال اول');old=SupportConversation.objects.get();self.send('سؤال تازه')
        self.reply(old,sequence=1)
        current=SupportConversation.objects.get()
        self.assertEqual(current.last_customer_sequence,2);self.assertEqual(current.answered_customer_sequence,1)
        self.assertTrue(support.thread_data(current)['needs_reply'])
        self.assertEqual(support.staff_summary(self.manager)['waiting_count'],1)

    def test_admin_close_requires_current_answered_thread_and_new_customer_message_reopens(self):
        self.send();thread=SupportConversation.objects.get()
        with self.assertRaises(APIError):support.close(self.manager,thread.pk,{'last_sequence':1})
        self.reply(thread);thread.refresh_from_db()
        with self.assertRaises(APIError):support.close(self.manager,thread.pk,{'last_sequence':1})
        support.close(self.manager,thread.pk,{'last_sequence':2})
        self.assertEqual(SupportConversation.objects.get().status,'closed')
        self.send('سؤال دیگری هم دارم');self.assertEqual(SupportConversation.objects.get().status,'open')
        self.assertEqual(support.staff_summary(self.manager)['waiting_count'],1)

    def test_customer_send_rate_limit_and_retries_do_not_spend_extra_slots(self):
        RequestLimit.objects.create(scope='support-customer-send',maximum=1,window_seconds=60)
        key=uuid.uuid4();self.send(key=key);self.send(key=key)
        with self.assertRaises(APIError) as caught:self.send('پیام تازه')
        self.assertEqual(caught.exception.code,'rate_limited');self.assertEqual(SupportMessage.objects.count(),1)

    def test_pagination_and_private_inbox_search_have_deterministic_order(self):
        RequestLimit.objects.create(scope='support-customer-send',maximum=100,window_seconds=60)
        for i in range(55):self.send(f'پیام شماره {i}')
        result=self.client.get('/api/v1/support/messages').json()
        self.assertEqual([m['sequence'] for m in result['messages']],list(range(6,56)))
        self.assertTrue(result['has_older'])
        previous=self.client.get('/api/v1/support/messages?before=6').json()
        self.assertEqual([m['sequence'] for m in previous['messages']],list(range(1,6)))
        self.assertFalse(previous['has_older'])
        result=self.post('/manage/support/inbox',{'query':'09123456789','filter':'all'},self.staff)
        self.assertEqual(result.json()['total'],1);self.assertNotIn('09123456789',result.content.decode())
        self.assertNotIn('پیام شماره',result.content.decode())
        account=Account.objects.get(user=self.user)
        from .privacy import DIGITS
        persian=str(account.pk).translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
        self.assertEqual(self.post('/manage/support/inbox',{'query':persian,'filter':'all'},self.staff).json()['total'],1)
        for data in ({'page':0},{'page':True},{'filter':'invalid'},{'filter':[]},{'query':[]},{'phone':'secret'}):
            self.assertEqual(self.post('/manage/support/inbox',data,self.staff).status_code,422)

    def test_ciphertext_rotation_and_audit_never_store_plain_support_text(self):
        text='متن خصوصی مخصوص آزمون پشتیبانی';self.send(text);thread=SupportConversation.objects.get();self.reply(thread,'پاسخ خصوصی آزمون')
        with connection.cursor() as cursor:
            cursor.execute('SELECT text FROM core_supportmessage');rows=cursor.fetchall()
        self.assertTrue(all(row[0].startswith('enc:v1:') for row in rows));self.assertNotIn(text,str(rows))
        self.assertNotIn(text,str(list(OperatorAudit.objects.values('before','after','reason'))))
        previous=settings.PHONE_ENCRYPTION_KEY
        with override_settings(PHONE_ENCRYPTION_KEY=Fernet.generate_key().decode(),PHONE_ENCRYPTION_FALLBACK_KEYS=[previous]):
            call_command('rotate_encryption',apply=True,stdout=StringIO())
            with override_settings(PHONE_ENCRYPTION_FALLBACK_KEYS=[]):self.assertEqual(SupportMessage.objects.first().text,text)

    def test_retention_redacts_old_or_deleted_account_text_without_touching_credits(self):
        first=self.send();self.send('پیام تازه')
        SupportMessage.objects.filter(pk=first['message']['id']).update(created_at=timezone.now()-timedelta(days=91))
        call_command('prune_private_data',dry_run=True,stdout=StringIO())
        self.assertTrue(SupportMessage.objects.get(pk=first['message']['id']).text)
        call_command('prune_private_data',stdout=StringIO())
        old=SupportMessage.objects.get(pk=first['message']['id']);self.assertEqual(old.text,'');self.assertIsNotNone(old.redacted_at)
        self.assertEqual(SupportMessage.objects.exclude(pk=old.pk).get().text,'پیام تازه')
        Account.objects.filter(user=self.user).update(deletion_requested_at=timezone.now()-timedelta(days=31))
        call_command('prune_private_data',stdout=StringIO())
        self.assertFalse(SupportMessage.objects.exclude(text='').exists())
        self.assertEqual(Account.objects.get(user=self.user).free_sends_remaining,3)

    def test_presence_reports_only_a_staff_member_actively_viewing_support(self):
        self.assertFalse(support.customer_summary(self.user)['staff_online'])
        support.staff_summary(self.manager);self.assertFalse(support.customer_summary(self.user)['staff_online'])
        support.inbox(self.manager,{});self.assertTrue(support.customer_summary(self.user)['staff_online'])


class SupportConcurrencyTests(SupportFixture,TransactionTestCase):
    def test_same_key_first_messages_create_one_thread_and_message(self):
        if connection.vendor!='postgresql':self.skipTest('requires PostgreSQL locking')
        actor_id=self.user.pk;key=uuid.uuid4()
        def send(_):
            connections.close_all()
            try:return support.send(get_user_model().objects.get(pk=actor_id),{'text':'پیام هم‌زمان آزمون'},key)['message']['id']
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(send,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(SupportMessage.objects.count(),1);self.assertEqual(SupportConversation.objects.count(),1)
        self.assertEqual(SupportConversation.objects.get().last_sequence,1)

    def test_different_keys_commit_contiguous_sequences(self):
        if connection.vendor!='postgresql':self.skipTest('requires PostgreSQL locking')
        actor_id=self.user.pk
        def send(i):
            connections.close_all()
            try:return support.send(get_user_model().objects.get(pk=actor_id),{'text':f'پیام هم‌زمان {i}'},uuid.uuid4())['message']['sequence']
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(send,range(3)))
        self.assertEqual(sorted(results),[1,2,3]);self.assertEqual(SupportConversation.objects.get().last_sequence,3)
