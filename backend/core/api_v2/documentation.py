"""No public CDN, schema, guide, client example or documentation asset routes."""
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import RequestDataTooBig
from django.http import FileResponse, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.csrf import ensure_csrf_cookie

from core.services import APIError, api, error_response, limited

ASSETS = Path(__file__).resolve().parent / 'docs_assets'
CONTENT = Path(__file__).resolve().parent / 'integration'
ASSET_TYPES = {'swagger-ui-bundle.js': 'text/javascript', 'swagger-ui.css': 'text/css',
               'init.js': 'text/javascript', 'docs.css': 'text/css', 'font.woff2': 'font/woff2'}


def authorized(user):
    # A documentation-only account does not need staff or a product Account.
    return user.is_authenticated and user.is_active and user.has_perm('core.view_api_documentation')


def missing():
    return error_response(APIError('not_found', 'درخواست پیدا نشد.', 404))


@ensure_csrf_cookie
@api(['GET', 'POST'])
def login_view(request):
    if not settings.API_DOCUMENTATION_ENABLED:
        return missing()
    if request.method == 'GET' and authorized(request.user):
        return HttpResponseRedirect('/api/v2/document')
    context = {}
    status = 200
    if request.method == 'POST':
        limited('api-docs-login-ip', request.META.get('REMOTE_ADDR', 'unknown'), 50, 600)
        try:
            data = request.POST
        except RequestDataTooBig:
            raise APIError('request_too_large', 'حجم درخواست بیش از حد مجاز است.', 413) from None
        username, password = data.get('username', ''), data.get('password', '')
        if (set(data) - {'username', 'password', 'csrfmiddlewaretoken'}
                or len(username) > 150 or len(password) > 256 or not username or not password):
            raise APIError('invalid_input', 'نام کاربری و رمز ورود معتبر وارد کنید.', 422)
        limited('api-docs-login-pair', request.META.get('REMOTE_ADDR', 'unknown') + ':' + username, 10, 600)
        user = authenticate(request, username=username, password=password)
        if user is not None and authorized(user):
            login(request, user)
            request.session.set_expiry(8 * 3600)
            response = HttpResponseRedirect('/api/v2/document')
            response.status_code = 303
            return response
        context['error'] = 'مشخصات ورود یا مجوز مشاهدهٔ مستندات معتبر نیست.'
        status = 403
    return render(request, 'core/api_v2/login.html', context, status=status)


@api(['POST'])
def logout_view(request):
    if not settings.API_DOCUMENTATION_ENABLED or not authorized(request.user):
        return missing()
    logout(request)
    response = HttpResponseRedirect('/api/v2/document/login')
    response.status_code = 303
    return response


def private_document(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not settings.API_DOCUMENTATION_ENABLED:
            return missing()
        if not authorized(request.user):
            if not request.user.is_authenticated and request.path == '/api/v2/document' and request.method == 'GET':
                return HttpResponseRedirect('/api/v2/document/login')
            return missing()
        if request.method != 'GET':
            response = error_response(APIError('method_not_allowed', 'روش درخواست مجاز نیست.', 405))
            response['Allow'] = 'GET'
            return response
        return view(request, *args, **kwargs)
    return wrapped


@private_document
def swagger(request):
    return HttpResponse(render_to_string('core/api_v2/swagger.html', request=request), content_type='text/html; charset=utf-8')


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
