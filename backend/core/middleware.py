import logging
import uuid
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


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
