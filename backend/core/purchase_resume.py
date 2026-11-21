"""Resolve the exact website preview without copying message data into financial records."""
import uuid

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from .models import CreditPurchase, MessageAttempt, Order, Preview
from .privacy import digest, normalize_phone
from .services import APIError


def resume_reference(data, key):
    if 'resume_preview_id' not in data:
        return None, ''
    try:
        preview_id = uuid.UUID(data['resume_preview_id'])
    except (ValueError, TypeError, AttributeError):
        raise APIError('invalid_input', 'شناسهٔ پیش‌نمایش معتبر نیست.', 422) from None
    # A purchase retry must still match after private-data retention clears its FK.
    return preview_id, digest(f'purchase-resume-v1:{key}:{preview_id}')


def is_measured_trial(user, preview_id, environment):
    # Keep financial attribution after routine preview deletion without copying its content or identifier.
    return bool(preview_id) and MessageAttempt.objects.filter(owner=user, preview_id=preview_id,
        preview__from_text_trial=True, status='accepted', trial_environment=environment).exists()


def unavailable():
    return APIError('preview_expired', 'این پیش‌نمایش دیگر قابل ادامه نیست. یک پیام تازه آماده کن.', 409)


def direct_recipient(preview):
    # Only the number from the accepted attempt may match the reviewed recipient.
    # Never read the private input or use it to reconstruct a message.
    try:
        attempts = MessageAttempt.objects.filter(preview=preview, owner_id=preview.owner_id, status='accepted')
        phone = attempts.values_list('recipient_phone', flat=True).first()
        phone = normalize_phone(phone)
    except (ValueError, InvalidToken):
        raise unavailable() from None
    if not preview.recipient_hash or digest(phone) != preview.recipient_hash:
        raise unavailable()
    return phone


def resolve(user, session_key, preview_id):
    from .freeform import validate_preview
    from .moderation import ModerationRejected, is_reviewed_template

    scoped = Preview.objects.defer('original_text').filter(pk=preview_id, owner=user, session_key=session_key,
                                                          order__owner_hidden_at__isnull=True)
    try:
        preview = scoped.first()
    except InvalidToken:
        raise unavailable() from None
    if not preview or not session_key:
        raise APIError('not_found', 'پیش‌نمایش پیدا نشد.', 404)
    if user.account.suspended or user.account.deletion_requested_at:
        raise APIError('account_unavailable', 'این حساب فعلاً اجازهٔ ارسال ندارد.', 403)
    if (preview.is_free or preview.expires_at <= timezone.now() or not preview.full_sms or not preview.recipient_hash
            or preview.payment_method != 'credit' or preview.price_toman != 0
            or preview.terms_version != settings.TERMS_VERSION or Order.objects.filter(preview=preview).exists()):
        raise unavailable()
    if preview.moderation_mode in {'gapgpt', 'ollama'}:
        try:
            validate_preview(preview)
        except ModerationRejected:
            raise unavailable() from None
    elif not is_reviewed_template(preview.category, preview.text):
        raise unavailable()
    if preview.reply_to_id:
        from .anonymous_replies import check_turn, counterpart_phone
        check_turn(preview.reply_to, user)
        target = counterpart_phone(preview.reply_to, user)
    elif preview.is_shared_destination:
        from .personal_share import target_phone
        target = target_phone(user, preview.personal_share_token)
    else:
        return preview, direct_recipient(preview)
    if digest(target) != preview.recipient_hash:
        raise unavailable()
    return preview, ''


def checkout_for_preview(user, session_key, preview_id, package_id, method):
    """Called under the sender lock, including when another tab supplies a new request key."""
    from .packages import purchase_data

    preview, _ = resolve(user, session_key, preview_id)
    purchases = CreditPurchase.objects.filter(owner=user, resume_preview=preview)
    purchases = purchases.exclude(environment='live') if settings.DEMO_MODE else purchases.filter(environment='live')
    latest = purchases.order_by('-created_at').first()
    if not latest or purchase_data(latest)['status'] in {'failed', 'wallet_returned', 'rejected', 'cancelled'}:
        return None
    if latest.package_id != package_id or latest.payment_method != method:
        raise APIError('payment_reconciliation', 'برای این پیام خریدی ثبت شده است. وضعیت همان خرید را بررسی کن.', 409)
    return latest


def purchase_fields(purchase, session_key):
    result = {'resume_status': None, 'resume_preview_id': None}
    if not purchase.credited_at or not purchase.resume_reference_digest:
        return result
    result['resume_status'] = 'unavailable'
    if purchase.resume_preview_id:
        try:
            resolve(purchase.owner, session_key, purchase.resume_preview_id)
        except APIError:
            return result
        result.update(resume_status='ready', resume_preview_id=str(purchase.resume_preview_id))
    return result


def linked_purchase(user, session_key, preview):
    rows = CreditPurchase.objects.filter(owner=user, resume_preview=preview)
    rows = rows.exclude(environment='live') if settings.DEMO_MODE else rows.filter(environment='live')
    purchase = rows.only('credited_at').order_by(F('credited_at').desc(nulls_last=True)).first()
    if purchase and (not session_key or preview.session_key != session_key or preview.owner_id != user.pk):
        raise APIError('not_found', 'پیش‌نمایش پیدا نشد.', 404)
    return purchase
