from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    # 🇪🇸 Base: /auditoria/

    # Main audit logs page
    path('', views.audit_index, name='index'),

    # AJAX endpoints for DataTable
    # 🇪🇸 ajax/logs → ajax/registros
    path('ajax/registros/', views.ajax_logs, name='ajax_logs'),
    # 🇪🇸 ajax/stats → ajax/estadisticas
    path('ajax/estadisticas/', views.ajax_stats, name='ajax_stats'),

    # Detail view
    # 🇪🇸 detail → detalle
    path('detalle/<uuid:log_id>/', views.log_detail, name='log_detail'),

    # Export
    # 🇪🇸 export → exportar
    path('exportar/', views.export_logs, name='export_logs'),
]