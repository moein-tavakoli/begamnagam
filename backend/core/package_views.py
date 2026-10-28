from django.conf import settings
from .management_api import staff_api
from .models import CreditPurchase, MessagePackage
from .packages import begin_purchase, package_data, purchase_data, save_package
from .services import APIError, api
from .views import body


def own_purchases(user):
    rows = CreditPurchase.objects.filter(owner=user)
    return rows.exclude(environment='live') if settings.DEMO_MODE else rows.filter(environment='live')


@api(['GET', 'POST'], authenticated=True)
def purchases(request):
    if request.method == 'POST':
        return begin_purchase(request.user, body(request), request.headers.get('Idempotency-Key', ''))
    return {'purchases': [purchase_data(p) for p in own_purchases(request.user).order_by('-created_at')[:30]]}


@api(['GET'], authenticated=True)
def purchase_detail(request, purchase_id):
    purchase = own_purchases(request.user).filter(pk=purchase_id).first()
    if not purchase:
        raise APIError('not_found', 'خرید پیدا نشد.', 404)
    return purchase_data(purchase)


@staff_api(['GET', 'POST'], 'core.manage_message_packages')
def packages(request):
    if request.method == 'POST':
        return package_data(save_package(request.user, body(request)))
    return {'packages': [package_data(p) for p in MessagePackage.objects.all()]}


@staff_api(['POST'], 'core.manage_message_packages')
def package_update(request, package_id):
    return package_data(save_package(request.user, body(request), package_id))
