"""Versioned settings for the recipient SMS layout and sending line."""
import json
import re
import unicodedata

from django.conf import settings
from django.db import transaction
from django.views.decorators.vary import vary_on_cookie

from .input_digits import ascii_digits
from .limits import fa_number
from .management_api import staff_api
from .models import OperatorAudit, SMSTemplateSettings
from .moderation import ANGRY_TEMPLATES, DIRECT_TEMPLATES, TEMPLATES
from .privacy import digest
from .services import APIError
from .sms import (DEFAULT_SMS_TEMPLATE, OPT_OUT_SLOT, REPLY_SLOT, SMS_PLACEHOLDER, SMS_VARIABLE_NAME,
                  SMS_WARNING_SEGMENTS, render_recipient_sms, sms_origin, sms_segments, sms_units)
from .views import body


LEGACY_SYSTEM_NAMES = {'message', 'opt_out'}
SYSTEM_NAMES = LEGACY_SYSTEM_NAMES | {'reply', 'site_url'}
MAX_VARIABLES = 8
SAMPLE_TOKEN = 'Sample-X'  # Cannot match the recipient capability format.
SAMPLE_MESSAGE = 'از اینکه با مهربانی کنارم بودی، ممنونم.'
MIN_BODY_UNITS = max(min(map(sms_units, choices))
                     for catalog in (TEMPLATES, DIRECT_TEMPLATES, ANGRY_TEMPLATES)
                     for choices in catalog.values())


def invalid(field, message):
    raise APIError('invalid_sms_template', message, 422, {field: [message]})


def plain_text(text, field, *, allow_empty=False):
    if not isinstance(text, str):
        invalid(field, 'مقدار باید متن باشد.')
    text = text.replace('\r\n', '\n').translate(str.maketrans('\r\u2028\u2029', '\n\n\n'))
    if not allow_empty and not text.strip():
        invalid(field, 'متن قالب را وارد کنید.')
    if any(unicodedata.category(char).startswith('C') and char not in '\n\t\u200c\u200d' for char in text):
        invalid(field, 'متن دارای نویسهٔ کنترلی است.')
    return ascii_digits(text)


def upgrade_legacy_layout(template, values):
    # Old layouts could use the new system names for operator-authored text.
    taken = SYSTEM_NAMES | values.keys()
    aliases = {}
    for name in SYSTEM_NAMES & values.keys():
        alias = name + '_custom'
        suffix = 2
        while alias in taken:
            alias = f'{name}_custom_{suffix}'
            suffix += 1
        aliases[name] = alias
        taken.add(alias)
    if aliases:
        template = SMS_PLACEHOLDER.sub(lambda match: '{{' + aliases.get(match[1], match[1]) + '}}', template)
        values = {aliases.get(name, name): value for name, value in values.items()}
    if REPLY_SLOT not in template:
        template = template.replace(OPT_OUT_SLOT, REPLY_SLOT + '\n' + OPT_OUT_SLOT, 1)
    return template, values


def compile_layout(template, variables, *, legacy_reply_footer=False):
    template = plain_text(template, 'template')
    template = SMS_PLACEHOLDER.sub(lambda match: '{{' + match[1] + '}}', template)
    text_without_slots = SMS_PLACEHOLDER.sub('', template)
    if '{{' in text_without_slots or '}}' in text_without_slots:
        invalid('template', 'متغیر را با قالب {{name}} وارد کنید.')
    if not isinstance(variables, list) or len(variables) > MAX_VARIABLES:
        invalid('variables', f'حداکثر {fa_number(MAX_VARIABLES)} متغیر سفارشی تعریف کنید.')
    reserved = LEGACY_SYSTEM_NAMES if legacy_reply_footer else SYSTEM_NAMES
    values = {}
    for item in variables:
        if not isinstance(item, dict) or set(item) != {'name', 'value'} or not isinstance(item['name'], str):
            invalid('variables', 'نام و مقدار متغیر را وارد کنید.')
        name = item['name'].strip()
        if not re.fullmatch(SMS_VARIABLE_NAME, name) or name in reserved or name in values:
            invalid('variables', 'نام متغیر باید یکتا باشد و با حرف کوچک انگلیسی شروع شود. ارقام و زیرخط هم مجازند.')
        values[name] = plain_text(item['value'], 'variables', allow_empty=True)
    if legacy_reply_footer:
        template, values = upgrade_legacy_layout(template, values)
    if set(SMS_PLACEHOLDER.findall(template)) - SYSTEM_NAMES - values.keys():
        invalid('template', 'همهٔ متغیرهای استفاده‌شده در قالب باید تعریف شوند.')
    return template, values


def stored_layout(item):
    return compile_layout(item.template, item.variables, legacy_reply_footer=item.legacy_reply_footer)


def current_sms_layout():
    item = SMSTemplateSettings.objects.filter(pk=1).first()
    if item is None:
        return DEFAULT_SMS_TEMPLATE, {}
    try:
        return stored_layout(item)
    except APIError:
        raise APIError('sms_template_unavailable', 'قالب پیامک در دسترس نیست.', 503) from None


def sample_preview(layout, variables):
    origin = sms_origin()
    full_sms = render_recipient_sms(SAMPLE_MESSAGE, origin, SAMPLE_TOKEN, reply_token=SAMPLE_TOKEN,
                                   layout=layout, variables=variables)
    names = SMS_PLACEHOLDER.findall(layout)
    occurrences = names.count('message')
    units = sms_units(full_sms)
    segments = sms_segments(full_sms)
    overhead = units - occurrences * sms_units(SAMPLE_MESSAGE)
    body_units = max(0, (SMS_WARNING_SEGMENTS * 67 - overhead) // occurrences) if occurrences else 0
    return {'full_sms': full_sms, 'sms_units': units, 'sms_segments': segments, 'body_units': body_units,
            'has_message': bool(occurrences), 'has_opt_out': 'opt_out' in names,
            'length_warning': segments > SMS_WARNING_SEGMENTS or bool(occurrences and body_units < MIN_BODY_UNITS)}


def settings_data(template, variables, revision, preview, *, sender=''):
    return {'template': template, 'variables': variables, 'revision': revision, 'preview': preview,
            'sender': sender, 'default_sender': settings.KAVENEGAR_SENDER,
            'default_template': DEFAULT_SMS_TEMPLATE, 'max_variables': MAX_VARIABLES}


def audit_value(item):
    raw = json.dumps([item.template, item.variables, item.sender, item.legacy_reply_footer],
                     ensure_ascii=True, separators=(',', ':'))
    return {'revision': item.revision, 'fingerprint': digest(raw)}


def clean_sender(value):
    if not isinstance(value, str):
        invalid('sender', 'شمارهٔ فرستنده باید به‌صورت متن وارد شود.')
    sender = ''.join(ascii_digits(value).split())
    if not re.fullmatch(r'[0-9]{0,20}', sender):
        invalid('sender', 'شمارهٔ خط کاوه‌نگار را با حداکثر ۲۰ رقم وارد کنید.')
    return sender


@transaction.atomic
def save(actor, data):
    required = {'template', 'variables', 'revision'}
    revision = data.get('revision')
    if (not required <= data.keys() <= (required | {'sender'})
            or type(revision) is not int or not 0 <= revision < 2147483647):
        invalid('template', 'ساختار یا نسخهٔ تنظیمات پیامک معتبر نیست. تنظیمات را دوباره دریافت کنید.')
    template, values = compile_layout(data['template'], data['variables'])
    variables = [{'name': name, 'value': value} for name, value in values.items()]
    preview = sample_preview(template, values)
    sender = clean_sender(data['sender']) if 'sender' in data else None
    item, _ = SMSTemplateSettings.objects.get_or_create(pk=1,
        defaults={'template': DEFAULT_SMS_TEMPLATE, 'legacy_reply_footer': False})
    item = SMSTemplateSettings.objects.select_for_update().get(pk=1)
    if item.revision != revision:
        raise APIError('settings_changed', 'تنظیمات پیامک تغییر کرده است. آخرین نسخه را دریافت کنید و ویرایش را دوباره بررسی کنید.', 409)
    if sender is None:
        sender = item.sender
    if item.legacy_reply_footer or (item.template, item.variables, item.sender) != (template, variables, sender):
        before = audit_value(item)
        item.template, item.variables, item.sender = template, variables, sender
        item.legacy_reply_footer = False
        item.revision += 1
        item.save(update_fields=['template', 'variables', 'sender', 'legacy_reply_footer', 'revision', 'updated_at'])
        OperatorAudit.objects.create(actor=actor, action='update_sms_template', object_id='sms-template',
            reason='ذخیرهٔ تنظیمات پیامک از پنل مدیریت', before=before, after=audit_value(item))
    return settings_data(template, variables, item.revision, preview, sender=item.sender)


@vary_on_cookie
@staff_api(['GET', 'PUT'], 'core.manage_site_limits')
def configuration(request):
    if request.method == 'PUT':
        return save(request.user, body(request))
    item = SMSTemplateSettings.objects.filter(pk=1).first()
    if item is None:
        return settings_data(DEFAULT_SMS_TEMPLATE, [], 0, sample_preview(DEFAULT_SMS_TEMPLATE, {}))
    template, values = stored_layout(item)
    variables = [{'name': name, 'value': value} for name, value in values.items()]
    return settings_data(template, variables, item.revision, sample_preview(template, values), sender=item.sender)


@vary_on_cookie
@staff_api(['POST'], 'core.manage_site_limits')
def preview(request):
    data = body(request)
    if set(data) != {'template', 'variables'}:
        invalid('template', 'ساختار پیش‌نمایش قالب معتبر نیست.')
    return sample_preview(*compile_layout(data['template'], data['variables']))
