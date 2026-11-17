"""A public receive link selects its owner's number inside the server."""
import re
import uuid

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.db import transaction

from .models import Account, PersonalShareLink
from .privacy import decrypt, digest, mask, normalize_phone
from .services import APIError, api, limited
from .views import body


def unavailable():
    return APIError('share_link_unavailable', 'این لینک شخصی در دسترس نیست. از صاحب لینک یک لینک تازه بگیر.', 404)


def parse_token(token):
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{32}', token):
        raise unavailable()
    return uuid.UUID(hex=token)


def can_publish(account):
    return bool(account.phone_cipher and not account.suspended and not account.deletion_requested_at)


def target_phone(sender, token_id, *, lock=False):
    links = PersonalShareLink.objects.select_related('account').filter(
        pk=token_id, account__user__is_active=True, account__suspended=False,
        account__deletion_requested_at__isnull=True,
    ).exclude(account__phone_cipher='')
    if lock:
        # A send and a revocation contend on the link, not the recipient's balance row.
        links = links.select_for_update(of=('self',))
    link = links.first()
    if link is None:
        raise unavailable()
    if link.account.phone_hash == sender.account.phone_hash:
        raise APIError('self_recipient', 'این لینک برای دریافت پیام به شمارهٔ خودت است. آن را برای دیگران بفرست.', 409)
    try:
        phone = normalize_phone(decrypt(link.account.phone_cipher))
    except (InvalidToken, ValueError):
        raise unavailable() from None
    if digest(phone) != link.account.phone_hash:
        raise unavailable()
    return phone


@api(['GET', 'POST', 'DELETE'], authenticated=True)
def manage(request):
    if request.method == 'GET':
        account = request.user.account
        token_id = PersonalShareLink.objects.filter(account=account).values_list('pk', flat=True).first()
    else:
        if request.method == 'POST':
            if body(request):
                raise APIError('invalid_input', 'لینک فقط برای شمارهٔ تأییدشدهٔ همین حساب ساخته می‌شود.', 422)
            limited('personal-share-create', str(request.user.pk), 20, 600)
        with transaction.atomic():
            account = Account.objects.select_for_update().get(user=request.user)
            if request.method == 'DELETE':
                PersonalShareLink.objects.filter(account=account).delete()
                return {'url': None}
            if not can_publish(account):
                raise APIError('account_unavailable', 'ساخت لینک برای این حساب در دسترس نیست.', 403)
            link, _ = PersonalShareLink.objects.get_or_create(account=account)
            token_id = link.pk
    result = {'url': f'{settings.APP_BASE_URL}/send#{token_id.hex}' if token_id else None}
    if token_id and not can_publish(account):
        result['paused'] = True
    return result


@api(['POST'], authenticated=True)
def resolve(request):
    data = body(request)
    if set(data) != {'share_token'}:
        raise APIError('invalid_input', 'فقط کد لینک شخصی را بفرست.', 422)
    limited('personal-share-resolve', str(request.user.pk), 30, 600)
    return {'recipient_masked': mask(target_phone(request.user, parse_token(data['share_token'])))}
