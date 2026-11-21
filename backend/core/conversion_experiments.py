"""Server-owned assignment, offer eligibility and first visible exposure."""
import hashlib
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Account, ConversionExposure, CreditPurchase, MessagePackage, Preview, SafetyControl
from .packages import balance_field, credit_environment, package_data
from .payment_options import options
from .services import APIError, api
from .wallet import has_open_checkout


SURFACES = {'preview': ('preview',), 'examples': ('pricing',), 'price': ('pricing', 'credits')}


def split(account_id, environment, experiment):
    seed = f'conversion-v1:{experiment}:{environment}:{account_id}'.encode('ascii')
    return 'treatment' if hashlib.sha256(seed).digest()[0] % 2 else 'control'


def assignment(account, payment_options=None):
    key = settings.CONVERSION_EXPERIMENT
    result = {'key': key, 'variant': None, 'inline_checkout': True, 'show_examples': key != 'examples'}
    if key == 'off' or not account or account.suspended or account.deletion_requested_at or account.unlimited_free_sends:
        return result
    methods = payment_options if payment_options is not None else options()
    demo_gateway = settings.DEMO_MODE and settings.PAYMENT_BACKEND == 'demo'
    if not (demo_gateway or methods['gateway_enabled'] or methods['card_enabled']):
        return result
    halted = SafetyControl.objects.filter(pk=1).values_list('halted', flat=True).first()
    if halted or (halted is None and not settings.DEMO_MODE):
        return result
    environment = credit_environment()
    purchases = CreditPurchase.objects.filter(owner_id=account.user_id, environment=environment)
    if purchases.filter(credited_at__isnull=False).exists() or has_open_checkout(account.user_id):
        return result
    packages = MessagePackage.objects.filter(active=True)
    if key == 'price':
        if (not packages.filter(message_count=9, price_toman=30000).exists()
                or packages.filter(message_count=8, price_toman=25000).exists()
                or not MessagePackage.objects.filter(price_experiment_only=True).exists()):
            return result
    elif key == 'preview':
        if not packages.filter(message_count=3, price_toman=10000).exists():
            return result
    elif not packages.exists():
        return result
    previous = ConversionExposure.objects.filter(account=account, environment=environment).only('experiment', 'variant').first()
    if previous and previous.experiment != key:
        return result
    variant = previous.variant if previous else split(account.pk, environment, key)
    result.update(variant=variant, inline_checkout=key != 'preview' or variant == 'treatment',
                  show_examples=key != 'examples' or variant == 'treatment')
    return result


def catalog(experiment):
    available = Q(active=True)
    if experiment['key'] == 'price' and experiment['variant'] == 'treatment':
        available |= Q(price_experiment_only=True)
    return [dict(package_data(p), active=True, experiment_only=True) if p.price_experiment_only else package_data(p)
            for p in MessagePackage.objects.filter(available)]


def checkout_package(package_id, account):
    package = MessagePackage.objects.select_for_update().filter(pk=package_id).first()
    if not package:
        return None
    if package.price_experiment_only:
        if settings.CONVERSION_EXPERIMENT != 'price' or assignment(account)['variant'] != 'treatment':
            return None
        return package
    return package if package.active else None


@api(['POST'], authenticated=True)
@transaction.atomic
def exposure(request):
    from .views import body
    data = body(request)
    key, surface = data.get('experiment'), data.get('surface')
    if (not isinstance(key, str) or surface not in SURFACES.get(key, ())
            or set(data) != ({'experiment', 'surface', 'preview_id'} if surface == 'preview' else {'experiment', 'surface'})):
        raise APIError('invalid_input', 'اطلاعات نمایش معتبر نیست.', 422)
    # Serialize first exposure with checkout creation on the same account.
    get_user_model().objects.select_for_update().only('pk').get(pk=request.user.pk)
    account = Account.objects.get(user_id=request.user.pk)
    current = assignment(account)
    if current['key'] != key or not current['variant']:
        return {'recorded': False}
    preview_id = None
    if surface == 'preview':
        try:
            preview_id = uuid.UUID(str(data['preview_id']))
        except (ValueError, TypeError, AttributeError):
            raise APIError('invalid_input', 'شناسهٔ پیش‌نمایش معتبر نیست.', 422) from None
        if (account.free_sends_remaining or getattr(account, balance_field())
                or not Preview.objects.filter(pk=preview_id, owner=request.user, session_key=request.session.session_key,
                    is_free=False, payment_method='credit', expires_at__gt=timezone.now(), order__isnull=True)
                    .exclude(from_text_trial=True, recipient_hash='').exists()):
            return {'recorded': False}
    _, created = ConversionExposure.objects.get_or_create(account=account, environment=credit_environment(),
        defaults={'experiment': key, 'variant': current['variant'], 'surface': surface, 'preview_id': preview_id})
    return {'recorded': created}
