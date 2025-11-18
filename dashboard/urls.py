from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main dashboard (Command Center)
    # 🇪🇸 Base: /panel/
    path('', views.dashboard_view, name='index'),

    # AJAX endpoints for real-time updates
    # 🇪🇸 pending-tasks → tareas-pendientes
    path('ajax/tareas-pendientes/', views.ajax_pending_tasks, name='ajax_pending_tasks'),
    # 🇪🇸 activity-stream → actividad
    path('ajax/actividad/', views.ajax_activity_stream, name='ajax_activity_stream'),
    # 🇪🇸 quick-stats → estadisticas-rapidas
    path('ajax/estadisticas-rapidas/', views.ajax_quick_stats, name='ajax_quick_stats'),

    # Legacy endpoints (kept for compatibility with modals and other features)
    # 🇪🇸 create-link-form → crear-enlace-form
    path('crear-enlace-form/', views.create_link_form, name='create_link_form'),
    # 🇪🇸 create-link → crear-enlace
    path('crear-enlace/', views.create_link, name='create_link'),
    # 🇪🇸 detail → detalle
    path('detalle/<str:detail_type>/<uuid:detail_id>/', views.detail_view, name='detail'),

    # Form helpers
    # 🇪🇸 recent-customers → clientes-recientes
    path('clientes-recientes/', views.recent_customers, name='recent_customers'),
    # 🇪🇸 rate-limit-info → info-limite-peticiones
    path('info-limite-peticiones/', views.rate_limit_info, name='rate_limit_info'),
    # 🇪🇸 verify-setup → verificar-configuracion
    path('verificar-configuracion/', views.verify_setup, name='verify_setup'),

    # Search API for Command Palette
    # 🇪🇸 api/search → api/buscar
    path('api/buscar/', views.search_api, name='search_api'),
]
