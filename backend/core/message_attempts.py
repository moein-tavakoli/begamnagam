"""Persist bounded private input separately from approved dispatch snapshots."""
import logging
from functools import wraps

from django.db import transaction

from .models import MessageAttempt
from .privacy import normalize_phone
from .services import APIError, is_product_authenticated

logger = logging.getLogger(__name__)


def record_attempt(request, *, preview=None, error=None):
    if error is not None and not getattr(request, "_message_attempt_admitted", False):
        return
    # Rejected quota admissions must not turn into an unbounded private-data sink.
    if error is not None and (error.status == 429 or error.code == 'invalid_input'):
        return
    if not is_product_authenticated(request.user):
        return
    data = getattr(request, '_message_attempt_data', {})
    text = preview.original_text if preview else data.get('text')
    if not isinstance(text, str) or not 0 < len(text) <= 280:
        return
    try:
        text.encode('utf-8')
    except UnicodeEncodeError:
        return
    try:
        phone = normalize_phone(data.get('recipient_phone', ''))
    except ValueError:
        phone = ''
    status = 'accepted' if preview else ('failed' if error.status >= 500 else 'rejected')
    try:
        # A savepoint also protects an existing request transaction on write failure.
        with transaction.atomic():
            MessageAttempt.objects.create(owner=request.user, preview=preview,
                original_text=text, recipient_phone=phone,
                message_tone=preview.message_tone if preview else getattr(request, '_message_attempt_tone', ''),
                status=status, reason_code='preview_accepted' if preview else error.code,
                moderation_event_id=getattr(request, '_message_attempt_moderation_event', None))
    except Exception:
        # Never include exception messages, payloads, phones or drafts in logs.
        logger.warning('Private message attempt persistence unavailable')
        if preview:
            request._message_attempt_moderation_event = None
            raise APIError('service_unavailable', 'سرویس موقتاً در دسترس نیست.', 503) from None


def capture_preview_attempt(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except APIError as exc:
            record_attempt(request, error=exc)
            raise
        except ValueError:
            record_attempt(request, error=APIError('invalid_input', '', 400))
            raise
    return wrapped
