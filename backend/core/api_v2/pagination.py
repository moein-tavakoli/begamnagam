"""Bounded keyset pages with cursors bound to the owner, resource and filters."""
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

from core.privacy import digest
from core.services import APIError

SALT = 'begamnagam.api-v2.cursor.v1'


def paginate(request, rows, serialize, scope, *, serialize_many=None):
    limit = request.api_query.get('limit', 20)
    owner = digest('api-cursor:' + str(request.user.pk))
    cursor = request.api_query.get('cursor')
    if cursor:
        try:
            value = signing.loads(cursor, salt=SALT, max_age=7 * 24 * 3600)
            if value['owner'] != owner or value['scope'] != scope:
                raise ValueError()
            stamp = parse_datetime(value['at'])
            if stamp is None or not is_aware(stamp):
                raise ValueError()
            identifier = rows.model._meta.pk.to_python(value['id'])
            rows = rows.filter(Q(created_at__lt=stamp) | Q(created_at=stamp, pk__lt=identifier))
        except (signing.BadSignature, ValidationError, ValueError, TypeError, KeyError):
            raise APIError('invalid_cursor', 'نشان صفحه معتبر نیست؛ فهرست را از ابتدا دریافت کن.', 422) from None
    values = list(rows.order_by('-created_at', '-pk')[:limit + 1])
    more = len(values) > limit
    values = values[:limit]
    next_cursor = None
    if more:
        next_cursor = signing.dumps({'owner': owner, 'scope': scope, 'at': values[-1].created_at.isoformat(),
                                     'id': str(values[-1].pk)}, salt=SALT, compress=True)
    return {'results': serialize_many(values) if serialize_many else [serialize(item) for item in values],
            'has_more': more, 'next_cursor': next_cursor}
