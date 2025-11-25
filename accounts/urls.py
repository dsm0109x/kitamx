"""URL configuration for accounts app."""
from django.urls import path

from . import views
from . import ajax_views

app_name = 'accounts'

urlpatterns = [
    # 🇪🇸 Base: /cuenta/

    # Main account page (Personal Profile)
    path('', views.account_index, name='index'),

    # Profile management (Personal)
    # 🇪🇸 update-profile → actualizar-perfil
    path('actualizar-perfil/', views.update_profile, name='update_profile'),
    # 🇪🇸 change-password → cambiar-contrasena
    path('cambiar-contrasena/', views.change_password, name='change_password'),

    # Sessions management (Personal)
    # 🇪🇸 sessions → sesiones
    path('sesiones/', views.user_sessions, name='user_sessions'),
    # 🇪🇸 revoke-session → revocar-sesion
    path('revocar-sesion/', views.revoke_session, name='revoke_session'),

    # AJAX endpoints
    # 🇪🇸 check-email → verificar-email
    path('verificar-email/', ajax_views.check_email_availability, name='check_email'),

    # Email verification resend
    path('reenviar-email-verificacion/', views.resend_verification_email, name='resend_verification'),

    # NOTE: Business info and CSD moved to /negocio/ (config app)
    # - /negocio/empresa/ (business information)
    # - /negocio/csd/ (CSD management)
]