"""Custom allauth adapter for Kita."""
from __future__ import annotations
from typing import Optional
import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.models import EmailAddress
from django.http import HttpRequest
from django.utils import timezone

from .models import User

logger = logging.getLogger(__name__)


class NoMessagesAccountAdapter(DefaultAccountAdapter):
    """
    Custom allauth adapter that suppresses automatic messages
    to prevent duplication with our custom toast system
    """

    def add_message(
        self,
        request: HttpRequest,
        level: int,
        message_template: str,
        message_context: Optional[dict] = None,
        extra_tags: str = ""
    ) -> None:
        """
        Override to suppress allauth automatic messages.

        We handle all notifications through our custom toast system.

        Args:
            request: HTTP request object
            level: Django message level
            message_template: Message template string
            message_context: Optional context for template
            extra_tags: Additional message tags
        """
        pass

    def send_mail(self, template_prefix, email, context):
        """
        Override to force multipart email (HTML + text).

        Args:
            template_prefix: Email template prefix
            email: Recipient email
            context: Template context

        Returns:
            None
        """
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string

        # Render subject
        subject = render_to_string(f"{template_prefix}_subject.txt", context)
        subject = " ".join(subject.splitlines()).strip()

        # Render text body (required)
        text_body = render_to_string(f"{template_prefix}_message.txt", context)

        # Render HTML body (optional)
        html_body = None
        try:
            html_body = render_to_string(f"{template_prefix}_message.html", context)
        except Exception as e:
            # If HTML template doesn't exist, just send text
            print(f"⚠️ HTML template not found for {template_prefix}: {e}")

        # Get from email
        from_email = self.get_from_email()

        # Create multipart message
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[email]
        )

        # Attach HTML alternative if exists
        if html_body:
            msg.attach_alternative(html_body, "text/html")
            print(f"✅ Sending multipart email (HTML + text) to {email}")
        else:
            print(f"⚠️ Sending text-only email to {email}")

        # Send the email
        msg.send()

    def login(self, request: HttpRequest, user: User) -> None:
        """
        Override login to prevent automatic 'successfully logged in' message.

        IMPORTANT: Must specify backend when multiple backends are configured.

        Args:
            request: HTTP request object
            user: User instance to login
        """
        from django.contrib.auth import login as auth_login

        # Specify backend explicitly (required when multiple backends configured)
        backend = 'allauth.account.auth_backends.AuthenticationBackend'
        auth_login(request, user, backend=backend)

    def confirm_email(self, request: HttpRequest, email_address: EmailAddress) -> None:
        """
        Override email confirmation to prevent automatic message.

        Args:
            request: HTTP request object
            email_address: EmailAddress instance being confirmed
        """
        super().confirm_email(request, email_address)


class KitaSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for Google OAuth.

    Handles auto-acceptance of terms/privacy and email verification sync
    when users sign up via Google OAuth.
    """

    def pre_social_login(self, request: HttpRequest, sociallogin):
        """
        Handle email verification sync for Google OAuth logins.

        Ensures that users logging in with Google OAuth always have their
        email marked as verified in both allauth and our User model.

        This handles multiple scenarios:
        1. New user signing up with Google → email verified
        2. Existing email/password user logging in with Google → connect + verify
        3. Existing Google user logging in again → sync verification if missing

        Args:
            request: HTTP request object
            sociallogin: SocialLogin instance
        """
        email = sociallogin.account.extra_data.get('email')
        if not email:
            return

        # Get or create the user
        try:
            user = User.objects.get(email__iexact=email)
            user_exists = True

            # If not already connected, connect the social account
            if not sociallogin.is_existing:
                sociallogin.connect(request, user)

        except User.DoesNotExist:
            # No existing user, will create new one in save_user()
            return

        # Always sync email verification for Google OAuth users
        # (Google has already verified the email)
        if user_exists and not user.is_email_verified:
            user.is_email_verified = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=['is_email_verified', 'email_verified_at'])

            logger.info(f"Synced email verification for Google OAuth user: {user.email}")

        # Ensure allauth EmailAddress is also marked as verified
        email_address, created = EmailAddress.objects.get_or_create(
            user=user,
            email__iexact=email,
            defaults={'verified': True, 'primary': True}
        )

        if not email_address.verified:
            email_address.verified = True
            email_address.primary = True
            email_address.save(update_fields=['verified', 'primary'])

            logger.info(f"Marked allauth EmailAddress as verified for: {user.email}")

    def save_user(self, request: HttpRequest, sociallogin, form=None):
        """
        Save user with auto-acceptance of terms and email verification sync.

        This is the correct method to override - it's called when the user
        is being saved to the database.

        Args:
            request: HTTP request object
            sociallogin: SocialLogin instance
            form: Optional form data

        Returns:
            Saved User instance
        """
        # Call parent to create user with basic data
        user = super().save_user(request, sociallogin, form)

        # Only for new signups (not existing users)
        if not sociallogin.is_existing:
            now = timezone.now()

            # Auto-accept terms and privacy for Google OAuth users
            # This is acceptable because:
            # 1. Disclaimer is visible before clicking Google button
            # 2. Timestamp proves they used the service (implicit acceptance)
            # 3. User can review terms anytime in dashboard
            user.terms_accepted_at = now
            user.privacy_accepted_at = now

            # Sync email verification from Google to our User model
            # Google has already verified the email, so we trust it
            user.is_email_verified = True
            user.email_verified_at = now

            # Save the updated fields
            user.save(update_fields=[
                'terms_accepted_at',
                'privacy_accepted_at',
                'is_email_verified',
                'email_verified_at'
            ])

        return user