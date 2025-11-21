"""URL configuration for billing app."""
from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # 🇪🇸 Base: /suscripcion/

    # Main subscription page
    path('', views.subscription_index, name='index'),

    # Subscription management
    # 🇪🇸 activate → activar
    path('activar/', views.activate_subscription, name='activate'),
    # 🇪🇸 cancel → cancelar
    path('cancelar/', views.cancel_subscription, name='cancel'),
    # 🇪🇸 pay-overdue → pagar-vencido
    path('pagar-vencido/', views.pay_overdue, name='pay_overdue'),

    # Payment management
    # 🇪🇸 payment-detail → detalle-pago
    path('detalle-pago/<uuid:payment_id>/', views.payment_detail, name='payment_detail'),
    # 🇪🇸 retry-payment → reintentar-pago
    path('reintentar-pago/<uuid:payment_id>/', views.retry_payment, name='retry_payment'),
    # 🇪🇸 invoice-payment → facturar-pago
    path('facturar/<uuid:payment_id>/', views.invoice_subscription_payment, name='invoice_payment'),
    # 🇪🇸 download invoice XML → descargar-factura-xml
    path('factura/<uuid:payment_id>/xml/', views.download_subscription_invoice_xml, name='download_invoice_xml'),
    # 🇪🇸 download invoice PDF → descargar-factura-pdf
    path('factura/<uuid:payment_id>/pdf/', views.download_subscription_invoice_pdf, name='download_invoice_pdf'),

    # Subscription payment callbacks (MercadoPago back URLs)
    # 🇪🇸 payment/success → pago/exito
    path('pago/exito/', views.subscription_payment_success, name='payment_success'),
    # 🇪🇸 payment/failure → pago/error
    path('pago/error/', views.subscription_payment_failure, name='payment_failure'),
    # 🇪🇸 payment/pending → pago/pendiente
    path('pago/pendiente/', views.subscription_payment_pending, name='payment_pending'),

    # AJAX endpoints
    # 🇪🇸 stats → estadisticas
    path('estadisticas/', views.subscription_stats, name='stats'),
]