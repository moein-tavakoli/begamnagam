from django.contrib import admin
from django.urls import include, path
from core import views
from core import invitations
from core import management_api as management
from core import ai_management
from core import wallet_views
from core import package_views
from core import example_views
from core import manual_payment_views, support_views, provider_balances

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"

urlpatterns = [
    path('api/v2/', include('core.api_v2.urls')),
    path('api/v1/manage/message-examples', example_views.catalog),
    path('api/v1/manage/message-examples/<str:kind>', example_views.save),
    path('api/v1/manage/message-examples/<str:kind>/<int:record_id>', example_views.save),
    path('api/v1/manage/message-examples/<str:kind>/<int:record_id>/delete', example_views.delete),
    path("api/v1/manage/provider-balances/<str:provider>", provider_balances.balance),
    path('api/v1/support/summary', support_views.summary),
    path('api/v1/support/messages', support_views.messages),
    path('api/v1/support/read', support_views.read),
    path('api/v1/manage/support/summary', support_views.staff_summary),
    path('api/v1/manage/support/inbox', support_views.inbox),
    path('api/v1/manage/support/<uuid:thread_id>/messages', support_views.staff_messages),
    path('api/v1/manage/support/<uuid:thread_id>/read', support_views.staff_read),
    path('api/v1/manage/support/<uuid:thread_id>/close', support_views.close),
    path('api/v1/manage/manual-payment-settings', manual_payment_views.configuration),
    path('api/v1/manage/manual-payments/grant', manual_payment_views.manual_grant),
    path('api/v1/manage/manual-payments/<uuid:manual_id>/approve', manual_payment_views.approve_payment),
    path('api/v1/manage/manual-payments/<uuid:manual_id>/reject', manual_payment_views.reject_payment),
    path('api/v1/credit-purchases/<uuid:purchase_id>/receipt', manual_payment_views.receipt),
    path('api/v1/credit-purchases/<uuid:purchase_id>/cancel-card', manual_payment_views.cancel),
    path('api/v1/wallet', wallet_views.wallet),
    path('api/v1/wallet/topups', wallet_views.topups),
    path('api/v1/wallet/topups/<uuid:topup_id>', wallet_views.topup),
    path('api/v1/orders/<uuid:order_id>/pay-wallet', wallet_views.pay_order),
    path('api/v1/manage/packages', package_views.packages),
    path('api/v1/manage/packages/<int:package_id>', package_views.package_update),
    path('api/v1/credit-purchases', package_views.purchases),
    path('api/v1/credit-purchases/<uuid:purchase_id>', package_views.purchase_detail),
    path('api/v1/orders/<uuid:order_id>/confirm-credit', views.confirm_free),
    path("api/v1/manage/ai", ai_management.configuration),
    path("api/v1/manage/ai/test", ai_management.evaluate),
    path("api/v1/manage/session", management.session),
    path("api/v1/manage/login", management.login_view),
    path("api/v1/manage/logout", management.logout_view),
    path("api/v1/manage/dashboard", management.dashboard),
    path("api/v1/manage/records/<slug:resource>", management.records),
    path("api/v1/manage/limits", management.limits),
    path("api/v1/manage/request-limits/<slug:scope>", management.request_limits),
    path("api/v1/manage/actions", management.action),
    path("api/v1/manage/reports/<uuid:report_id>/review", management.review_report),
    path("api/v1/manage/orders/<uuid:order_id>/texts", management.review_message),
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
    path("api/v1/orders/<uuid:order_id>/confirm-free", views.confirm_free),
    path("api/v1/orders/<uuid:order_id>", views.order_detail),
    path("api/v1/orders/<uuid:order_id>/payments", views.begin_payment),
    path("api/v1/payments/return/zarinpal", views.payment_return),
    path("api/v1/recipient/actions/<str:action>", views.recipient_action),
    path("api/v1/account/deletion", views.request_deletion),
    path("api/v1/operations/status", views.operations_status),
    path("api/v1/preferences", views.preferences),
    path("api/v1/invitations", invitations.invitations_view),
    path("api/v1/invitations/<uuid:invitation_id>/resend", invitations.resend_view),
]
