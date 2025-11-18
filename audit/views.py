"""
Views for audit logging and monitoring.

Provides secure, optimized access to audit logs with caching and proper validation.
"""
from __future__ import annotations
from typing import Any, Optional, Dict
from datetime import datetime, timedelta, date
import json
import csv
import logging

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Q, Count
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django_ratelimit.decorators import ratelimit

from core.models import AuditLog
from core.exceptions import ErrorResponseBuilder
from accounts.utils import AuditLogger
from accounts.decorators import tenant_required

logger = logging.getLogger(__name__)


# Translation helpers (display only, not DB)
def translate_action(action: str) -> str:
    """Translate action to Spanish for display."""
    translations = {
        'create': 'Crear',
        'update': 'Actualizar',
        'delete': 'Eliminar',
        'cancel': 'Cancelar',
        'duplicate': 'Duplicar',
        'login': 'Inicio de sesión',
        'logout': 'Cierre de sesión',
        'login_failed': 'Inicio fallido',
        'send_reminder': 'Enviar recordatorio',
        'export_audit_logs': 'Exportar logs',
        'view_audit_details': 'Ver detalles',
        'password_change': 'Cambio de contraseña',
        'password_reset': 'Reseteo de contraseña',
        'email_verified': 'Email verificado',
        'permission_denied': 'Permiso denegado',
        'rate_limited': 'Límite de tasa',
    }
    return translations.get(action, action.replace('_', ' ').title())


def translate_entity(entity_type: str) -> str:
    """Translate entity type to Spanish for display."""
    translations = {
        'PaymentLink': 'Link de Pago',
        'Payment': 'Pago',
        'Invoice': 'Factura',
        'User': 'Usuario',
        'Tenant': 'Empresa',
        'TenantUser': 'Usuario de Empresa',
        'Subscription': 'Suscripción',
        'CSDCertificate': 'Certificado CSD',
        'AuditLog': 'Log de Auditoría',
        'Notification': 'Notificación',
    }
    return translations.get(entity_type, entity_type)


def format_changes_for_display(old_values: dict, new_values: dict) -> list:
    """
    Format old/new values for user-friendly display.

    Returns list of dicts with:
    - field: field name (translated if possible)
    - old: old value
    - new: new value
    - changed: boolean
    """
    changes = []

    # Get all unique keys from both dicts
    all_keys = set(list(old_values.keys()) + list(new_values.keys()))

    # Field name translations
    field_translations = {
        'title': 'Título',
        'amount': 'Monto',
        'customer_name': 'Nombre del cliente',
        'customer_email': 'Email del cliente',
        'customer_rfc': 'RFC del cliente',
        'description': 'Descripción',
        'expires_at': 'Fecha de expiración',
        'validity_days': 'Días de vigencia',
        'expires_days': 'Días de vigencia',
        'status': 'Estado',
        'requires_invoice': 'Requiere factura',
        'notifications_enabled': 'Notificaciones activas',
        'notify_on_create': 'Notificar al crear',
        'send_reminders': 'Enviar recordatorios',
        'reminder_hours_before': 'Recordatorio (horas antes)',
        'cancellation_reason': 'Razón de cancelación',
        'max_uses': 'Usos máximos',
        'currency': 'Moneda',
    }

    # Status translations
    status_translations = {
        'active': 'Activo',
        'paid': 'Pagado',
        'expired': 'Expirado',
        'cancelled': 'Cancelado',
        'pending': 'Pendiente',
        'approved': 'Aprobado',
        'rejected': 'Rechazado',
    }

    for key in sorted(all_keys):
        old_val = old_values.get(key, '—')
        new_val = new_values.get(key, '—')

        # Translate field name
        field_name = field_translations.get(key, key.replace('_', ' ').title())

        # Format dates (ISO format detection)
        if old_val != '—' and isinstance(old_val, str) and 'T' in str(old_val) and len(str(old_val)) > 10:
            try:
                from dateutil import parser
                dt = parser.parse(old_val)
                old_val = dt.strftime('%d/%m/%Y %H:%M')
            except:
                pass  # Keep original if parsing fails

        if new_val != '—' and isinstance(new_val, str) and 'T' in str(new_val) and len(str(new_val)) > 10:
            try:
                from dateutil import parser
                dt = parser.parse(new_val)
                new_val = dt.strftime('%d/%m/%Y %H:%M')
            except:
                pass  # Keep original if parsing fails

        # Translate values if they're status
        if key == 'status' or 'status' in key.lower():
            old_val = status_translations.get(str(old_val), old_val) if old_val != '—' else '—'
            new_val = status_translations.get(str(new_val), new_val) if new_val != '—' else '—'

        # Format booleans
        if isinstance(old_val, bool):
            old_val = 'Sí' if old_val else 'No'
        if isinstance(new_val, bool):
            new_val = 'Sí' if new_val else 'No'

        changes.append({
            'field': field_name,
            'old': str(old_val) if old_val != '—' else '—',
            'new': str(new_val) if new_val != '—' else '—',
            'changed': old_val != new_val
        })

    return changes


class AuditStatsCalculator:
    """Calculate and cache audit statistics."""

    @staticmethod
    def get_stats_cache_key(tenant_id: str, start_date: date, end_date: date) -> str:
        """Generate cache key for stats using standardized format."""
        from core.cache import KitaRedisCache
        return KitaRedisCache.generate_standard_key('audit', tenant_id, 'stats', f"{start_date}_{end_date}")

    @staticmethod
    def calculate(tenant: Any, start_date: date, end_date: date) -> Dict[str, Any]:
        """
        Calculate audit statistics with caching.

        Args:
            tenant: Tenant instance
            start_date: Start date for stats
            end_date: End date for stats

        Returns:
            Dictionary with audit statistics
        """
        cache_key = AuditStatsCalculator.get_stats_cache_key(
            str(tenant.id), start_date, end_date
        )

        # Try cache first
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return cached_stats

        # Calculate stats
        logs = AuditLog.objects.filter(
            tenant=tenant,
            created_at__date__range=[start_date, end_date]
        ).select_related('tenant')

        # Count by action
        actions_breakdown = list(
            logs.values('action')
            .annotate(count=Count('action'))
            .order_by('-count')[:10]
        )

        # Count by entity type
        entities_breakdown = list(
            logs.values('entity_type')
            .annotate(count=Count('entity_type'))
            .order_by('-count')[:10]
        )

        # Count by user - limit to top 10
        users_breakdown = list(
            logs.values('user_email', 'user_name')
            .annotate(count=Count('user_email'))
            .order_by('-count')[:10]
        )

        # Daily activity (optimized)
        daily_activity = []
        if (end_date - start_date).days <= 90:  # Only for reasonable date ranges
            current_date = start_date
            while current_date <= end_date:
                daily_count = logs.filter(created_at__date=current_date).count()
                daily_activity.append({
                    'date': current_date.isoformat(),
                    'count': daily_count
                })
                current_date += timedelta(days=1)

        stats = {
            'total_logs': logs.count(),
            'unique_users': logs.values('user_email').distinct().count(),
            'actions_breakdown': actions_breakdown,
            'entities_breakdown': entities_breakdown,
            'users_breakdown': users_breakdown,
            'daily_activity': daily_activity,
        }

        # Cache for 5 minutes
        cache.set(cache_key, stats, 300)

        return stats


def validate_date_range(
    start_date: Optional[str],
    end_date: Optional[str],
    max_days: int = 365
) -> tuple[date, date]:
    """
    Validate and parse date range.

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)
        max_days: Maximum allowed date range

    Returns:
        Tuple of (start_date, end_date) as date objects

    Raises:
        ValidationError: If dates are invalid
    """
    today = timezone.now().date()

    # Parse start date
    if start_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Invalid start date format')
    else:
        start = today - timedelta(days=30)

    # Parse end date
    if end_date:
        try:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError('Invalid end date format')
    else:
        end = today

    # Validate range
    if start > end:
        raise ValidationError('Start date must be before end date')

    if (end - start).days > max_days:
        raise ValidationError(f'Date range cannot exceed {max_days} days')

    # Don't allow future dates
    if end > today:
        end = today

    return start, end


@login_required
@tenant_required(require_owner=True)
@ensure_csrf_cookie
def audit_index(request: HttpRequest) -> HttpResponse:
    """
    Main audit logs page with statistics.

    Only accessible by tenant owners for security.
    """
    tenant_user = request.tenant_user  # Set by decorator
    tenant = tenant_user.tenant

    try:
        start_date, end_date = validate_date_range(
            request.GET.get('start_date'),
            request.GET.get('end_date')
        )
    except ValidationError:
        # Use defaults on validation error
        today = timezone.now().date()
        start_date = today - timedelta(days=30)
        end_date = today

    # Calculate stats with caching
    stats = AuditStatsCalculator.calculate(tenant, start_date, end_date)

    # Log audit page access
    AuditLogger.log_action(
        request=request,
        action='view_audit_logs',
        entity_type='AuditLog',
        entity_id=None,
        notes=f"Viewed audit logs from {start_date} to {end_date}"
    )

    context = {
        'user': request.user,
        'tenant': tenant,
        'tenant_user': tenant_user,
        'stats': stats,
        'start_date': start_date,
        'end_date': end_date,
        'page_title': 'Logs de Auditoría'
    }

    return render(request, 'audit/index.html', context)


@login_required
@tenant_required(require_owner=True)
@ratelimit(key='user', rate='60/m', method='GET')
@require_http_methods(["GET"])
def ajax_logs(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint for DataTable with audit logs.

    Optimized with select_related and pagination.
    Rate limited to prevent abuse.
    """
    tenant = request.tenant_user.tenant

    # DataTable parameters with validation
    try:
        draw = int(request.GET.get('draw', 1))
        start = max(0, int(request.GET.get('start', 0)))
        length = min(100, int(request.GET.get('length', 25)))  # Max 100 per page
    except (ValueError, TypeError):
        return ErrorResponseBuilder.build_error(
            message='Invalid parameters',
            code='validation_error',
            status=400
        )

    search_value = request.GET.get('search[value]', '').strip()[:100]  # Limit search length

    # Filters with validation
    action_filter = request.GET.get('action', '').strip()[:50]
    entity_filter = request.GET.get('entity_type', '').strip()[:50]
    user_filter = request.GET.get('user_email', '').strip()[:254]

    try:
        date_from, date_to = validate_date_range(
            request.GET.get('date_from'),
            request.GET.get('date_to'),
            max_days=90  # Limit for AJAX queries
        )
    except ValidationError:
        date_from = date_to = None

    # Build optimized queryset
    logs = AuditLog.objects.filter(tenant=tenant).select_related('tenant')

    # Apply filters
    if action_filter:
        logs = logs.filter(action=action_filter)

    if entity_filter:
        logs = logs.filter(entity_type=entity_filter)

    if user_filter:
        logs = logs.filter(user_email__icontains=user_filter)

    if date_from:
        logs = logs.filter(created_at__date__gte=date_from)

    if date_to:
        logs = logs.filter(created_at__date__lte=date_to)

    # Search across multiple fields
    if search_value:
        logs = logs.filter(
            Q(action__icontains=search_value) |
            Q(entity_type__icontains=search_value) |
            Q(entity_name__icontains=search_value) |
            Q(user_name__icontains=search_value) |
            Q(user_email__icontains=search_value) |
            Q(notes__icontains=search_value)
        )

    # Get total count before pagination
    total_records = logs.count()

    # Order and paginate
    logs = logs.order_by('-created_at')[start:start + length]

    # Format data for DataTables
    data = []
    for log in logs:
        data.append({
            'id': str(log.id),
            'action': log.action,
            'action_display': translate_action(log.action),
            'entity_type': log.entity_type,
            'entity_type_display': translate_entity(log.entity_type),
            'entity_name': log.entity_name or '',
            'user_name': log.user_name,
            'user_email': log.user_email,
            'created_at': log.created_at.isoformat(),
            'ip_address': log.ip_address,
            'notes': (log.notes[:100] + '...') if len(log.notes) > 100 else log.notes,
            'has_changes': bool(log.old_values or log.new_values),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })


@login_required
@tenant_required(require_owner=True)
@cache_page(60)  # Cache for 1 minute
@require_http_methods(["GET"])
def ajax_stats(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint for audit statistics.

    Cached to reduce database load.
    """
    tenant = request.tenant_user.tenant

    try:
        start_date, end_date = validate_date_range(
            request.GET.get('date_from'),
            request.GET.get('date_to')
        )
    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)

    stats = AuditStatsCalculator.calculate(tenant, start_date, end_date)

    return JsonResponse({
        'success': True,
        'stats': stats,
        'date_range': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
    })


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["GET"])
def log_detail(request: HttpRequest, log_id: str) -> HttpResponse:
    """
    Get audit log details for modal/panel view.

    Args:
        request: HTTP request
        log_id: UUID of the audit log
    """
    tenant = request.tenant_user.tenant

    # Get log with tenant validation
    log = get_object_or_404(
        AuditLog.objects.select_related('tenant'),
        id=log_id,
        tenant=tenant
    )

    # Log access comentado para evitar loop infinito y error de 'details'
    # if log.old_values or log.new_values:
    #     AuditLogger.log_action(
    #         request=request,
    #         action='view_audit_details',
    #         entity_type='AuditLog',
    #         entity_id=str(log_id)
    #     )

    # Format changes for user-friendly display
    changes = []
    if log.old_values or log.new_values:
        changes = format_changes_for_display(
            log.old_values or {},
            log.new_values or {}
        )

    context = {
        'log': log,
        'tenant': tenant,
        'action_display': translate_action(log.action),
        'entity_display': translate_entity(log.entity_type),
        'changes': changes,
        'has_changes': bool(changes),
        # Keep JSON for fallback/debugging
        'old_values_json': json.dumps(log.old_values, indent=2, ensure_ascii=False) if log.old_values else None,
        'new_values_json': json.dumps(log.new_values, indent=2, ensure_ascii=False) if log.new_values else None,
    }

    return render(request, 'audit/log_detail.html', context)


@login_required
@tenant_required(require_owner=True)
@ratelimit(key='user', rate='10/h', method='GET')
@require_http_methods(["GET"])
def export_logs(request: HttpRequest) -> HttpResponse:
    """
    Export audit logs to CSV.

    Rate limited to prevent resource abuse.
    Limited to 10,000 records for performance.
    """
    tenant = request.tenant_user.tenant

    # Validate filters
    action_filter = request.GET.get('action', '').strip()[:50]
    entity_filter = request.GET.get('entity_type', '').strip()[:50]

    try:
        date_from, date_to = validate_date_range(
            request.GET.get('date_from'),
            request.GET.get('date_to'),
            max_days=90  # Limit export range
        )
    except ValidationError as e:
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='validation_error',
            status=400
        )

    # Build queryset with filters
    logs = AuditLog.objects.filter(
        tenant=tenant,
        created_at__date__range=[date_from, date_to]
    ).select_related('tenant')

    if action_filter:
        logs = logs.filter(action=action_filter)

    if entity_filter:
        logs = logs.filter(entity_type=entity_filter)

    # Limit to 10,000 records
    logs = logs.order_by('-created_at')[:10000]

    # Log export action
    filters_applied = []
    if action_filter:
        filters_applied.append(f"action={action_filter}")
    if entity_filter:
        filters_applied.append(f"entity={entity_filter}")

    filters_str = ", ".join(filters_applied) if filters_applied else "sin filtros"

    AuditLogger.log_action(
        request=request,
        action='export_audit_logs',
        entity_type='AuditLog',
        entity_id=None,
        notes=f"Exported {logs.count()} logs from {date_from} to {date_to}. Filters: {filters_str}"
    )

    # Generate CSV response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Encoding'] = 'utf-8'

    today_str = timezone.now().strftime('%Y%m%d')
    filename = f"audit_logs_{tenant.slug}_{today_str}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Write BOM for Excel compatibility
    response.write('\ufeff')

    writer = csv.writer(response)
    writer.writerow([
        'Fecha', 'Usuario', 'Email', 'Acción', 'Entidad',
        'Nombre', 'IP', 'Notas'
    ])

    for log in logs:
        writer.writerow([
            log.created_at.strftime('%d/%m/%Y %H:%M:%S'),
            log.user_name,
            log.user_email,
            log.action,
            log.entity_type,
            log.entity_name or '',
            log.ip_address,
            log.notes[:500]  # Limit notes length in export
        ])

    return response