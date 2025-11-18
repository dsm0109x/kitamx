"""WSGI config for Kita project.

Exposes the WSGI callable for production server deployment.
Used by Gunicorn, uWSGI, and other WSGI servers.
"""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

from django.core.wsgi import get_wsgi_application

if TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIHandler

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kita.settings')

# Initialize Django WSGI application
application: WSGIHandler = get_wsgi_application()

# Production deployment examples:
# Gunicorn: gunicorn kita.wsgi:application --bind 0.0.0.0:8000 --workers 4
# uWSGI: uwsgi --http :8000 --module kita.wsgi:application --master --processes 4
