"""Build reviewed recipient SMS snapshots and resolve the current sending line."""
import re

from django.conf import settings

from .models import SMSTemplateSettings
from .moderation import DIRECT_TEMPLATES, TEMPLATES, ModerationRejected, is_reviewed_template, moderate
from .recipient_codes import ACTION_CODE_PATTERN, INVITE_CODE_PATTERN, SHORT_REPLY_PATTERN, SHORT_STOP_PATTERN, is_short_code

SMS_INTRO = 'نمیدونم بهت بگم یا نگم؟'
MESSAGE_SLOT = '{{message}}'
OPT_OUT_SLOT = '{{opt_out}}'
REPLY_SLOT = '{{reply}}'
DEFAULT_SMS_TEMPLATE = '\n'.join((SMS_INTRO, MESSAGE_SLOT, REPLY_SLOT, OPT_OUT_SLOT))
SMS_VARIABLE_NAME = r'[a-z][a-z0-9_]{0,23}'
SMS_PLACEHOLDER = re.compile(r'\{\{ *(' + SMS_VARIABLE_NAME + r') *\}\}')
SMS_WARNING_SEGMENTS = 3
MAX_REWRITE_BODY_UNITS = 201
_REPLY_LINK = re.compile(rf'پاسخ: \S+?/(?:r/p[A-Za-z0-9]{{8}}|(?:r/)?{SHORT_REPLY_PATTERN})(?=\s|$)')
_OPT_OUT_LINK = re.compile(rf'لغو: \S+?/(?:r/[A-Za-z0-9]{{8}}|(?:r/)?{SHORT_STOP_PATTERN}|preferences)(?=\s|$)')
_ACTION_LINK = re.compile(rf'پاسخ یا لغو: \S+?/(?:r/)?{ACTION_CODE_PATTERN}(?=\s|$)')


def site_sms_origin():
    return settings.APP_BASE_URL.removeprefix('https://').removeprefix('http://').rstrip('/')


def sms_origin():
    return settings.SMS_LINK_HOST or site_sms_origin()


def recipient_sms_url(origin, token, *, root_path=None):
    short = is_short_code(token) or re.fullmatch(INVITE_CODE_PATTERN, token) is not None
    if root_path is None:
        root_path = settings.SMS_LINK_ROOT_PATH and origin == settings.SMS_LINK_HOST
    if short and root_path:
        return f'{origin}/{token}'
    return f'{origin}/r/{token}'


def current_sms_sender():
    sender = SMSTemplateSettings.objects.filter(pk=1).values_list('sender', flat=True).first()
    return sender or settings.KAVENEGAR_SENDER


def sms_units(text):
    return len(text.encode('utf-16-le')) // 2


def sms_segments(text):
    units = sms_units(text)
    return 1 if units <= 70 else (units + 66) // 67


def render_recipient_sms(body, origin, token, *, layout=DEFAULT_SMS_TEMPLATE, variables=None):
    link_url = recipient_sms_url(origin, token) if token else origin + '/preferences'
    combined = re.fullmatch(ACTION_CODE_PATTERN, token) is not None
    slots = {'reply', 'opt_out'}
    values = {
        **(variables or {}),
        'message': body,
        'site_url': settings.APP_BASE_URL.rstrip('/'),
    }
    link = ('پاسخ یا لغو: ' if combined else 'لغو: ') + link_url
    pieces = []
    has_link = False
    # The first eligible slot owns the shared link. Preserve the operator's
    # other text and skip lines left empty by the removed slots.
    for line in layout.split('\n'):
        line_parts = []
        skipped_slot = False
        after_recipient_link = False
        for index, part in enumerate(SMS_PLACEHOLDER.split(line)):
            name = part if index % 2 else None
            if name in slots:
                if has_link or (name == 'reply' and not combined):
                    skipped_slot = True
                    continue
                text = link
                has_link = True
            else:
                text = values[name] if name is not None else part
            if not text:
                continue
            if after_recipient_link and not text[0].isspace():
                line_parts.append(' ')
            line_parts.append(text)
            after_recipient_link = name in slots
        rendered_line = ''.join(line_parts)
        if skipped_slot and not rendered_line.strip():
            continue
        pieces.append(rendered_line)
    rendered = '\n'.join(pieces)
    if has_link:
        return rendered
    separator = '\n' if rendered and not rendered.endswith('\n') else ''
    return rendered + separator + link


def sender_sms(full_sms, *, is_reply):
    if not is_reply or not full_sms:
        return full_sms
    # The sender of an anonymous reply must not see the recipient's capabilities.
    # Replace the labeled links wherever they appear in the sealed copy.
    text = _ACTION_LINK.sub('لینک پاسخ یا لغو دریافت', full_sms)
    return _OPT_OUT_LINK.sub('لینک لغو دریافت', _REPLY_LINK.sub('لینک پاسخ', text))


def compose_recipient_sms(category, body, origin, token, *, direct=False, message_tone=None,
                          layout=DEFAULT_SMS_TEMPLATE, variables=None, exact=False):
    if exact:
        if not is_reviewed_template(category, body):
            raise ModerationRejected('unreviewed_template')
    else:
        if message_tone is None:
            templates = (DIRECT_TEMPLATES if direct else TEMPLATES)[category]
        else:
            from .message_tones import templates as tone_templates
            templates = tone_templates(category, message_tone)
        if body not in templates:
            raise ModerationRejected('unreviewed_template')
    moderate(body)
    return body, render_recipient_sms(body, origin, token, layout=layout, variables=variables)


def compose_freeform_sms(body, origin, token, *, layout=DEFAULT_SMS_TEMPLATE, variables=None):
    from .draft_guard import validate_polite_body
    body = validate_polite_body(body, max_units=MAX_REWRITE_BODY_UNITS)
    return render_recipient_sms(body, origin, token, layout=layout, variables=variables)
