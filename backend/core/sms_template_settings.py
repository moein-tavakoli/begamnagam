"""One versioned template for recipient messages, with literal substitutions."""
import json
import re
import unicodedata

from django.db import transaction
from django.views.decorators.vary import vary_on_cookie

from .draft_guard import validate_sms_decoration
from .input_digits import ascii_digits
from .limits import fa_number
from .management_api import staff_api
from .models import OperatorAudit, SMSTemplateSettings
from .moderation import ANGRY_TEMPLATES, DIRECT_TEMPLATES, TEMPLATES, ModerationRejected
from .privacy import digest
from .services import APIError
from .sms import (DEFAULT_SMS_TEMPLATE, MESSAGE_SLOT, OPT_OUT_SLOT, freeform_body_limit,
                  render_recipient_sms, sms_origin, sms_segments, sms_units)
from .views import body


VARIABLE_NAME = r'[a-z][a-z0-9_]{0,23}'
PLACEHOLDER = re.compile(r'\{\{ *(' + VARIABLE_NAME + r') *\}\}')
REQUIRED_NAMES = {'message', 'opt_out'}
MAX_TEMPLATE_LENGTH = 600
MAX_VARIABLES = 8
MAX_VALUE_LENGTH = 80
SAMPLE_TOKEN = 'Sample-X'  # Cannot match the recipient capability format.
SAMPLE_MESSAGE = 'از اینکه با مهربانی کنارم بودی، ممنونم.'
MIN_BODY_UNITS = max(min(map(sms_units, choices))
                     for catalog in (TEMPLATES, DIRECT_TEMPLATES, ANGRY_TEMPLATES)
                     for choices in catalog.values())


def invalid(field, message):
    raise APIError('invalid_sms_template', message, 422, {field: [message]})


def plain_text(text, maximum, field):
    if not isinstance(text, str) or not 0 < len(text) <= maximum:
        invalid(field, f'متن باید بین ۱ و {fa_number(maximum)} نویسه داشته باشد.')
    text = text.replace('\r\n', '\n').translate(str.maketrans('\r\u2028\u2029', '\n\n\n'))
    text = ascii_digits(text).strip()
    if not text or any(unicodedata.category(char).startswith('C') and char not in '\n\u200c' for char in text):
        invalid(field, 'متن خالی یا دارای نویسهٔ کنترلی است.')
    return text


def check_decoration(text, field):
    try:
        validate_sms_decoration(text)
    except ModerationRejected:
        invalid(field, 'در متن ثابت قالب و متغیرها، لینک، اطلاعات تماس و عبارت‌های نامجاز وارد نکنید.')


def compile_layout(template, variables):
    template = plain_text(template, MAX_TEMPLATE_LENGTH, 'template')
    template = '\n'.join(line.strip() for line in template.split('\n'))
    template = PLACEHOLDER.sub(lambda match: '{{' + match[1] + '}}', template)
    text_without_slots = PLACEHOLDER.sub('', template)
    if '{' in text_without_slots or '}' in text_without_slots:
        invalid('template', 'متغیر را با قالب {{name}} وارد کنید.')
    names = PLACEHOLDER.findall(template)
    lines = template.split('\n')
    if names.count('message') != 1 or MESSAGE_SLOT not in lines:
        invalid('template', '{{message}} باید یک بار در یک خط جدا بیاید.')
    if names.count('opt_out') != 1 or lines[-1] != OPT_OUT_SLOT:
        invalid('template', '{{opt_out}} باید یک بار در آخرین خط قالب بیاید.')

    if not isinstance(variables, list) or len(variables) > MAX_VARIABLES:
        invalid('variables', f'حداکثر {fa_number(MAX_VARIABLES)} متغیر سفارشی تعریف کنید.')
    values = {}
    for item in variables:
        if not isinstance(item, dict) or set(item) != {'name', 'value'} or not isinstance(item['name'], str):
            invalid('variables', 'نام و مقدار متغیر را وارد کنید.')
        name = item['name'].strip()
        if not re.fullmatch(VARIABLE_NAME, name) or name in REQUIRED_NAMES or name in values:
            invalid('variables', 'نام متغیر باید یکتا باشد و با حرف کوچک انگلیسی شروع شود. ارقام و زیرخط هم مجازند.')
        value = plain_text(item['value'], MAX_VALUE_LENGTH, 'variables')
        if '\n' in value:
            invalid('variables', 'مقدار متغیر باید در یک خط باشد.')
        check_decoration(value, 'variables')
        values[name] = value
    if set(names) - REQUIRED_NAMES - values.keys():
        invalid('template', 'همهٔ متغیرهای استفاده‌شده در قالب باید تعریف شوند.')
    layout = PLACEHOLDER.sub(lambda match: values.get(match[1], match[0]), template)
    check_decoration(layout.replace(MESSAGE_SLOT, '').replace(OPT_OUT_SLOT, ''), 'template')
    return template, [{'name': name, 'value': value} for name, value in values.items()], layout


def current_sms_layout():
    item = SMSTemplateSettings.objects.filter(pk=1).first()
    if item is None:
        return DEFAULT_SMS_TEMPLATE
    try:
        return compile_layout(item.template, item.variables)[2]
    except APIError:
        raise APIError('sms_template_unavailable', 'قالب پیامک در دسترس نیست.', 503) from None


def sample_preview(layout):
    origin = sms_origin()
    full_sms = render_recipient_sms(SAMPLE_MESSAGE, origin, SAMPLE_TOKEN, layout=layout)
    body_units = freeform_body_limit(origin, SAMPLE_TOKEN, layout=layout)
    return {'full_sms': full_sms, 'sms_units': sms_units(full_sms),
            'sms_segments': sms_segments(full_sms), 'body_units': body_units}


def draft(data):
    template, variables, layout = compile_layout(data['template'], data['variables'])
    sample = sample_preview(layout)
    # Account for the legacy anonymous preview's slightly longer preferences link.
    if min(sample['body_units'], freeform_body_limit(sms_origin(), '', layout=layout)) < MIN_BODY_UNITS:
        invalid('template', f'قالب را کوتاه‌تر کنید تا دست‌کم {fa_number(MIN_BODY_UNITS)} واحد برای متن پیام جا بماند.')
    return template, variables, sample


def settings_data(template, variables, revision, preview):
    return {'template': template, 'variables': variables, 'revision': revision, 'preview': preview,
            'default_template': DEFAULT_SMS_TEMPLATE, 'max_template_length': MAX_TEMPLATE_LENGTH,
            'max_variables': MAX_VARIABLES, 'max_value_length': MAX_VALUE_LENGTH}


def audit_value(item):
    raw = json.dumps([item.template, item.variables], ensure_ascii=True, separators=(',', ':'))
    return {'revision': item.revision, 'fingerprint': digest(raw)}


@transaction.atomic
def save(actor, data):
    if set(data) != {'template', 'variables', 'revision'} or type(data['revision']) is not int or not 0 <= data['revision'] < 2147483647:
        invalid('template', 'ساختار یا نسخهٔ قالب معتبر نیست. قالب را دوباره دریافت کنید.')
    template, variables, preview = draft(data)
    item, _ = SMSTemplateSettings.objects.get_or_create(pk=1, defaults={'template': DEFAULT_SMS_TEMPLATE})
    item = SMSTemplateSettings.objects.select_for_update().get(pk=1)
    if item.revision != data['revision']:
        raise APIError('settings_changed', 'قالب تغییر کرده است. آخرین نسخه را دریافت کنید و ویرایش را دوباره بررسی کنید.', 409)
    if (item.template, item.variables) != (template, variables):
        before = audit_value(item)
        item.template, item.variables = template, variables
        item.revision += 1
        item.save(update_fields=['template', 'variables', 'revision', 'updated_at'])
        OperatorAudit.objects.create(actor=actor, action='update_sms_template', object_id='sms-template',
            reason='ذخیرهٔ قالب پیامک از پنل مدیریت', before=before, after=audit_value(item))
    return settings_data(template, variables, item.revision, preview)


@vary_on_cookie
@staff_api(['GET', 'PUT'], 'core.manage_site_limits')
def configuration(request):
    if request.method == 'PUT':
        return save(request.user, body(request))
    item = SMSTemplateSettings.objects.filter(pk=1).first()
    if item is None:
        return settings_data(DEFAULT_SMS_TEMPLATE, [], 0, sample_preview(DEFAULT_SMS_TEMPLATE))
    template, variables, layout = compile_layout(item.template, item.variables)
    return settings_data(template, variables, item.revision, sample_preview(layout))


@vary_on_cookie
@staff_api(['POST'], 'core.manage_site_limits')
def preview(request):
    data = body(request)
    if set(data) != {'template', 'variables'}:
        invalid('template', 'ساختار پیش‌نمایش قالب معتبر نیست.')
    return draft(data)[2]
