"""
URLs de autenticación en español.

Este módulo override las URLs principales de Django Allauth con paths cortos
en español para mejor SEO y UX en el mercado mexicano.

URLs públicas (usuario ve en navegador):
- /registrarme/ → Signup
- /ingresar/ → Login
- /salir/ → Logout
- /recuperar-contrasena/ → Password Reset (solicitar)
- /recuperar-contrasena/enviado/ → Password Reset Done (confirmación)
- /confirmar-nueva-contrasena/ → Password Reset From Key Done (redirect con toast)

URLs secundarias (confirmación email, OAuth callbacks, etc.) siguen en /accounts/
vía Allauth estándar para mantener compatibilidad y evitar romper funcionalidad crítica.

Estrategia:
- Django busca match en ORDEN de inclusión en urls.py
- auth_urls_es.py se incluye PRIMERO → tiene prioridad
- allauth.urls se incluye DESPUÉS → maneja lo que no matcheó
- Mismo 'name' en ambos → {% url %} resuelve automáticamente al primero

AJAX Support:
- Login y Signup ahora usan vistas AJAX-aware
- Si request tiene header X-Requested-With: XMLHttpRequest → devuelve JSON
- Si es request normal → devuelve template HTML como antes

Author: Kita Team
Date: 2025-10-16
Updated: 2025-10-19 - Added AJAX support
"""
from django.urls import path
from allauth.account import views as allauth_views
from accounts import views as custom_views
from accounts.ajax_views import AjaxLoginView, AjaxSignupView

urlpatterns = [
    # Registro / Signup - AJAX-aware
    path('registrarme/',
         AjaxSignupView.as_view(),  # ✅ Soporte AJAX + fallback HTML
         name='account_signup'),

    # Login / Iniciar Sesión - AJAX-aware
    path('ingresar/',
         AjaxLoginView.as_view(),  # ✅ Soporte AJAX + fallback HTML
         name='account_login'),

    # Logout / Cerrar Sesión
    path('salir/',
         allauth_views.logout,
         name='account_logout'),  # Mantener nombre Allauth

    # Password Reset / Recuperar Contraseña
    path('recuperar-contrasena/',
         allauth_views.password_reset,
         name='account_reset_password'),  # Mantener nombre Allauth

    # Password Reset Done / Confirmación de envío
    path('recuperar-contrasena/enviado/',
         allauth_views.password_reset_done,
         name='account_reset_password_done'),  # Mantener nombre Allauth

    # Password Reset From Key Done / Contraseña cambiada (redirect a login con toast)
    path('confirmar-nueva-contrasena/',
         custom_views.password_reset_done_redirect,
         name='account_reset_password_from_key_done'),  # Override allauth default

    # Email Verification / Verificación de Email
    path('verificar-email/',
         allauth_views.email_verification_sent,
         name='account_email_verification_sent'),  # Override allauth

    path('verificar-email/<key>/',
         custom_views.email_confirm_redirect,
         name='account_confirm_email'),  # Override con redirect + toast

    # Password Management (Usuario Autenticado) / Gestión de Contraseñas
    path('cuenta/cambiar-contrasena/',
         allauth_views.password_change,
         name='account_change_password'),  # Override allauth

    path('cuenta/establecer-contrasena/',
         allauth_views.password_set,
         name='account_set_password'),  # Override allauth

    # Email Management / Gestión de Correos
    path('cuenta/correos/',
         allauth_views.email,
         name='account_email'),  # Override allauth

    # Account Inactive / Cuenta Inactiva
    path('cuenta-inactiva/',
         allauth_views.account_inactive,
         name='account_inactive'),  # Override allauth
]

# Password Reset From Key (Link del email) - Español
# NOTE: Importamos re_path aquí para el regex
from django.urls import re_path

urlpatterns += [
    # Password reset con key - ESPAÑOLIZADO
    # Link que aparece en el EMAIL de password reset
    # Antes: /accounts/password/reset/key/{uuid}-{token}/
    # Ahora: /restablecer/{uuid}-{token}/

    # Strict pattern para UUIDs reales (32 hex chars) - PRIMERA PRIORIDAD
    re_path(r'^restablecer/(?P<uidb36>[0-9a-f]{32})-(?P<key>.+)/$',
            allauth_views.password_reset_from_key,
            name='account_reset_password_from_key_strict'),

    # Flexible pattern para reverse() con placeholders - FALLBACK
    # Usado por allauth al generar email templates
    path('restablecer/<uidb36>-<key>/',
         allauth_views.password_reset_from_key,
         name='account_reset_password_from_key'),
]
