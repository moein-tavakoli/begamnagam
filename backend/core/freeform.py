"""Approve a bounded AI rewrite and bind it to the exact reviewed SMS snapshot."""
import hmac
import json
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import Account, Preview, RewriteBudget, RewriteUsage
from .privacy import digest
from .services import APIError
from .moderation import ModerationRejected, RewriteUnavailable, moderate, is_reviewed_template


def available():
    return (settings.AI_MODE == 'gapgpt' and bool(settings.GAPGPT_API_KEY) and bool(settings.GAPGPT_MODEL)
        and settings.GAPGPT_DAILY_REQUEST_LIMIT > 0 and settings.GAPGPT_USER_DAILY_LIMIT > 0)


def reserve(owner):
    """Reserve one rewrite (at most TWO 320-output-token API calls), no refund.

    Daily rows survive restarts/cache flushing. Unknown/failed requests retain the
    reservation because the provider may have charged either call.
    """
    if not available():
        raise APIError('freeform_unavailable', 'بازنویسی متن دلخواه فعلاً فعال نیست؛ از پیشنهاد آماده استفاده کن.', 409)
    from .safety import ensure_open
    ensure_open()
    day = timezone.localdate()
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner.pk)
        account = Account.objects.get(user=owner)
        if account.suspended or account.deletion_requested_at or not owner.is_active:
            raise APIError('account_unavailable', 'بازنویسی با این حساب فعلاً مجاز نیست.', 403)
        RewriteBudget.objects.get_or_create(day=day, defaults={'limit_requests': settings.GAPGPT_DAILY_REQUEST_LIMIT})
        budget = RewriteBudget.objects.select_for_update().get(pk=day)
        if RewriteUsage.objects.filter(owner=owner, budget=budget).count() >= settings.GAPGPT_USER_DAILY_LIMIT:
            raise APIError('rewrite_daily_limit', 'سقف بازنویسی امروز حساب تکمیل شده است؛ فردا دوباره تلاش کن.', 429)
        if budget.reserved_requests >= min(budget.limit_requests, settings.GAPGPT_DAILY_REQUEST_LIMIT):
            raise RewriteUnavailable()
        budget.reserved_requests += 1
        budget.save(update_fields=['reserved_requests'])
        return RewriteUsage.objects.create(owner=owner, budget=budget)


def prepare(owner, text, *, max_units, direct=False):
    from .draft_guard import sanitize_draft, validate_polite_body
    from .gapgpt import rewrite_message, GapGPTUnavailable, GapGPTRejected
    cleaned = sanitize_draft(text)
    reserve(owner)
    try:
        output = rewrite_message(cleaned, max_units=max_units, direct=direct)
    except GapGPTRejected:
        raise ModerationRejected('unsafe_or_changed_intent') from None
    except GapGPTUnavailable:
        raise RewriteUnavailable() from None
    # Only the polite model body is persisted; raw/sanitized drafts are transient.
    return validate_polite_body(output, max_units=max_units)


def signature(preview):
    value = [str(preview.pk), preview.owner_id, preview.category, preview.moderation_mode,
        preview.generated_body, preview.text, preview.full_sms, preview.recipient_hash,
        preview.terms_version, preview.expires_at.isoformat(), preview.is_free, preview.price_toman]
    return digest('approved-gapgpt-v1:'+json.dumps(value, ensure_ascii=False, separators=(',', ':')))


def validate_preview(preview, *, recipient_hash=None):
    from .draft_guard import validate_polite_body
    if (preview.moderation_mode != 'gapgpt' or preview.category != 'custom' or preview.text != ''
            or not preview.generated_body or not preview.review_signature
            or not hmac.compare_digest(preview.review_signature, signature(preview))
            or (recipient_hash is not None and recipient_hash != preview.recipient_hash)):
        raise ModerationRejected('unreviewed_snapshot')
    validate_polite_body(preview.generated_body, max_units=201)
    if len(preview.full_sms.encode('utf-16-le'))//2 > 201:
        raise ModerationRejected('unreviewed_snapshot')


def validate_order(order):
    preview = order.preview
    if preview.moderation_mode == 'gapgpt':
        validate_preview(preview, recipient_hash=order.recipient_hash)
        if order.owner_id != preview.owner_id or order.text != '' or order.category != 'custom' or order.full_sms != preview.full_sms:
            raise ModerationRejected('unreviewed_snapshot')
    else:
        moderate(order.text)
        if not is_reviewed_template(order.category, order.text) or order.full_sms != preview.full_sms:
            raise ModerationRejected('unreviewed_snapshot')
