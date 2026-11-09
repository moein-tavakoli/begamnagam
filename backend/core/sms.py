"""Build the reviewed recipient SMS snapshot before the sender confirms it."""
from django.conf import settings

from .moderation import DIRECT_TEMPLATES, TEMPLATES, ModerationRejected, is_reviewed_template, moderate

SMS_INTRO = 'نمیدونم بهت بگم یا نگم؟'
MESSAGE_SLOT = '{{message}}'
OPT_OUT_SLOT = '{{opt_out}}'
DEFAULT_SMS_TEMPLATE = '\n'.join((SMS_INTRO, MESSAGE_SLOT, OPT_OUT_SLOT))
SMS_WARNING_SEGMENTS = 3
MAX_REWRITE_BODY_UNITS = 201


def sms_origin():
    return settings.APP_BASE_URL.removeprefix('https://').removeprefix('http://')


def sms_units(text):
    return len(text.encode('utf-16-le')) // 2


def sms_segments(text):
    units = sms_units(text)
    return 1 if units <= 70 else (units + 66) // 67


def render_recipient_sms(body, origin, token, *, reply_token='', layout=DEFAULT_SMS_TEMPLATE):
    stop_path = '/r/' + token if token else '/preferences'
    footer = 'لغو: ' + origin + stop_path
    if reply_token:
        footer = 'پاسخ: ' + origin + '/r/p' + reply_token + '\n' + footer
    return layout.replace(OPT_OUT_SLOT, footer).replace(MESSAGE_SLOT, body)


def sender_sms(full_sms, *, is_reply):
    if not is_reply or not full_sms:
        return full_sms
    # Reply snapshots end in the stop link, optionally preceded by a reply link.
    # The copy sent to the recipient is sealed and retains both capabilities.
    lines = full_sms.split('\n')
    lines[-1] = 'لینک لغو دریافت'
    if len(lines) >= 2 and lines[-2].startswith('پاسخ: ') and '/r/p' in lines[-2]:
        lines[-2] = 'لینک پاسخ'
    return '\n'.join(lines)


def compose_recipient_sms(category, body, origin, token, *, direct=False, message_tone=None,
                          reply_token='', layout=DEFAULT_SMS_TEMPLATE, exact=False):
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
    return body, render_recipient_sms(body, origin, token, reply_token=reply_token, layout=layout)


def compose_freeform_sms(body, origin, token, *, reply_token='', layout=DEFAULT_SMS_TEMPLATE):
    from .draft_guard import validate_polite_body
    body = validate_polite_body(body, max_units=MAX_REWRITE_BODY_UNITS)
    return render_recipient_sms(body, origin, token, reply_token=reply_token, layout=layout)
