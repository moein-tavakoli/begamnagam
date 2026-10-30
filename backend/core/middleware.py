import logging
import ipaddress
import uuid
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import RequestDataTooBig
from django.core.cache import cache
from .privacy import digest
from django.utils.deprecation import MiddlewareMixin


class RuntimeLimits:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .limits import limit_scope
        with limit_scope():
            return self.get_response(request)


class TrustedProxyClientIP(MiddlewareMixin):
    def process_request(self, request):
        peer = request.META.get("REMOTE_ADDR", "")
        trusted = getattr(settings, "TRUSTED_CLIENT_PROXY_IPS", set())
        request.META.pop("HTTP_X_VERIFIED_CLIENT_IP", None)
        chain = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if peer not in trusted or not chain or len(chain) > 2048:
            return
        try:
            addresses = [str(ipaddress.ip_address(part.strip())) for part in chain.split(",")]
        except ValueError:
            return
        for address in reversed(addresses):
            if address not in trusted:
                request.META["REMOTE_ADDR"] = address
                break


class PrivateResponses(MiddlewareMixin):
    def process_request(self, request):
        request.public_request_id = uuid.uuid4().hex

    def process_response(self, request, response):
        if request.path in {'/api', '/admin', '/r'} or request.path.startswith(('/api/', '/admin/', '/r/')):
            response['Cache-Control'] = 'no-store'
            # Native admin POST forms need their same-origin context for CSRF.
            # Keep private capability/API responses from sending any referrer.
            response['Referrer-Policy'] = 'same-origin' if request.path.startswith('/admin/') else 'no-referrer'
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['X-Request-ID'] = getattr(request, 'public_request_id', uuid.uuid4().hex)
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        # Django admin uses local external scripts, including its popup response.
        # Inline CSS is used by the built-in widgets and our audited forms.
        response.setdefault('Content-Security-Policy', "; ".join([
            "default-src 'none'", "script-src 'self'", "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:", "font-src 'self'", "connect-src 'self'",
            "object-src 'none'", "base-uri 'none'", "frame-ancestors 'none'", "form-action 'self'",
        ]))
        return response

    def process_exception(self, request, exception):
        if request.path.startswith('/api/'):
            # Do not render Django debug pages containing cookies, phone input,
            # capabilities or provider credentials, even in a shared local demo.
            logging.getLogger(__name__).error('API failure request_id=%s type=%s', request.public_request_id, type(exception).__name__)
            return JsonResponse({'error': {'code': 'service_unavailable', 'message': 'سرویس موقتاً در دسترس نیست؛ کمی بعد تلاش کن.', 'request_id': request.public_request_id}}, status=503)


class AdminLoginThrottle(MiddlewareMixin):
    """Bound real admin password attempts across sessions; never read passwords."""
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if request.method != 'POST' or not match or match.url_name != 'login' or 'admin' not in match.app_names:
            return
        from unicodedata import normalize
        window = settings.ADMIN_LOGIN_WINDOW_SECONDS
        try:
            username = normalize('NFKC', request.POST.get('username', '')[:254]).strip().casefold()
            address = request.META.get('REMOTE_ADDR', 'unknown')
            identities = [('ip', address, settings.ADMIN_LOGIN_IP_LIMIT),
                          ('pair', address + ':' + username, settings.ADMIN_LOGIN_PAIR_LIMIT)]
            for scope, identity, maximum in identities:
                key = 'security:admin-login:' + scope + ':' + digest(identity)
                count = 1 if cache.add(key, 1, timeout=window) else cache.incr(key)
                if count > maximum:
                    response = HttpResponse('تعداد تلاش‌های ورود زیاد است؛ چند دقیقه بعد دوباره تلاش کنید.',
                                            status=429, content_type='text/plain; charset=utf-8')
                    response['Retry-After'] = str(window)
                    return response
        except RequestDataTooBig:
            return HttpResponse('درخواست بیش از حد بزرگ است.', status=413, content_type='text/plain; charset=utf-8')
        except Exception:
            # Cache failure must not silently remove protection of admin passwords.
            return HttpResponse('ورود موقتاً در دسترس نیست؛ کمی بعد تلاش کنید.',
                                status=503, content_type='text/plain; charset=utf-8')


class CanonicalAdminInput(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if request.method != 'POST' or not match or 'admin' not in match.app_names:
            return
        from .input_digits import canonical_input
        data = request.POST.copy()
        for key, values in data.lists():
            data.setlist(key, [canonical_input(value, key) for value in values])
        request.POST = data
