"""
Mixins comunes para Django Admin en la aplicación Kita.

Este módulo proporciona mixins reutilizables para reducir duplicación
en configuraciones de admin y asegurar consistencia.
"""
from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html


class BaseKitaAdminMixin:
    """
    Mixin base para todas las configuraciones admin de Kita.

    Proporciona configuración común y optimizaciones de queries.
    """

    list_per_page = 50
    show_full_result_count = False  # Mejor performance para tablas grandes
    ordering = ['-created_at']

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimizar queryset con select_related básico."""
        qs = super().get_queryset(request)
        # Solo select_related si el modelo tiene tenant
        if hasattr(self.model, 'tenant'):
            return qs.select_related('tenant')
        return qs


class TimestampAdminMixin(BaseKitaAdminMixin):
    """
    Mixin para modelos con campos de timestamp.

    Agrega campos comunes de fecha y configuraciones readonly.
    """

    date_hierarchy = 'created_at'
    readonly_fields = ['id', 'created_at', 'updated_at']

    def get_list_filter(self):
        """Agregar filtros de fecha a list_filter existente."""
        base_filters = list(getattr(self, 'list_filter', []))
        return base_filters + ['created_at']


class TenantScopedAdminMixin(TimestampAdminMixin):
    """
    Mixin para modelos que pertenecen a un tenant.

    Proporciona filtrado por tenant y optimizaciones relacionadas.
    """

    def get_list_display(self):
        """Agregar tenant a list_display si no está presente."""
        base_display = list(getattr(self, 'list_display', []))
        if 'tenant' not in base_display:
            base_display.insert(0, 'tenant')
        return base_display

    def get_list_filter(self):
        """Agregar filtro de tenant."""
        base_filters = super().get_list_filter()
        return ['tenant'] + base_filters

    def get_search_fields(self):
        """Agregar búsqueda por tenant."""
        base_search = list(getattr(self, 'search_fields', []))
        tenant_fields = ['tenant__name', 'tenant__slug', 'tenant__email']
        # Solo agregar si no están presentes
        for field in tenant_fields:
            if field not in base_search:
                base_search.append(field)
        return base_search

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimizar con select_related para tenant."""
        qs = super().get_queryset(request)
        return qs.select_related('tenant')


class StatusAdminMixin(BaseKitaAdminMixin):
    """
    Mixin para modelos con campo status.

    Proporciona filtros y displays comunes para status.
    """

    def get_list_filter(self):
        """Agregar filtro de status."""
        base_filters = list(getattr(self, 'list_filter', []))
        if 'status' not in base_filters:
            base_filters.append('status')
        return base_filters

    def status_display(self, obj) -> str:
        """Display colorizado para status."""
        if not hasattr(obj, 'status'):
            return '-'

        status = obj.status
        colors = {
            'active': '#28a745',
            'inactive': '#6c757d',
            'pending': '#ffc107',
            'expired': '#dc3545',
            'paid': '#28a745',
            'cancelled': '#dc3545',
            'error': '#dc3545',
            'stamped': '#28a745',
            'draft': '#6c757d'
        }

        color = colors.get(status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            status.title()
        )

    status_display.short_description = 'Status'


class ExternalReferenceAdminMixin(BaseKitaAdminMixin):
    """
    Mixin para modelos con referencias externas (MercadoPago, SW, etc.).

    Proporciona campos readonly y filtros para IDs externos.
    """

    def get_readonly_fields(self, request, obj=None):
        """Agregar campos de referencia externa como readonly."""
        base_readonly = list(getattr(self, 'readonly_fields', []))
        external_fields = []

        # Campos comunes de referencia externa
        model_fields = [f.name for f in self.model._meta.fields]

        external_patterns = [
            'mp_', 'sw_', 'external_', '_id', '_token', '_reference'
        ]

        for field_name in model_fields:
            if any(pattern in field_name for pattern in external_patterns):
                if field_name not in base_readonly:
                    external_fields.append(field_name)

        return base_readonly + external_fields


class AuditableAdminMixin(TimestampAdminMixin):
    """
    Mixin para modelos con audit trail (created_by, updated_by).

    Proporciona configuración para campos de auditoría.
    """

    def get_readonly_fields(self, request, obj=None):
        """Agregar campos de auditoría como readonly."""
        base_readonly = list(super().get_readonly_fields(request, obj))
        audit_fields = ['created_by', 'updated_by']

        model_fields = [f.name for f in self.model._meta.fields]
        for field in audit_fields:
            if field in model_fields and field not in base_readonly:
                base_readonly.append(field)

        return base_readonly

    def save_model(self, request, obj, form, change):
        """Automáticamente setear created_by/updated_by."""
        if not change:  # Creando nuevo objeto
            if hasattr(obj, 'created_by') and not obj.created_by:
                obj.created_by = request.user

        if hasattr(obj, 'updated_by'):
            obj.updated_by = request.user

        super().save_model(request, obj, form, change)


# Mixins compuestos para casos comunes
class FullKitaAdminMixin(
    TenantScopedAdminMixin,
    StatusAdminMixin,
    ExternalReferenceAdminMixin,
    AuditableAdminMixin
):
    """
    Mixin completo para modelos Kita con todas las funcionalidades.

    Combina: tenant scoping, status, referencias externas, y auditoría.
    """
    pass


class SimpleKitaAdminMixin(TimestampAdminMixin, StatusAdminMixin):
    """
    Mixin simple para modelos básicos con timestamps y status.
    """
    pass


class TenantModelAdminMixin(TenantScopedAdminMixin, StatusAdminMixin):
    """
    Mixin para modelos básicos con tenant y status.
    """
    pass


__all__ = [
    'BaseKitaAdminMixin',
    'TimestampAdminMixin',
    'TenantScopedAdminMixin',
    'StatusAdminMixin',
    'ExternalReferenceAdminMixin',
    'AuditableAdminMixin',
    'FullKitaAdminMixin',
    'SimpleKitaAdminMixin',
    'TenantModelAdminMixin',
]