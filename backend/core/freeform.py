"""Approve a bounded AI rewrite and bind it to the exact reviewed SMS snapshot."""
import hmac
import json
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import Account, Preview, RewriteBudget, RewriteUsage
from .privacy import decrypt, digest
from .services import APIError
from .moderation import ModerationRejected, RewriteUnavailable, moderate, is_reviewed_template
from .sms import MAX_REWRITE_BODY_UNITS


def available(config=None):
    from .ai_config import available as ai_available
    return ai_available(config)


def reserve(owner, config=None):
    """Reserve one rewrite (at most two 256-output-token calls), no refund.

    Daily rows survive restarts/cache flushing. Unknown/failed requests retain the
    reservation because the provider may have charged either call.
    """
    from .ai_config import current
    config = config or current()
    if not available(config):
        raise APIError('freeform_unavailable', 'بازنویسی متن دلخواه فعلاً فعال نیست؛ از پیشنهاد آماده استفاده کن.', 409)
    from .safety import ensure_open
    ensure_open()
    day = timezone.localdate()
    from .limits import policy
    limits = policy()
    local = config.provider == 'ollama'
    daily = config.daily_limit if local else limits.rewrite_daily_limit
    per_user = config.user_daily_limit if local else limits.rewrite_user_limit
    unlimited = not local and limits.rewrite_daily_unlimited
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=owner.pk)
        account = Account.objects.get(user=owner)
        if account.suspended or account.deletion_requested_at or not owner.is_active:
            raise APIError('account_unavailable', 'بازنویسی با این حساب فعلاً مجاز نیست.', 403)
        if account.rewrite_daily_limit is not None:
            per_user = account.rewrite_daily_limit
        RewriteBudget.objects.get_or_create(day=day, defaults={'limit_requests': daily})
        budget = RewriteBudget.objects.select_for_update().get(pk=day)
        if (per_user or account.rewrite_daily_limit is None) and RewriteUsage.objects.filter(owner=owner, budget=budget).count() >= per_user:
            raise APIError('rewrite_daily_limit', 'سقف بازنویسی امروز حساب تکمیل شده است؛ فردا دوباره تلاش کن.', 429)
        daily_limit = daily if local or not limits._state.adding else min(budget.limit_requests, daily)
        if not unlimited and budget.reserved_requests >= daily_limit:
            raise RewriteUnavailable()
        budget.reserved_requests += 1
        budget.save(update_fields=['reserved_requests'])
        return RewriteUsage.objects.create(owner=owner, budget=budget)


def prepare(owner, text, *, max_units, direct=False, message_tone=None, config=None, exact_wording=False, preserve_phrase=''):
    from .draft_guard import contains_whole_phrase, sanitize_draft, validate_polite_body, validate_trial_phrase, wording_matches
    from .gapgpt import rewrite_message, GapGPTUnavailable, GapGPTRejected
    from .ai_config import current
    config = config or current()
    cleaned = sanitize_draft(text)
    rewrite_options = {'message_tone': message_tone} if message_tone is not None else {}
    if exact_wording:
        # A verbatim source must already meet all local output requirements.
        # Its original typography then reaches both independent model stages.
        try:
            cleaned = validate_polite_body(text, max_units=max_units)
        except ModerationRejected:
            raise ModerationRejected('trial_wording_unavailable') from None
        rewrite_options['wording'] = {'exact_wording': True}
    elif preserve_phrase:
        validate_trial_phrase(preserve_phrase, text, cleaned, max_units=max_units)
        rewrite_options['wording'] = {'preserve_phrase': preserve_phrase,
                                      'whole_words': contains_whole_phrase(text, preserve_phrase)}
    try:
        if config.provider == 'ollama':
            from .ollama_rewrite import slot, rewrite_message as local_rewrite
            with slot(config.parallel_requests):
                reserve(owner, config)
                output = local_rewrite(cleaned, max_units=max_units, direct=direct, config=config, **rewrite_options)
        else:
            reserve(owner, config)
            # Preserve the legacy call contract when no DB override exists.
            options = {'config': config} if not config._state.adding else {}
            output = rewrite_message(cleaned, max_units=max_units, direct=direct, **options, **rewrite_options)
    except GapGPTRejected as exc:
        raise ModerationRejected(exc.reason) from None
    except GapGPTUnavailable:
        raise RewriteUnavailable() from None
    # Only this approved body enters the sealed SMS snapshot. The view stores
    # the original separately in an encrypted, administrator-only field.
    approved = validate_polite_body(output, max_units=max_units)
    if 'wording' in rewrite_options and not wording_matches(approved, text, **rewrite_options['wording']):
        raise ModerationRejected('trial_wording_unavailable')
    return approved


def signature(preview):
    value = [str(preview.pk), preview.owner_id, preview.category, preview.moderation_mode,
        preview.generated_body, preview.text, preview.full_sms, preview.recipient_hash,
        preview.terms_version, preview.expires_at.isoformat(), preview.is_free, preview.price_toman]
    if preview.payment_method in {'wallet', 'gateway'}:
        value += ['payment-v1', preview.payment_method, preview.wallet_policy_version]
    if preview.message_tone != 'polite':
        value += ['tone-v1', preview.message_tone]
    if preview.reply_to_id:
        value += ['reply-v1', str(preview.reply_to_id)]
    if preview.is_shared_destination:
        value += ['personal-share-v1', str(preview.personal_share_token)]
    if preview.from_text_trial:
        # Retention clears session keys even on a pending order. Once bound,
        # the recipient hash remains part of the approved dispatch snapshot.
        value += ['text-trial-v1', '' if preview.recipient_hash else preview.session_key]
    return digest('approved-gapgpt-v1:'+json.dumps(value, ensure_ascii=False, separators=(',', ':')))


def validate_preview(preview, *, recipient_hash=None, allow_unbound_trial=False):
    from .draft_guard import validate_polite_body
    if (preview.moderation_mode not in {'gapgpt', 'ollama'} or preview.category != 'custom' or preview.text != ''
            or (preview.from_text_trial and not preview.recipient_hash and not allow_unbound_trial)
            or not preview.generated_body or not preview.review_signature
            or not hmac.compare_digest(preview.review_signature, signature(preview))
            or (recipient_hash is not None and recipient_hash != preview.recipient_hash)):
        raise ModerationRejected('unreviewed_snapshot')
    validate_polite_body(preview.generated_body, max_units=MAX_REWRITE_BODY_UNITS)


def validate_order(order):
    preview = order.preview
    if order.reply_to_id != preview.reply_to_id or bool(order.reply_to_id) != bool(order.reply_depth):
        raise ModerationRejected('unreviewed_snapshot')
    if preview.is_shared_destination or preview.from_text_trial:
        from cryptography.fernet import InvalidToken
        try:
            actual_hash = digest(decrypt(order.recipient_cipher))
        except InvalidToken:
            raise ModerationRejected('unreviewed_snapshot') from None
        if order.recipient_hash != preview.recipient_hash or actual_hash != order.recipient_hash:
            raise ModerationRejected('unreviewed_snapshot')
    if order.reply_to_id:
        from cryptography.fernet import InvalidToken
        from .anonymous_replies import counterpart_phone
        try:
            phone = counterpart_phone(order.reply_to, order.owner)
            if (order.reply_depth != order.reply_to.reply_depth + 1 or order.recipient_hash != digest(phone)
                    or decrypt(order.recipient_cipher) != phone):
                raise ModerationRejected('unreviewed_snapshot')
        except (APIError, InvalidToken):
            raise ModerationRejected('unreviewed_snapshot') from None
        if preview.moderation_mode not in {'gapgpt', 'ollama'}:
            raise ModerationRejected('unreviewed_snapshot')
    if preview.from_text_trial or preview.moderation_mode in {'gapgpt', 'ollama'}:
        validate_preview(preview, recipient_hash=order.recipient_hash)
        if order.owner_id != preview.owner_id or order.text != '' or order.category != 'custom' or order.full_sms != preview.full_sms:
            raise ModerationRejected('unreviewed_snapshot')
    else:
        moderate(order.text)
        if not is_reviewed_template(order.category, order.text) or order.full_sms != preview.full_sms:
            raise ModerationRejected('unreviewed_snapshot')
