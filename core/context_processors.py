"""
Context processors for Kita.

Provides global template variables available in all templates.
"""
from __future__ import annotations
from typing import Dict, Any
from django.http import HttpRequest
from django.conf import settings
from django.templatetags.static import static


def logo_context(request: HttpRequest) -> Dict[str, Any]:
    """
    Determine which logo to use based on the current page.

    Logo strategy:
    - Logo Negro (kita-logo-negro.png): Public pages (landing, auth, onboarding)
    - Logo Original (kita-logo.png): Private pages (dashboard, tenant views)

    Returns:
        dict: Context with logo_path variable
    """
    path = request.path

    # Public pages use black logo
    public_paths = (
        '/',                    # Landing
        '/accounts/',           # Login, signup, password reset, etc.
        '/incorporacion/',      # All onboarding steps 🇪🇸
    )

    is_public = any(path.startswith(prefix) for prefix in public_paths)

    logo_filename = 'images/kita-logo-negro.png' if is_public else 'images/kita-logo.png'

    return {
        'logo_path': logo_filename,
        'is_public_page': is_public,
    }


def seo_defaults(request: HttpRequest) -> Dict[str, Any]:
    """
    Provide default SEO metadata for all pages.

    Views can override these defaults by passing their own values in context.
    This reduces repetition and ensures consistency.

    Returns:
        dict: Default SEO metadata
    """
    return {
        'default_title': 'Kita - Cobra y Factura CFDI 4.0 Sin Complicaciones',
        'default_description': 'Crea enlaces de pago y genera facturas CFDI 4.0 automáticamente. Ideal para freelancers y emprendedores en México. 30 días gratis, sin tarjeta de crédito.',
        'default_keywords': 'facturación electrónica, CFDI 4.0, enlaces de pago, MercadoPago, SAT México, factura digital, emprendedores México, freelancers México',
        'app_base_url': settings.APP_BASE_URL,
        'subscription_price': settings.MONTHLY_SUBSCRIPTION_PRICE,
        'TURNSTILE_SITE_KEY': settings.TURNSTILE_SITE_KEY,  # For anti-bot protection
    }


