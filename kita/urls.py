"""URL configuration for Kita project.

Main URL routing for all application modules.

IMPORTANTE - URLs de Autenticación:
- URLs principales (signup, login, logout, password reset) están en español
  vía auth_urls_es.py para SEO y UX en mercado mexicano
- URLs secundarias (confirmación email, etc.) siguen en /accounts/
  vía allauth_urls_filtered.py para compatibilidad
"""
from __future__ import annotations

from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.conf import settings
from django.utils.cache import patch_vary_headers
from django.templatetags.static import static
from django.views.generic import TemplateView
from django.views.decorators.cache import cache_page

from core.middleware import allow_without_tenant
from core.sitemaps import StaticViewSitemap

# Sitemaps configuration
sitemaps = {
    'static': StaticViewSitemap,
}

@allow_without_tenant
def home_view(request: HttpRequest) -> HttpResponse:
    """Home page view - public landing page.

    Args:
        request: HTTP request object

    Returns:
        Rendered home page template

    Note:
        Most SEO metadata comes from seo_defaults context processor.
        Only page-specific overrides are defined here.
        No stats for new app - honest approach.

        Cache Strategy:
        - Authenticated users: No cache (always fresh)
        - Anonymous users: 15 min cache, public
    """
    context = {
        # SEO overrides (defaults from context processor)
        'og_image': f"{settings.APP_BASE_URL}{static('images/kita-logo-negro.png')}",
        'canonical_url': request.build_absolute_uri(request.path),
    }
    response = render(request, 'home.html', context)

    # Conditional cache based on authentication
    if request.user.is_authenticated:
        # No cache for logged-in users (may have personalized content)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
    else:
        # Public cache for anonymous users (15 minutes)
        response['Cache-Control'] = 'public, max-age=900'  # 15 minutes
        # Vary cache by Cookie to differentiate between authenticated/anonymous
        patch_vary_headers(response, ['Cookie'])

    return response

# Main URL patterns
urlpatterns = [
    # Home
    path('', home_view, name='home'),

    # SEO
    path('sitemap.xml',
         cache_page(86400)(sitemap),
         {'sitemaps': sitemaps},
         name='sitemap'),
    path('robots.txt',
         cache_page(86400)(
             TemplateView.as_view(
                 template_name='robots.txt',
                 content_type='text/plain'
             )
         ),
         name='robots'),

    # Admin (ruta oscurecida por seguridad)
    path('gestion-kita-2025/', admin.site.urls),

    # Auth en español (URLs principales visibles)
    path('', include('kita.auth_urls_es')),

    # Social Auth Providers (Google OAuth - DEBE ir ANTES de allauth.socialaccount.urls)
    path('accounts/', include('allauth.socialaccount.providers.google.urls')),

    # Social Auth (Base URLs - login/cancelled, signup, etc.)
    path('accounts/', include('allauth.socialaccount.urls')),

    # Apps (Allauth secundarias - email confirmations, password reset keys)
    path('accounts/', include('kita.allauth_urls_filtered')),
    path('incorporacion/', include('onboarding.urls')),  # 🇪🇸 onboarding → incorporacion
    path('panel/', include('dashboard.urls')),  # 🇪🇸 dashboard → panel
    path('enlaces/', include('links.urls')),  # 🇪🇸 links → enlaces
    path('ia/', include('kita_ia.urls')),  # ✅ AI (universal acronym)
    path('suscripcion/', include('billing.urls')),  # 🇪🇸 subscription → suscripcion
    path('facturas/', include('invoicing.urls')),  # 🇪🇸 invoices → facturas
    path('cuenta/', include('accounts.urls')),  # 🇪🇸 account → cuenta
    path('negocio/', include('config.urls')),  # 🇪🇸 business settings → negocio
    path('auditoria/', include('audit.urls')),  # 🇪🇸 logs → auditoria
    path('webhooks/', include('webhooks.urls')),  # ✅ Technical standard (keep English)
    path('legal/', include('legal.urls')),  # ✅ Already in Spanish
    path('', include('core.urls')),  # ✅ Technical routes (/api/, /health/)
    path('', include('payments.urls')),  # ✅ Public routes (/hola/, /facturar/)
]

if settings.DEBUG:
    urlpatterns += [
        path('__debug__/', include('debug_toolbar.urls')),
    ]
