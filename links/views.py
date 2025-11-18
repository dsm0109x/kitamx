from __future__ import annotations

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from datetime import datetime, timedelta
import json
import logging
import csv
from io import StringIO

from core.models import AuditLog
from core.exceptions import ErrorResponseBuilder
from accounts.decorators import tenant_required
from accounts.utils import AuditLogger
from core.security import SecureIPDetector
from core.query_optimizations import get_cached_tenant_stats, QueryOptimizer
from payments.models import PaymentLink

logger = logging.getLogger(__name__)


# get_client_ip is now imported directly from core.security
# Use: from core.security import get_client_ip
# Or use: SecureIPDetector.get_client_ip(request)


@login_required
@tenant_required()
def links_index(request: HttpRequest) -> HttpResponse:
    """
    Payment Links main management interface.

    Renders the primary payment links dashboard with comprehensive statistics,
    DataTables integration for link management, and cached performance metrics.
    Central hub for payment link operations and business insights.

    Args:
        request: HTTP request from authenticated tenant user

    Returns:
        HttpResponse: Links management page with stats and data table setup

    Raises:
        403: If user lacks tenant access
    """
    user = request.user
    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    # Calculate stats using optimized cached version
    stats = get_cached_tenant_stats(tenant, 'payments', timeout=300)

    # Format stats for component
    stats_display = [
        {
            'icon': 'link',
            'label': 'Total Links',
            'value': stats.get('total', 0),
            'value_id': 'total-links',
            'color': 'primary'
        },
        {
            'icon': 'check-circle',
            'label': 'Pagados',
            'value': stats.get('paid', 0),
            'value_id': 'paid-links',
            'color': 'success'
        },
        {
            'icon': 'clock',
            'label': 'Activos',
            'value': stats.get('active', 0),
            'value_id': 'active-links',
            'color': 'warning'
        },
        {
            'icon': 'dollar',
            'label': 'Total Cobrado',
            'value': f"${stats.get('revenue', 0):.2f}",
            'value_id': 'total-revenue',
            'color': 'info'
        }
    ]

    # Empty state features
    empty_features = [
        'Genera link en segundos',
        'Recibe pagos con MercadoPago',
        'Factura automática CFDI 4.0',
        'Notificaciones por WhatsApp y Email'
    ]

    context = {
        'user': user,
        'tenant': tenant,
        'tenant_user': tenant_user,
        'stats': stats,
        'stats_display': stats_display,
        'empty_features': empty_features,
        'page_title': 'Links de Pago'
    }

    return render(request, 'links/index.html', context)


@login_required
@tenant_required()
def ajax_data(request: HttpRequest) -> JsonResponse:
    """
    DataTables AJAX endpoint for payment links with advanced filtering.

    Provides server-side processing for payment links table with comprehensive
    filtering, sorting, search, and pagination. Includes optimized queries
    for performance and supports multiple filter criteria for business analysis.

    Args:
        request: HTTP GET request with DataTables parameters:
                - draw: Request counter for DataTables
                - start: Starting record index
                - length: Number of records per page
                - search[value]: Global search term
                - order[0][column]: Sort column index
                - order[0][dir]: Sort direction (asc/desc)
                - status: Filter by link status
                - requires_invoice: Filter by invoice requirement
                - date_from/date_to: Date range filters
                - customer: Customer name/email filter
                - amount_min/amount_max: Amount range filters

    Returns:
        JsonResponse: DataTables format with draw, recordsTotal, recordsFiltered,
                     and data array with link details, payment info, and metrics

    Raises:
        403: If user lacks tenant access
    """
    tenant = request.tenant

    # DataTables parameters
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search_value = request.GET.get('search[value]', '')

    # Order parameters
    order_column_index = int(request.GET.get('order[0][column]', 3))
    order_direction = request.GET.get('order[0][dir]', 'desc')

    # Column mapping for ordering
    columns = [
        'title', 'customer_name', 'amount', 'created_at',
        'expires_at', 'status', '', '', '', '', ''
    ]

    # Build query with optimizations
    links_qs = QueryOptimizer.optimize_payment_links(
        PaymentLink.objects.filter(tenant=tenant)
    )

    # Apply filters
    status_filter = request.GET.get('status')
    if status_filter:
        links_qs = links_qs.filter(status=status_filter)

    invoice_filter = request.GET.get('requires_invoice')
    if invoice_filter == 'required':
        links_qs = links_qs.filter(requires_invoice=True)
    elif invoice_filter == 'not_required':
        links_qs = links_qs.filter(requires_invoice=False)

    date_from = request.GET.get('date_from')
    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        links_qs = links_qs.filter(created_at__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        links_qs = links_qs.filter(created_at__date__lte=date_to)

    customer_filter = request.GET.get('customer')
    if customer_filter:
        links_qs = links_qs.filter(
            Q(customer_name__icontains=customer_filter) |
            Q(customer_email__icontains=customer_filter)
        )

    # Amount filters con validación
    amount_min = request.GET.get('amount_min')
    if amount_min:
        try:
            amount_min_value = float(amount_min)
            if amount_min_value >= 0:
                links_qs = links_qs.filter(amount__gte=amount_min_value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_min filter: {amount_min}")
            # Ignorar filtro inválido, no crashear

    amount_max = request.GET.get('amount_max')
    if amount_max:
        try:
            amount_max_value = float(amount_max)
            if amount_max_value > 0:
                links_qs = links_qs.filter(amount__lte=amount_max_value)
        except (ValueError, TypeError):
            logger.warning(f"Invalid amount_max filter: {amount_max}")
            # Ignorar filtro inválido, no crashear

    # Apply search
    if search_value:
        links_qs = links_qs.filter(
            Q(title__icontains=search_value) |
            Q(description__icontains=search_value) |
            Q(customer_name__icontains=search_value) |
            Q(customer_email__icontains=search_value) |
            Q(token__icontains=search_value)
        )

    # Apply ordering
    if order_column_index < len(columns) and columns[order_column_index]:
        order_field = columns[order_column_index]
        if order_direction == 'desc':
            order_field = '-' + order_field
        links_qs = links_qs.order_by(order_field)
    else:
        links_qs = links_qs.order_by('-created_at')

    # Count total records
    total_records = links_qs.count()

    # Apply pagination with prefetch_related to avoid N+1
    links_page = links_qs.prefetch_related('payments')[start:start + length]

    # Format data for DataTables
    data = []
    for link in links_page:
        # Get payment info if exists (usando prefetch, no query adicional)
        approved_payments = [p for p in link.payments.all() if p.status == 'approved']
        payment = approved_payments[0] if approved_payments else None
        invoice = payment.invoice if payment and hasattr(payment, 'invoice') else None

        data.append({
            'id': str(link.id),
            'token': link.token,
            'title': link.title,
            'description': link.description,
            'customer_name': link.customer_name,
            'customer_email': link.customer_email,
            'amount': float(link.amount),
            'created_at': link.created_at.isoformat(),
            'expires_at': link.expires_at.isoformat(),
            'status': link.status,
            'status_display': link.get_status_display(),
            'requires_invoice': link.requires_invoice,
            'payment_successful': payment is not None,
            'payment_amount': float(payment.amount) if payment else None,
            'invoice_uuid': str(invoice.uuid) if invoice and invoice.uuid else None,
            'views': link.get_views_count(),
            'clicks': link.get_clicks_count(),
            'reminders_sent': link.get_reminders_count()
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })


@login_required
@tenant_required()
def stats(request: HttpRequest) -> JsonResponse:
    """
    Real-time payment links statistics for dashboard cards.

    Provides current statistics including total links, status breakdown,
    and revenue calculations using optimized aggregate queries for
    performance. Updates dashboard cards with live business metrics.

    Args:
        request: HTTP GET request from authenticated tenant user

    Returns:
        JsonResponse: Statistics object with total, paid, active, expired
                     link counts and total revenue

    Raises:
        403: If user lacks tenant access
    """
    tenant = request.tenant

    # Optimized: single aggregate query instead of multiple counts
    from django.db.models import Q, Sum
    stats_agg = PaymentLink.objects.filter(tenant=tenant).aggregate(
        total=Count('id'),
        paid=Count('id', filter=Q(status='paid')),
        active=Count('id', filter=Q(status='active')),
        expired=Count('id', filter=Q(status='expired')),
        revenue=Sum('payments__amount', filter=Q(status='paid', payments__status='approved'))
    )

    stats = {
        'total': stats_agg['total'],
        'paid': stats_agg['paid'],
        'active': stats_agg['active'],
        'expired': stats_agg['expired'],
        'revenue': float(stats_agg['revenue'] or 0)
    }

    return JsonResponse({'success': True, 'stats': stats})


@login_required
@tenant_required()
def detail(request: HttpRequest, link_id: str) -> HttpResponse:
    """
    Payment link detail panel with comprehensive information.

    Renders detailed view of a payment link including all associated payments,
    customer information, and link performance metrics. Used in sidebar panels
    for quick access to link details without page navigation.

    Args:
        request: HTTP request from authenticated tenant user
        link_id: UUID of the payment link to display

    Returns:
        HttpResponse: Detailed link panel template with link, payments,
                     and related information

    Raises:
        404: If payment link not found or not owned by tenant
    """
    tenant = request.tenant

    link = get_object_or_404(PaymentLink, id=link_id, tenant=tenant)

    # Get notifications for this link
    from core.models import Notification
    link_notifications = Notification.objects.filter(
        tenant=tenant,
        payment_link_id=str(link.id)
    )

    # Calculate notification statistics
    sent_notifications = link_notifications.filter(status='sent')
    delivered_count = sum(1 for n in sent_notifications if n.email_delivered)
    opened_count = sum(1 for n in sent_notifications if n.email_opened)
    total_sent = sent_notifications.count()

    # Calculate rates
    delivery_rate = (delivered_count / total_sent * 100) if total_sent > 0 else 0
    open_rate = (opened_count / total_sent * 100) if total_sent > 0 else 0

    context = {
        'link': link,
        'tenant': tenant,
        'payments': link.payments.all().order_by('-created_at'),
        'notifications': {
            'sent': sent_notifications.order_by('-created_at'),
            'pending': link_notifications.filter(status='pending'),
            'delivered_count': delivered_count,
            'opened_count': opened_count,
            'delivery_rate': delivery_rate,
            'open_rate': open_rate,
        }
    }

    return render(request, 'shared/link_detail_panel.html', context)


@login_required
@tenant_required()
@require_http_methods(["POST"])
@ratelimit(key='user', rate='15/h', method='POST')
def duplicate(request: HttpRequest) -> JsonResponse:
    """
    Duplicate an existing payment link with new token and expiry.

    Creates a copy of an existing payment link with identical details but
    fresh token, extended expiry, and "(Copia)" suffix. Useful for recurring
    payment scenarios or template-based link creation. Includes audit logging.

    Args:
        request: HTTP POST request with JSON body containing:
                - link_id: UUID of the payment link to duplicate

    Returns:
        JsonResponse: Success with new link_id and token, or error details

    Raises:
        429: If rate limit exceeded (15 requests/hour)
        404: If original payment link not found
        500: If duplication fails
    """
    tenant = request.tenant

    try:
        data = json.loads(request.body)
        original_link = get_object_or_404(PaymentLink, id=data['link_id'], tenant=tenant)

        # ✅ Parámetros personalizados desde modal
        custom_title = data.get('title', f"{original_link.title} (Copia)")
        validity_days = int(data.get('validity_days', 3))
        copy_notifications = data.get('copy_notifications', True)
        keep_customer_data = data.get('keep_customer_data', True)

        # Validar validity_days
        if validity_days not in [1, 3, 7, 30]:
            validity_days = 3  # Default

        # Validar título
        if not custom_title or len(custom_title) < 3:
            custom_title = f"{original_link.title} (Copia)"
        if len(custom_title) > 255:
            custom_title = custom_title[:255]

        # Generate new token
        import secrets
        new_token = secrets.token_urlsafe(16)

        # New expiry
        new_expires = timezone.now() + timedelta(days=validity_days)

        # ✅ Create duplicate con configuración completa
        new_link = PaymentLink.objects.create(
            tenant=tenant,
            token=new_token,
            title=custom_title,
            description=original_link.description,
            amount=original_link.amount,
            customer_name=original_link.customer_name if keep_customer_data else None,
            customer_email=original_link.customer_email if keep_customer_data else None,
            customer_rfc=original_link.customer_rfc if keep_customer_data else None,
            requires_invoice=original_link.requires_invoice,
            expires_at=new_expires,
            # ✅ Copiar configuración de notificaciones
            notify_on_create=original_link.notify_on_create if copy_notifications else False,
            send_reminders=original_link.send_reminders if copy_notifications else False,
            reminder_hours_before=original_link.reminder_hours_before if copy_notifications else 24,
            notify_on_expiry=original_link.notify_on_expiry if copy_notifications else False,
            notifications_enabled=original_link.notifications_enabled if copy_notifications else False,
        )

        # Log audit action
        AuditLogger.log_action(
            request=request,
            action='duplicate',
            entity_type='PaymentLink',
            entity_id=new_link.id,
            entity_name=new_link.title,
            notes=f'Duplicated from {original_link.title} (validity: {validity_days}d, notifications: {copy_notifications})',
            tenant=tenant
        )

        # ✅ Retornar datos completos para success modal
        return JsonResponse({
            'success': True,
            'link_id': str(new_link.id),
            'token': new_link.token,
            'title': new_link.title,
            'amount': float(new_link.amount),
            'expires_at': new_link.expires_at.strftime('%d/%m/%Y %H:%M'),
            'public_url': request.build_absolute_uri(new_link.public_url)
        })

    except Exception as e:
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
@require_http_methods(["POST"])
@ratelimit(key='user', rate='20/h', method='POST')
def cancel(request: HttpRequest) -> JsonResponse:
    """
    Cancel an active payment link to prevent further payments.

    Changes payment link status to 'cancelled' to prevent new payments
    while preserving existing payment history. Includes business logic
    validation and comprehensive audit logging for compliance.

    Args:
        request: HTTP POST request with JSON body containing:
                - link_id: UUID of the payment link to cancel

    Returns:
        JsonResponse: Success confirmation or error with validation message

    Raises:
        429: If rate limit exceeded (20 requests/hour)
        400: If link is not active or cannot be cancelled
        404: If payment link not found
        500: If cancellation fails
    """
    tenant = request.tenant

    try:
        data = json.loads(request.body)
        link = get_object_or_404(PaymentLink, id=data['link_id'], tenant=tenant)

        # ✅ VALIDACIÓN 1: Solo links activos
        if link.status != 'active':
            return ErrorResponseBuilder.build_error(
                message='Solo se pueden cancelar links activos',
                code='validation_error',
                status=400
            )

        # ✅ VALIDACIÓN 2: Verificar pagos pendientes
        from payments.models import Payment
        pending_payments = Payment.objects.filter(
            payment_link=link,
            status='pending'
        )
        pending_count = pending_payments.count()

        if pending_count > 0:
            return ErrorResponseBuilder.build_error(
                message=f'Este link tiene {pending_count} pago(s) en proceso. Espera a que finalice(n) antes de cancelar.',
                code='payment_in_progress',
                status=400
            )

        # ✅ VALIDACIÓN 3: Verificar pagos aprobados (doble check de seguridad)
        approved_payments = Payment.objects.filter(
            payment_link=link,
            status='approved'
        )
        if approved_payments.exists():
            # El link debería estar 'paid', no 'active' - corregir
            link.status = 'paid'
            link.save()
            return ErrorResponseBuilder.build_error(
                message='Este link ya tiene pagos aprobados. No se puede cancelar.',
                code='already_paid',
                status=400
            )

        # Obtener parámetros del modal
        cancellation_reason = data.get('cancellation_reason', 'not_specified')
        notify_customer = data.get('notify_customer', False)

        # ✅ Cambiar status y guardar metadata
        link.status = 'cancelled'
        link.cancelled_at = timezone.now()
        link.cancelled_by = request.user
        link.cancellation_reason = cancellation_reason
        link.save()

        # ✅ Notificar al cliente si se solicitó
        if notify_customer and link.customer_email:
            from core.notifications import notification_service
            try:
                notification_service.send_link_cancelled(
                    payment_link=link,
                    cancellation_reason=cancellation_reason
                )
                logger.info(f'Cancellation notification sent to {link.customer_email}')
            except Exception as email_error:
                logger.error(f'Failed to send cancellation email: {email_error}')
                # No fallar la cancelación si falla el email

        # Audit log con razón y metadata
        AuditLogger.log_action(
            request=request,
            action='cancel',
            entity_type='PaymentLink',
            entity_id=link.id,
            entity_name=link.title,
            notes=f'Link cancelled. Reason: {cancellation_reason}. Customer notified: {notify_customer}',
            tenant=tenant
        )

        logger.info(f"Link {link.id} cancelled by {request.user.email}. Reason: {cancellation_reason}")

        return JsonResponse({'success': True})

    except Exception as e:
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
def edit_data(request: HttpRequest, link_id: str) -> JsonResponse:
    """
    Retrieve payment link data for editing interface.

    Provides current payment link details formatted for edit forms,
    enabling users to modify link properties while maintaining data
    integrity and business rules.

    Args:
        request: HTTP GET request from authenticated tenant user
        link_id: UUID of the payment link to retrieve for editing

    Returns:
        JsonResponse: Link data object with all editable fields
                     formatted for form population

    Raises:
        404: If payment link not found or not owned by tenant
        500: If data retrieval fails
    """
    tenant = request.tenant

    try:
        link = get_object_or_404(PaymentLink, id=link_id, tenant=tenant)

        data = {
            'success': True,
            'link': {
                'id': str(link.id),
                'token': link.token,  # ✅ Agregar token
                'title': link.title,
                'description': link.description,
                'amount': float(link.amount),
                'customer_name': link.customer_name,
                'customer_email': link.customer_email,
                'requires_invoice': link.requires_invoice,
                'status': link.status,  # ✅ Agregar status
                'expires_at': link.expires_at.isoformat(),
                'created_at': link.created_at.isoformat(),  # ✅ Agregar created_at
            }
        }

        return JsonResponse(data)

    except Exception as e:
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
@require_http_methods(["POST"])
@ratelimit(key='user', rate='30/h', method='POST')
def edit(request: HttpRequest) -> JsonResponse:
    """
    Edit an existing payment link with comprehensive validation.

    Updates payment link properties including title, description, amount,
    customer information, and expiry settings. Includes business rule
    validation, audit logging with before/after values, and maintains
    data integrity.

    Args:
        request: HTTP POST request with JSON body containing:
                - link_id: UUID of the payment link to edit
                - title: Updated link title
                - description: Updated description (optional)
                - amount: Updated payment amount
                - customer_name: Updated customer name (optional)
                - customer_email: Updated customer email (optional)
                - requires_invoice: Updated invoice requirement (optional)
                - expires_days: Updated expiry in days (optional)

    Returns:
        JsonResponse: Success confirmation or error with validation details

    Raises:
        429: If rate limit exceeded (30 requests/hour)
        400: If link is not active or validation fails
        404: If payment link not found
        500: If update fails
    """
    tenant = request.tenant

    try:
        data = json.loads(request.body)
        link = get_object_or_404(PaymentLink, id=data['link_id'], tenant=tenant)

        # Only allow editing active links
        if link.status != 'active':
            return ErrorResponseBuilder.build_error(
                message='Solo se pueden editar links activos',
                code='validation_error',
                status=400
            )

        # ========================================
        # VALIDACIONES BACKEND (same as create_link)
        # ========================================

        # Título
        title = data.get('title', '').strip()
        if not title:
            return ErrorResponseBuilder.build_error(
                message='Título es requerido',
                code='validation_error',
                status=400
            )
        if len(title) < 3:
            return ErrorResponseBuilder.build_error(
                message='Título debe tener al menos 3 caracteres',
                code='validation_error',
                status=400
            )
        if len(title) > 255:
            return ErrorResponseBuilder.build_error(
                message='Título no puede exceder 255 caracteres',
                code='validation_error',
                status=400
            )

        # Monto - NO editable (mantener valor actual)
        # Ignorar cualquier valor enviado del frontend
        amount = link.amount  # Mantener monto original

        # Descripción
        description = data.get('description', '').strip()
        if len(description) > 500:
            return ErrorResponseBuilder.build_error(
                message='Descripción no puede exceder 500 caracteres',
                code='validation_error',
                status=400
            )

        # Email del cliente
        customer_email = data.get('customer_email', '').strip().lower()
        if customer_email:
            import re
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', customer_email):
                return ErrorResponseBuilder.build_error(
                    message='Formato de email inválido',
                    code='validation_error',
                    status=400
                )
            if len(customer_email) > 254:
                return ErrorResponseBuilder.build_error(
                    message='Email no puede exceder 254 caracteres',
                    code='validation_error',
                    status=400
                )

        # Nombre del cliente
        customer_name = data.get('customer_name', '').strip()
        if len(customer_name) > 255:
            return ErrorResponseBuilder.build_error(
                message='Nombre no puede exceder 255 caracteres',
                code='validation_error',
                status=400
            )

        # Store old values for audit
        old_values = {
            'title': link.title,
            'description': link.description,
            'amount': float(link.amount),
            'customer_name': link.customer_name,
            'customer_email': link.customer_email,
            'requires_invoice': link.requires_invoice,
            'expires_at': link.expires_at.isoformat()
        }

        # Update ONLY editable fields
        link.title = title
        link.description = description
        link.customer_name = customer_name
        link.customer_email = customer_email

        # NO editar: amount, requires_invoice, expires_at
        # Estos campos se mantienen con sus valores originales

        link.save()

        # Log audit action
        new_values = {
            'title': link.title,
            'description': link.description,
            'amount': float(link.amount),
            'customer_name': link.customer_name,
            'customer_email': link.customer_email,
            'requires_invoice': link.requires_invoice,
            'expires_at': link.expires_at.isoformat()
        }

        AuditLogger.log_action(
            request=request,
            action='update',
            entity_type='PaymentLink',
            entity_id=link.id,
            entity_name=link.title,
            old_values=old_values,
            new_values=new_values,
            notes=f'Link updated by user',
            tenant=tenant
        )

        return JsonResponse({'success': True})

    except Exception as e:
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
@require_http_methods(["POST"])
@ratelimit(key='user', rate='10/h', method='POST')
def send_reminder(request: HttpRequest) -> JsonResponse:
    """
    Send payment reminder notification to customer.

    Sends email reminder for active payment links to improve collection
    rates and customer engagement. Includes business validation, notification
    service integration, and audit logging for compliance tracking.

    Args:
        request: HTTP POST request with JSON body containing:
                - link_id: UUID of the payment link for reminder

    Returns:
        JsonResponse: Success confirmation or error with specific failure reason

    Raises:
        429: If rate limit exceeded (10 requests/hour)
        400: If link is not active or missing customer email
        404: If payment link not found
        500: If reminder sending fails
    """
    tenant = request.tenant

    try:
        data = json.loads(request.body)
        link = get_object_or_404(PaymentLink, id=data['link_id'], tenant=tenant)

        if link.status != 'active':
            return ErrorResponseBuilder.build_error(
                message='Solo se pueden enviar recordatorios a links activos',
                code='validation_error',
                status=400
            )

        if not link.customer_email:
            return ErrorResponseBuilder.build_error(
                message='No hay email del cliente',
                code='validation_error',
                status=400
            )

        # Send reminder
        from core.notifications import notification_service
        result = notification_service.send_payment_reminder(link)

        if result['success']:
            # Log audit action
            AuditLogger.log_action(
                request=request,
                action='send_reminder',
                entity_type='PaymentLink',
                entity_id=link.id,
                entity_name=link.title,
                notes=f'Manual reminder sent to {link.customer_email}',
                tenant=tenant
            )
            return JsonResponse({'success': True})
        else:
            return ErrorResponseBuilder.build_error(
                message=result.get('error', 'Error enviando recordatorio'),
                code='notification_error',
                status=500
            )

    except Exception as e:
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
@ratelimit(key='user', rate='10/h', method='GET')
def export_links(request: HttpRequest, format: str) -> HttpResponse:
    """Export payment links to CSV."""
    tenant = request.tenant

    if format not in ['csv', 'xlsx']:
        return HttpResponse('Invalid format', status=400)

    links_qs = PaymentLink.objects.filter(tenant=tenant).prefetch_related('payments')

    status_filter = request.GET.get('status')
    if status_filter:
        links_qs = links_qs.filter(status=status_filter)

    links = links_qs.order_by('-created_at')[:1000]

    if format == 'csv':
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Título', 'Monto', 'Cliente', 'Email', 'Estado', 'Creado', 'Expira', 'Token'])

        for link in links:
            writer.writerow([
                link.title,
                float(link.amount),
                link.customer_name,
                link.customer_email,
                link.get_status_display(),
                link.created_at.strftime('%Y-%m-%d %H:%M'),
                link.expires_at.strftime('%Y-%m-%d %H:%M'),
                link.token
            ])

        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="links_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response

    return HttpResponse('Excel coming soon', status=501)
