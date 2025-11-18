from __future__ import annotations

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.urls import reverse
from django_ratelimit.decorators import ratelimit
from django.db import transaction
from django.views.decorators.csrf import csrf_protect
import json
import logging
import uuid
import secrets

logger = logging.getLogger(__name__)

from core.models import Tenant, TenantUser
from core.exceptions import ErrorResponseBuilder
from payments.services import MercadoPagoService
from .forms import TenantIdentityForm
from .utils import generate_unique_slug
from core.validators import RFCValidator
from accounts.decorators import tenant_required
from .decorators import onboarding_required
from django.utils.translation import gettext as _
from typing import Any


def get_user_tenant_or_error(user: Any, error_message: str = "No se encontró tu empresa") -> tuple[Any, Any]:
    """Helper function to get user's tenant with consistent error handling.

    Returns:
        tuple: (tenant_user, tenant) if found, (None, error_response) if not found
    """
    tenant_user = TenantUser.objects.filter(email=user.email, is_owner=True).first()

    if not tenant_user:
        return None, ErrorResponseBuilder.build_error(
            message=error_message,
            code='tenant_not_found',
            status=403
        )

    return tenant_user, tenant_user.tenant


@login_required
def onboarding_start(request: HttpRequest) -> HttpResponse:
    """
    Intelligent onboarding flow router for user setup progression.

    Determines the appropriate onboarding step based on user progress
    and redirects to the correct step. Handles completed onboarding
    by redirecting to dashboard. Central entry point for onboarding flow.

    Args:
        request: HTTP request from authenticated user

    Returns:
        HttpResponse: Redirect to appropriate onboarding step or dashboard
                     - Step 1: Business identity and tenant creation
                     - Step 2: MercadoPago OAuth integration
                     - Step 3: CSD certificate upload
                     - Step 4: Subscription and trial activation
                     - Dashboard: If onboarding completed

    Raises:
        Redirect: Always redirects, never renders template
    """
    user = request.user

    if user.onboarding_completed:
        return redirect('dashboard:index')

    # Determine current step
    if user.onboarding_step == 1:
        return redirect('onboarding:step1')
    elif user.onboarding_step == 2:
        return redirect('onboarding:step2')
    elif user.onboarding_step == 3:
        return redirect('onboarding:step3')
    elif user.onboarding_step == 4:
        return redirect('onboarding:step4')

    return redirect('onboarding:step1')


def is_ajax(request: HttpRequest) -> bool:
    """Verificar si es request AJAX."""
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
@onboarding_required
def onboarding_step1(request: HttpRequest) -> HttpResponse:
    """
    Step 1: Business identity setup and tenant creation.

    Handles the critical first step of onboarding where users define their
    business identity, create tenant records, and establish the foundation
    for invoice generation. Supports both new tenant creation and editing
    existing tenant information.

    AJAX Support:
    - If X-Requested-With: XMLHttpRequest → Returns JSON
    - If normal request → Returns HTML template

    Args:
        request: HTTP request from authenticated user
                POST: Form data with business information:
                     - name: Business display name
                     - business_name: Legal business name
                     - rfc: Mexican tax identifier (RFC)
                     - email: Business email
                     - phone: Business phone
                     - address: Business address
                     - fiscal_regime: Tax regime code
                     - postal_code: Business postal code

    Returns:
        HttpResponse: Step 1 template with form or redirect to step 2
                     JsonResponse: If AJAX request
                     - GET: Renders form (pre-filled if tenant exists)
                     - POST: Validates, saves, and redirects to step 2

    Raises:
        ValidationError: If form data is invalid
        IntegrityError: If RFC already exists
    """
    user = request.user

    # BUG FIX #4: Validate user.email before processing
    if not user.email or '@' not in user.email:
        messages.error(request, 'Tu email no es válido. Por favor actualízalo en tu perfil.')
        logger.error(f"User {user.id} has invalid email: {user.email}")
        return redirect('accounts:account')

    # Allow returning to previous steps for editing

    if request.method == 'POST':
        form = TenantIdentityForm(request.POST, user=user)

        if form.is_valid():
            # Check if user already has a tenant (allow editing)
            tenant_user = TenantUser.objects.filter(email=user.email, is_owner=True).first()

            if tenant_user:
                # Update existing tenant
                tenant = tenant_user.tenant
                tenant.name = form.cleaned_data['name']
                tenant.business_name = form.cleaned_data['business_name']
                tenant.rfc = form.cleaned_data['rfc']
                tenant.email = user.email  # Siempre usar email del usuario
                tenant.phone = form.cleaned_data.get('phone', '')
                tenant.fiscal_regime = form.cleaned_data['fiscal_regime']

                # Address fields (structured)
                tenant.codigo_postal = form.cleaned_data['codigo_postal']
                tenant.colonia = form.cleaned_data['colonia']
                tenant.municipio = form.cleaned_data['municipio']
                tenant.estado = form.cleaned_data['estado']
                tenant.calle = form.cleaned_data['calle']
                tenant.numero_exterior = form.cleaned_data['numero_exterior']
                tenant.numero_interior = form.cleaned_data.get('numero_interior', '')

                tenant.slug = generate_unique_slug(tenant.name)
                tenant.save()

                success_msg = f'Datos de "{tenant.name}" actualizados.'
                messages.success(request, success_msg)
                logger.info(f"Tenant {tenant.id} updated in onboarding step 1")

            else:
                # Create new tenant
                tenant = Tenant.objects.create(
                    name=form.cleaned_data['name'],
                    business_name=form.cleaned_data['business_name'],
                    rfc=form.cleaned_data['rfc'],
                    email=user.email,  # ✅ Siempre usar email del usuario (readonly)
                    phone=form.cleaned_data.get('phone', ''),
                    fiscal_regime=form.cleaned_data['fiscal_regime'],
                    # Address fields
                    codigo_postal=form.cleaned_data['codigo_postal'],
                    colonia=form.cleaned_data['colonia'],
                    municipio=form.cleaned_data['municipio'],
                    estado=form.cleaned_data['estado'],
                    calle=form.cleaned_data['calle'],
                    numero_exterior=form.cleaned_data['numero_exterior'],
                    numero_interior=form.cleaned_data.get('numero_interior', ''),
                    slug=generate_unique_slug(form.cleaned_data['name'])
                )

                # Create TenantUser relationship
                TenantUser.objects.create(
                    tenant=tenant,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_owner=True,
                    role='owner',
                    can_create_links=True,
                    can_manage_settings=True,
                    can_view_analytics=True
                )

                success_msg = f'¡Excelente! Tu empresa "{tenant.name}" ha sido creada.'
                messages.success(request, success_msg)
                logger.info(f"New tenant {tenant.id} created in onboarding step 1")

            # Update user onboarding step
            if user.onboarding_step < 2:
                user.onboarding_step = 2
                user.save()

            # AJAX response
            if is_ajax(request):
                return JsonResponse({
                    'success': True,
                    'redirect_url': '/incorporacion/paso2/',  # 🇪🇸 Migrado
                    'message': success_msg
                })

            return redirect('onboarding:step2')

        else:
            # Form invalid
            if is_ajax(request):
                # Convertir errores a dict
                errors = {}
                for field, error_list in form.errors.items():
                    errors[field] = [str(e) for e in error_list]

                error_msg = 'Por favor corrige los errores en el formulario'
                if form.non_field_errors():
                    error_msg = form.non_field_errors()[0]

                return JsonResponse({
                    'success': False,
                    'errors': errors,
                    'error': error_msg
                }, status=400)

    else:
        # Pre-fill with existing tenant data if user has one
        tenant_user = TenantUser.objects.filter(email=user.email, is_owner=True).first()

        if tenant_user:
            # Pre-fill with existing tenant data for editing
            tenant = tenant_user.tenant
            initial_data = {
                'name': tenant.name,
                'business_name': tenant.business_name,
                'rfc': tenant.rfc,
                'email': tenant.email,
                'phone': tenant.phone,
                'fiscal_regime': tenant.fiscal_regime,
                # Address fields (structured)
                'codigo_postal': tenant.codigo_postal,
                'colonia': tenant.colonia,
                'municipio': tenant.municipio,
                'estado': tenant.estado,
                'calle': tenant.calle,
                'numero_exterior': tenant.numero_exterior,
                'numero_interior': tenant.numero_interior,
            }
        else:
            # Pre-fill with user data for new tenant
            initial_data = {}  # Email prellenado desde template

        form = TenantIdentityForm(initial=initial_data, user=user)

    context = {
        'form': form,
        'step': 1,
        'total_steps': 4,
        'step_title': 'Identidad de tu Empresa',
        'step_description': 'Cuéntanos sobre tu negocio para comenzar a facturar',
    }

    return render(request, 'onboarding/step1.html', context)


@tenant_required(require_owner=True)
@onboarding_required
def onboarding_step2(request: HttpRequest) -> HttpResponse:
    """
    Step 2: MercadoPago OAuth integration for payment processing.

    Handles the critical payment gateway integration using OAuth 2.0 flow.
    Manages both OAuth URL generation for authorization and callback
    processing for token exchange. Essential for payment processing
    capabilities.

    Args:
        request: HTTP request from authenticated tenant owner
                GET with 'code' parameter: OAuth callback processing
                GET without 'code': Initial OAuth setup page

    Returns:
        HttpResponse: Step 2 template with OAuth URL or redirect to step 3
                     - Initial visit: Renders OAuth connection interface
                     - OAuth callback: Processes authorization and redirects
                     - Error cases: Returns to step 2 with error messages

    Raises:
        SecurityError: If OAuth state parameter doesn't match tenant ID
        IntegrationError: If token exchange fails
        ConfigurationError: If MercadoPago credentials not configured
    """
    user = request.user
    tenant = request.tenant
    tenant_user = request.tenant_user

    # Allow access if user is on step 2 or higher (can edit previous steps)

    # Check if already connected
    mp_service = MercadoPagoService(tenant)
    mp_connected = mp_service.integration and mp_service.integration.is_valid


    # Handle OAuth callback
    if 'code' in request.GET:
        code = request.GET.get('code')
        state = request.GET.get('state')

        # Debug the callback parameters
        logger.info(f"OAuth callback - code: {code[:20]}..., state: {state}, tenant_id: {tenant.id}")

        # BUG FIX #1: Verify state with session-stored random token for security
        stored_state = request.session.get('oauth_state')
        stored_tenant_id = request.session.get('oauth_tenant_id')

        if not stored_state or state != stored_state:
            messages.error(request, 'Hubo un problema de seguridad. Por favor intenta conectar tu cuenta de nuevo.')
            logger.warning(f"OAuth state mismatch for tenant {tenant.id}: received={state}, stored={stored_state}")
            return redirect('onboarding:step2')

        if stored_tenant_id != str(tenant.id):
            messages.error(request, 'Hubo un problema de seguridad. Por favor intenta conectar tu cuenta de nuevo.')
            logger.warning(f"OAuth tenant mismatch: session={stored_tenant_id}, current={tenant.id}")
            return redirect('onboarding:step2')

        # Clear session state after validation
        request.session.pop('oauth_state', None)
        request.session.pop('oauth_tenant_id', None)

        try:
            # Exchange code for token
            redirect_uri = request.build_absolute_uri(reverse('onboarding:step2'))
            logger.info(f"Token exchange - redirect_uri: {redirect_uri}")

            result = mp_service.exchange_code_for_token(code, redirect_uri)

            if result['success']:
                # Update user onboarding step
                user.onboarding_step = 3
                user.save()

                messages.success(request, '¡Mercado Pago conectado exitosamente!')
                return redirect('onboarding:step3')
            else:
                messages.error(request, 'No pudimos conectar tu cuenta de Mercado Pago. Por favor intenta de nuevo.')
                return redirect('onboarding:step2')

        except Exception as e:
            logger.error(f"OAuth callback error for tenant {tenant.id}: {str(e)}")
            # In development, show actual error
            if settings.DEBUG:
                messages.error(request, 'Hubo un problema conectando con Mercado Pago. Por favor intenta de nuevo.')
            else:
                messages.error(request, 'No pudimos procesar la autorización. Por favor intenta conectar de nuevo.')
            return redirect('onboarding:step2')

    # Generate OAuth URL for production
    redirect_uri = request.build_absolute_uri(reverse('onboarding:step2'))

    try:
        # BUG FIX #1: Generate cryptographically secure state parameter
        state = secrets.token_urlsafe(32)
        request.session['oauth_state'] = state
        request.session['oauth_tenant_id'] = str(tenant.id)

        oauth_url = mp_service.get_oauth_url(redirect_uri, state)
    except ValueError:
        messages.error(request, 'Hay un problema de configuración. Por favor contacta al administrador.')
        oauth_url = None

    context = {
        'step': 2,
        'total_steps': 4,
        'step_title': 'Conectar Mercado Pago',
        'step_description': 'Conecta tu cuenta de Mercado Pago para recibir pagos',
        'tenant': tenant,
        'oauth_url': oauth_url,
        'mp_app_id_configured': bool(settings.MERCADOPAGO_APP_ID),
        'mp_connected': mp_connected,
    }

    return render(request, 'onboarding/step2.html', context)


@tenant_required(require_owner=True)
@onboarding_required
def onboarding_step3(request: HttpRequest) -> HttpResponse:
    """
    Step 3: Digital certificate (CSD) upload for CFDI invoice compliance.

    Renders the interface for uploading Mexican tax authority digital
    certificates required for CFDI invoice generation. Integrates with
    secure file upload system and certificate validation services.

    Args:
        request: HTTP request from authenticated tenant owner

    Returns:
        HttpResponse: Step 3 template with:
                     - CSD upload interface
                     - Certificate validation components
                     - Upload session identifier
                     - Progress indicators

    Raises:
        403: If user is not tenant owner
    """
    user = request.user
    tenant = request.tenant
    tenant_user = request.tenant_user

    # Allow access if user is on step 3 or higher

    # BUG FIX #24: Generate and store upload_session in session for validation
    upload_session = str(uuid.uuid4())
    request.session['csd_upload_session'] = upload_session
    request.session['csd_upload_session_created'] = timezone.now().isoformat()

    context = {
        'step': 3,
        'total_steps': 4,
        'step_title': 'Certificado Digital (CSD)',
        'step_description': 'Sube tu certificado de sello digital para facturar',
        'tenant': tenant,
        'upload_session': upload_session,
    }

    return render(request, 'onboarding/step3.html', context)


@tenant_required(require_owner=True)
@onboarding_required
def onboarding_step4(request: HttpRequest) -> HttpResponse:
    """
    Step 4: Trial activation and subscription management.

    Final onboarding step for activating trial access or setting up
    paid subscriptions. Provides users with immediate access to the
    platform while establishing billing relationships.

    Args:
        request: HTTP request from authenticated tenant owner

    Returns:
        HttpResponse: Step 4 template with:
                     - Trial activation options
                     - Subscription plan information
                     - Payment processing interface
                     - Access activation controls

    Raises:
        403: If user is not tenant owner
    """
    user = request.user
    tenant = request.tenant
    tenant_user = request.tenant_user

    context = {
        'step': 4,
        'total_steps': 4,
        'step_title': 'Activar tu Acceso',
        'step_description': 'Activa tu trial gratuito para comenzar a facturar',
        'tenant': tenant,
    }

    return render(request, 'onboarding/step4.html', context)


@login_required
def subscription_success(request: HttpRequest) -> HttpResponse:
    """Subscription payment success callback"""
    payment_id = request.GET.get('payment_id')

    if payment_id:
        # Process webhook manually for immediate activation
        from webhooks.views import process_subscription_webhook
        try:
            # Get payment info and activate subscription
            webhook_data = {"data": {"id": payment_id}, "type": "payment"}
            process_subscription_webhook(payment_id, webhook_data)

            messages.success(request, '¡Suscripción activada exitosamente!')
        except Exception as e:
            logger.error(f"Error processing subscription success: {str(e)}")
            messages.info(request, 'Pago recibido. La activación puede tomar unos minutos.')

    return redirect('dashboard:index')


@login_required
def subscription_failure(request: HttpRequest) -> HttpResponse:
    """Subscription payment failure callback"""
    messages.error(request, 'El pago no pudo ser procesado. Intenta de nuevo.')
    return redirect('onboarding:step4')


@login_required
def subscription_pending(request: HttpRequest) -> HttpResponse:
    """Subscription payment pending callback"""
    messages.info(request, 'Tu pago está siendo procesado. Te notificaremos cuando se confirme.')
    return redirect('onboarding:step4')


@login_required
@require_http_methods(["POST"])
@ratelimit(key='user', rate='5/h', method='POST')
@csrf_protect
def start_trial(request: HttpRequest) -> JsonResponse:
    """
    Activate 30-day trial subscription for immediate platform access.

    Creates trial subscription through billing system, marks user onboarding
    as completed, and provides immediate access to all platform features.
    Critical for user conversion and platform adoption.

    Args:
        request: HTTP POST request from authenticated user with valid tenant

    Returns:
        JsonResponse: Trial activation result with:
                     - success: Boolean activation status
                     - trial_ends_at: ISO format trial expiration date
                     - error: Error message if activation fails

    Raises:
        429: If rate limit exceeded (5 requests/hour)
        400: If trial already activated or tenant validation fails
        403: If user lacks tenant owner access
        500: If trial creation fails
    """
    try:
        from datetime import timedelta

        tenant_user, result = get_user_tenant_or_error(request.user)
        if not tenant_user:
            return result  # Return the error response

        tenant = result  # When successful, result is the tenant

        # Validar que completó step 1 (identidad fiscal)
        if not tenant.rfc or not tenant.business_name or not tenant.codigo_postal:
            return ErrorResponseBuilder.build_error(
                message='Completa primero la identidad de tu empresa (Step 1)',
                code='step1_incomplete',
                status=400
            )

        # BUG FIX #2 + #23: Start trial with atomic transaction and proper completion timing
        from billing.models import Subscription

        # BUG FIX #24: Check if MP or CSD are configured (warning only)
        has_mp = bool(tenant.mercadopago_user_id)
        has_csd = tenant.csdcertificate_set.exists()

        if not has_mp and not has_csd:
            logger.warning(f"Trial activated without MP or CSD for tenant {tenant.id}")

        with transaction.atomic():
            # Use select_for_update to lock the row and prevent race conditions
            try:
                subscription = Subscription.objects.select_for_update().get(tenant=tenant)
                # Subscription already exists
                return ErrorResponseBuilder.build_error(
                    message='Trial ya fue activado anteriormente',
                    code='trial_already_activated',
                    status=400
                )
            except Subscription.DoesNotExist:
                # Create new subscription
                subscription = Subscription.objects.create(
                    tenant=tenant,
                    trial_ends_at=timezone.now() + timedelta(days=settings.TRIAL_DAYS)
                )

                # BUG FIX #23: Prepare response data BEFORE marking onboarding as completed
                # This ensures that if JsonResponse construction fails, user isn't left in inconsistent state
                response_data = {
                    'success': True,
                    'trial_ends_at': subscription.trial_ends_at.isoformat(),
                    'warnings': []
                }

                # BUG FIX #24: Add warning if trial activated without MP or CSD
                if not has_mp and not has_csd:
                    response_data['warnings'].append('No conectaste Mercado Pago ni subiste tu CSD. Completa estos pasos desde Configuración para poder cobrar y facturar.')
                elif not has_mp:
                    response_data['warnings'].append('No conectaste Mercado Pago. Conéctalo desde Configuración para poder crear links de cobro.')
                elif not has_csd:
                    response_data['warnings'].append('No subiste tu CSD. Súbelo desde Configuración para poder emitir facturas.')

                # Mark user onboarding as completed ONLY after response is prepared
                request.user.onboarding_completed = True
                request.user.save()

                logger.info(f"Trial started for tenant {tenant.name} via new billing system (MP:{has_mp}, CSD:{has_csd})")

                return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error starting trial: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message='Error interno del servidor',
            code='server_error',
            status=500
        )


# @login_required
# @require_http_methods(["POST"])
# def create_subscription(request):
#     """DISABLED - Create subscription payment preference with cards only"""
#     return ErrorResponseBuilder.build_error(
#         message='Suscripciones de pago temporalmente deshabilitadas',
#         code='feature_disabled',
#         status=403
#     )


@login_required
@require_http_methods(["POST"])
@csrf_protect
def disconnect_mercado_pago(request: HttpRequest) -> JsonResponse:
    """
    Disconnect MercadoPago integration and reset onboarding progress.

    Safely removes MercadoPago OAuth integration while preserving tenant
    data and resetting user to step 2 for re-integration. Includes
    comprehensive cleanup of tokens and integration status.

    Args:
        request: HTTP POST request from authenticated tenant owner

    Returns:
        JsonResponse: Disconnection result with:
                     - success: Boolean operation status
                     - warning: Warning message if active links exist
                     - error: Error message if disconnection fails

    Raises:
        400: If no active MercadoPago integration found
        403: If user lacks tenant owner access
        500: If disconnection process fails
    """
    try:
        from payments.models import MercadoPagoIntegration, PaymentLink

        tenant_user, result = get_user_tenant_or_error(request.user)
        if not tenant_user:
            return result  # Return the error response

        tenant = result  # When successful, result is the tenant

        # Check for active payment links
        active_links = PaymentLink.objects.filter(
            tenant=tenant,
            status='active'
        )
        active_links_count = active_links.count()

        # Get MP integration
        integration = MercadoPagoIntegration.objects.filter(
            tenant=tenant,
            is_active=True
        ).first()

        if integration:
            # BUG FIX #59: Revoke token at MercadoPago before disconnecting
            mp_service = MercadoPagoService(tenant)
            mp_service.revoke_token(integration.access_token)

            # BUG FIX #60: Cancel active payment links that will stop working
            if active_links_count > 0:
                from django.db.models import F
                active_links.update(
                    status='cancelled',
                    metadata=F('metadata')  # Preserve existing metadata
                )
                logger.info(f"Cancelled {active_links_count} active payment links for tenant {tenant.name}")

            # Mark integration as inactive
            integration.is_active = False
            integration.save()

            # Clear tenant MP data
            tenant.mercadopago_user_id = ''
            tenant.mercadopago_access_token = ''
            tenant.mercadopago_refresh_token = ''
            tenant.save()

            # Reset user onboarding step to 2
            request.user.onboarding_step = 2
            request.user.save()

            logger.info(f"MP integration disconnected for tenant {tenant.name}")

            response = {'success': True}

            # Add warning if payment links were cancelled
            if active_links_count > 0:
                response['warning'] = f'Se {"cancelaron" if active_links_count > 1 else "canceló"} {active_links_count} link{"s" if active_links_count > 1 else ""} de pago que {"estaban" if active_links_count > 1 else "estaba"} activo{"s" if active_links_count > 1 else ""}'
                response['active_links_count'] = active_links_count

            return JsonResponse(response)
        else:
            return ErrorResponseBuilder.build_error(
                message='No hay conexión activa de Mercado Pago',
                code='integration_not_found',
                status=400
            )

    except Exception as e:
        logger.error(f"Error disconnecting MP: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message='Error interno del servidor',
            code='server_error',
            status=500
        )


@login_required
@require_http_methods(["POST"])
@ratelimit(key='user', rate='30/h', method='POST')
@csrf_protect
def validate_rfc(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint for real-time RFC validation and uniqueness checking.

    Provides immediate feedback during onboarding form completion using
    centralized RFC validation utilities. Ensures Mexican tax identifier
    compliance and prevents duplicate registrations.

    Args:
        request: HTTP POST request with JSON body:
                - rfc: Mexican tax identifier string to validate

    Returns:
        JsonResponse: Validation result with:
                     - valid: Boolean validation status
                     - message: Validation message for user feedback

    Raises:
        429: If rate limit exceeded (30 requests/hour)
        400: If RFC format is invalid or already exists
    """
    try:
        data = json.loads(request.body)
        rfc = data.get('rfc', '').strip().upper()

        # Use centralized validator for format validation
        is_valid, error_message = RFCValidator.validate(rfc)
        if not is_valid:
            return JsonResponse({'valid': False, 'message': error_message})  # Keep format for frontend compatibility

        # BUG FIX #58: Exclude user's own tenant from uniqueness check when editing
        exclude_tenant = None
        tenant_user = TenantUser.objects.filter(email=request.user.email, is_owner=True).first()
        if tenant_user:
            exclude_tenant = tenant_user.tenant

        # Check if RFC already exists using centralized validator
        if not RFCValidator.check_uniqueness(rfc, exclude_tenant):
            return JsonResponse({'valid': False, 'message': _('Este RFC ya está registrado')})

        return JsonResponse({'valid': True, 'message': _('RFC válido')})

    except Exception:
        return JsonResponse({'valid': False, 'message': _('Error al validar RFC')})


@login_required
@require_http_methods(["POST"])
@ratelimit(key='user', rate='30/h', method='POST')
@csrf_protect
def validate_business_name(request: HttpRequest) -> JsonResponse:
    """
    AJAX endpoint for business name validation with slug generation.

    Validates business name input and generates URL-friendly slug suggestions
    for tenant identification. Provides real-time feedback during onboarding
    form completion with immediate slug preview.

    Args:
        request: HTTP POST request with JSON body:
                - business_name: Legal business name string to validate

    Returns:
        JsonResponse: Validation result with:
                     - valid: Boolean validation status
                     - suggested_slug: Generated URL-friendly identifier
                     - message: Validation message for user feedback

    Raises:
        429: If rate limit exceeded (30 requests/hour)
        400: If business name is empty or invalid
    """
    try:
        data = json.loads(request.body)
        business_name = data.get('business_name', '').strip()

        if not business_name:
            return JsonResponse({'valid': False, 'message': _('Razón social es requerida')})

        # Generate suggested slug
        suggested_slug = generate_unique_slug(business_name)

        return JsonResponse({
            'valid': True,
            'suggested_slug': suggested_slug,
            'message': _('Razón social válida')
        })

    except Exception:
        return JsonResponse({'valid': False, 'message': 'Error al validar razón social'})


@tenant_required(require_owner=True)
def onboarding_success(request: HttpRequest) -> HttpResponse:
    """
    Onboarding completion celebration and next steps page.

    Renders success page after user completes all onboarding steps,
    providing confirmation of successful setup and guidance for
    initial platform usage. Accessible only to users who have
    completed onboarding.

    Args:
        request: HTTP request from authenticated tenant owner

    Returns:
        HttpResponse: Success template with:
                     - Completion confirmation
                     - Next steps guidance
                     - Platform feature highlights
                     - Quick action buttons

    Raises:
        Redirect: To onboarding start if not yet completed
        403: If user is not tenant owner
    """
    user = request.user
    tenant = request.tenant

    if not user.onboarding_completed:
        return redirect('onboarding:start')

    context = {
        'user': user,
        'tenant': tenant,
    }

    return render(request, 'onboarding/success.html', context)