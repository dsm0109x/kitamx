from django.urls import path
from django.views.generic import TemplateView
from core.views import health
from core import api_views

app_name = 'core'

urlpatterns = [
    # Health checks
    path('health/', health.health_check, name='health_check'),
    path('health/detailed/', health.health_detailed, name='health_detailed'),
    path('health/readiness/', health.health_readiness, name='health_readiness'),
    path('health/liveness/', health.health_liveness, name='health_liveness'),

    # Address Autocomplete API
    path('api/address/postal-code/', api_views.api_lookup_postal_code, name='api_lookup_postal_code'),
    path('api/address/suggest-streets/', api_views.api_suggest_streets, name='api_suggest_streets'),
    path('api/address/reverse-geocode/', api_views.api_reverse_geocode, name='api_reverse_geocode'),

    # Recipient Lookup API (for invoice autofill)
    path('api/recipients/lookup/', api_views.api_lookup_recipient, name='api_lookup_recipient'),

    # Static
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),
]