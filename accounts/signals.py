"""Signal handlers for accounts app."""
from __future__ import annotations
from typing import Any

from django.dispatch import receiver
from django.http import HttpRequest
from django.utils import timezone
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed

from .cache import CacheManager
from .models import User
from .utils import AuditLogger


@receiver(email_confirmed)
def email_confirmed_handler(
    sender: type[EmailAddress],
    request: HttpRequest,
    email_address: EmailAddress,
    **kwargs: Any
) -> None:
    """
    Handle email confirmation from allauth.

    When an email is confirmed via allauth, update our User model
    and invalidate related caches.

    Args:
        sender: Signal sender (EmailAddress model)
        request: HTTP request that triggered confirmation
        email_address: EmailAddress instance that was confirmed
        **kwargs: Additional signal arguments
    """
    try:
        user = User.objects.get(email=email_address.email)
        user.is_email_verified = True
        user.email_verified_at = timezone.now()
        user.save(update_fields=['is_email_verified', 'email_verified_at'])

        # Invalidate user cache after email verification
        CacheManager.invalidate_user_cache(user.id)

        # Log the email verification
        AuditLogger.log_action(
            request=request,
            action='email_verified',
            entity_type='User',
            entity_id=str(user.id),
            details={'email': email_address.email}
        )

    except User.DoesNotExist:
        pass  # User not found, ignore silently