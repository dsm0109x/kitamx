"""
Sitemaps for Kita.

Provides dynamic sitemap generation for SEO using Django Sitemaps Framework.
"""
from __future__ import annotations
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static public pages."""

    protocol = 'https'

    def get_urls(self, page=1, site=None, protocol=None):
        """Override to use APP_BASE_URL from settings."""
        from django.conf import settings
        from django.contrib.sites.models import Site

        # Use APP_BASE_URL if available, otherwise fall back to Site
        if hasattr(settings, 'APP_BASE_URL'):
            from urllib.parse import urlparse
            parsed = urlparse(settings.APP_BASE_URL)
            protocol = parsed.scheme or 'https'

            # Create a mock site object with the correct domain
            class MockSite:
                domain = parsed.netloc or 'kita.mx'
            site = MockSite()

        return super().get_urls(page=page, site=site, protocol=protocol)

    def items(self):
        """Return list of static page URL names."""
        return [
            'home',           # Landing page
            'account_login',  # Login page
            'account_signup', # Signup page
            'legal:terms',    # Términos de servicio
            'legal:privacy',  # Política de privacidad
            'legal:cookies',  # Política de cookies
        ]

    def location(self, item):
        """Generate URL from URL name."""
        return reverse(item)

    def priority(self, item):
        """Set priority based on page importance (0.0 - 1.0)."""
        priorities = {
            'home': 1.0,          # Highest priority
            'account_login': 0.9,  # High priority
            'account_signup': 0.9, # High priority
            'legal:terms': 0.6,
            'legal:privacy': 0.6,
            'legal:cookies': 0.5,
        }
        return priorities.get(item, 0.5)

    def changefreq(self, item):
        """Set change frequency based on page type."""
        frequencies = {
            'home': 'daily',       # Landing changes frequently
            'account_login': 'weekly',   # May have UI updates
            'account_signup': 'weekly',  # May have UI updates
            'legal:terms': 'monthly',
            'legal:privacy': 'monthly',
            'legal:cookies': 'monthly',
        }
        return frequencies.get(item, 'monthly')


# FUTURE: When you have dynamic public content
class PublicLinksSitemap(Sitemap):
    """
    Sitemap for public payment links (if applicable).
    
    NOTE: Currently not used because payment links are:
    - Temporary (expire in 1-7 days)
    - Would create 404s after expiration
    - Not ideal for SEO indexing
    
    Uncomment and add to sitemaps dict in urls.py when needed.
    """

    changefreq = 'daily'
    priority = 0.7

    def items(self):
        # Example implementation (commented out):
        # from links.models import PaymentLink
        # from django.utils import timezone
        # return PaymentLink.objects.filter(
        #     is_public=True,
        #     status='active',
        #     expires_at__gt=timezone.now()
        # )[:1000]  # Limit to 1000 for performance
        return []  # Empty for now

    def lastmod(self, obj):
        """Return last modification date."""
        return obj.updated_at

    def location(self, obj):
        """Return public URL for the link."""
        return obj.get_public_url()
