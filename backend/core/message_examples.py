"""Editable writing prompts. They never become approved outbound SMS templates."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from .input_digits import ascii_digits
from .limit_services import validate_reason
from .models import ExampleCategory, MessageExample, OperatorAudit
from .services import APIError

FIELDS = {
    'groups': ('name', 'active', 'sort_order'),
    'examples': ('group_id', 'label', 'description', 'text', 'topic', 'active', 'sort_order'),
}
MODELS = {'groups': ExampleCategory, 'examples': MessageExample}
POSITIVE_TOPICS = ('appreciation', 'encouragement', 'congratulations')


def record_data(kind, item):
    return {'id': item.pk, 'revision': item.revision, **{key: getattr(item, key) for key in FIELDS[kind]}}


def visible_examples(*, freeform=False):
    rows = MessageExample.objects.filter(active=True, group__active=True).select_related('group')
    if not freeform:
        rows = rows.exclude(topic='')
    if settings.PILOT_POSITIVE_ONLY:
        rows = rows.filter(topic__in=POSITIVE_TOPICS)
    return rows.order_by('group__sort_order', 'group_id', 'sort_order', 'id')


def public_catalog(*, freeform=False):
    rows = list(visible_examples(freeform=freeform))
    groups = {item.group_id: {'id': item.group_id, 'label': item.group.name} for item in rows}
    return {'category_groups': list(groups.values()), 'categories': [
        {'key': str(item.pk), 'id': item.topic or 'custom', 'group_id': item.group_id,
         'label': item.label, 'description': item.description, 'example': item.text} for item in rows]}


def is_current_suggestion(topic, text):
    return isinstance(text, str) and visible_examples().filter(topic=topic, text=text).exists()


@transaction.atomic
def write_record(actor, kind, data, record_id=None, *, delete=False):
    if not actor.is_active or not actor.is_staff or not actor.has_perm('core.manage_message_examples'):
        raise APIError('forbidden', 'مجوز مدیریت پیام‌های نمونه را ندارید.', 403)
    if kind not in MODELS:
        raise APIError('not_found', 'بخش پیدا نشد.', 404)
    allowed = {'revision', 'reason'} if delete else {'values', 'revision', 'reason'}
    if not isinstance(data, dict) or set(data) != allowed or type(data.get('revision')) is not int:
        raise APIError('invalid_input', 'مشخصات و نسخهٔ فعلی را وارد کنید.', 422)
    reason = ascii_digits(validate_reason(data.get('reason')))
    model = MODELS[kind]
    item = model.objects.select_for_update().filter(pk=record_id).first() if record_id else model()
    if item is None:
        raise APIError('not_found', 'رکورد پیدا نشد.', 404)
    if item.revision != data['revision']:
        raise APIError('settings_changed', 'این مورد تغییر کرده؛ فهرست را تازه‌سازی کنید.', 409)
    before = record_data(kind, item) if record_id else {}
    if delete:
        if not record_id:
            raise APIError('invalid_input', 'رکورد را انتخاب کنید.', 422)
        try:
            item.delete()
        except ProtectedError:
            raise APIError('category_not_empty', 'ابتدا نمونه‌های این دسته را به دستهٔ دیگری منتقل یا حذف کنید.', 409) from None
        after = {}
    else:
        values = data['values']
        if not isinstance(values, dict) or set(values) != set(FIELDS[kind]):
            raise APIError('invalid_input', 'همهٔ مشخصات نمونه یا دسته را وارد کنید.', 422)
        for key, value in values.items():
            expected = bool if key == 'active' else int if key in {'group_id', 'sort_order'} else str
            if type(value) is not expected:
                raise APIError('invalid_input', 'نوع مقدار واردشده معتبر نیست.', 422)
            setattr(item, key, ascii_digits(value.strip()) if isinstance(value, str) else value)
        # Serialize group deletion/moving against creation of children too.
        if kind == 'examples' and not ExampleCategory.objects.select_for_update().filter(pk=item.group_id).exists():
            raise APIError('invalid_settings', 'دستهٔ انتخاب‌شده موجود نیست.', 422)
        try:
            item.full_clean()
            item.revision += 1
            with transaction.atomic():
                item.save()
        except (ValidationError, IntegrityError):
            raise APIError('invalid_settings', 'نام یکتا، متن ۳ تا ۲۸۰ حرف و ترتیب معتبر وارد کنید.', 422) from None
        after = record_data(kind, item)
    OperatorAudit.objects.create(actor=actor, action=('delete_' if delete else 'save_') + 'message_' + kind,
        object_id=str(record_id or item.pk), reason=reason, before=before, after=after)
    return after
