"""An exact-IP exception for aggregate monitoring, never an auth session."""
import ipaddress
import json

from django.conf import settings
from django.db import transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.vary import vary_on_cookie

from .input_digits import ascii_digits
from .management_api import staff_api
from .models import MonitoringAccessSettings, OperatorAudit
from .privacy import digest
from .services import APIError, api
from .views import body


def _address(value):
    if not isinstance(value, str) or not value or len(value) > 45 or '%' in value:
        raise ValueError('invalid_ip')
    parsed = ipaddress.ip_address(value)
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped:
        parsed = parsed.ipv4_mapped
    return parsed


def _client_address(value):
    address = _address(value)
    proxies = {_address(ip) for ip in getattr(settings, 'TRUSTED_CLIENT_PROXY_IPS', ())}
    if (address.is_loopback or address.is_unspecified or address.is_multicast
            or address.is_link_local or address.is_reserved or address in proxies):
        raise ValueError('not_client_ip')
    return str(address)


def client_address(request):
    # A forwarded request must have passed our proxy-chain verifier. Never use
    # X-Real-IP, Forwarded, X-Verified-Client-IP or XFF itself as a credential.
    if ('HTTP_X_FORWARDED_FOR' in request.META
            and not getattr(request, 'verified_proxy_client_ip', None)):
        return None
    try:
        return _client_address(request.META.get('REMOTE_ADDR', ''))
    except ValueError:
        return None


def can_monitor(request):
    user = request.user
    if user.is_authenticated and user.is_active and user.is_staff and user.has_perm('core.view_operations'):
        return True
    address = client_address(request)
    if not address:
        return False
    values = MonitoringAccessSettings.objects.filter(pk=1).values_list('ips', flat=True).first()
    if not isinstance(values, list) or len(values) > 50:
        return False
    try:
        return address in {_client_address(value) for value in values}
    except (ValueError, TypeError):
        return False


def require_monitoring(request):
    if can_monitor(request):
        return
    if not request.user.is_authenticated:
        raise APIError('management_login_required', 'برای مشاهدهٔ مانیتورینگ وارد شوید.', 401)
    raise APIError('forbidden', 'مجوز مشاهدهٔ مانیتورینگ را ندارید.', 403)


@vary_on_cookie
@ensure_csrf_cookie
@api(['GET'])
def access(request):
    # Expose no IPs, usernames, permissions or credentials to this public gate.
    return {'allowed': can_monitor(request)}


def _data(request, instance=None):
    return {'ips': instance.ips if instance else [], 'revision': instance.revision if instance else 0,
            'current_ip': client_address(request)}


def _invalid(message='IPهای مشخص‌شده را اصلاح کنید.'):
    raise APIError('invalid_settings', message, 422, {'ips': [message]})


def _values(data):
    if not isinstance(data, dict) or set(data) != {'ips', 'revision'}:
        _invalid('ساختار تنظیمات IP معتبر نیست.')
    if type(data['revision']) is not int or not 0 <= data['revision'] < 2147483647:
        _invalid('نسخهٔ تنظیمات معتبر نیست؛ آخرین تنظیمات را دریافت کنید.')
    values = data['ips']
    if not isinstance(values, list) or len(values) > 50:
        _invalid('حداکثر ۵۰ IP دقیق وارد کنید؛ هر IP در یک خط.')
    try:
        result = [_client_address(ascii_digits(value.strip())) if isinstance(value, str) else None for value in values]
    except ValueError:
        _invalid('فقط IP دقیق IPv4 یا IPv6 مجاز است؛ دامنه، بازه، IP پراکسی و آدرس محلی دستگاه پذیرفته نمی‌شود.')
    if None in result or len(set(result)) != len(result):
        _invalid('هر IP باید معتبر و غیرتکراری باشد.')
    return sorted(result)


def _audit_value(ips):
    # Audit viewers need an attributable change, not the raw network allowlist.
    return {'count': len(ips), 'fingerprint': digest(json.dumps(ips, separators=(',', ':')))}


@transaction.atomic
def _update(request, data):
    values = _values(data)
    instance, _ = MonitoringAccessSettings.objects.get_or_create(pk=1)
    instance = MonitoringAccessSettings.objects.select_for_update().get(pk=instance.pk)
    if instance.revision != data['revision']:
        raise APIError('settings_changed', 'تنظیمات تغییر کرده است؛ آخرین تنظیمات را دریافت کنید و دوباره بررسی کنید.', 409)
    before = instance.ips
    if before != values:
        instance.ips, instance.revision = values, instance.revision + 1
        instance.save(update_fields=['ips', 'revision', 'updated_at'])
        OperatorAudit.objects.create(actor=request.user, action='update_monitoring_access', object_id='1',
            reason='تغییر IPهای مجاز مانیتورینگ از تنظیمات سامانه',
            before=_audit_value(before), after=_audit_value(values))
    return _data(request, instance)


@vary_on_cookie
@staff_api(['GET', 'PUT'])
def configuration(request):
    if not request.user.is_superuser:
        raise APIError('forbidden', 'فقط مدیر اصلی می‌تواند IPهای مجاز مانیتورینگ را تنظیم کند.', 403)
    if request.method == 'PUT':
        return _update(request, body(request))
    return _data(request, MonitoringAccessSettings.objects.filter(pk=1).first())
