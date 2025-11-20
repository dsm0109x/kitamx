"""
Views for billing and subscription management.

Handles subscription activation, cancellation, payments, and usage tracking.
"""
from __future__ import annotations
from typing import Any, Dict
from decimal import Decimal
import json
import logging

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import cache_page
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.core.cache import cache
from django_ratelimit.decorators import ratelimit

from core.models import Notification
from accounts.utils import AuditLogger
from accounts.decorators import tenant_required
from payments.models import PaymentLink
from payments.billing import KitaBillingService
from invoicing.models import Invoice

from .models import Subscription, BillingPayment
from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger(__name__)


class UsageStatsCalculator:
    """Calculate and cache usage statistics for billing."""

    @staticmethod
    def get_cache_key(tenant_id: str, period: str = 'month') -> str:
        """Generate cache key for usage stats."""
        today = timezone.now().date()
        return f"billing:usage:{tenant_id}:{period}:{today}"

    @staticmethod
    def calculate(tenant: Any) -> Dict[str, Any]:
        """
        Calculate usage statistics for current month.

        Args:
            tenant: Tenant instance

        Returns:
            Dictionary with usage statistics
        """
        cache_key = UsageStatsCalculator.get_cache_key(str(tenant.id))

        # Try cache first
        cached_stats = cache.get(cache_key)
        if cached_stats:
            return cached_stats

        # Calculate stats (optimizado - menos queries)
        today = timezone.now().date()
        current_month_start = today.replace(day=1)

        # Agregado en una sola query de PaymentLink
        from django.db.models import Case, When, Value, IntegerField
        link_stats = PaymentLink.objects.filter(
            tenant=tenant,
            created_at__date__gte=current_month_start
        ).aggregate(
            total_created=Count('id'),
            total_revenue=Sum('amount', filter=Q(status='paid'))
        )

        # Resto de stats en queries separadas (diferentes tablas)
        invoices_count = Invoice.objects.filter(
            tenant=tenant,
            created_at__date__gte=current_month_start
        ).count()

        notifications_count = Notification.objects.filter(
            tenant=tenant,
            created_at__date__gte=current_month_start,
            status='sent'
        ).count()

        stats = {
            'links_created': link_stats['total_created'] or 0,
            'invoices_generated': invoices_count,
            'notifications_sent': notifications_count,
            'total_revenue': link_stats['total_revenue'] or Decimal('0'),
            'month': current_month_start.strftime('%B %Y'),
        }

        # Cache for 1 hour
        cache.set(cache_key, stats, 3600)

        return stats


@login_required
@tenant_required(require_owner=True, require_active=False)
def subscription_index(request: HttpRequest) -> HttpResponse:
    """
    Subscription management main page.

    Shows subscription status, payment history, and usage statistics.
    """
    tenant_user = request.tenant_user  # Set by decorator
    tenant = tenant_user.tenant

    # Get or create subscription with optimized query
    subscription, created = Subscription.objects.get_or_create_for_tenant(tenant)

    # Get payment history with prefetch
    payments = (
        subscription.payments
        .select_related('subscription', 'tenant')
        .order_by('-created_at')[:10]
    )

    # Determine which payments can be invoiced
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    for payment in payments:
        # Can invoice if:
        # 1. Payment is completed
        # 2. Payment is from current month
        # 3. Invoice not yet generated
        # 4. Tenant has valid fiscal data
        payment.can_invoice = (
            payment.status == 'completed' and
            payment.created_at >= current_month_start and
            not payment.invoice_generated and
            tenant.rfc and
            tenant.business_name and
            tenant.codigo_postal
        )

    # Calculate cached usage stats
    usage_stats = UsageStatsCalculator.calculate(tenant)

    # Check for warnings
    warnings = []
    if subscription.is_trial and subscription.days_until_trial_end <= 7:
        warnings.append({
            'type': 'trial_ending',
            'message': f'Tu periodo de prueba termina en {subscription.days_until_trial_end} días',
            'action': 'activate'
        })

    if subscription.is_past_due:
        warnings.append({
            'type': 'past_due',
            'message': 'Tu suscripción está vencida. Por favor actualiza tu pago.',
            'action': 'pay_overdue'
        })

    context = {
        'user': request.user,
        'tenant': tenant,
        'tenant_user': tenant_user,
        'subscription': subscription,
        'payments': payments,
        'usage_stats': usage_stats,
        'warnings': warnings,
        'page_title': 'Suscripción',
        'can_cancel': subscription.status in ['active', 'past_due'],
        'can_activate': subscription.status in ['trial', 'cancelled'],
    }

    return render(request, 'billing/index.html', context)


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='5/h', method='POST')
@transaction.atomic
def activate_subscription(request: HttpRequest) -> JsonResponse:
    """
    Activate subscription by creating payment preference.

    Rate limited to prevent abuse.
    """
    tenant = request.tenant_user.tenant

    try:
        subscription = get_object_or_404(Subscription, tenant=tenant)

        if subscription.is_active:
            return JsonResponse({
                'success': False,
                'error': 'La suscripción ya está activa'
            }, status=400)

        # Create billing service
        billing_service = KitaBillingService()
        result = billing_service.create_subscription_preference(tenant)

        if result['success']:
            # Log activation attempt usando core.models.AuditLog directamente
            from core.models import AuditLog
            from core.security import SecureIPDetector

            AuditLog.objects.create(
                tenant=tenant,
                user_email=request.user.email,
                user_name=request.user.get_full_name() or request.user.email,
                action='activate_subscription',
                entity_type='Subscription',
                entity_id=subscription.id,
                entity_name=subscription.plan_name,
                ip_address=SecureIPDetector.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                new_values={
                    'plan': subscription.plan_name,
                    'price': float(subscription.monthly_price),
                    'preference_id': result.get('preference_id')
                },
                notes='Subscription activation attempt'
            )

            return JsonResponse({
                'success': True,
                'payment_url': result['init_point'],
                'preference_id': result['preference_id']
            })
        else:
            logger.error(f"Failed to create preference for tenant {tenant.id}: {result.get('error')}")
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Error al crear preferencia de pago')
            }, status=500)

    except Exception:
        logger.exception(f"Error activating subscription for tenant {tenant.id}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno al activar suscripción'
        }, status=500)


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='5/d', method='POST')
@transaction.atomic
def cancel_subscription(request: HttpRequest) -> JsonResponse:
    """
    Cancel subscription.

    Rate limited to 5 per day to prevent accidental cancellations.
    """
    tenant = request.tenant_user.tenant

    try:
        data = json.loads(request.body)
        immediate = data.get('immediate', False)
        reason = data.get('reason', 'Usuario solicitó cancelación')

        # Validate and sanitize reason
        if not isinstance(reason, str):
            reason = 'Usuario solicitó cancelación'

        reason = reason.strip()

        if len(reason) > 500:
            reason = reason[:500]

        # Sanitizar para prevenir inyección
        import html
        reason = html.escape(reason)

        subscription = get_object_or_404(Subscription, tenant=tenant)

        if subscription.is_cancelled:
            return JsonResponse({
                'success': False,
                'error': 'La suscripción ya está cancelada'
            }, status=400)

        # Cancel subscription
        subscription.cancel_subscription(reason=reason, immediate=immediate)

        # Log cancellation
        AuditLogger.log_action(
            request=request,
            action='cancel_subscription',
            entity_type='Subscription',
            entity_id=str(subscription.id),
            details={
                'immediate': immediate,
                'reason': reason,
                'plan': subscription.plan_name
            }
        )

        # Invalidate cache
        cache_key = UsageStatsCalculator.get_cache_key(str(tenant.id))
        cache.delete(cache_key)

        return JsonResponse({
            'success': True,
            'message': 'Suscripción cancelada correctamente',
            'immediate': immediate
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Datos inválidos'
        }, status=400)
    except Exception:
        logger.exception(f"Error cancelling subscription for tenant {tenant.id}")
        return JsonResponse({
            'success': False,
            'error': 'Error al cancelar suscripción'
        }, status=500)


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='10/h', method='POST')
@transaction.atomic
def pay_overdue(request: HttpRequest) -> JsonResponse:
    """
    Pay overdue subscription.

    Creates payment preference for past due subscriptions.
    """
    tenant = request.tenant_user.tenant

    try:
        subscription = get_object_or_404(Subscription, tenant=tenant)

        if not subscription.is_past_due:
            return JsonResponse({
                'success': False,
                'error': 'La suscripción no está vencida'
            }, status=400)

        # Create billing service
        billing_service = KitaBillingService()
        result = billing_service.create_subscription_preference(tenant)

        if result['success']:
            # Log payment attempt
            AuditLogger.log_action(
                request=request,
                action='pay_overdue',
                entity_type='Subscription',
                entity_id=str(subscription.id),
                details={
                    'failed_attempts': subscription.failed_payment_attempts,
                    'preference_id': result.get('preference_id')
                }
            )

            return JsonResponse({
                'success': True,
                'payment_url': result['init_point'],
                'preference_id': result['preference_id']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Error al crear preferencia de pago')
            }, status=500)

    except Exception:
        logger.exception(f"Error processing overdue payment for tenant {tenant.id}")
        return JsonResponse({
            'success': False,
            'error': 'Error al procesar pago vencido'
        }, status=500)


@login_required
@tenant_required(require_owner=True)
def payment_detail(request: HttpRequest, payment_id: str) -> HttpResponse:
    """
    Get billing payment details.

    Shows detailed information about a specific payment.
    """
    tenant = request.tenant_user.tenant

    payment = get_object_or_404(
        BillingPayment.objects.select_related('subscription', 'tenant'),
        id=payment_id,
        tenant=tenant
    )

    # Log sensitive data access
    if payment.external_payment_data:
        AuditLogger.log_action(
            request=request,
            action='view_payment_details',
            entity_type='BillingPayment',
            entity_id=str(payment_id),
            notes=f'Viewed payment details for ${payment.amount}'
        )

    context = {
        'payment': payment,
        'tenant': tenant,
        'subscription': payment.subscription,
        'can_retry': payment.can_retry,
        'external_data': json.dumps(payment.external_payment_data, indent=2) if payment.external_payment_data else None,
    }

    return render(request, 'billing/payment_detail.html', context)


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='3/h', method='POST')
@transaction.atomic
def retry_payment(request: HttpRequest, payment_id: str) -> JsonResponse:
    """
    Retry a failed billing payment.

    Rate limited to prevent abuse of payment gateway.
    """
    tenant = request.tenant_user.tenant

    try:
        payment = get_object_or_404(
            BillingPayment.objects.with_subscription(),
            id=payment_id,
            tenant=tenant
        )

        if not payment.can_retry:
            return JsonResponse({
                'success': False,
                'error': f'El pago no puede ser reintentado (intentos: {payment.retry_count}/{payment.max_retries})'
            }, status=400)

        # Create billing service
        billing_service = KitaBillingService()
        result = billing_service.create_subscription_preference(payment.subscription.tenant)

        if result['success']:
            # Update retry count
            payment.retry_count += 1
            payment.save()

            # Log retry attempt
            AuditLogger.log_action(
                request=request,
                action='retry_payment',
                entity_type='BillingPayment',
                entity_id=str(payment_id),
                details={
                    'retry_count': payment.retry_count,
                    'amount': float(payment.amount),
                    'preference_id': result.get('preference_id')
                }
            )

            return JsonResponse({
                'success': True,
                'payment_url': result['init_point'],
                'preference_id': result['preference_id'],
                'retry_count': payment.retry_count,
                'remaining_retries': payment.max_retries - payment.retry_count
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Error al reintentar pago')
            }, status=500)

    except Exception:
        logger.exception(f"Error retrying payment {payment_id} for tenant {tenant.id}")
        return JsonResponse({
            'success': False,
            'error': 'Error al reintentar pago'
        }, status=500)


@login_required
@tenant_required(require_owner=True)
@cache_page(60)  # Cache for 1 minute
def subscription_stats(request: HttpRequest) -> JsonResponse:
    """
    Get subscription statistics via AJAX.

    Cached endpoint for dashboard widgets.
    """
    tenant = request.tenant_user.tenant

    try:
        subscription = Subscription.objects.get(tenant=tenant)

        # Get payment stats
        from django.db.models import Max
        payment_stats = subscription.payments.aggregate(
            total_paid=Sum('amount', filter=Q(status='completed')),
            total_failed=Count('id', filter=Q(status='failed')),
            last_payment=Max('processed_at', filter=Q(status='completed'))
        )

        stats = {
            'status': subscription.status,
            'days_until_trial_end': subscription.days_until_trial_end if subscription.is_trial else None,
            'is_past_due': subscription.is_past_due,
            'failed_attempts': subscription.failed_payment_attempts,
            'total_paid': float(payment_stats['total_paid'] or 0),
            'total_failed': payment_stats['total_failed'],
            'last_payment': payment_stats['last_payment'].isoformat() if payment_stats['last_payment'] else None,
            'can_use_features': subscription.can_use_features,
        }

        return JsonResponse({
            'success': True,
            'stats': stats
        })

    except Subscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No subscription found'
        }, status=404)
    except Exception:
        logger.exception(f"Error getting subscription stats for tenant {tenant.id}")
        return JsonResponse({
            'success': False,
            'error': 'Error al obtener estadísticas'
        }, status=500)

# ========================================
# SUBSCRIPTION PAYMENT CALLBACKS
# ========================================

@login_required
@tenant_required(require_owner=True, require_active=False)
def subscription_payment_success(request: HttpRequest) -> HttpResponse:
    """
    Subscription payment success callback.
    
    Handles successful subscription payments from MercadoPago.
    Works for both onboarding and post-onboarding subscription activations.
    
    No @onboarding_required decorator to allow post-onboarding access.
    """
    payment_id = request.GET.get('payment_id')
    tenant = request.tenant_user.tenant

    if payment_id:
        try:
            # Process payment via webhook handler
            from payments.webhook_handler import webhook_handler
            
            webhook_data = {
                "data": {"id": payment_id}, 
                "type": "payment",
                "action": "payment.updated"
            }
            
            result = webhook_handler._process_subscription_payment(payment_id, webhook_data)
            
            if result.get('success'):
                messages.success(request, '¡Suscripción activada exitosamente!')
                logger.info(f"Subscription payment processed successfully for tenant {tenant.id}")
            else:
                messages.info(request, 'Pago recibido. La activación puede tomar unos minutos.')
                logger.warning(f"Subscription payment processing issue: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"Error processing subscription success callback: {str(e)}", exc_info=True)
            messages.info(request, 'Pago recibido. La activación puede tomar unos minutos.')
    
    return redirect('billing:index')


@login_required
@tenant_required(require_owner=True, require_active=False)
def subscription_payment_failure(request: HttpRequest) -> HttpResponse:
    """
    Subscription payment failure callback.
    
    Handles failed subscription payments from MercadoPago.
    """
    tenant = request.tenant_user.tenant
    
    messages.error(request, 'El pago no pudo ser procesado. Por favor intenta de nuevo.')
    logger.warning(f"Subscription payment failed for tenant {tenant.id}")
    
    return redirect('billing:index')


@login_required
@tenant_required(require_owner=True, require_active=False)
def subscription_payment_pending(request: HttpRequest) -> HttpResponse:
    """
    Subscription payment pending callback.
    
    Handles pending subscription payments (e.g., OXXO, bank transfer).
    """
    tenant = request.tenant_user.tenant
    
    messages.info(request, 'Tu pago está siendo procesado. Te notificaremos cuando se confirme.')
    logger.info(f"Subscription payment pending for tenant {tenant.id}")
    
    return redirect('billing:index')


# ========================================
# SUBSCRIPTION INVOICE GENERATION
# ========================================

@login_required
@tenant_required(require_owner=True, require_active=False)
def invoice_subscription_payment(request: HttpRequest, payment_id: str) -> HttpResponse:
    """
    Invoice subscription payment form.

    Shows form to collect fiscal data and generate CFDI invoice
    for a subscription payment made to Kita.

    Emisor: Kita (configured in settings)
    Receptor: Tenant (form data)
    """
    tenant = request.tenant_user.tenant
    
    # Get payment
    payment = get_object_or_404(
        BillingPayment,
        id=payment_id,
        tenant=tenant
    )
    
    # Validate payment can be invoiced
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    can_invoice = (
        payment.status == 'completed' and
        payment.created_at >= current_month_start and
        not payment.invoice_generated
    )
    
    if not can_invoice:
        messages.error(request, 'Este pago no puede ser facturado en este momento.')
        return redirect('billing:index')
    
    # Handle form submission (POST)
    if request.method == 'POST':
        try:
            # Extract form data
            fiscal_data = {
                'rfc': payment.tenant.rfc,  # From tenant (readonly)
                'business_name': payment.tenant.business_name,  # From tenant (readonly)
                'email': payment.tenant.email,
                'codigo_postal': request.POST.get('codigo_postal'),
                'fiscal_regime': payment.tenant.fiscal_regime,
                'uso_cfdi': request.POST.get('uso_cfdi'),
                'forma_pago': request.POST.get('forma_pago'),
            }

            # Validate required fields
            if not all([fiscal_data['uso_cfdi'], fiscal_data['forma_pago'], fiscal_data['codigo_postal']]):
                messages.error(request, 'Por favor completa todos los campos requeridos.')
                return redirect('billing:invoice_payment', payment_id=payment.id)

            # Generate invoice
            from billing.invoice_service import subscription_invoice_service

            result = subscription_invoice_service.generate_invoice(payment, fiscal_data)

            if result['success']:
                messages.success(
                    request,
                    f'¡Factura generada exitosamente! UUID: {result["uuid"]}'
                )
                logger.info(f"Subscription invoice generated for payment {payment.id}")
                return redirect('billing:index')
            else:
                messages.error(request, f'Error: {result.get("message", "Error generando factura")}')
                logger.error(f"Failed to generate invoice: {result.get('error')}")
                return redirect('billing:invoice_payment', payment_id=payment.id)

        except Exception as e:
            logger.error(f"Error processing invoice form: {e}", exc_info=True)
            messages.error(request, f'Error inesperado: {str(e)}')
            return redirect('billing:invoice_payment', payment_id=payment.id)
    
    # Show form (GET)
    context = {
        'tenant': tenant,
        'payment': payment,
        'page_title': 'Facturar Suscripción',
        # Autocompleted data
        'rfc': tenant.rfc,
        'business_name': tenant.business_name,
        'codigo_postal': tenant.codigo_postal,
        'colonia': tenant.colonia,
        'municipio': tenant.municipio,
        'estado': tenant.estado,
        'calle': tenant.calle,
        'numero_exterior': tenant.numero_exterior,
        'numero_interior': tenant.numero_interior,
        'fiscal_regime': tenant.fiscal_regime,
    }
    
    return render(request, 'billing/invoice_form.html', context)
