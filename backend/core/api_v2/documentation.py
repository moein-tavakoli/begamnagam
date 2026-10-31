"""No public CDN, schema, guide, client example or documentation asset routes."""
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse, JsonResponse
from django.template.loader import render_to_string

from core.services import APIError, error_response

ASSETS = Path(__file__).resolve().parent / 'docs_assets'
CONTENT = Path(__file__).resolve().parent / 'integration'
ASSET_TYPES = {'swagger-ui-bundle.js': 'text/javascript', 'swagger-ui.css': 'text/css',
               'init.js': 'text/javascript', 'docs.css': 'text/css', 'font.woff2': 'font/woff2'}


def private_document(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if (not settings.API_DOCUMENTATION_ENABLED or not user.is_authenticated or not user.is_active
                or not user.is_staff or not user.has_perm('core.view_api_documentation')):
            return error_response(APIError('not_found', 'درخواست پیدا نشد.', 404))
        if request.method != 'GET':
            response = error_response(APIError('method_not_allowed', 'روش درخواست مجاز نیست.', 405))
            response['Allow'] = 'GET'
            return response
        return view(request, *args, **kwargs)
    return wrapped


@private_document
def swagger(request):
    return HttpResponse(render_to_string('core/api_v2/swagger.html'), content_type='text/html; charset=utf-8')


@private_document
def schema(request):
    from .openapi import specification
    return JsonResponse(specification(), json_dumps_params={'ensure_ascii': False})


@private_document
def asset(request, filename):
    if filename not in ASSET_TYPES:
        return error_response(APIError('not_found', 'درخواست پیدا نشد.', 404))
    path = (Path(__file__).resolve().parents[1] / 'static/admin/fonts/vazirmatn-fd/Vazirmatn-FD-Regular.woff2'
            if filename == 'font.woff2' else ASSETS / filename)
    return FileResponse(path.open('rb'), content_type=ASSET_TYPES[filename])


@private_document
def guide(request):
    return FileResponse((CONTENT / 'guide.fa.md').open('rb'), content_type='text/plain; charset=utf-8')


@private_document
def client_example(request):
    return FileResponse((CONTENT / 'client.py').open('rb'), content_type='text/plain; charset=utf-8')
