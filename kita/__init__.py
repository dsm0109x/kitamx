"""Kita - Mexican Payment Links and CFDI 4.0 Invoicing Platform.

A Django-based SaaS platform for creating payment links via MercadoPago
and generating CFDI 4.0 compliant invoices through FiscalAPI.
"""
from __future__ import annotations
from typing import Tuple

# Import Celery app for task queue initialization
from .celery import app as celery_app

# This ensures Celery app is loaded when Django starts
__all__: Tuple[str, ...] = ('celery_app',)

# Version info
__version__ = '1.0.0'
__author__ = 'Kita Team'
__license__ = 'Proprietary'