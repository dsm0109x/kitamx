from django.urls import path
from . import views

app_name = 'onboarding'

urlpatterns = [
    # 🇪🇸 Base: /incorporacion/

    path('', views.onboarding_start, name='start'),
    # 🇪🇸 step1 → paso1
    path('paso1/', views.onboarding_step1, name='step1'),
    # 🇪🇸 step2 → paso2
    path('paso2/', views.onboarding_step2, name='step2'),
    # 🇪🇸 step3 → paso3
    path('paso3/', views.onboarding_step3, name='step3'),
    # 🇪🇸 step4 → paso4
    path('paso4/', views.onboarding_step4, name='step4'),
    # 🇪🇸 success → completado
    path('completado/', views.onboarding_success, name='success'),

    # Subscription callbacks
    # 🇪🇸 subscription/success → suscripcion/exito
    path('suscripcion/exito/', views.subscription_success, name='subscription_success'),
    # 🇪🇸 subscription/failure → suscripcion/error
    path('suscripcion/error/', views.subscription_failure, name='subscription_failure'),
    # 🇪🇸 subscription/pending → suscripcion/pendiente
    path('suscripcion/pendiente/', views.subscription_pending, name='subscription_pending'),

    # AJAX endpoints
    # 🇪🇸 api/validate-rfc → api/validar-rfc
    path('api/validar-rfc/', views.validate_rfc, name='validate_rfc'),
    # 🇪🇸 api/validate-business-name → api/validar-razon-social
    path('api/validar-razon-social/', views.validate_business_name, name='validate_business_name'),
    # 🇪🇸 api/disconnect-mp → api/desconectar-mp
    path('api/desconectar-mp/', views.disconnect_mercado_pago, name='disconnect_mp'),
    # 🇪🇸 api/start-trial → api/iniciar-prueba
    path('api/iniciar-prueba/', views.start_trial, name='start_trial'),
    # path('api/crear-suscripcion/', views.create_subscription, name='create_subscription'),  # DISABLED
]