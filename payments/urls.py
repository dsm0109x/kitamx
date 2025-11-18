from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Public payment link (creative branding, keep)
    # ✅ /hola/ - Creative and memorable
    path('hola/<str:token>/', views.public_payment_link, name='public_link'),

    # Payment result pages
    # 🇪🇸 success → exito
    path('exito/<str:token>/', views.payment_success, name='success'),
    # 🇪🇸 failure → error
    path('error/<str:token>/', views.payment_failure, name='failure'),
    # 🇪🇸 pending → pendiente
    path('pendiente/<str:token>/', views.payment_pending, name='pending'),

    # Self-service billing (creative branding, keep)
    # ✅ /facturar/ - Clear and action-oriented
    path('facturar/<str:token>/', views.billing_form, name='billing_form'),
    # ✅ /descargar/ - Clear and action-oriented
    path('descargar/<str:token>/<uuid:uuid>/', views.download_invoice, name='download_invoice'),

    # Analytics tracking for public links
    # ✅ Keep in English (internal tracking endpoints)
    path('track-view/', views.track_view, name='track_view'),
    path('track-interaction/', views.track_interaction, name='track_interaction'),

    # Webhooks (technical, keep in English)
    # ✅ webhook/mercadopago/ - Technical standard
    path('webhook/mercadopago/', views.mercadopago_webhook, name='mp_webhook'),
]