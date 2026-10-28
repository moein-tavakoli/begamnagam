from django.conf import settings
from .models import WalletEntry, WalletTopup
from .services import APIError, api
from .views import body
from .wallet import begin_topup, summary, topup_data


@api(['GET'], authenticated=True)
def wallet(request):
    environment = 'live' if not settings.DEMO_MODE else None
    entries = WalletEntry.objects.filter(account__user=request.user)
    entries = entries.filter(environment=environment) if environment else entries.exclude(environment='live')
    records = [{'id': str(row.pk), 'kind': row.kind, 'amount_toman': row.amount_toman,
        'balance_after_toman': str(row.balance_after_toman), 'created_at': row.created_at,
        'order_id': str(row.order_id) if row.order_id else None,
        'purchase_id': str(row.purchase_id) if row.purchase_id else None} for row in entries.order_by('-created_at')[:100]]
    topup_rows = WalletTopup.objects.filter(owner=request.user)
    topup_rows = topup_rows.filter(environment='live') if not settings.DEMO_MODE else topup_rows.exclude(environment='live')
    return {**summary(request.user), 'entries': records,
        'topups': [topup_data(item) for item in topup_rows.order_by('-created_at')[:30]]}


@api(['POST'], authenticated=True)
def topups(request):
    return begin_topup(request.user, body(request), request.headers.get('Idempotency-Key', ''))


@api(['GET'], authenticated=True)
def topup(request, topup_id):
    item = WalletTopup.objects.filter(owner=request.user, pk=topup_id).first()
    if not item or (item.environment == 'live') != (not settings.DEMO_MODE):
        raise APIError('not_found', 'شارژ پیدا نشد.', 404)
    return topup_data(item)


@api(['POST'], authenticated=True)
def pay_order(request, order_id):
    if body(request):
        raise APIError('server_snapshot_required', 'مبلغ و متن از سفارش بررسی‌شده خوانده می‌شود.', 422)
    from .wallet import pay_order as pay
    from .services import serialize_order
    return serialize_order(pay(request.user, order_id))
