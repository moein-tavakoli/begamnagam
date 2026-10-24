import json
from pathlib import Path
import time
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.test import Client, override_settings
from django.utils import timezone
from core.models import Order, Outbox, PaymentAttempt, MessageDelivery, FinancialEvent, Refund, RecipientState, AbuseReport, OperatorAudit, SpendBudget, SpendReservation
from core.provider_fixture import LocalProviders
from core.provider_delivery import reconcile_delivery
from core.provider_services import process_refund
from core.safety import operator_action, refresh_alerts


class Command(BaseCommand):
    help = 'Run synthetic pilot on a new isolated pilot DB with loopback vendor contracts. No real volunteers/providers.'

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        if not settings.DEMO_MODE or not connection.settings_dict['NAME'].startswith('begamnagam_pilot_') or Order.objects.exists() or not settings.CELERY_TASK_ALWAYS_EAGER:
            raise CommandError('Requires an empty isolated demo pilot DB and eager tasks')
        scenarios=[]
        with LocalProviders() as fixture, override_settings(PROVIDER_NETWORK_MODE='local',
            KAVENEGAR_BASE_URL=fixture.url, ZARINPAL_BASE_URL=fixture.url, ZARINPAL_REDIRECT_BASE=fixture.url,
            KAVENEGAR_API_KEY='synthetic-key', KAVENEGAR_OTP_TEMPLATE='synthetic', ZARINPAL_MERCHANT_ID='synthetic-merchant',
            SMS_BACKEND='kavenegar', OTP_BACKEND='kavenegar', PAYMENT_BACKEND='zarinpal',
            PROVIDER_ENVIRONMENT='sandbox', PROVIDER_DAILY_BUDGET_RIAL=1000000, OTP_MAX_COST_RIAL=500,
            SMS_MAX_COST_RIAL=2000, ALLOWED_HOSTS=['testserver'], SENDING_WINDOW_ENABLED=False,
            PILOT_POSITIVE_ONLY=False, APP_BASE_URL='http://localhost:8012'):
            def call(client,path,data=None,key=None,status=200):
                if data is None:
                    response=client.get('/api/v1'+path)
                else:
                    response=client.post('/api/v1'+path,data=json.dumps(data),content_type='application/json',HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value,**({'HTTP_IDEMPOTENCY_KEY':key} if key else {}))
                if response.status_code != status:
                    raise CommandError('Synthetic scenario failed at '+path.split('?')[0]+'; response content withheld')
                return response.json() if response.headers.get('Content-Type','').startswith('application/json') else {}

            def login(phone):
                client=Client(enforce_csrf_checks=True)
                call(client,'/bootstrap')
                challenge=call(client,'/auth/request-otp',{'phone':phone})
                assert 'debug_code' not in challenge
                call(client,'/auth/verify-otp',{'challenge_id':challenge['challenge_id'],'code':fixture.codes[phone]})
                return client

            def make_order(client,category,phone):
                quote=call(client,'/messages/preview',{'category':category,'text':'یک پیام مصنوعی محترمانه برای آزمون محلی','recipient_phone':phone})
                key=str(uuid.uuid4())
                payload={'preview_id':quote['preview_id'],'recipient_phone':phone,'consent':True,'terms_version':quote['terms_version']}
                order=call(client,'/orders',payload,key=key)
                assert call(client,'/orders',payload,key=key)['id']==order['id']
                attempt=call(client,'/orders/'+order['id']+'/payments',{},key=str(uuid.uuid4()))
                payment=PaymentAttempt.objects.get(pk=attempt['attempt_id'])
                return order,payment,quote

            def callback(client,payment):
                call(client,'/payments/return/zarinpal?Authority='+payment.authority+'&Status=OK',status=302)

            records=[]
            categories=['appreciation','encouragement','congratulations','body','breath','noise','shared_space']
            for i,category in enumerate(categories):
                client=login('0993'+str(i).zfill(7))
                order,payment,quote=make_order(client,category,'0994'+str(i).zfill(7))
                callback(client,payment) # A forged OK while still unpaid cannot dispatch.
                assert not Outbox.objects.filter(order_id=order['id']).exists()
                fixture.payments[payment.authority]['status']='PAID'
                callback(client,payment)
                callback(client,payment) # Duplicate callback does not duplicate capture.
                delivery=MessageDelivery.objects.get(order_id=order['id'])
                assert delivery.status=='accepted'
                fixture.messages[str(delivery.local_id)]['status']=10
                records.append((client,order,payment,quote,delivery.pk))
            self.stdout.write('Seven provider-contract journeys accepted. Waiting for the real30s reconciliation interval...')
            time.sleep(31)
            for client,order,payment,quote,delivery_id in records:
                reconcile_delivery(delivery_id)
                assert Order.objects.get(pk=order['id']).status=='delivered'
                scenarios.append({'name':'reviewed_topic_'+Order.objects.get(pk=order['id']).category,'result':'PASS'})

            public=Client(enforce_csrf_checks=True)
            call(public,'/bootstrap')
            token=records[0][3]['full_sms'].split('/r#')[1]
            before=call(public,'/recipient/actions/inspect',{'token':token})
            assert set(before)=={'active','can_report'}
            report={'token':token,'reason':'unwanted','details':'گزارش مصنوعی پایلوت محلی'}
            receipt=call(public,'/recipient/actions/report',report)
            assert call(public,'/recipient/actions/report',report)==receipt
            assert AbuseReport.objects.count()==1
            scenarios.append({'name':'anonymous_report_deduplicated_and_receipt_stopped','result':'PASS'})

            # Keep the transaction open until preference stop commits; no SMS can
            # be dispatched from the on-commit outbox before this point.
            sender=login('09930000008')
            receiver_phone='09940000008'
            race_order,payment,_=make_order(sender,'appreciation',receiver_phone)
            fixture.payments[payment.authority]['status']='PAID'
            receiver=login(receiver_phone)
            sends_before=fixture.calls.count('send')
            with transaction.atomic():
                callback(sender,payment)
                call(receiver,'/preferences',{'blocked':True})
            assert Order.objects.get(pk=race_order['id']).status=='cancelled'
            assert fixture.calls.count('send')==sends_before
            refund=Refund.objects.get(payment=payment)
            process_refund(refund.pk)
            assert Refund.objects.get(pk=refund.pk).status=='refunded'
            scenarios.append({'name':'stop_between_payment_and_dispatch_refunds_without_sms','result':'PASS'})

            actor=get_user_model().objects.create_superuser(username='synthetic-operator',password=None)
            operator_action(actor,'halt','global','synthetic incident exercise')
            operator_action(actor,'resume','global','synthetic incident resolved')
            assert OperatorAudit.objects.filter(actor=actor).count()==2
            scenarios.append({'name':'audited_emergency_stop_resume','result':'PASS'})
            with override_settings(PILOT_POSITIVE_ONLY=True):
                call(sender,'/messages/preview',{'category':'body','text':'یک یادآوری دوستانه'},status=422)
            scenarios.append({'name':'positive_only_pilot_policy_enforced','result':'PASS'})
            call(sender,'/messages/preview',{'category':'appreciation','text':'می کشمت'},status=422)
            scenarios.append({'name':'unsafe_input_rejected_before_persistence','result':'PASS'})
            captures=FinancialEvent.objects.filter(kind='payment').count()
            refunds=FinancialEvent.objects.filter(kind='refund').count()
            assert captures==8 and refunds==1 and fixture.calls.count('send')==7
            report={'kind':'synthetic_app_client_and_loopback_vendor_HTTP','human_volunteers':0,'external_provider_calls':0,
                'live_money_moved':False,'scenarios':scenarios,'passed':all(s['result']=='PASS' for s in scenarios),
                'captures':captures,'refunds':refunds,'vendor_content_submissions':fixture.calls.count('send'),
                'gross_provider_budget_reserved_rial':SpendBudget.objects.get().reserved_rial,
                'observed_simulated_provider_cost_rial':sum(r.actual_rial or 0 for r in SpendReservation.objects.all()),
                'open_synthetic_reports':AbuseReport.objects.filter(status='open').count(),
                'human_pilot_acceptance':'DEFERRED_BY_OWNER','metrics':refresh_alerts()}
            Path(options['output']).parent.mkdir(parents=True,exist_ok=True)
            Path(options['output']).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            self.stdout.write(self.style.SUCCESS('Synthetic pilot PASS. Human pilot was not run.'))
