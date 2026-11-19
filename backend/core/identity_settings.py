"""The site-wide switch for the website consent flow."""
from django.db import transaction
from django.views.decorators.vary import vary_on_cookie

from .management_api import staff_api
from .models import IdentityRequestSettings, OperatorAudit
from .services import APIError
from .views import body


def identity_requests_enabled():
    return IdentityRequestSettings.objects.filter(pk=1, enabled=True).exists()


@transaction.atomic
def update(actor, data):
    enabled, revision = data.get('enabled'), data.get('revision')
    if (set(data) != {'enabled', 'revision'} or type(enabled) is not bool
            or type(revision) is not int or not 0 <= revision < 2147483647):
        raise APIError('invalid_settings', 'وضعیت یا نسخهٔ تنظیم «میخوام بدونم» معتبر نیست.', 422)

    current, _ = IdentityRequestSettings.objects.select_for_update().get_or_create(pk=1)
    if current.revision != revision:
        raise APIError('settings_changed', 'وضعیت قابلیت تغییر کرده است. آخرین وضعیت را دوباره دریافت کنید.', 409)
    if current.enabled != enabled:
        previous = current.enabled
        current.enabled = enabled
        current.revision += 1
        current.save(update_fields=['enabled', 'revision'])
        OperatorAudit.objects.create(
            actor=actor, action='update_identity_settings', object_id='identity-requests',
            reason='تغییر وضعیت «میخوام بدونم» در تنظیمات سایت',
            before={'enabled': previous}, after={'enabled': enabled},
        )
    return {'enabled': current.enabled, 'revision': current.revision}


@vary_on_cookie
@staff_api(['GET', 'PUT'], 'core.manage_site_limits')
def configuration(request):
    if request.method == 'PUT':
        return update(request.user, body(request))
    saved = IdentityRequestSettings.objects.filter(pk=1).values('enabled', 'revision').first()
    return saved or {'enabled': False, 'revision': 0}
