from django.urls import path
from . import views

app_name = 'config'

urlpatterns = [
    # 🇪🇸 Base: /negocio/

    # Main settings page
    path('', views.settings_index, name='index'),

    # Business Information (Moved from /account/)
    # 🇪🇸 business → empresa
    path('empresa/', views.update_business_info, name='business'),
    # 🇪🇸 update-business → actualizar-empresa
    path('actualizar-empresa/', views.update_business_info, name='update_business'),

    # CSD Management (Moved from /account/)
    path('csd/', views.csd_management, name='csd'),
    # 🇪🇸 csd/deactivate → csd/desactivar
    path('csd/desactivar/', views.deactivate_csd, name='deactivate_csd'),
    # 🇪🇸 csd/validate-ajax → csd/validar-ajax
    path('csd/validar-ajax/', views.validate_csd_settings, name='validate_csd_settings'),
    # 🇪🇸 csd/upload-ajax → csd/subir-ajax
    path('csd/subir-ajax/', views.save_csd_settings, name='save_csd_settings'),

    # Integrations
    # 🇪🇸 integrations → integraciones
    path('integraciones/', views.integrations, name='integrations'),
    # 🇪🇸 update-mp-integration → actualizar-mp-integracion
    path('actualizar-mp-integracion/', views.update_mp_integration, name='update_mp_integration'),
    # 🇪🇸 test-mp-connection → probar-conexion-mp
    path('probar-conexion-mp/', views.test_mp_connection, name='test_mp_connection'),
    # 🇪🇸 update-whatsapp → actualizar-whatsapp
    path('actualizar-whatsapp/', views.update_whatsapp, name='update_whatsapp'),
    # 🇪🇸 test-whatsapp → probar-whatsapp
    path('probar-whatsapp/', views.test_whatsapp, name='test_whatsapp'),
    # 🇪🇸 update-email → actualizar-email
    path('actualizar-email/', views.update_email, name='update_email'),
    # 🇪🇸 test-email → probar-email
    path('probar-email/', views.test_email, name='test_email'),

    # Notifications
    # 🇪🇸 notifications → notificaciones
    path('notificaciones/', views.notifications_settings, name='notifications'),
    # 🇪🇸 update-notifications → actualizar-notificaciones
    path('actualizar-notificaciones/', views.update_notifications, name='update_notifications'),

    # Advanced settings
    # 🇪🇸 advanced → avanzado
    path('avanzado/', views.advanced_settings, name='advanced'),
    # 🇪🇸 update-advanced → actualizar-avanzado
    path('actualizar-avanzado/', views.update_advanced, name='update_advanced'),

    # Webhooks info (read-only)
    path('webhooks/', views.webhooks_management, name='webhooks'),
]