"""Phone invitations. No referral codes, user-authored SMS or automatic resends."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from .models import Account, Invitation, InvitationSend, RecipientState
from .privacy import digest, encrypt, mask, normalize_phone
from .services import APIError, api, limited, recipient_unavailable

CONSENT_VERSION = 'invitations-v1'
ACTIVE = ['pending', 'submitting', 'unknown', 'accepted']
INVITE_BODY = 'یکی از آشناهایت به بگم نگم دعوتت کرده. با ثبت‌نام ۳ ارسال رایگان داری:'


def compose(token):
    from .sms import SMS_INTRO, SMSTooLong
    origin = settings.APP_BASE_URL.removeprefix('https://').removeprefix('http://').rstrip('/')
    text = SMS_INTRO + '\n' + INVITE_BODY + '\n' + origin + '\nلغو: ' + origin + '/r/' + token
    if len(text.encode('utf-16-le'))//2 > 201:
        raise SMSTooLong()
    return text


def lock_phone(phone_hash):
    # Registration, claims, delivery and opt-out share this lock.
    RecipientState.objects.get_or_create(phone_hash=phone_hash)
    return RecipientState.objects.select_for_update().get(phone_hash=phone_hash)


def record_registration(account):
    """Called in the verified signup transaction, with the phone lock held."""
    invitation = Invitation.objects.select_for_update().filter(phone_hash=account.phone_hash,
        registered_at__isnull=True, created_at__lte=account.created_at).first()
    if invitation:
        invitation.registered_at = timezone.now()
        invitation.save(update_fields=['registered_at'])
        # Reward takes the sender lock first, outside the signup's phone lock.
        # A durable unawarded row lets beat repair a lost callback after a crash.
        transaction.on_commit(lambda: reward_registration(invitation.pk), robust=True)
    InvitationSend.objects.filter(invitation__phone_hash=account.phone_hash, status='pending').update(
        status='cancelled', last_error_code='registered')


def reward_registration(invitation_id):
    from django.db.models import F
    from .models import OperatorAudit
    meta = Invitation.objects.filter(pk=invitation_id).values('inviter_id', 'phone_hash').first()
    if not meta:
        return
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=meta['inviter_id'])
        lock_phone(meta['phone_hash'])
        invitation = Invitation.objects.select_for_update().get(pk=invitation_id)
        if not invitation.registered_at or invitation.reward_awarded_at:
            return
        inviter = Account.objects.select_for_update().get(user_id=invitation.inviter_id)
        if inviter.deletion_requested_at:
            return
        # The initial signup grant and earned grants are updated independently.
        Account.objects.filter(pk=inviter.pk).update(free_sends_remaining=F('free_sends_remaining')+3,
            free_sends_earned_total=F('free_sends_earned_total')+3)
        invitation.reward_awarded_at = timezone.now()
        invitation.save(update_fields=['reward_awarded_at'])
        OperatorAudit.objects.create(action='invitation_reward', object_id=str(invitation.pk),
            reason='Verified first signup after phone invitation', after={'credits': 3})


def ensure_account(user):
    account = Account.objects.get(user=user)
    if not user.is_active or account.suspended or account.deletion_requested_at:
        raise APIError('account_unavailable', 'امکان دعوت با این حساب فعلاً وجود ندارد.', 403)
    return account


def new_send(invitation, key):
    from .limits import policy
    limits = policy()
    now = timezone.now()
    sends = list(invitation.sends.order_by('ordinal'))
    if invitation.registered_at or Account.objects.filter(phone_hash=invitation.phone_hash).exists():
        raise APIError('already_registered', 'این شخص قبلاً عضو سایت شده و امکان افزودن یا دعوت دوباره ندارد.', 409)
    if limits.invitation_validity_days and now >= invitation.created_at + timedelta(days=limits.invitation_validity_days):
        raise APIError('invitation_expired', f'مهلت {limits.invitation_validity_days}روزهٔ ارسال این دعوت تمام شده است.', 409)
    if limits.invitation_max_sends and len(sends) >= limits.invitation_max_sends:
        raise APIError('invitation_limit', f'برای هر مخاطب حداکثر {limits.invitation_max_sends} درخواست پیامک دعوت مجاز است.', 409)
    if any(s.status in ACTIVE for s in sends if s.status != 'accepted'):
        raise APIError('invitation_pending', 'نتیجهٔ دعوت قبلی هنوز مشخص نیست؛ دوباره ارسال نکن.', 409)
    if limits.invitation_cooldown_hours and sends and sends[-1].created_at + timedelta(hours=limits.invitation_cooldown_hours) > now:
        raise APIError('invitation_cooldown', f'بین دو درخواست دعوت به همین شماره باید {limits.invitation_cooldown_hours} ساعت فاصله باشد.', 409)
    if limits.invitation_limit and limits.invitation_window_hours and InvitationSend.objects.filter(invitation__inviter=invitation.inviter,
            created_at__gt=now-timedelta(hours=limits.invitation_window_hours)).count() >= limits.invitation_limit:
        raise APIError('invitation_daily_limit', f'سقف {limits.invitation_limit} درخواست دعوت در {limits.invitation_window_hours} ساعت تکمیل شده است.', 429)
    from .recipient import issue_grant
    send = InvitationSend.objects.create(invitation=invitation, ordinal=len(sends)+1, idempotency_key=key,
        available_at=now, consent_at=now, consent_version=CONSENT_VERSION,
        provider='console' if settings.DEMO_MODE and settings.SMS_BACKEND == 'console' else 'kavenegar')
    token = issue_grant(None, invitation.phone_hash, invitation_send=send)
    try:
        send.full_sms = compose(token)
    except Exception:
        raise APIError('invitation_unavailable', 'ثبت دعوت فعلاً ممکن نیست.', 503) from None
    send.save(update_fields=['full_sms'])
    transaction.on_commit(lambda: publish(send.pk))
    return send


def request_invitation(user, phone, key, invitation_id=None):
    phone = normalize_phone(phone) if phone is not None else None
    try:
        key = uuid.UUID(str(key))
    except (ValueError, TypeError, AttributeError):
        raise APIError('idempotency_required', 'شناسهٔ درخواست معتبر نیست.') from None
    with transaction.atomic():
        # Serializes the sender's daily quota across different target numbers.
        get_user_model().objects.select_for_update().get(pk=user.pk)
        account = ensure_account(user)
        previous = InvitationSend.objects.select_related('invitation').filter(idempotency_key=key).first()
        if previous:
            if previous.invitation.inviter_id != user.pk or (phone and previous.invitation.phone_hash != digest(phone)) or (invitation_id and previous.invitation_id != invitation_id):
                raise APIError('idempotency_conflict', 'شناسهٔ درخواست قبلاً استفاده شده است.', 409)
            return previous.invitation
        if invitation_id:
            meta = Invitation.objects.filter(pk=invitation_id, inviter=user).first()
            if not meta:
                raise APIError('not_found', 'دعوت پیدا نشد.', 404)
            phone_hash = meta.phone_hash
        else:
            phone_hash = digest(phone)
        if phone_hash == account.phone_hash:
            raise APIError('self_invitation', 'نمی‌توانی شمارهٔ خودت را دعوت کنی.', 409)
        state = lock_phone(phone_hash)
        invitation = Invitation.objects.select_for_update().filter(phone_hash=phone_hash).first()
        # The requested membership notice is confined to this authenticated panel.
        if Account.objects.filter(phone_hash=phone_hash).exists():
            raise APIError('already_registered', 'این شخص قبلاً عضو سایت شده و امکان افزودن یا دعوت دوباره ندارد.', 409)
        if invitation and invitation.inviter_id != user.pk:
            raise APIError('already_invited', 'این شماره قبلاً دعوت شده و امکان افزودن آن وجود ندارد.', 409)
        if invitation and not invitation_id:
            raise APIError('already_added', 'این شماره در فهرست دعوت‌های خودت هست؛ از همان فهرست پیگیری کن.', 409)
        if state.blocked:
            raise recipient_unavailable()
        if not invitation:
            invitation = Invitation.objects.create(inviter=user, phone_hash=phone_hash,
                phone_cipher=encrypt(phone), phone_masked=mask(phone))
        new_send(invitation, key)
    return invitation


def serialize(invitation):
    from .limits import policy
    limits = policy()
    sends = list(invitation.sends.all())
    latest = max(sends, key=lambda s: s.ordinal) if sends else None
    registered = invitation.registered_at is not None
    expired = bool(limits.invitation_validity_days and timezone.now() >= invitation.created_at + timedelta(days=limits.invitation_validity_days))
    pending = any(s.status in ['pending', 'submitting', 'unknown'] for s in sends)
    next_at = (max((s.created_at+timedelta(hours=limits.invitation_cooldown_hours) for s in sends), default=invitation.created_at)
               if limits.invitation_cooldown_hours else timezone.now())
    can_resend = not registered and not expired and (not limits.invitation_max_sends or len(sends) < limits.invitation_max_sends) and not pending and timezone.now() >= next_at
    reasons = {'registered': 'این مخاطب ثبت‌نام کرده است؛ دعوت دیگری ارسال نمی‌شود.',
        'account_unavailable': 'ارسال دعوت با این حساب فعلاً محدود شده است.',
        'recipient_unavailable': 'امکان ارسال یا دریافت برای این شماره فعلاً وجود ندارد.',
        'queue_expired': 'مهلت ارسال این درخواست تمام شده است.',
        'recipient_cooldown': 'دعوت پس از گذشت فاصلهٔ مجاز دریافت ارسال می‌شود.',
        'outside_sending_window': 'دعوت در ساعت مجاز ارسال خواهد شد.'}
    reason = reasons.get(latest.last_error_code) if latest else None
    if latest and latest.status == 'failed':
        reason = reason or 'ارسال دعوت انجام نشد؛ در زمان مجاز می‌توانی دوباره درخواست بدهی.'
    if latest and latest.status in ['unknown', 'submitting']:
        reason = 'نتیجهٔ ارسال در حال بررسی است؛ برای جلوگیری از تکرار، ارسال دوباره بسته است.'
    return {'id': str(invitation.pk), 'phone_masked': invitation.phone_masked,
        'created_at': invitation.created_at.isoformat(), 'registered_at': invitation.registered_at.isoformat() if registered else None,
        'status': 'registered' if registered else 'expired' if expired else 'waiting',
        'reward_credits': 3 if invitation.reward_awarded_at else 0,
        'reward_pending': registered and invitation.reward_awarded_at is None,
        'send_count': len(sends), 'sends_remaining': max(0, limits.invitation_max_sends-len(sends)) if limits.invitation_max_sends else None, 'can_resend': can_resend,
        'max_sends': limits.invitation_max_sends or None, 'cooldown_hours': limits.invitation_cooldown_hours, 'validity_days': limits.invitation_validity_days or None,
        'next_send_at': next_at.isoformat(), 'delivery_status': latest.status if latest else 'pending',
        'reason': reason, 'sends': [{'number': s.ordinal, 'status': s.status, 'created_at': s.created_at.isoformat()} for s in sends]}


@api(['GET', 'POST'], authenticated=True)
def invitations_view(request):
    from .views import body
    if request.method == 'POST':
        data = body(request)
        validate_request(request, data)
        invitation = request_invitation(request.user, data.get('phone', ''), request.headers.get('Idempotency-Key'))
        invitation.refresh_from_db()
        return serialize(invitation)
    try:
        offset = max(0, int(request.GET.get('offset', '0')))
    except ValueError:
        raise APIError('invalid_input', 'شمارهٔ صفحه معتبر نیست.') from None
    query = Invitation.objects.filter(inviter=request.user)
    from .limits import policy
    limits = policy()
    items = list(query.order_by('-created_at', '-id').prefetch_related('sends')[offset:offset+51])
    window_limit = limits.invitation_limit if limits.invitation_window_hours else 0
    return {'results': [serialize(i) for i in items[:50]], 'next_offset': offset+50 if len(items)>50 else None,
        'total': query.count(), 'registered': query.filter(registered_at__isnull=False).count(),
        'earned_credits': query.filter(reward_awarded_at__isnull=False).count()*3,
        'daily_remaining': max(0, window_limit-InvitationSend.objects.filter(invitation__inviter=request.user,
            created_at__gt=timezone.now()-timedelta(hours=limits.invitation_window_hours)).count()) if window_limit else None,
        'consent_version': CONSENT_VERSION, 'max_sends': limits.invitation_max_sends or None, 'daily_limit': window_limit or None,
        'window_hours': limits.invitation_window_hours, 'cooldown_hours': limits.invitation_cooldown_hours,
        'validity_days': limits.invitation_validity_days or None}


def validate_request(request, data):
    if data.get('consent') is not True or data.get('consent_version') != CONSENT_VERSION:
        raise APIError('consent_required', 'فقط آشنایانِ مایل به دریافت دعوت را اضافه کن و تأیید را بزن.', 422)
    # Limits failed membership lookups as well as successful invitations.
    limited('invite-account', str(request.user.pk), 30, 86400)
    limited('invite-ip', request.META.get('REMOTE_ADDR', 'unknown'), 100, 86400)


@api(['POST'], authenticated=True)
def resend_view(request, invitation_id):
    from .views import body
    validate_request(request, body(request))
    invitation = request_invitation(request.user, None, request.headers.get('Idempotency-Key'), invitation_id)
    invitation.refresh_from_db()
    return serialize(invitation)


def publish(send_id):
    from .tasks import deliver_invitation
    try:
        deliver_invitation.delay(str(send_id))
    except Exception:
        # Beat retries only the pending outbox, never an ambiguous submission.
        pass
