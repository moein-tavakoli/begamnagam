import logging
import ipaddress
import uuid
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


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
        if request.path.startswith(('/api/', '/admin/')) or request.path == '/r':
            response['Cache-Control'] = 'no-store'
            response['Referrer-Policy'] = 'no-referrer'
            response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        response['X-Request-ID'] = getattr(request, 'public_request_id', uuid.uuid4().hex)
        return response

    def process_exception(self, request, exception):
        if request.path.startswith('/api/'):
            # Do not render Django debug pages containing cookies, phone input,
            # capabilities or provider credentials, even in a shared local demo.
            logging.getLogger(__name__).error('API failure request_id=%s type=%s', request.public_request_id, type(exception).__name__)
            return JsonResponse({'error': {'code': 'service_unavailable', 'message': 'سرویس موقتاً در دسترس نیست؛ کمی بعد تلاش کن.', 'request_id': request.public_request_id}}, status=503)
