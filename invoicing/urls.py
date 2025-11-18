from django.urls import path
from . import views

app_name = 'invoicing'

urlpatterns = [
    # 🇪🇸 Base: /facturas/

    # File upload endpoints (legacy)
    # 🇪🇸 upload → subir
    path('subir/', views.upload_file, name='upload_file'),
    # 🇪🇸 upload/delete → subir/eliminar
    path('subir/eliminar/<uuid:upload_token>/', views.delete_file, name='delete_file'),

    # CSD validation and processing
    # 🇪🇸 csd/validate-local → csd/validar-local
    path('csd/validar-local/', views.validate_csd_local, name='validate_csd_local'),
    # 🇪🇸 csd/save-complete → csd/guardar-completo
    path('csd/guardar-completo/', views.save_csd_complete, name='save_csd_complete'),

    # Facturación section (CFDI management)
    path('', views.facturacion_index, name='index'),
    # 🇪🇸 ajax/invoices → ajax/facturas
    path('ajax/facturas/', views.ajax_invoices, name='ajax_invoices'),
    # 🇪🇸 ajax/stats → ajax/estadisticas
    path('ajax/estadisticas/', views.ajax_invoice_stats, name='ajax_invoice_stats'),
    # 🇪🇸 detail → detalle
    path('detalle/<uuid:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    # 🇪🇸 cancel → cancelar
    path('cancelar/', views.cancel_invoice, name='cancel_invoice'),
    # 🇪🇸 resend → reenviar
    path('reenviar/', views.resend_invoice, name='resend_invoice'),
    # 🇪🇸 download → descargar
    path('descargar/<uuid:invoice_id>/<str:file_type>/', views.download_file, name='download_file'),
    # 🇪🇸 export → exportar
    path('exportar/', views.export_invoices, name='export_invoices'),
]