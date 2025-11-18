"""URL patterns for Kita IA application.

Defines routes for AI chat interface and SSE streaming.
All URLs in Spanish for consistency.
"""
from __future__ import annotations
from typing import List

from django.urls import path, URLPattern
from . import views

app_name: str = 'kita_ia'

urlpatterns: List[URLPattern] = [
    # 🇪🇸 Base: /ia/ (IA is universal acronym)

    path('', views.kita_ia_index, name='index'),
    # 🇪🇸 chat/stream → chat/flujo
    path('chat/flujo/', views.chat_stream, name='chat_stream'),
    # 🇪🇸 chat/message → chat/mensaje
    path('chat/mensaje/', views.send_message, name='send_message'),
    # 🇪🇸 chat/confirm → chat/confirmar
    path('chat/confirmar/', views.confirm_link, name='confirm_link'),
]