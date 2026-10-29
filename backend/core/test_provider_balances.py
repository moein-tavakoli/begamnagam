import io
import json
import urllib.error
from email.message import Message
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from . import provider_balances as balances
from .models import FinancialEvent, Outbox, RewriteUsage
from .privacy import digest

SECRET='synthetic-private-sms-key'
PROFILE=dict(DEMO_MODE=False,PROVIDER_NETWORK_MODE='external',LIVE_PROVIDERS_ENABLED=True,
    SMS_BACKEND='kavenegar',OTP_BACKEND='kavenegar',KAVENEGAR_BASE_URL='https://api.kavenegar.com',
    KAVENEGAR_API_KEY=SECRET,GAPGPT_API_KEY='synthetic-private-gapgpt-key')


class Response(io.BytesIO):
    def __init__(self,value,*,status=200,content_type='application/json',url=None):
        super().__init__(json.dumps(value).encode() if isinstance(value,dict) else value)
        self.status=status;self.headers=Message();self.headers['Content-Type']=content_type
        self.url=url or 'https://api.kavenegar.com/v1/'+SECRET+'/account/info.json'
    def geturl(self):return self.url


@override_settings(**PROFILE)
class BalanceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.actor=get_user_model().objects.create_user('balance-admin',is_staff=True)
        self.actor.user_permissions.add(Permission.objects.get(codename='view_operations'))
        self.client.force_login(self.actor)
    def namespace(self,key=SECRET):return 'provider-balance:v1:'+digest('kavenegar:'+key)
    def expire_observation(self):
        cache.delete(self.namespace());cache.delete(self.namespace()+':inflight')
    def info(self,value):return {'return':{'status':200},'entries':{'remaincredit':value,'account':'private-account-not-for-ui'}}

    def test_ops_permission_required_before_any_provider_request(self):
        endpoint='/api/v1/manage/provider-balances/kavenegar'
        with patch('core.provider_balances._read_json') as read:
            self.assertEqual(Client().get(endpoint).status_code,401)
            ordinary=get_user_model().objects.create_user('member');self.client.force_login(ordinary)
            self.assertEqual(self.client.get(endpoint).status_code,403)
            ordinary.is_staff=True;ordinary.save();self.client.force_login(ordinary)
            self.assertEqual(self.client.get(endpoint).status_code,403);read.assert_not_called()

    def test_api_returns_only_the_observed_amount_and_never_secrets_or_account_details(self):
        with patch('core.provider_balances._read_json',return_value=self.info(15000001)) as read:
            response=self.client.get('/api/v1/manage/provider-balances/kavenegar')
        self.assertEqual(response.status_code,200,response.content)
        result=response.json();self.assertEqual((result['status'],result['amount'],result['currency']),('available','15000001','IRR'))
        self.assertIsNotNone(result['observed_at']);self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertNotIn(SECRET,response.content.decode());self.assertNotIn('private-account',response.content.decode())
        self.assertFalse(FinancialEvent.objects.exists());self.assertFalse(Outbox.objects.exists());self.assertFalse(RewriteUsage.objects.exists())
        request=read.call_args.args[0];self.assertEqual(request.get_method(),'GET');self.assertIsNone(request.data)
        self.assertEqual(request.full_url,'https://api.kavenegar.com/v1/'+SECRET+'/account/info.json')

    def test_gapgpt_does_not_probe_undocumented_endpoints_or_confuse_key_quota_with_wallet(self):
        with patch('core.provider_balances._read_json') as read:
            result=self.client.get('/api/v1/manage/provider-balances/gapgpt').json()
        self.assertEqual(result['status'],'unsupported');self.assertIsNone(result['amount']);self.assertIsNone(result['currency']);read.assert_not_called()

    def test_default_disabled_missing_credentials_and_altered_hosts_make_no_network_request(self):
        for override in [dict(DEMO_MODE=True),dict(PROVIDER_NETWORK_MODE='disabled'),dict(LIVE_PROVIDERS_ENABLED=False),dict(KAVENEGAR_API_KEY=''),dict(KAVENEGAR_API_KEY='bad/key'),dict(KAVENEGAR_BASE_URL='https://evil.test'),dict(SMS_BACKEND='console',OTP_BACKEND='demo')]:
            with self.subTest(fields=list(override)),override_settings(**override),patch('core.provider_balances._read_json') as read:
                result=balances.observe('kavenegar');self.assertIsNone(result['amount']);self.assertIn(result['status'],['disabled','not_configured']);read.assert_not_called()

    def test_zero_and_large_integer_balances_remain_exact_and_errors_never_become_zero(self):
        for amount in [0,1,-1,999999999999999999]:
            cache.clear()
            with patch('core.provider_balances._read_json',return_value=self.info(amount)):
                result=balances.observe('kavenegar');self.assertEqual(result['status'],'available');self.assertEqual(result['amount'],str(amount))
        cache.clear()
        with patch('core.provider_balances._read_json',side_effect=balances.BalanceUnavailable()):
            result=balances.observe('kavenegar');self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['amount'])

    def test_bad_or_ambiguous_money_is_not_reported_as_a_balance(self):
        for value in [True,1.5,'1000',None,10**19]:
            cache.clear()
            with patch('core.provider_balances._read_json',return_value=self.info(value)):
                self.assertEqual(balances.observe('kavenegar')['status'],'unavailable')
        for data in [{'return':{'status':200},'entries':[{'remaincredit':100}]},{'return':{'status':403,'message':SECRET},'entries':None}]:
            cache.clear()
            with patch('core.provider_balances._read_json',return_value=data):
                result=balances.observe('kavenegar');self.assertIsNone(result['amount']);self.assertNotIn(SECRET,str(result))

    def test_short_cache_is_shared_and_rotating_keys_does_not_reuse_another_accounts_balance(self):
        with patch('core.provider_balances._read_json',return_value=self.info(100)) as read:
            first=balances.observe('kavenegar');second=balances.observe('kavenegar');self.assertEqual(first,second);read.assert_called_once()
        with override_settings(KAVENEGAR_API_KEY='different-synthetic-key'),patch('core.provider_balances._read_json',return_value=self.info(200)) as read:
            self.assertEqual(balances.observe('kavenegar')['amount'],'200');read.assert_called_once()

    def test_outage_uses_a_clearly_stale_observation_with_its_original_timestamp(self):
        with patch('core.provider_balances._read_json',return_value=self.info(12345)):first=balances.observe('kavenegar')
        self.expire_observation()
        with patch('core.provider_balances._read_json',side_effect=balances.BalanceUnavailable()):
            stale=balances.observe('kavenegar')
        self.assertEqual(stale['status'],'stale');self.assertEqual(stale['amount'],'12345');self.assertEqual(stale['observed_at'],first['observed_at'])
        self.expire_observation();cache.delete(self.namespace()+':last-good')
        with patch('core.provider_balances._read_json',side_effect=balances.BalanceUnavailable()):
            result=balances.observe('kavenegar');self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['amount'])

    def test_inflight_and_cache_failure_do_not_multiply_network_calls(self):
        cache.add(self.namespace()+':inflight',True,timeout=8)
        with patch('core.provider_balances._read_json') as read:
            self.assertEqual(balances.observe('kavenegar')['status'],'updating');read.assert_not_called()
        cache.clear()
        with patch('core.provider_balances.cache.get',side_effect=RuntimeError('private cache error')),patch('core.provider_balances._read_json') as read:
            result=balances.observe('kavenegar');self.assertEqual(result['reason'],'cache_unavailable');read.assert_not_called()

    def test_http_is_get_bounded_json_without_redirects(self):
        opener=Mock();opener.open.return_value=Response(self.info(123))
        with patch('core.provider_balances.urllib.request.build_opener',return_value=opener):
            self.assertEqual(balances.observe('kavenegar')['amount'],'123')
        self.assertEqual(opener.open.call_args.kwargs['timeout'],4)
        self.assertIsNone(balances.NoRedirect().redirect_request(None,None,302,'Found',{},'https://evil.test'))

    def test_transport_and_schema_failures_hide_key_bearing_urls_and_raw_response(self):
        cases=[Response(self.info(123),url='https://evil.test'),Response(self.info(123),content_type='text/html'),Response(b'x'*(balances.MAX_BYTES+1)),Response(b'{"return":{"status":200},"entries":{"remaincredit":1,"remaincredit":9}}')]
        for response in cases:
            cache.clear();opener=Mock();opener.open.return_value=response
            with patch('core.provider_balances.urllib.request.build_opener',return_value=opener):
                result=self.client.get('/api/v1/manage/provider-balances/kavenegar')
                self.assertIsNone(result.json()['amount']);self.assertNotIn(SECRET,result.content.decode())
        cache.clear();opener=Mock();opener.open.side_effect=urllib.error.HTTPError('https://api.kavenegar.com/'+SECRET,403,'secret '+SECRET,{},io.BytesIO(SECRET.encode()))
        with patch('core.provider_balances.urllib.request.build_opener',return_value=opener):
            result=self.client.get('/api/v1/manage/provider-balances/kavenegar').json()
            self.assertEqual(result['reason'],'access_denied');self.assertNotIn(SECRET,str(result))

    def test_unknown_provider_cannot_turn_this_endpoint_into_a_generic_proxy(self):
        with patch('core.provider_balances._read_json') as read:
            self.assertEqual(self.client.get('/api/v1/manage/provider-balances/other').status_code,404);read.assert_not_called()
