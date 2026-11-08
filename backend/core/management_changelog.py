"""Packaged release summaries; deliberately outside public static assets."""
import json
from importlib.resources import files

from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie

from .management_api import staff_api
from .services import APIError


@never_cache
@vary_on_cookie
@staff_api(['GET'])
def changelog(request):
    from .staff_roles import can_view_changelog
    if not can_view_changelog(request.user):
        raise APIError('forbidden', 'مجوز مشاهدهٔ تاریخچهٔ تغییرات را ندارید.', 403)
    try:
        return json.loads(files('core').joinpath('release_notes.fa.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise APIError('service_unavailable', 'تاریخچهٔ تغییرات موقتاً در دسترس نیست.', 503) from None
