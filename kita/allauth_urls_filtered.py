"""
Allauth URLs filtradas - Solo URLs secundarias.

EXCLUYE: signup, login, logout, password_reset (están en auth_urls_es.py)
INCLUYE: Email confirmations, social auth, password reset keys, etc.
"""
from django.urls import path, include, re_path
from allauth.account import views as allauth_views

urlpatterns = [
    # NOTE: TODAS las URLs de account fueron movidas a auth_urls_es.py (españolizadas)
    # - Email confirmation → /verificar-email/
    # - Email management → /cuenta/correos/
    # - Account inactive → /cuenta-inactiva/
    # - Password change/set → /cuenta/cambiar-contrasena/ y /cuenta/establecer-contrasena/
    # - Password reset from key → /restablecer/{uuid}-{token}/

    # Este archivo ahora está vacío - todas las URLs están españolizadas en auth_urls_es.py
]

# Nota: Social Auth URLs ahora están en urls.py principal
# para evitar doble include
