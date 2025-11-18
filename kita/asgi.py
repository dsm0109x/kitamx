"""ASGI config for Kita project.

Exposes the ASGI callable for async server deployment.
Supports WebSockets, Server-Sent Events, and HTTP/2.
"""
from __future__ import annotations
import os
from typing import TYPE_CHECKING

from django.core.asgi import get_asgi_application

if TYPE_CHECKING:
    from django.core.handlers.asgi import ASGIHandler

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kita.settings')

# Initialize Django ASGI application
application: ASGIHandler = get_asgi_application()

# Note: For WebSocket support with channels, use:
# from channels.routing import ProtocolTypeRouter, URLRouter
# from channels.auth import AuthMiddlewareStack
# application = ProtocolTypeRouter({
#     "http": get_asgi_application(),
#     "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
# })
