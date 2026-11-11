"""Write-only management of the Kavenegar credential override."""
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import transaction
from django.views.decorators.vary import vary_on_cookie

from .management_api import staff_api
from .models import KavenegarSettings, OperatorAudit
from .providers.kavenegar import valid_api_key
from .services import APIError
from .views import body


def read_saved_key(instance):
    try:
        return instance.api_key if instance is not None else ''
    except InvalidToken:
        return None


def status_data(key, revision):
    if key is None:
        source = 'unreadable'
    elif key:
        source = 'panel'
    else:
        source = 'environment' if valid_api_key(settings.KAVENEGAR_API_KEY) else 'missing'
    return {'source': source, 'revision': revision}


@transaction.atomic
def update_key(actor, data):
    key = data.get('api_key')
    revision = data.get('revision')
    if set(data) != {'api_key', 'revision'} or type(revision) is not int or not 0 <= revision < 2147483647:
        raise APIError('invalid_kavenegar_key', 'ساختار یا نسخهٔ تنظیمات کلید معتبر نیست.', 422)
    if key != '' and not valid_api_key(key):
        raise APIError('invalid_kavenegar_key', 'کلید کاوه‌نگار را بدون فاصله و با نویسه‌های انگلیسی وارد کنید.', 422)

    # Defer decryption so even an unreadable key can be replaced under the row lock.
    instance, _ = KavenegarSettings.objects.defer('api_key').select_for_update().get_or_create(pk=1)
    if instance.revision != revision:
        raise APIError('settings_changed', 'کلید تغییر کرده است. وضعیت فعلی را دوباره بررسی کنید.', 409)
    saved_key = read_saved_key(instance)
    if saved_key != key:
        before = status_data(saved_key, instance.revision)
        instance.api_key = key
        instance.revision += 1
        instance.save(update_fields=['api_key', 'revision'])
        OperatorAudit.objects.create(actor=actor, action='update_kavenegar_key', object_id='kavenegar',
            reason='تغییر کلید کاوه‌نگار از تنظیمات پیامک', before=before, after=status_data(key, instance.revision))
    return status_data(key, instance.revision)


@vary_on_cookie
@staff_api(['GET', 'PUT'])
def configuration(request):
    if not request.user.is_superuser:
        raise APIError('forbidden', 'فقط مدیر اصلی می‌تواند کلید کاوه‌نگار را تغییر دهد.', 403)
    if request.method == 'PUT':
        return update_key(request.user, body(request))
    instance = KavenegarSettings.objects.defer('api_key').filter(pk=1).first()
    return status_data(read_saved_key(instance), instance.revision if instance is not None else 0)
