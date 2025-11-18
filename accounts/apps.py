"""App configuration for accounts."""
from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Django app configuration for the accounts module.

    Handles user authentication, profiles, and session management.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'Accounts'

    def ready(self) -> None:
        """
        Import signal handlers when app is ready.

        This ensures signal handlers are connected when
        Django starts up.
        """
