"""
Legal pages views - Privacy, Terms, Cookies
"""
from django.shortcuts import render
from django.views.decorators.cache import cache_page


#@cache_page(60 * 60 * 24)  # Cache 24 hours
def privacy_view(request):
    """Aviso de Privacidad (LFPDPPP México)"""
    return render(request, 'legal/privacy.html', {
        'title': 'Aviso de Privacidad - Kita',
        'meta_description': 'Aviso de Privacidad de Kita. Conoce cómo protegemos tus datos personales, derechos ARCO, seguridad AES-256 y cumplimiento LFPDPPP.',
    })


#@cache_page(60 * 60 * 24)
def terms_view(request):
    """Términos de Servicio"""
    return render(request, 'legal/terms.html', {
        'title': 'Términos de Servicio - Kita',
        'meta_description': 'Términos y condiciones de uso de Kita. Conoce tus derechos, responsabilidades, planes, cancelación y más. Transparencia total.',
    })


#@cache_page(60 * 60 * 24)
def cookies_view(request):
    """Política de Cookies"""
    return render(request, 'legal/cookies.html', {
        'title': 'Política de Cookies - Kita',
        'meta_description': 'Conoce qué cookies utiliza Kita y cómo gestionarlas. Transparencia total sobre cookies esenciales, analytics y terceros. GDPR compliant.',
    })
