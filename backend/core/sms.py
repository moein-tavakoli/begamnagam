"""Build the reviewed recipient SMS snapshot before the sender confirms it."""
from django.conf import settings

from .moderation import DIRECT_TEMPLATES, TEMPLATES, ModerationRejected, moderate

SMS_INTRO = 'نمیدونم بهت بگم یا نگم؟'
MESSAGE_SLOT = '{{message}}'
OPT_OUT_SLOT = '{{opt_out}}'
DEFAULT_SMS_TEMPLATE = '\n'.join((SMS_INTRO, MESSAGE_SLOT, OPT_OUT_SLOT))
MAX_SMS_UNITS = 201


class SMSTooLong(Exception):
    pass


def sms_origin():
    return settings.APP_BASE_URL.removeprefix('https://').removeprefix('http://')


def sms_units(text):
    return len(text.encode('utf-16-le')) // 2


def sms_segments(text):
    units = sms_units(text)
    return 1 if units <= 70 else (units + 66) // 67


def render_recipient_sms(body, origin, token, *, layout=DEFAULT_SMS_TEMPLATE):
    link = origin + ('/r/' + token if token else '/preferences')
    return layout.replace(OPT_OUT_SLOT, 'بگم نگم | لغو: ' + link).replace(MESSAGE_SLOT, body)


def compose_recipient_sms(category, body, origin, token, *, direct=False, message_tone=None, layout=DEFAULT_SMS_TEMPLATE):
    if message_tone is None:
        templates = (DIRECT_TEMPLATES if direct else TEMPLATES)[category]
    else:
        from .message_tones import templates as tone_templates
        templates = tone_templates(category, message_tone)
    if body not in templates:
        raise ModerationRejected('unreviewed_template')
    # Keep the selected text when it fits. A longer legacy/model choice can use
    # another reviewed text in the same category and tone, never truncation.
    for candidate in [body, *templates]:
        full_sms = render_recipient_sms(candidate, origin, token, layout=layout)
        if sms_units(full_sms) <= MAX_SMS_UNITS:
            moderate(candidate)
            return candidate, full_sms
    raise SMSTooLong()


def freeform_body_limit(origin, token='Ab12Cd34', *, layout=DEFAULT_SMS_TEMPLATE):
    return MAX_SMS_UNITS - sms_units(render_recipient_sms('', origin, token, layout=layout))


def compose_freeform_sms(body, origin, token, *, layout=DEFAULT_SMS_TEMPLATE):
    from .draft_guard import validate_polite_body
    limit = freeform_body_limit(origin, token, layout=layout)
    if limit < 1:
        raise SMSTooLong()
    body = validate_polite_body(body, max_units=limit)
    return render_recipient_sms(body, origin, token, layout=layout)
