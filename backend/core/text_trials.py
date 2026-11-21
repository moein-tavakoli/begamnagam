"""Bind a privately reviewed first-message trial exactly once, without another rewrite."""
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from . import ai_config, freeform
from .demo_limits import unlimited_demo_sends
from .message_tones import resolve as resolve_tone
from .models import Account, MessageAttempt, Order, Preview
from .moderation import ModerationRejected
from .privacy import digest, normalize_phone
from .purchase_resume import unavailable
from .recipient import issue_grant
from .safety import ensure_open
from .services import APIError, api, limited
from .sms import REPLY_SLOT, compose_freeform_sms, sms_origin
from .sms_template_settings import current_sms_layout, sample_recipient_code
from .views import body, limit_preview_origin, preview_data


@api(['POST'], authenticated=True)
def bind(request, trial_id):
    data = body(request)
    if set(data) != {'recipient_phone'}:
        raise APIError('invalid_input', 'فقط شمارهٔ گیرنده را وارد کن.', 422)
    unlimited = unlimited_demo_sends(request.user)
    limit_preview_origin(request, unlimited)
    if not unlimited:
        limited('preview-user', str(request.user.pk), 20, 600)
    phone = normalize_phone(data['recipient_phone'])
    recipient_hash = digest(phone)
    with transaction.atomic():
        # Orders, checkout and other binds for this sender use the same lock order.
        get_user_model().objects.select_for_update().only('pk').get(pk=request.user.pk)
        account = Account.objects.get(user=request.user)
        if account.suspended or account.deletion_requested_at:
            raise APIError('account_unavailable', 'این حساب فعلاً اجازهٔ ارسال ندارد.', 403)
        ensure_open()
        try:
            preview = Preview.objects.select_for_update().defer('original_text').get(pk=trial_id,
                from_text_trial=True, owner=request.user, session_key=request.session.session_key)
        except Preview.DoesNotExist:
            raise APIError('not_found', 'پیش‌نمایش پیدا نشد.', 404) from None
        except InvalidToken:
            raise unavailable() from None
        if (preview.expires_at <= timezone.now() or preview.terms_version != settings.TERMS_VERSION
                or Order.objects.filter(preview=preview).exists() or settings.PILOT_POSITIVE_ONLY):
            raise unavailable()
        if recipient_hash == account.phone_hash:
            raise APIError('self_recipient', 'شمارهٔ گیرنده باید با شمارهٔ خودت متفاوت باشد.', 422)
        try:
            freeform.validate_preview(preview, allow_unbound_trial=True)
        except ModerationRejected:
            raise unavailable() from None
        if preview.recipient_hash:
            if preview.recipient_hash != recipient_hash:
                raise APIError('quote_recipient_changed', 'شماره عوض شده؛ پیش‌نمایش تازه بساز.', 409)
            return preview_data(preview)

        if preview.message_tone != resolve_tone(None, ai_config.current()):
            raise unavailable()
        layout, variables = current_sms_layout()
        origin = sms_origin()
        sample = compose_freeform_sms(preview.generated_body, origin, sample_recipient_code(layout),
                                      layout=layout, variables=variables)
        if sample != preview.full_sms:
            raise unavailable()
        token = issue_grant(preview, recipient_hash, with_reply=REPLY_SLOT in layout)
        preview.full_sms = compose_freeform_sms(preview.generated_body, origin, token, layout=layout, variables=variables)
        preview.recipient_hash = recipient_hash
        preview.is_free = account.unlimited_free_sends or account.free_sends_remaining > 0
        preview.review_signature = freeform.signature(preview)
        preview.save(update_fields=['full_sms', 'recipient_hash', 'is_free', 'review_signature'])
        attempts = MessageAttempt.objects.filter(preview=preview, owner=request.user, status='accepted')
        if attempts.update(recipient_phone=phone) != 1:
            raise unavailable()
        return preview_data(preview)
