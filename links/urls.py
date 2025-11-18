"""URL patterns for Payment Links application.

Defines routes for link management, AJAX operations, and actions.
All URLs in Spanish for better UX.
"""
from __future__ import annotations
from typing import List

from django.urls import path, URLPattern
from . import views

app_name: str = 'links'

urlpatterns: List[URLPattern] = [
    # 🇪🇸 Base: /enlaces/
    path('', views.links_index, name='index'),

    # AJAX endpoints
    # 🇪🇸 ajax/data → ajax/datos
    path('ajax/datos/', views.ajax_data, name='ajax_data'),
    # 🇪🇸 ajax/stats → ajax/estadisticas
    path('ajax/estadisticas/', views.stats, name='stats'),

    # Export
    # 🇪🇸 export → exportar
    path('exportar/<str:format>/', views.export_links, name='export'),

    # Detail and actions
    # 🇪🇸 detail → detalle
    path('detalle/<uuid:link_id>/', views.detail, name='detail'),
    # 🇪🇸 duplicate → duplicar
    path('duplicar/', views.duplicate, name='duplicate'),
    # 🇪🇸 cancel → cancelar
    path('cancelar/', views.cancel, name='cancel'),
    # 🇪🇸 send-reminder → enviar-recordatorio
    path('enviar-recordatorio/', views.send_reminder, name='send_reminder'),
    # 🇪🇸 edit-data → editar-datos
    path('editar-datos/<uuid:link_id>/', views.edit_data, name='edit_data'),
    # 🇪🇸 edit → editar
    path('editar/', views.edit, name='edit'),
]