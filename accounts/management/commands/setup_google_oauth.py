"""
Management command to setup Google OAuth.

Usage:
    python manage.py setup_google_oauth
"""
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings
from allauth.socialaccount.models import SocialApp


class Command(BaseCommand):
    help = 'Setup Google OAuth SocialApp'

    def handle(self, *args, **options):
        # Get or create site
        site = Site.objects.get_current()
        self.stdout.write(f'Using site: {site.domain}')

        # Check if Google OAuth credentials are set
        if not settings.GOOGLE_OAUTH_CLIENT_ID or not settings.GOOGLE_OAUTH_CLIENT_SECRET:
            self.stdout.write(self.style.ERROR(
                '❌ Google OAuth credentials not found in settings!'
            ))
            self.stdout.write(
                'Please set GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET in .env'
            )
            return

        # Get or create Google SocialApp
        google_app, created = SocialApp.objects.get_or_create(
            provider='google',
            defaults={
                'name': 'Google',
                'client_id': settings.GOOGLE_OAUTH_CLIENT_ID,
                'secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
            }
        )

        if not created:
            # Update existing
            google_app.client_id = settings.GOOGLE_OAUTH_CLIENT_ID
            google_app.secret = settings.GOOGLE_OAUTH_CLIENT_SECRET
            google_app.save()
            self.stdout.write(self.style.SUCCESS(
                f'✅ Updated existing Google OAuth app'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Created new Google OAuth app'
            ))

        # Add site to app
        google_app.sites.add(site)

        self.stdout.write(self.style.SUCCESS(
            f'✅ Google OAuth configured successfully!'
        ))
        self.stdout.write(
            f'   Provider: {google_app.provider}'
        )
        self.stdout.write(
            f'   Client ID: {google_app.client_id[:20]}...'
        )
        self.stdout.write(
            f'   Sites: {", ".join([s.domain for s in google_app.sites.all()])}'
        )
