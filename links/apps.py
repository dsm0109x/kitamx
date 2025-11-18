"""Application configuration for Links module.

Configures the payment links management application.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from django.apps import AppConfig

if TYPE_CHECKING:
    pass


class LinksConfig(AppConfig):
    """Configuration for Links application."""

    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'links'
    verbose_name: str = 'Payment Links Management'