from __future__ import annotations

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from typing import Any, Optional
import json
import logging
import uuid

from .models import PaymentLink, Payment, MercadoPagoIntegration
from .services import MercadoPagoService
from core.validators import RFCValidator, PostalCodeValidator, BusinessNameValidator
from core.security import SecureIPDetector
from core.exceptions import ErrorResponseBuilder
from accounts.validators import TurnstileValidator
from django.core.exceptions import ValidationError as DjangoValidationError

logger = logging.getLogger(__name__)


@ratelimit(key='ip', rate='30/m', method='GET')
def public_payment_link(request: HttpRequest, token: str) -> HttpResponse:
    """Public payment link view with rate limiting"""
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related('tenant'),
        token=token
    )

    # Handle different payment link states
    if payment_link.status == 'paid':
        # Payment completed - show hub with options
        successful_payment = payment_link.payments.filter(status='approved').first()

        context = {
            'payment_link': payment_link,
            'tenant': payment_link.tenant,
            'payment': successful_payment,
            'page_type': 'paid_hub'
        }
        return render(request, 'payments/payment_hub.html', context)

    elif payment_link.status == 'expired':
        # Link expired
        context = {
            'payment_link': payment_link,
            'error_type': 'expired',
            'tenant': payment_link.tenant
        }
        return render(request, 'payments/link_inactive.html', context)

    elif payment_link.status == 'cancelled':
        # Link cancelled
        context = {
            'payment_link': payment_link,
            'error_type': 'cancelled',
            'tenant': payment_link.tenant
        }
        return render(request, 'payments/link_inactive.html', context)

    elif not payment_link.is_active:
        # Other inactive states (used, max uses reached, etc)
        context = {
            'payment_link': payment_link,
            'error_type': 'used',
            'tenant': payment_link.tenant
        }
        return render(request, 'payments/link_inactive.html', context)

    # Track view
    payment_link.track_view(
        ip_address=SecureIPDetector.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        referrer=request.META.get('HTTP_REFERER', '')
    )

    # Get MercadoPago integration
    try:
        mp_integration = MercadoPagoIntegration.objects.get(tenant=payment_link.tenant, is_active=True)
    except MercadoPagoIntegration.DoesNotExist:
        context = {
            'payment_link': payment_link,
            'error_type': 'no_integration',
            'tenant': payment_link.tenant
        }
        return render(request, 'payments/link_error.html', context)

    # Initialize MercadoPago service
    mp_service = MercadoPagoService(payment_link.tenant)

    # Create MercadoPago preference if not exists and get init_point
    init_point = None
    if not payment_link.mp_preference_id:
        try:
            preference_data = mp_service.create_payment_preference(payment_link)
            if preference_data['success']:
                init_point = preference_data['init_point']
                logger.info(f"MP preference created for link {payment_link.token}")
            else:
                raise ValueError("Failed to create preference")
        except Exception as e:
            logger.error(f"Failed to create MP preference for link {payment_link.id}: {str(e)}")
            context = {
                'payment_link': payment_link,
                'error_type': 'mp_error',
                'tenant': payment_link.tenant,
                'error_message': str(e)
            }
            return render(request, 'payments/link_error.html', context)
    else:
        # Get existing preference init_point
        try:
            import requests
            preference_url = f"{settings.MERCADOPAGO_PREFERENCES_URL}/{payment_link.mp_preference_id}"
            headers = {
                "Authorization": f"Bearer {mp_integration.access_token}",
                "Content-Type": "application/json"
            }
            response = requests.get(preference_url, headers=headers, timeout=10)
            if response.status_code == 200:
                preference_data = response.json()
                init_point = preference_data.get('init_point')
            else:
                logger.warning(f"Could not retrieve existing preference, will recreate")
                # Recreate preference
                payment_link.mp_preference_id = ''
                payment_link.save()
                preference_data = mp_service.create_payment_preference(payment_link)
                init_point = preference_data['init_point']
        except Exception as e:
            logger.error(f"Error retrieving existing preference: {e}")
            init_point = None

    context = {
        'payment_link': payment_link,
        'tenant': payment_link.tenant,
        'init_point': init_point,
        'preference_id': payment_link.mp_preference_id,
        'app_base_url': settings.APP_BASE_URL
    }

    return render(request, 'payments/public_link.html', context)


@ratelimit(key='ip', rate='20/m', method='GET')
def payment_success(request: HttpRequest, token: str) -> HttpResponse:
    """
    Payment success page with validation

    Validates:
    1. Payment exists with status='approved'
    2. OR comes from MercadoPago with payment_id
    3. Payment not too old (< 7 days)
    """
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related('tenant'),
        token=token
    )

    # Get payment info from MercadoPago redirect
    payment_id = request.GET.get('payment_id')
    collection_id = request.GET.get('collection_id')
    comes_from_mp = bool(payment_id or collection_id)

    # Get payment from database
    payment = payment_link.payments.filter(status='approved').order_by('-created_at').first()

    # VALIDATION: Prevent direct access without valid context
    if not payment and not comes_from_mp:
        # No payment AND not coming from MP = invalid access
        client_ip = SecureIPDetector.get_client_ip(request)
        logger.warning(
            f"Invalid direct access to success page for token={token} "
            f"from IP={client_ip}"
        )
        return redirect(f'/hola/{token}/')

    # VALIDATION: Check if payment is too old (> 7 days) when not from MP
    if payment and not comes_from_mp:
        from datetime import timedelta
        if payment.created_at < timezone.now() - timedelta(days=7):
            logger.info(f"Old payment access for token={token}, redirecting to hub")
            return redirect(f'/hola/{token}/')

    # Prepare context
    context = {
        'payment_link': payment_link,
        'tenant': payment_link.tenant,
        'payment': payment,
        'payment_id': payment_id,
        'collection_id': collection_id,
        'processing': not payment and comes_from_mp  # Webhook not processed yet
    }

    return render(request, 'payments/success.html', context)


@ratelimit(key='ip', rate='20/m', method='GET')
def payment_failure(request: HttpRequest, token: str) -> HttpResponse:
    """
    Payment failure page with validation

    Validates:
    1. PaymentLink not already paid (status != 'paid')
    2. Payment exists with failed status OR comes from MP
    """
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related('tenant'),
        token=token
    )

    # VALIDATION: Don't show failure if already paid
    if payment_link.status == 'paid':
        logger.info(f"Failure page accessed for paid link {token}, redirecting to hub")
        return redirect(f'/hola/{token}/')

    # Check if comes from MercadoPago
    collection_id = request.GET.get('collection_id')
    comes_from_mp = bool(collection_id)

    # Get failed payment from database
    payment = payment_link.payments.filter(
        status__in=['rejected', 'failed', 'cancelled']
    ).order_by('-created_at').first()

    # VALIDATION: Prevent direct access
    if not payment and not comes_from_mp:
        client_ip = SecureIPDetector.get_client_ip(request)
        logger.warning(
            f"Invalid direct access to failure page for token={token} "
            f"from IP={client_ip}"
        )
        return redirect(f'/hola/{token}/')

    context = {
        'payment_link': payment_link,
        'tenant': payment_link.tenant,
        'payment': payment
    }

    return render(request, 'payments/failure.html', context)


@ratelimit(key='ip', rate='20/m', method='GET')
def payment_pending(request: HttpRequest, token: str) -> HttpResponse:
    """
    Payment pending page with validation

    Validates:
    1. PaymentLink not already paid
    2. Payment exists with pending status OR comes from MP
    3. Payment not too old (< 30 days)
    """
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related('tenant'),
        token=token
    )

    # VALIDATION: Don't show pending if already paid
    if payment_link.status == 'paid':
        logger.info(f"Pending page accessed for paid link {token}, redirecting to hub")
        return redirect(f'/hola/{token}/')

    # Check if comes from MercadoPago
    payment_id = request.GET.get('payment_id')
    comes_from_mp = bool(payment_id)

    # Get pending payment from database
    payment = payment_link.payments.filter(
        status__in=['pending', 'in_process', 'in_mediation']
    ).order_by('-created_at').first()

    # VALIDATION: Prevent direct access
    if not payment and not comes_from_mp:
        client_ip = SecureIPDetector.get_client_ip(request)
        logger.warning(
            f"Invalid direct access to pending page for token={token} "
            f"from IP={client_ip}"
        )
        return redirect(f'/hola/{token}/')

    # VALIDATION: Check if payment too old (> 30 days) when not from MP
    if payment and not comes_from_mp:
        from datetime import timedelta
        if payment.created_at < timezone.now() - timedelta(days=30):
            logger.info(f"Old pending payment for token={token}, redirecting to hub")
            return redirect(f'/hola/{token}/')

    context = {
        'payment_link': payment_link,
        'tenant': payment_link.tenant,
        'payment': payment
    }

    return render(request, 'payments/pending.html', context)


@ratelimit(key='ip', rate='10/m', method=['GET', 'POST'])
def billing_form(request: HttpRequest, token: str) -> HttpResponse:
    """Self-service billing form for customers"""
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related('tenant'),
        token=token
    )

    # Check if payment exists and is successful
    successful_payment = payment_link.payments.filter(status='approved').first()

    if not successful_payment:
        # Redirect back to hub with error message
        return redirect(f'/hola/{token}/?error=no_payment')

    # Check if invoice already generated - redirect to hub
    if successful_payment.invoice:
        return redirect(f'/hola/{token}/?invoice_ready=1')

    # Handle POST request (form submission)
    if request.method == 'POST':
        try:
            # ==========================================
            # VALIDATE TURNSTILE (Anti-bot protection)
            # ==========================================
            turnstile_token = request.POST.get('cf-turnstile-response', '')
            client_ip = SecureIPDetector.get_client_ip(request)

            # Validate Turnstile token
            turnstile_validator = TurnstileValidator()
            try:
                turnstile_validator(turnstile_token, client_ip)
                logger.info(f"Turnstile passed for billing form {token} from IP {client_ip}")
            except DjangoValidationError as e:
                logger.warning(f"Turnstile failed for billing form {token} from IP {client_ip}: {e}")
                context = {
                    'payment_link': payment_link,
                    'tenant': payment_link.tenant,
                    'payment': successful_payment,
                    'error_message': 'Verificación anti-bot falló. Por favor recarga la página e intenta nuevamente.'
                }
                return render(request, 'payments/billing_form.html', context)
            # ==========================================

            # Process the billing form
            invoice = process_billing_form_data(request, successful_payment)

            # Success - redirect back to hub with flash message
            from django.contrib import messages
            messages.success(
                request,
                f'¡Factura generada exitosamente! Recibirás el XML y PDF en {successful_payment.payer_email or successful_payment.customer_email} en unos minutos.'
            )
            return redirect('payments:public_link', token=token)

        except DjangoValidationError as e:
            # Error de validación - mostrar mensaje específico
            logger.warning(f"Validation error in billing form for payment {successful_payment.id}: {e}")
            context = {
                'payment_link': payment_link,
                'tenant': payment_link.tenant,
                'payment': successful_payment,
                'error_message': str(e) if len(str(e)) < 200 else 'Error de validación. Verifica tus datos.'
            }
            return render(request, 'payments/billing_form.html', context)
        except Exception as e:
            # Error inesperado - NO exponer detalles técnicos
            logger.error(f"Unexpected error generating invoice for payment {successful_payment.id}: {e}", exc_info=True)
            context = {
                'payment_link': payment_link,
                'tenant': payment_link.tenant,
                'payment': successful_payment,
                'error_message': 'Error al generar la factura. Por favor intenta nuevamente en unos minutos o contacta a soporte.'
            }
            return render(request, 'payments/billing_form.html', context)

    # GET request - show form
    context = {
        'payment_link': payment_link,
        'tenant': payment_link.tenant,
        'payment': successful_payment
    }

    return render(request, 'payments/billing_form.html', context)


def process_billing_form_data(request: HttpRequest, payment: Any) -> Any:
    """Process billing form data and generate invoice"""
    # Validate billing data using centralized validators
    rfc = request.POST.get('rfc', '').upper().strip()
    business_name = request.POST.get('business_name', '').strip()
    postal_code = request.POST.get('postal_code', '').strip()

    # Validate RFC
    try:
        rfc = RFCValidator.clean(rfc)
    except DjangoValidationError as e:
        raise ValueError('RFC inválido. Debe tener 13 caracteres para personas físicas (Ej: XAXX010101000)')
    except Exception as e:
        logger.error(f"Unexpected RFC validation error: {e}")
        raise ValueError('Error al validar RFC. Verifica el formato.')

    # Validate business name
    try:
        business_name = BusinessNameValidator.clean(business_name)
    except DjangoValidationError as e:
        raise ValueError('Razón social inválida. Verifica que no contenga caracteres especiales.')
    except Exception as e:
        logger.error(f"Unexpected business name validation error: {e}")
        raise ValueError('Error al validar razón social.')

    # Validate postal code
    try:
        postal_code = PostalCodeValidator.clean(postal_code)
    except DjangoValidationError as e:
        raise ValueError('Código postal inválido. Debe tener 5 dígitos.')
    except Exception as e:
        logger.error(f"Unexpected postal code validation error: {e}")
        raise ValueError('Error al validar código postal.')

    billing_data = {
        'rfc': rfc,
        'business_name': business_name,
        'postal_code': postal_code,
        'fiscal_regime': request.POST.get('fiscal_regime', ''),
        'cfdi_use': request.POST.get('cfdi_use', 'G03'),
        'email': request.POST.get('email', '').strip()
    }

    # Basic validation for required fields
    if not billing_data['email']:
        raise ValueError('Email es requerido para enviar la factura')

    if not billing_data['fiscal_regime']:
        raise ValueError('Régimen fiscal es requerido')

    # Generate invoice using CFDI service
    from invoicing.cfdi_service import InvoiceGenerationService

    invoice_service = InvoiceGenerationService(payment.payment_link.tenant)
    invoice = invoice_service.generate_invoice_from_payment(
        payment=payment,
        fiscal_data=billing_data
    )

    # Link payment to invoice
    payment.invoice = invoice
    payment.save()

    return invoice


# Legacy function - kept for compatibility
def process_billing_form(request: HttpRequest, payment: Any) -> Any:
    """Legacy billing form processor"""
    return process_billing_form_data(request, payment)


@ratelimit(key='ip', rate='20/m', method='GET')
def download_invoice(request: HttpRequest, token: str, uuid: str) -> HttpResponse:
    """Download invoice PDF or XML"""
    payment_link = get_object_or_404(
        PaymentLink.objects.select_related('tenant'),
        token=token
    )
    
    # Get the payment and invoice
    payment = payment_link.payments.filter(status='approved').first()
    if not payment or not payment.invoice:
        return ErrorResponseBuilder.build_error(
            message='Factura no encontrada',
            code='invoice_not_found',
            status=404
        )

    invoice = payment.invoice
    file_format = request.GET.get('format', 'pdf').lower()

    # Track download
    payment_link.track_interaction(
        action=f'invoice_download_{file_format}',
        ip_address=SecureIPDetector.get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    if file_format == 'xml':
        # Return XML file
        from django.http import HttpResponse
        response = HttpResponse(invoice.xml_content, content_type='application/xml')
        response['Content-Disposition'] = f'attachment; filename="factura_{invoice.serie_folio}.xml"'
        return response
    else:
        # Return PDF file
        if invoice.pdf_file:
            from django.http import FileResponse
            response = FileResponse(
                invoice.pdf_file.open('rb'),
                content_type='application/pdf'
            )
            response['Content-Disposition'] = f'attachment; filename="factura_{invoice.serie_folio}.pdf"'
            return response
        else:
            return ErrorResponseBuilder.build_error(
                message='PDF no disponible',
                code='file_not_found',
                status=404
            )


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='100/m', method='POST')
def mercadopago_webhook(request: HttpRequest) -> JsonResponse:
    """Handle MercadoPago webhooks.

    This function now delegates to the centralized webhook handler
    to avoid duplication with webhooks/views.py.
    """
    from .webhook_handler import webhook_handler
    return webhook_handler.handle_webhook(request, webhook_type='general')


# Legacy webhook functions have been moved to webhook_handler.py
# Keeping minimal versions for backward compatibility

def _handle_payment_notification(data: dict) -> JsonResponse:
    """Handle payment notifications from MercadoPago (private helper function)"""
    try:
        payment_id = data['data']['id']

        # Idempotency check
        from core.cache import kita_cache
        idempotency_key = f"payment_webhook_{payment_id}"
        if kita_cache.get('global', idempotency_key):
            logger.info(f"Payment {payment_id} already processed")
            return JsonResponse({'status': 'already_processed'})

        # Get payment data from MercadoPago API first to get external_reference
        # Try to find MP integration from any tenant (we don't know which one yet)
        from payments.models import PaymentLink

        mp_data = None
        payment_link = None

        # Strategy: Get payment data from MP to extract external_reference
        # Then lookup PaymentLink directly by ID (external_reference)

        # Try to get payment from MP using first available integration
        # This is suboptimal but necessary without knowing tenant upfront
        first_integration = MercadoPagoIntegration.objects.filter(is_active=True).first()

        if first_integration:
            try:
                mp_data = _get_payment_from_mp_api(payment_id, first_integration.access_token)

                if mp_data and mp_data.get('external_reference'):
                    # Try to find payment link by ID (external_reference)
                    try:
                        payment_link_id = uuid.UUID(mp_data['external_reference'])
                        payment_link = PaymentLink.objects.select_related('tenant').get(id=payment_link_id)

                        # Create payment record
                        payment_obj = _create_payment_from_mp_data(payment_link, mp_data)

                        # Mark cache as processed
                        kita_cache.set('global', idempotency_key, 'processed', 3600)

                        logger.info(f"Payment {payment_id} processed successfully for link {payment_link.token}. Status: {mp_data.get('status')}")

                        return JsonResponse({'status': 'processed'})

                    except (ValueError, PaymentLink.DoesNotExist) as e:
                        logger.error(f"Payment link not found for external_reference {mp_data.get('external_reference')}: {e}")

            except Exception as e:
                logger.error(f"Error getting payment from MP API: {e}")

        logger.warning(f"Payment {payment_id} could not be matched to any payment link")
        return JsonResponse({'status': 'not_matched'})

    except Exception as e:
        logger.error(f"Error handling payment notification: {e}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='payment_notification_error',
            status=400
        )


# This function has been integrated into webhook_handler.py
# Keeping for backward compatibility if called directly
def _create_payment_from_mp_data(payment_link: Any, mp_data: dict) -> Any:
    """Create Payment object from MercadoPago data (deprecated - use webhook_handler) (private helper function)"""
    from decimal import Decimal
    
    # Map MP status to our status
    status_map = {
        'approved': 'approved',
        'authorized': 'approved', 
        'pending': 'pending',
        'in_process': 'processing',
        'in_mediation': 'processing',
        'rejected': 'rejected',
        'cancelled': 'cancelled',
        'refunded': 'refunded',
        'charged_back': 'charged_back'
    }
    
    payment_status = status_map.get(mp_data.get('status'), 'pending')
    
    # Create payment record
    payment = Payment.objects.create(
        tenant=payment_link.tenant,
        payment_link=payment_link,
        mp_payment_id=mp_data['id'],
        mp_preference_id=mp_data.get('preference_id', ''),
        mp_collection_id=mp_data.get('collection_id', ''),
        amount=Decimal(str(mp_data.get('transaction_amount', 0))),
        currency=mp_data.get('currency_id', 'MXN'),
        status=payment_status,
        payment_method=mp_data.get('payment_method_id', ''),
        payment_type=mp_data.get('payment_type_id', ''),
        payer_email=mp_data.get('payer', {}).get('email', ''),
        payer_name=f"{mp_data.get('payer', {}).get('first_name', '')} {mp_data.get('payer', {}).get('last_name', '')}".strip(),
        processed_at=timezone.now() if payment_status == 'approved' else None,
        webhook_data=mp_data
    )
    
    # Update payment link status if payment successful
    if payment_status == 'approved':
        payment_link.status = 'paid'
        payment_link.uses_count += 1
        payment_link.save()
        
        # Send notifications
        try:
            from core.notifications import notification_service
            notification_service.send_payment_received(payment)
        except Exception as e:
            logger.error(f"Failed to send payment notification: {e}")
    
    return payment


def _get_payment_from_mp_api(payment_id: str, access_token: str) -> Optional[dict]:
    """Get payment information from MercadoPago API (private helper function).

    This is a wrapper for backward compatibility.
    Uses the consolidated implementation from MercadoPagoService.
    """
    from .services import MercadoPagoService
    try:
        return MercadoPagoService.get_payment_from_mp_api(payment_id, access_token)
    except ValueError as e:
        logger.error(f"MP API error for payment {payment_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error querying MP API for payment {payment_id}: {str(e)}")
        return None


def _handle_merchant_order_notification(data: dict) -> JsonResponse:
    """Handle merchant order notifications from MercadoPago (deprecated - use webhook_handler) (private helper function)."""
    try:
        order_id = data.get('data', {}).get('id', '')
        logger.info(f"Processing merchant order notification for order {order_id}")
        # TODO: Implement merchant order processing if needed
        return JsonResponse({'status': 'processed'})

    except Exception as e:
        logger.error(f"Error handling merchant order notification: {e}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='merchant_order_error',
            status=400
        )


@require_http_methods(["POST"])
@ratelimit(key='ip', rate='100/m', method='POST')
def track_view(request: HttpRequest) -> JsonResponse:
    """Track payment link view for analytics"""
    # Validar Origin header para seguridad (en lugar de @csrf_exempt)
    origin = request.META.get('HTTP_ORIGIN', '')
    allowed_origins = [settings.APP_BASE_URL, 'http://localhost:8000', 'http://127.0.0.1:8000']

    if origin and origin not in allowed_origins:
        logger.warning(f"Tracking request from unauthorized origin: {origin}")
        return JsonResponse({'error': 'Unauthorized origin'}, status=403)

    try:
        data = json.loads(request.body)
        token = data.get('token')
        action = data.get('action', 'page_view')

        payment_link = get_object_or_404(
            PaymentLink.objects.select_related('tenant'),
            token=token
        )

        payment_link.track_view(
            ip_address=SecureIPDetector.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            referrer=request.META.get('HTTP_REFERER', ''),
            action=action
        )

        return JsonResponse({'status': 'tracked'})

    except Exception as e:
        logger.error(f"Error tracking view: {e}")
        return ErrorResponseBuilder.build_error(
            message='Error tracking view',
            code='tracking_error',
            status=400
        )


@require_http_methods(["POST"])
@ratelimit(key='ip', rate='100/m', method='POST')
def track_interaction(request: HttpRequest) -> JsonResponse:
    """Track payment link interactions for analytics"""
    # Validar Origin header para seguridad (en lugar de @csrf_exempt)
    origin = request.META.get('HTTP_ORIGIN', '')
    allowed_origins = [settings.APP_BASE_URL, 'http://localhost:8000', 'http://127.0.0.1:8000']

    if origin and origin not in allowed_origins:
        logger.warning(f"Tracking interaction from unauthorized origin: {origin}")
        return JsonResponse({'error': 'Unauthorized origin'}, status=403)

    try:
        data = json.loads(request.body)
        token = data.get('token')
        action = data.get('action')

        payment_link = get_object_or_404(
            PaymentLink.objects.select_related('tenant'),
            token=token
        )

        payment_link.track_interaction(
            action=action,
            ip_address=SecureIPDetector.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

        return JsonResponse({'status': 'tracked'})

    except Exception as e:
        logger.error(f"Error tracking interaction: {e}")
        return ErrorResponseBuilder.build_error(
            message='Error tracking interaction',
            code='tracking_error',
            status=400
        )
