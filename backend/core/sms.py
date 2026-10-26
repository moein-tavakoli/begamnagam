"""Build the reviewed recipient SMS snapshot before the sender confirms it."""
from .moderation import DIRECT_TEMPLATES, TEMPLATES, ModerationRejected, moderate

SMS_INTRO = 'نمیدونم بهت بگم یا نگم؟'


class SMSTooLong(Exception):
    pass


def compose_recipient_sms(category, body, origin, token, *, direct=False):
    templates = (DIRECT_TEMPLATES if direct else TEMPLATES)[category]
    if body not in templates:
        raise ModerationRejected('unreviewed_template')
    footer = '\nبگم نگم | لغو: ' + origin + ('/r/' + token if token else '/preferences')
    # Keep the selected text when it fits. A longer legacy/model choice can use
    # another reviewed text in the same category and tone, never truncation.
    for candidate in [body, *templates]:
        full_sms = SMS_INTRO + '\n' + candidate + footer
        if len(full_sms.encode('utf-16-le')) // 2 <= 201:
            moderate(candidate)
            return candidate, full_sms
    raise SMSTooLong()


def freeform_body_limit(origin, token='Ab12Cd34'):
    envelope = SMS_INTRO + '\n' + '\nبگم نگم | لغو: ' + origin + ('/r/'+token if token else '/preferences')
    return 201-len(envelope.encode('utf-16-le'))//2


def compose_freeform_sms(body, origin, token):
    from .draft_guard import validate_polite_body
    limit = freeform_body_limit(origin, token)
    if limit < 1:
        raise SMSTooLong()
    body = validate_polite_body(body, max_units=limit)
    return SMS_INTRO+'\n'+body+'\nبگم نگم | لغو: '+origin+('/r/'+token if token else '/preferences')
