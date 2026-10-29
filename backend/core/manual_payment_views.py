from .management_api import staff_api
from .manual_payments import save_settings, settings_data, submit_receipt, cancel_purchase, approve, reject, grant_package
from .package_views import own_purchases
from .packages import purchase_data
from .services import APIError, api
from .views import body


@staff_api(['GET','POST'],'core.manage_manual_payments')
def configuration(request):
    return save_settings(request.user,body(request)) if request.method=='POST' else settings_data()


@api(['POST'],authenticated=True)
def receipt(request,purchase_id):
    purchase=own_purchases(request.user).filter(pk=purchase_id,payment_method='card').first()
    if not purchase:raise APIError('not_found','خرید پیدا نشد.',404)
    return purchase_data(submit_receipt(request.user,purchase,body(request)))


@api(['POST'],authenticated=True)
def cancel(request,purchase_id):
    if body(request):raise APIError('invalid_input','بدنهٔ این درخواست باید خالی باشد.',422)
    purchase=own_purchases(request.user).filter(pk=purchase_id,payment_method='card').first()
    if not purchase:raise APIError('not_found','خرید پیدا نشد.',404)
    return purchase_data(cancel_purchase(request.user,purchase))


@staff_api(['POST'],'core.approve_manual_payments')
def approve_payment(request,manual_id):
    return purchase_data(approve(request.user,manual_id,body(request)))


@staff_api(['POST'],'core.approve_manual_payments')
def reject_payment(request,manual_id):
    return purchase_data(reject(request.user,manual_id,body(request)))


@staff_api(['POST'],'core.approve_manual_payments')
def manual_grant(request):
    return purchase_data(grant_package(request.user,body(request),request.headers.get('Idempotency-Key','')))
