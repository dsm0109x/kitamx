"""
Dashboard views - Command Center (Action-Oriented)

PHILOSOPHY:
- NO analytics/charts (eso va en /reports/)
- Focus on ACTIONS and TASKS
- Show what requires attention TODAY
- Quick access to common workflows
"""
from __future__ import annotations
from typing import Dict, List, Any
from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q, Count
from django.core.cache import cache
from django.conf import settings

from core.models import Tenant
from accounts.decorators import tenant_required
from payments.models import PaymentLink, Payment
from invoicing.models import Invoice, CSDCertificate
from billing.models import Subscription
from core.cache import KitaRedisCache

import logging
logger = logging.getLogger(__name__)


@login_required
@tenant_required()
def dashboard_view(request: HttpRequest) -> HttpResponse:
    """
    Command Center Dashboard - Action-oriented workspace.

    Shows:
    - Pending tasks that require attention
    - Quick action buttons
    - Recent activity stream
    - Health snapshot (simple KPIs only)
    - Notifications and alerts

    Does NOT show:
    - Analytics charts (→ /reports/)
    - Detailed metrics (→ /reports/)
    - Historical data (→ /reports/)
    """
    user = request.user
    tenant = request.tenant

    # Check onboarding
    if not user.onboarding_completed:
        return redirect('onboarding:start')

    # Try cache first (5 min TTL for dashboard data)
    cache_key = KitaRedisCache.generate_standard_key(
        'dashboard',      # module
        str(tenant.id),   # tenant_id
        'workspace'       # key_type
    )
    context = cache.get(cache_key)

    if context is None:
        context = build_command_center_context(tenant, user)
        cache.set(cache_key, context, 300)  # 5 minutes

    # Always refresh user data (not cached)
    context.update({
        'user': user,
        'tenant': tenant,
        'page_title': 'Dashboard'
    })

    return render(request, 'dashboard/command_center.html', context)


def build_command_center_context(tenant: Tenant, user: Any) -> Dict[str, Any]:
    """
    Build action-oriented dashboard context.

    Returns:
        Dict with:
        - pending_tasks: Things that need attention today
        - quick_stats: Simple KPIs (numbers only, no charts)
        - recent_activity: Last 10 events
        - alerts: Critical notifications
        - subscription_info: Current plan status
    """
    today = timezone.now()

    # === PENDING TASKS ===
    pending_tasks = get_pending_tasks(tenant, today)

    # === QUICK STATS (Simple numbers) ===
    quick_stats = {
        'active_links_count': PaymentLink.objects.filter(
            tenant=tenant,
            status='active',
            expires_at__gt=today
        ).count(),

        'pending_invoices_count': Payment.objects.filter(
            tenant=tenant,
            status='approved',
            billing_data_provided=True,
            invoice__isnull=True
        ).count(),

        'payments_today': Payment.objects.filter(
            tenant=tenant,
            status='approved',
            created_at__date=today.date()
        ).count(),

        'customers_count': Payment.objects.filter(
            tenant=tenant
        ).values('payer_email').distinct().count()
    }

    # === RECENT ACTIVITY ===
    recent_activity = get_recent_activity_stream(tenant, limit=10)

    # === ALERTS ===
    alerts = get_critical_alerts(tenant, today)

    # === SUBSCRIPTION INFO ===
    subscription = Subscription.objects.filter(tenant=tenant).first()
    subscription_info = {
        'is_trial': subscription.is_trial if subscription else True,
        'trial_ends_at': subscription.trial_ends_at if subscription else None,
        'days_until_expiry': subscription.days_until_trial_end if subscription else 0,
        'status': subscription.status if subscription else 'trial',
        'next_billing_date': subscription.next_billing_date if subscription else None
    }

    return {
        'pending_tasks': pending_tasks,
        'quick_stats': quick_stats,
        'recent_activity': recent_activity,
        'alerts': alerts,
        'subscription_info': subscription_info
    }


def get_pending_tasks(tenant: Tenant, today: timezone.datetime) -> List[Dict[str, Any]]:
    """
    Get list of tasks that require user attention.

    Returns:
        List of task dictionaries with:
        - type: Task category
        - title: Display title
        - description: Task details
        - count: Number of items
        - action_url: Where to go
        - priority: high|medium|low
    """
    tasks = []

    # CSD Certificate expiring soon (within 30 days)
    csd_cert = CSDCertificate.objects.filter(
        tenant=tenant,
        is_active=True,
        valid_to__lte=today + timedelta(days=30),
        valid_to__gt=today
    ).first()

    if csd_cert:
        days_remaining = (csd_cert.valid_to - today).days
        tasks.append({
            'type': 'csd_expiring',
            'title': f'Certificado CSD vence en {days_remaining} día{"s" if days_remaining > 1 else ""}',
            'description': 'Renueva tu certificado para seguir facturando',
            'count': 1,
            'action_url': '/negocio/',  # 🇪🇸 Migrado
            'priority': 'medium' if days_remaining > 15 else 'high',
            'icon': 'iconoir-key'
        })

    # Subscription expiring soon
    subscription = Subscription.objects.filter(tenant=tenant).first()
    if subscription and subscription.is_trial:
        days_remaining = subscription.days_until_trial_end
        if days_remaining <= 7:
            tasks.append({
                'type': 'trial_expiring',
                'title': f'Trial termina en {days_remaining} día{"s" if days_remaining > 1 else ""}',
                'description': 'Suscríbete para continuar usando Kita',
                'count': 1,
                'action_url': '/suscripcion/',  # 🇪🇸 Migrado
                'priority': 'high' if days_remaining <= 3 else 'medium',
                'icon': 'iconoir-calendar'
            })

    return tasks


def get_recent_activity_stream(tenant: Tenant, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get recent activity timeline (last events across all entities).

    Returns:
        List of activity events with:
        - timestamp: When it happened
        - type: Event type (payment, link_created, invoice, etc)
        - title: Display title
        - description: Event details
        - icon: Icon class
        - url: Link to details
    """
    activities = []

    # Recent payments (last 24h)
    recent_payments = Payment.objects.filter(
        tenant=tenant,
        status='approved',
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).select_related('payment_link').order_by('-created_at')[:5]

    for payment in recent_payments:
        activities.append({
            'timestamp': payment.created_at,
            'type': 'payment',
            'title': f'Pago recibido: ${payment.amount} MXN',
            'description': f'Link: {payment.payment_link.title}',
            'icon': 'iconoir-dollar',
            'color': 'success',
            'url': f'/panel/detalle/payment/{payment.id}/',  # 🇪🇸 Migrado
            'detail_type': 'payment',
            'detail_id': str(payment.id)
        })

    # Recent links (last 24h)
    recent_links = PaymentLink.objects.filter(
        tenant=tenant,
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-created_at')[:5]

    for link in recent_links:
        activities.append({
            'timestamp': link.created_at,
            'type': 'link_created',
            'title': f'Enlace creado: {link.title}',
            'description': f'Monto: ${link.amount} MXN',
            'icon': 'iconoir-link',
            'color': 'primary',
            'url': f'/panel/detalle/link/{link.id}/',  # 🇪🇸 Migrado
            'detail_type': 'link',
            'detail_id': str(link.id)
        })

    # Recent invoices (last 24h)
    recent_invoices = Invoice.objects.filter(
        tenant=tenant,
        status='stamped',
        stamped_at__gte=timezone.now() - timedelta(hours=24)
    ).order_by('-stamped_at')[:5]

    for invoice in recent_invoices:
        activities.append({
            'timestamp': invoice.stamped_at,
            'type': 'invoice',
            'title': f'Factura timbrada: {invoice.serie_folio}',
            'description': f'Cliente: {invoice.customer_name}',
            'icon': 'iconoir-page',
            'color': 'info',
            'url': f'/panel/detalle/invoice/{invoice.id}/',  # 🇪🇸 Migrado
            'detail_type': 'invoice',
            'detail_id': str(invoice.id)
        })

    # Sort by timestamp and limit
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    return activities[:limit]


def get_critical_alerts(tenant: Tenant, today: timezone.datetime) -> List[Dict[str, Any]]:
    """
    Get critical alerts that need immediate attention.

    Returns:
        List of alert dictionaries
    """
    alerts = []

    # Failed payments in last 24h
    failed_payments = Payment.objects.filter(
        tenant=tenant,
        status__in=['rejected', 'cancelled'],
        created_at__gte=today - timedelta(hours=24)
    ).count()

    if failed_payments > 0:
        alerts.append({
            'type': 'failed_payments',
            'severity': 'warning',
            'message': f'{failed_payments} pago{"s" if failed_payments > 1 else ""} fallido{"s" if failed_payments > 1 else ""} en las últimas 24h',
            'action_url': '/enlaces/'
        })

    # MercadoPago integration status
    from payments.models import MercadoPagoIntegration
    mp_integration = MercadoPagoIntegration.objects.filter(
        tenant=tenant,
        is_active=True
    ).first()

    if not mp_integration:
        alerts.append({
            'type': 'mp_disconnected',
            'severity': 'danger',
            'message': 'MercadoPago no está conectado',
            'action_url': '/negocio/'  # 🇪🇸 Migrado
        })

    # No active CSD certificate
    active_csd = CSDCertificate.objects.filter(
        tenant=tenant,
        is_active=True,
        valid_to__gt=today
    ).exists()

    if not active_csd:
        alerts.append({
            'type': 'no_csd',
            'severity': 'danger',
            'message': 'No tienes un certificado CSD activo',
            'action_url': '/negocio/'  # 🇪🇸 Migrado
        })

    return alerts


# === AJAX ENDPOINTS (for dynamic updates) ===

@login_required
@tenant_required()
def ajax_pending_tasks(request: HttpRequest) -> JsonResponse:
    """Real-time pending tasks update."""
    tenant = request.tenant
    tasks = get_pending_tasks(tenant, timezone.now())

    return JsonResponse({
        'success': True,
        'tasks': tasks,
        'count': len(tasks)
    })


@login_required
@tenant_required()
def ajax_activity_stream(request: HttpRequest) -> JsonResponse:
    """Real-time activity stream update."""
    tenant = request.tenant
    limit = int(request.GET.get('limit', 10))

    activities = get_recent_activity_stream(tenant, limit)

    # Convert datetime to ISO format for JSON
    for activity in activities:
        activity['timestamp'] = activity['timestamp'].isoformat()

    return JsonResponse({
        'success': True,
        'activities': activities,
        'count': len(activities)
    })


@login_required
@tenant_required()
def ajax_quick_stats(request: HttpRequest) -> JsonResponse:
    """Real-time quick stats update."""
    tenant = request.tenant
    today = timezone.now()

    quick_stats = {
        'active_links_count': PaymentLink.objects.filter(
            tenant=tenant,
            status='active',
            expires_at__gt=today
        ).count(),

        'pending_invoices_count': Payment.objects.filter(
            tenant=tenant,
            status='approved',
            billing_data_provided=True,
            invoice__isnull=True
        ).count(),

        'payments_today': Payment.objects.filter(
            tenant=tenant,
            status='approved',
            created_at__date=today.date()
        ).count()
    }

    return JsonResponse({
        'success': True,
        'stats': quick_stats
    })


# === LEGACY ENDPOINTS (kept for compatibility) ===
# These are used by other parts of the app (modals, detail views, etc)

from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.shortcuts import get_object_or_404
from core.security import SecureIPDetector
from core.exceptions import ErrorResponseBuilder
from core.notifications import notification_service
import json
import secrets


@login_required
@tenant_required()
def create_link_form(request: HttpRequest) -> HttpResponse:
    """
    Load the payment link creation form interface.

    Renders the modal form component for creating new payment links directly
    from the dashboard. Used in AJAX workflows for seamless user experience.
    """
    return render(request, 'dashboard/forms/create_link.html', {
        'tenant': request.tenant
    })


@login_required
@tenant_required()
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='100/h', method='POST')
@transaction.atomic
def create_link(request: HttpRequest) -> JsonResponse:
    """
    Create a new payment link with comprehensive business logic.

    Handles the core business function of creating payment links with automatic
    token generation, expiry calculation, customer notifications, and audit logging.
    Rate limited to prevent abuse and wrapped in transaction for data consistency.
    """
    tenant = request.tenant

    try:
        data = json.loads(request.body)

        # ========================================
        # VALIDACIONES BACKEND
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

        # Monto
        try:
            amount = float(data.get('amount', 0))
        except (ValueError, TypeError):
            return ErrorResponseBuilder.build_error(
                message='Monto inválido',
                code='validation_error',
                status=400
            )

        if amount < 1:
            return ErrorResponseBuilder.build_error(
                message='Monto mínimo: $1 MXN',
                code='validation_error',
                status=400
            )
        if amount > 999999:
            return ErrorResponseBuilder.build_error(
                message='Monto máximo: $999,999 MXN',
                code='validation_error',
                status=400
            )

        # Descripción (opcional pero con límite)
        description = data.get('description', '').strip()
        if len(description) > 500:
            return ErrorResponseBuilder.build_error(
                message='Descripción no puede exceder 500 caracteres',
                code='validation_error',
                status=400
            )

        # Email del cliente (opcional pero validar formato)
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

        # Nombre del cliente (opcional)
        customer_name = data.get('customer_name', '').strip()
        if len(customer_name) > 255:
            return ErrorResponseBuilder.build_error(
                message='Nombre no puede exceder 255 caracteres',
                code='validation_error',
                status=400
            )

        # Vigencia (whitelist)
        expires_days = data.get('expires_days', 3)
        try:
            expires_days = int(expires_days)
        except (ValueError, TypeError):
            expires_days = 3

        if expires_days not in settings.LINK_EXPIRY_OPTIONS:
            return ErrorResponseBuilder.build_error(
                message=f'Vigencia inválida. Opciones permitidas: {settings.LINK_EXPIRY_OPTIONS}',
                code='validation_error',
                status=400
            )

        # Generate unique token
        token = secrets.token_urlsafe(16)

        # Calculate expiry
        expires_at = timezone.now() + timedelta(days=expires_days)

        # ========================================
        # NOTIFICATION CONFIGURATION (Email only)
        # ========================================
        notifications_config = {
            'notifications_enabled': data.get('notifications_enabled', True),
            'notify_on_create': data.get('notify_on_create', True),
            'send_reminders': data.get('send_reminders', True),
            'reminder_hours_before': int(data.get('reminder_hours_before', 24)),
            'notify_on_expiry': data.get('notify_on_expiry', False),
        }

        # Validar reminder_hours_before
        valid_hours = [6, 12, 24, 48, 72]
        if notifications_config['reminder_hours_before'] not in valid_hours:
            notifications_config['reminder_hours_before'] = 24

        # Validar lógica: reminder_hours debe ser < expiry_hours
        if notifications_config['send_reminders']:
            expiry_hours = expires_days * 24
            reminder_hours = notifications_config['reminder_hours_before']
            hours_after_creation = expiry_hours - reminder_hours

            # Si recordatorio >= vigencia, no tiene sentido
            if reminder_hours >= expiry_hours or hours_after_creation < 6:
                # Desactivar recordatorios automáticamente
                notifications_config['send_reminders'] = False
                logger.warning(
                    f"Reminder ({reminder_hours}h) not compatible with expiry ({expiry_hours}h). "
                    f"Reminders disabled for link."
                )

            # Si recordatorio es muy cercano, advertir en logs
            elif hours_after_creation < 12:
                logger.info(
                    f"Reminder will be sent {hours_after_creation}h after creation "
                    f"(expiry {expires_days}d, reminder {reminder_hours}h before)"
                )

        # Create payment link with notification configuration
        payment_link = PaymentLink.objects.create(
            tenant=tenant,
            token=token,
            title=title,
            description=description,
            amount=amount,
            customer_name=customer_name,
            customer_email=customer_email,
            customer_rfc=data.get('customer_rfc', ''),
            requires_invoice=data.get('requires_invoice', False),
            expires_at=expires_at,
            **notifications_config  # Unpack notification settings
        )

        # Send notification if enabled and customer email provided
        if (payment_link.notifications_enabled and
            payment_link.notify_on_create and
            payment_link.customer_email):

            try:
                notification_service.send_payment_link_created(
                    payment_link,
                    recipient_phone='',
                    recipient_email=payment_link.customer_email
                )
                # Increment notification counter
                payment_link.notification_count += 1
                payment_link.save(update_fields=['notification_count'])
                logger.info(f"Link creation notification sent for link {payment_link.id}")
            except Exception as e:
                logger.error(f"Failed to send link creation notification: {e}")

        # Log audit action
        from core.models import AuditLog
        try:
            AuditLog.objects.create(
                tenant=tenant,
                user_email=request.user.email,
                user_name=request.user.get_full_name() or request.user.email,
                action='create',
                entity_type='PaymentLink',
                entity_id=payment_link.id,
                entity_name=payment_link.title,
                ip_address=SecureIPDetector.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                new_values={
                    'title': payment_link.title,
                    'amount': float(payment_link.amount),
                    'expires_days': expires_days,
                    'requires_invoice': payment_link.requires_invoice
                },
                notes=f'Payment link created via dashboard'
            )
        except Exception as e:
            logger.error(f"Failed to log audit action: {e}")

        # ✅ Invalidar caché del dashboard para reflejar cambios inmediatamente
        cache_key = KitaRedisCache.generate_standard_key(
            'dashboard',
            str(tenant.id),
            'workspace'
        )
        cache.delete(cache_key)
        logger.info(f"Dashboard cache invalidated for tenant {tenant.id}")

        return JsonResponse({
            'success': True,
            'link_id': str(payment_link.id),
            'token': payment_link.token,
            'url': request.build_absolute_uri(payment_link.public_url),  # ✅ Sin doble slash
            'title': payment_link.title,
            'amount': float(payment_link.amount),
            'customer_email': payment_link.customer_email or None,
            'customer_name': payment_link.customer_name or None
        })

    except Exception as e:
        logger.error(f"Error creating payment link: {e}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='link_creation_error',
            status=500
        )


@login_required
@tenant_required()
def detail_view(request: HttpRequest, detail_type: str, detail_id: str) -> HttpResponse:
    """
    Load detailed information panel for business entities.

    Provides comprehensive detail views for payment links, payments, and invoices
    in sidebar panels. Includes related entity information and optimized queries
    for performance.
    """
    tenant = request.tenant

    from core.query_optimizations import QueryOptimizer

    templates = {
        'link': 'shared/link_detail_panel.html',
        'payment': 'dashboard/details/payment.html',
        'invoice': 'invoicing/invoice_detail.html'  # ✅ Use existing template
    }

    template = templates.get(detail_type)
    if not template:
        return ErrorResponseBuilder.build_error(
            message='Detail type not found',
            code='not_found',
            status=404
        )

    try:
        if detail_type == 'link':
            obj = get_object_or_404(PaymentLink, id=detail_id, tenant=tenant)
        elif detail_type == 'payment':
            obj = get_object_or_404(Payment, id=detail_id, tenant=tenant)
        elif detail_type == 'invoice':
            obj = get_object_or_404(Invoice, id=detail_id, tenant=tenant)

        context = {
            'tenant': tenant
        }

        if detail_type == 'link':
            context['link'] = obj

            # Get payments for this link with optimization
            payments = QueryOptimizer.optimize_payments(
                Payment.objects.filter(payment_link=obj, tenant=tenant)
            ).order_by('-created_at')
            context['payments'] = payments

            # === OPTIMIZED METRICS - Single aggregate query ===
            from django.db.models import Count, Q, Aggregate
            from payments.models import PaymentLinkView, PaymentLinkClick

            # Views y clicks en una sola query (optimizado)
            view_stats = PaymentLinkView.objects.filter(payment_link=obj).aggregate(
                total_views=Count('id')
            )

            click_stats = PaymentLinkClick.objects.filter(payment_link=obj).aggregate(
                total_clicks=Count('id')
            )

            # Payment stats en una sola query
            payment_stats = obj.payments.aggregate(
                total_attempts=Count('id'),
                successful=Count('id', filter=Q(status='approved'))
            )

            views = view_stats['total_views'] or 0
            clicks = click_stats['total_clicks'] or 0
            attempts = payment_stats['total_attempts'] or 0
            successful = payment_stats['successful'] or 0

            # Safe division con manejo de cero
            def safe_percent(numerator, denominator):
                return int((numerator / denominator * 100)) if denominator > 0 else 0

            def safe_percent_decimal(numerator, denominator):
                return round((numerator / denominator * 100), 1) if denominator > 0 else 0

            context['funnel_data'] = {
                'views': views,
                'clicks': clicks,
                'clicks_percent': safe_percent(clicks, views),
                'attempts': attempts,
                'attempts_percent': safe_percent(attempts, views),
                'successful': successful,
                'success_percent': safe_percent(successful, views),
                'conversion_rate': safe_percent_decimal(successful, views)
            }

            # Calculate engagement metrics
            abandoned = clicks - successful if clicks > successful else 0
            context['engagement'] = {
                'clicks': clicks,
                'clicks_percent': safe_percent(clicks, views),
                'paid': successful,
                'paid_percent': safe_percent(successful, views),
                'abandoned': abandoned,
                'abandoned_percent': safe_percent(abandoned, views),
                'only_viewed': views - clicks if views > clicks else 0,
                'only_viewed_percent': safe_percent(views - clicks, views)
            }

            # Calculate time remaining
            from datetime import timedelta
            time_left = obj.expires_at - timezone.now()
            context['time_left_hours'] = time_left.total_seconds() / 3600

            # ========================================
            # NOTIFICATION TRACKING DATA
            # ========================================
            from core.models import Notification, EmailEvent

            # Get all notifications for this link
            notifications_sent = Notification.objects.filter(
                tenant=tenant,
                payment_link_id=detail_id,
                channel='email'
            ).prefetch_related('email_events').order_by('-sent_at')

            # Calculate email analytics
            total_sent = notifications_sent.count()
            delivered_count = sum(1 for n in notifications_sent if n.email_delivered)
            opened_count = sum(1 for n in notifications_sent if n.email_opened)
            bounced_count = sum(1 for n in notifications_sent if n.email_bounced)

            # Spam complaints
            spam_count = EmailEvent.objects.filter(
                notification__payment_link_id=detail_id,
                spam_complaint=True
            ).count()

            # Calcular tasas
            delivery_rate = (delivered_count / total_sent * 100) if total_sent > 0 else 0
            open_rate = (opened_count / delivered_count * 100) if delivered_count > 0 else 0
            bounce_rate = (bounced_count / total_sent * 100) if total_sent > 0 else 0
            spam_rate = (spam_count / total_sent * 100) if total_sent > 0 else 0

            # Tiempo promedio hasta abrir
            open_times = [
                n.get_email_event().time_to_open
                for n in notifications_sent
                if n.get_email_event() and n.get_email_event().time_to_open
            ]
            avg_time_to_open = None
            if open_times:
                avg_seconds = sum(open_times) / len(open_times)
                if avg_seconds < 60:
                    avg_time_to_open = f"{int(avg_seconds)} segundos"
                elif avg_seconds < 3600:
                    avg_time_to_open = f"{int(avg_seconds / 60)} minutos"
                else:
                    avg_time_to_open = f"{int(avg_seconds / 3600)} horas"

            # Notificaciones programadas (pendientes)
            # SOLO para links activos - si ya está pagado/expirado/cancelado no tiene sentido
            now = timezone.now()
            pending_notifications = []

            if obj.status == 'active' and obj.send_reminders and not obj.reminder_sent:
                reminder_time = obj.expires_at - timedelta(hours=obj.reminder_hours_before)
                if reminder_time > now:
                    pending_notifications.append({
                        'type': 'payment_reminder',
                        'type_display': 'Recordatorio de Pago',
                        'scheduled_for': reminder_time
                    })

            context['notifications'] = {
                'sent': notifications_sent,
                'delivered_count': delivered_count,
                'opened_count': opened_count,
                'delivery_rate': delivery_rate,
                'open_rate': open_rate,
                'bounce_rate': bounce_rate,
                'spam_rate': spam_rate,
                'avg_time_to_open': avg_time_to_open,
                'pending': pending_notifications
            }

        elif detail_type == 'payment':
            context['object'] = obj
        elif detail_type == 'invoice':
            context['invoice'] = obj  # ✅ Use 'invoice' key (required by template)

        return render(request, template, context)

    except Exception as e:
        logger.error(f"Error loading detail view: {e}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='not_found',
            status=404
        )


@login_required
@tenant_required()
@require_http_methods(["GET"])
def recent_customers(request: HttpRequest) -> JsonResponse:
    """
    Get recent customers for autocomplete in payment link form.

    Returns the last 10 unique customers (by name/email) who have
    received payment links from this tenant, useful for datalist autocomplete.
    """
    tenant = request.tenant

    try:
        from payments.models import PaymentLink

        # Get last 10 unique customers
        recent_links = PaymentLink.objects.filter(
            tenant=tenant
        ).exclude(
            customer_name=''
        ).exclude(
            customer_email=''
        ).order_by('-created_at').values(
            'customer_name', 'customer_email'
        ).distinct()[:10]

        customers = []
        seen_names = set()
        seen_emails = set()

        for link in recent_links:
            name = link.get('customer_name', '').strip()
            email = link.get('customer_email', '').strip()

            # Only add if not already seen
            if name and name not in seen_names:
                seen_names.add(name)
                customers.append({
                    'name': name,
                    'email': email if email and email not in seen_emails else None
                })
                if email:
                    seen_emails.add(email)

        return JsonResponse({
            'success': True,
            'customers': customers
        })

    except Exception as e:
        logger.error(f"Error fetching recent customers: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@tenant_required()
@require_http_methods(["GET"])
def rate_limit_info(request: HttpRequest) -> JsonResponse:
    """
    Get rate limit information for payment link creation.

    Returns how many links the user has created in the last hour
    compared to the rate limit of 30/hour.
    """
    tenant = request.tenant
    user = request.user

    try:
        from payments.models import PaymentLink
        from datetime import timedelta

        # Get links created in the last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)

        links_count = PaymentLink.objects.filter(
            tenant=tenant,
            created_at__gte=one_hour_ago
        ).count()

        # Rate limit is 100/hour (from @ratelimit decorator)
        limit = 100
        remaining = max(0, limit - links_count)

        return JsonResponse({
            'success': True,
            'links_created': links_count,
            'limit': limit,
            'remaining': remaining,
            'can_create': remaining > 0
        })

    except Exception as e:
        logger.error(f"Error fetching rate limit info: {e}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@tenant_required()
@require_http_methods(["GET"])
def search_api(request: HttpRequest) -> JsonResponse:
    """
    Unified search API for Command Palette.

    Searches across:
    - Payment Links (by title, customer name, customer email)
    - Invoices (by folio, customer name, RFC)

    Optimizations:
    - PostgreSQL ILIKE with indexes
    - LIMIT 10 per model (max 20 results total)
    - Select only necessary fields
    - Redis cache (60s TTL)

    Query params:
        ?q=<search_query>

    Returns:
        JSON with success, links[], invoices[]
    """
    tenant = request.tenant
    query = request.GET.get('q', '').strip()

    if not query:
        return JsonResponse({
            'success': False,
            'error': 'Query parameter "q" is required'
        }, status=400)

    # Minimum query length
    if len(query) < 2:
        return JsonResponse({
            'success': True,
            'links': [],
            'invoices': []
        })

    # Check cache first
    cache_key = f'search:{tenant.id}:{query.lower()}'
    cached_result = cache.get(cache_key)

    if cached_result:
        logger.info(f"[Search] Cache hit for query: {query}")
        return JsonResponse(cached_result)

    try:
        # ========================================
        # Search Payment Links
        # ========================================
        link_filters = (
            Q(title__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(customer_email__icontains=query)
        )

        links = PaymentLink.objects.filter(
            tenant=tenant
        ).filter(link_filters).order_by('-created_at')[:10]

        links_data = [{
            'id': str(link.id),
            'title': link.title,
            'amount': str(link.amount),
            'currency': link.currency,
            'customer_name': link.customer_name or '',
            'customer_email': link.customer_email or '',
            'status': link.status,
            'created_at': link.created_at.isoformat()
        } for link in links]

        # ========================================
        # Search Invoices
        # ========================================
        invoice_filters = (
            Q(folio__icontains=query) |
            Q(serie__icontains=query) |
            Q(customer_name__icontains=query) |
            Q(customer_rfc__icontains=query)
        )

        invoices = Invoice.objects.filter(
            tenant=tenant
        ).filter(invoice_filters).order_by('-created_at')[:10]

        invoices_data = [{
            'id': str(invoice.id),  # Always available (PK)
            'uuid': str(invoice.uuid) if invoice.uuid else '',  # May be null for drafts
            'serie_folio': f"{invoice.serie}-{invoice.folio}" if invoice.serie else invoice.folio,
            'customer_name': invoice.customer_name,
            'customer_rfc': invoice.customer_rfc,
            'total': str(invoice.total),
            'currency': invoice.currency,
            'status': invoice.status,
            'stamped_at': invoice.stamped_at.isoformat() if invoice.stamped_at else None
        } for invoice in invoices]

        result = {
            'success': True,
            'query': query,
            'links': links_data,
            'invoices': invoices_data,
            'total_results': len(links_data) + len(invoices_data)
        }

        # Cache for 60 seconds
        cache.set(cache_key, result, 60)

        logger.info(f"[Search] Query: {query} | Results: {result['total_results']}")

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"[Search] Error: {e}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error en búsqueda'
        }, status=500)


@login_required
@tenant_required()
@require_http_methods(["GET"])
def verify_setup(request: HttpRequest) -> JsonResponse:
    """
    Verify tenant setup configuration.

    Checks:
    - MercadoPago integration
    - CSD certificates

    Returns warnings but doesn't block the flow.
    """
    tenant = request.tenant

    try:
        from payments.models import MercadoPagoIntegration
        from invoicing.models import CSDCertificate

        # Check MercadoPago
        has_mercadopago = MercadoPagoIntegration.objects.filter(
            tenant=tenant,
            is_active=True
        ).exists()

        # Check CSD
        has_csd = CSDCertificate.objects.filter(
            tenant=tenant,
            is_active=True
        ).exists()

        return JsonResponse({
            'success': True,
            'has_mercadopago': has_mercadopago,
            'has_csd': has_csd,
        })

    except Exception as e:
        logger.error(f"Error verifying setup: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Failed to verify setup'
        }, status=500)
