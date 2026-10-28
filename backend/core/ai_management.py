"""AI administration and transient local evaluation; never creates an SMS."""
import time
from django.conf import settings
from .ai_config import current, update, values
from .management_api import staff_api
from .services import APIError, limited
from .views import body


def payload(config):
    from .message_tones import TONES
    return {'values': values(config), 'revision': config.revision,
            'tone_options': [{key: row[key] for key in ('id', 'field', 'label', 'description')} for row in TONES],
            'gapgpt_credentials_configured': bool(settings.GAPGPT_API_KEY),
            'synchronous': True, 'cloud_fallback': False}


@staff_api(['GET', 'POST'], 'core.manage_ai')
def configuration(request):
    config = current()
    if request.method == 'POST':
        data = body(request)
        config = update(request.user, data.get('values'), data.get('revision'), data.get('reason'))
    return payload(config)


@staff_api(['POST'], 'core.manage_ai')
def evaluate(request):
    from .draft_guard import sanitize_draft, validate_polite_body
    from .gapgpt import GapGPTRejected, GapGPTUnavailable
    from .moderation import ModerationRejected
    from .ollama_rewrite import rewrite_message, slot
    limited('ai-admin-test', str(request.user.pk), 10, 60)
    data = body(request)
    config = current()
    from .message_tones import resolve as resolve_tone
    tone = resolve_tone(data.get('message_tone'), config)
    # The test console never spends a paid API credit, even when GapGPT is active.
    config.provider = 'ollama'
    started = time.monotonic()
    try:
        cleaned = sanitize_draft(data.get('text'))
        with slot(config.parallel_requests):
            result = rewrite_message(cleaned, max_units=140, message_tone=tone, config=config)
        result = validate_polite_body(result, max_units=140)
        return {'allowed': True, 'message': result, 'elapsed_seconds': round(time.monotonic()-started, 3)}
    except (ModerationRejected, GapGPTRejected):
        return {'allowed': False, 'message': '', 'elapsed_seconds': round(time.monotonic()-started, 3)}
    except GapGPTUnavailable:
        raise APIError('rewrite_unavailable', 'مدل محلی در مهلت مشخص پاسخ تأییدشده نداد؛ نصب و آماده‌بودن مدل را بررسی کن.', 503) from None
