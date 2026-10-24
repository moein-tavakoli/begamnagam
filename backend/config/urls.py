from django.contrib import admin
from django.urls import path
from core import views

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", views.health),
    path("api/v1/bootstrap", views.bootstrap),
    path("api/v1/auth/request-otp", views.request_otp),
    path("api/v1/auth/verify-otp", views.verify_otp),
    path("api/v1/auth/logout", views.logout_view),
    path("api/v1/messages/preview", views.preview),
    path("api/v1/messages", views.messages),
    path("api/v1/orders", views.create_order),
    path("api/v1/orders/<uuid:order_id>/pay-demo", views.pay_demo),
    path("api/v1/orders/<uuid:order_id>", views.order_detail),
    path("api/v1/orders/<uuid:order_id>/payments", views.begin_payment),
    path("api/v1/payments/return/zarinpal", views.payment_return),
    path("api/v1/recipient/actions/<str:action>", views.recipient_action),
    path("api/v1/account/deletion", views.request_deletion),
    path("api/v1/operations/status", views.operations_status),
    path("api/v1/preferences", views.preferences),
]
