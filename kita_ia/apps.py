"""Application configuration for Kita IA.

Configures the AI-powered payment link creation module.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from django.apps import AppConfig

if TYPE_CHECKING:
    pass


class KitaIaConfig(AppConfig):
    """Configuration for Kita IA application."""

    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'kita_ia'
    verbose_name: str = 'Kita IA - AI Assistant'