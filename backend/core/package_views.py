from django.conf import settings
from .management_api import staff_api
from .models import CreditPurchase, MessagePackage
from .packages import begin_purchase, package_data, purchase_data, save_package
from .services import APIError, api
from .views import body


def own_purchases(user):
    rows = CreditPurchase.objects.filter(owner=user)
    return rows.exclude(environment='live') if settings.DEMO_MODE else rows.filter(environment='live')


def website_session(request):
    return request.session.session_key if request.path.startswith('/api/v1/') else None


@api(['GET', 'POST'], authenticated=True)
def purchases(request):
    session = website_session(request)
    if request.method == 'POST':
        data = body(request)
        if data.get('payment_method') == 'card':
            from .manual_payments import begin_purchase as begin_card_purchase
            purchase = begin_card_purchase(request.user, data, request.headers.get('Idempotency-Key', ''), session_key=session)
            return purchase_data(purchase, session_key=session)
        return begin_purchase(request.user, data, request.headers.get('Idempotency-Key', ''), session_key=session)
    return {'purchases': [purchase_data(p, session_key=session) for p in own_purchases(request.user).order_by('-created_at')[:30]]}


@api(['GET'], authenticated=True)
def purchase_detail(request, purchase_id):
    purchase = own_purchases(request.user).filter(pk=purchase_id).first()
    if not purchase:
        raise APIError('not_found', 'خرید پیدا نشد.', 404)
    return purchase_data(purchase, session_key=website_session(request))


@staff_api(['GET', 'POST'], 'core.manage_message_packages', automatic_reason=True)
def packages(request):
    if request.method == 'POST':
        return package_data(save_package(request.user, body(request)))
    return {'packages': [package_data(p) for p in MessagePackage.objects.filter(price_experiment_only=False)]}


@staff_api(['POST'], 'core.manage_message_packages', automatic_reason=True)
def package_update(request, package_id):
    return package_data(save_package(request.user, body(request), package_id))
