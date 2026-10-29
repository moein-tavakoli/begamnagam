"""Staff-only provider credit observations, independent of send and spend paths."""
import json
import re
import socket
import ssl
import time
import urllib.error
import urllib.request
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from .management_api import staff_api
from .privacy import digest
from .services import APIError, limited

TIMEOUT = 4
MAX_BYTES = 16384
FRESH_SECONDS = 120
FAILURE_SECONDS = 30
STALE_SECONDS = 1800
PROVIDERS = {'kavenegar', 'gapgpt'}


class BalanceUnavailable(Exception):
    def __init__(self,reason='provider_unavailable'):
        self.reason=reason
        super().__init__(reason)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate_key')
        result[key]=value
    return result


def _read_json(request):
    deadline=time.monotonic()+TIMEOUT
    try:
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=TIMEOUT) as response:
            if response.status!=200 or response.geturl()!=request.full_url:
                raise BalanceUnavailable()
            if response.headers.get_content_type()!='application/json':
                raise BalanceUnavailable('invalid_response')
            content=bytearray()
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise BalanceUnavailable()
                stream=getattr(getattr(response,'fp',None),'raw',None)
                connection=getattr(stream,'_sock',None)
                if connection is not None:connection.settimeout(remaining)
                chunk=response.read1(min(4096,MAX_BYTES+1-len(content)))
                if time.monotonic()>=deadline:raise BalanceUnavailable()
                if not chunk:break
                content.extend(chunk)
                if len(content)>MAX_BYTES:raise BalanceUnavailable('invalid_response')
            value=json.loads(content,parse_float=Decimal,object_pairs_hook=_unique_object)
            if not isinstance(value,dict):raise BalanceUnavailable('invalid_response')
            return value
    except urllib.error.HTTPError as error:
        reason='access_denied' if error.code in {401,403} else 'provider_unavailable'
        error.close()
        raise BalanceUnavailable(reason) from None
    except BalanceUnavailable:
        raise
    except (OSError,ValueError,TypeError,AttributeError,socket.timeout,ssl.SSLError):
        # URLs contain the SMS key. Never expose/log exceptions or raw responses.
        raise BalanceUnavailable() from None


def _kavenegar_balance():
    request=urllib.request.Request('https://api.kavenegar.com/v1/'+settings.KAVENEGAR_API_KEY+'/account/info.json',
        headers={'Accept':'application/json','Accept-Encoding':'identity'},method='GET')
    value=_read_json(request)
    result,entry=value.get('return'),value.get('entries')
    if not isinstance(result,dict) or type(result.get('status')) is not int:
        raise BalanceUnavailable('invalid_response')
    if result['status']!=200:
        raise BalanceUnavailable('access_denied' if result['status'] in {401,403,407} else 'provider_unavailable')
    if not isinstance(entry,dict) or type(entry.get('remaincredit')) is not int or abs(entry['remaincredit'])>10**18:
        raise BalanceUnavailable('invalid_response')
    return str(entry['remaincredit'])


def _record(provider,status,*,amount=None,observed_at=None,reason=None):
    return {'provider':provider,'status':status,'amount':amount,'currency':'IRR' if provider=='kavenegar' else None,
        'observed_at':observed_at,'checked_at':timezone.now().isoformat(),'reason':reason}


def observe(provider):
    if provider not in PROVIDERS:raise APIError('not_found','سرویس پیدا نشد.',404)
    key=settings.KAVENEGAR_API_KEY if provider=='kavenegar' else settings.GAPGPT_API_KEY
    if not key or not isinstance(key,str):return _record(provider,'not_configured',reason='missing_key')
    if (settings.DEMO_MODE or settings.PROVIDER_NETWORK_MODE!='external' or not settings.LIVE_PROVIDERS_ENABLED):
        return _record(provider,'disabled',reason='network_disabled')
    if provider=='gapgpt':
        # The official wallet uses a web login. No API-key balance contract was
        # found; do not probe guessed endpoints or reuse web-session credentials.
        return _record(provider,'unsupported',reason='api_not_documented')
    if settings.KAVENEGAR_BASE_URL!='https://api.kavenegar.com' or not re.fullmatch(r'[A-Za-z0-9_-]{1,256}',key):
        return _record(provider,'not_configured',reason='invalid_configuration')
    if settings.SMS_BACKEND!='kavenegar' and settings.OTP_BACKEND!='kavenegar':
        return _record(provider,'disabled',reason='provider_disabled')
    namespace='provider-balance:v1:'+digest(provider+':'+key)
    try:
        previous=cache.get(namespace)
        if previous is not None:return previous
        good=cache.get(namespace+':last-good')
        if not cache.add(namespace+':inflight',True,timeout=TIMEOUT+4):
            return _record(provider,'stale' if good else 'updating',amount=good['amount'] if good else None,
                observed_at=good['observed_at'] if good else None,reason='refresh_in_progress')
    except Exception:
        return _record(provider,'unavailable',reason='cache_unavailable')
    try:
        amount=_kavenegar_balance()
        result=_record(provider,'available',amount=amount,observed_at=timezone.now().isoformat())
    except BalanceUnavailable as error:
        result=_record(provider,'stale' if good else 'unavailable',amount=good['amount'] if good else None,
            observed_at=good['observed_at'] if good else None,reason=error.reason)
    try:
        if result['status']=='available':cache.set(namespace+':last-good',result,timeout=STALE_SECONDS)
        cache.set(namespace,result,timeout=FRESH_SECONDS if result['status']=='available' else FAILURE_SECONDS)
        # The short inflight lease expires by itself; no delayed worker may
        # accidentally delete another request's lease after a network failure.
    except Exception:
        pass
    return result


@staff_api(['GET'],'core.view_operations')
def balance(request,provider):
    limited('provider-balance-read',str(request.user.pk),30,60)
    return observe(provider)
