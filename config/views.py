from __future__ import annotations
from typing import Any, Dict
from datetime import timedelta
import logging

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.views.decorators.cache import cache_page
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django_ratelimit.decorators import ratelimit
import json

from core.models import Notification
from payments.models import MercadoPagoIntegration
from accounts.decorators import tenant_required
from core.query_optimizations import QueryOptimizer

logger = logging.getLogger(__name__)


@login_required
@tenant_required(require_owner=True)
def settings_index(request: HttpRequest) -> HttpResponse:
    """
    Settings main page - company configuration.

    Shows business info, CSD certificates, and integrations.
    """
    from invoicing.models import CSDCertificate

    tenant_user = request.tenant_user  # Set by decorator
    tenant = tenant_user.tenant

    # Get CSD certificates
    certificates = CSDCertificate.objects.filter(tenant=tenant).order_by('-created_at')

    # Get existing integrations with optimized query
    mp_integrations = MercadoPagoIntegration.objects.filter(tenant=tenant, is_active=True)
    mp_integration = mp_integrations.first()

    # Current settings from environment
    current_settings: Dict[str, Any] = {
        'whatsapp': {
            'configured': bool(settings.WA_TOKEN and settings.WA_PHONE_ID),
            'phone_id': settings.WA_PHONE_ID[:8] + '...' if settings.WA_PHONE_ID else '',
        },
        'email': {
            'configured': bool(settings.EMAIL_HOST_USER),
            'from_email': settings.DEFAULT_FROM_EMAIL,
        },
        'mercadopago': {
            'configured': bool(mp_integration),
            'user_id': mp_integration.user_id if mp_integration else '',
            'last_refresh': mp_integration.last_token_refresh if mp_integration else None,
            'is_active': mp_integration.is_active if mp_integration else False,
        }
    }

    context = {
        'user': request.user,
        'tenant': tenant,
        'tenant_user': tenant_user,
        'certificates': certificates,
        'mp_integration': mp_integration,
        'now': timezone.now(),
        'current_settings': current_settings,
        'page_title': 'Mi Negocio'
    }

    return render(request, 'config/index.html', context)


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='10/h', method='POST')
def test_mp_connection(request: HttpRequest) -> JsonResponse:
    """
    Test MercadoPago connection.

    Rate limited to prevent API abuse.
    """
    tenant = request.tenant_user.tenant

    try:
        from payments.services import MercadoPagoService
        mp_service = MercadoPagoService(tenant)

        if not mp_service.integration:
            return JsonResponse({
                'success': False,
                'error': 'No hay integración de MercadoPago configurada'
            })

        # Test connection using existing service
        result = mp_service.get_payment_methods()

        return JsonResponse({
            'success': True,
            'message': 'Conexión MercadoPago exitosa',
            'data': result
        })

    except Exception as e:
        logger.error(f"Error testing MP connection: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error de conexión con MercadoPago'
        })


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='10/h', method='POST')
def test_whatsapp(request: HttpRequest) -> JsonResponse:
    """
    Test WhatsApp notification service.

    Rate limited to prevent SMS/WhatsApp abuse.
    """
    tenant = request.tenant_user.tenant

    try:
        from core.notifications import notification_service

        test_phone = getattr(request.user, 'phone', None) or '+5215551234567'  # Test number

        result = notification_service.send_notification(
            tenant=tenant,
            notification_type='test',
            recipient_email=request.user.email,
            recipient_phone=test_phone,
            recipient_name=request.user.get_full_name(),
            context={'message': 'Prueba de conexión WhatsApp desde Kita'}
        )

        return JsonResponse({
            'success': result['success'],
            'message': 'Prueba de WhatsApp enviada' if result['success'] else 'Error enviando prueba',
            'error': result.get('error', '')
        })

    except Exception as e:
        logger.error(f"Error testing WhatsApp: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error probando WhatsApp'
        })


@login_required
@tenant_required(require_owner=True)
@require_http_methods(["POST"])
@csrf_protect
@ratelimit(key='user', rate='10/h', method='POST')
def test_email(request: HttpRequest) -> JsonResponse:
    """
    Test email notification service.

    Rate limited to prevent email abuse.
    """
    tenant = request.tenant_user.tenant

    try:
        from core.notifications import notification_service

        result = notification_service.send_notification(
            tenant=tenant,
            notification_type='test',
            recipient_email=request.user.email,
            recipient_name=request.user.get_full_name(),
            context={'message': 'Prueba de conexión email desde Kita'}
        )

        return JsonResponse({
            'success': result['success'],
            'message': 'Email de prueba enviado' if result['success'] else 'Error enviando email',
            'error': result.get('error', '')
        })

    except Exception as e:
        logger.error(f"Error testing email: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error probando email'
        })


@login_required
@tenant_required(require_owner=True)
@cache_page(60)  # Cache for 1 minute
def integrations(request: HttpRequest) -> HttpResponse:
    """
    Show integrations status dashboard.

    Cached to reduce database queries.
    """
    tenant = request.tenant_user.tenant

    # Optimized queries with select_related
    mp_integration = (
        MercadoPagoIntegration.objects
        .filter(tenant=tenant, is_active=True)
        .only('user_id', 'last_token_refresh', 'is_active', 'created_at')
        .first()
    )

    # Get recent notifications with optimized query
    last_7_days = timezone.now() - timedelta(days=7)
    recent_notifications = (
        Notification.objects
        .filter(tenant=tenant, created_at__gte=last_7_days)
        .only('notification_type', 'channel', 'status', 'created_at', 'recipient_email')
        .order_by('-created_at')[:10]
    )

    context = {
        'tenant': tenant,
        'mp_integration': mp_integration,
        'recent_notifications': recent_notifications,
    }

    return render(request, 'config/integrations.html', context)


@login_required
@tenant_required(require_owner=True)
@cache_page(60)  # Cache for 1 minute
def notifications_settings(request: HttpRequest) -> HttpResponse:
    """
    Show notification preferences and statistics.

    Cached to reduce aggregation queries.
    """
    tenant = request.tenant_user.tenant

    # Cache key for stats
    cache_key = f"config:notification_stats:{tenant.id}"
    notification_stats = cache.get(cache_key)

    if not notification_stats:
        last_30_days = timezone.now() - timedelta(days=30)

        # Use single query with conditional aggregation for better performance
        from django.db.models import Count, Q

        stats = Notification.objects.filter(
            tenant=tenant,
            created_at__gte=last_30_days
        ).aggregate(
            total_sent=Count('id', filter=Q(status='sent')),
            whatsapp_sent=Count('id', filter=Q(channel='whatsapp', status='sent')),
            email_sent=Count('id', filter=Q(channel='email', status='sent')),
            failed=Count('id', filter=Q(status='failed'))
        )

        notification_stats = stats
        # Cache for 5 minutes
        cache.set(cache_key, notification_stats, 300)

    context = {
        'tenant': tenant,
        'notification_stats': notification_stats,
    }

    return render(request, 'config/notifications.html', context)


@login_required
@tenant_required(require_owner=True)
def update_mp_integration(request: HttpRequest) -> JsonResponse:
    """Redirect to existing OAuth flow."""
    return JsonResponse({
        'redirect': '/incorporacion/paso2/',  # 🇪🇸 Migrado
        'message': 'Use existing OAuth flow in onboarding'
    })

@login_required
@tenant_required(require_owner=True)
def update_whatsapp(request: HttpRequest) -> JsonResponse:
    """Info about WhatsApp settings."""
    return JsonResponse({
        'message': 'WhatsApp settings are managed via environment variables',
        'info': 'Contact system administrator to update WA_TOKEN and WA_PHONE_ID'
    })

@login_required
@tenant_required(require_owner=True)
def update_email(request: HttpRequest) -> JsonResponse:
    """Info about email settings."""
    return JsonResponse({
        'message': 'Email settings are managed via environment variables',
        'info': 'Contact system administrator to update POSTMARK_TOKEN and EMAIL_FROM'
    })

@login_required
@tenant_required(require_owner=True)
def update_notifications(request: HttpRequest) -> JsonResponse:
    """Redirect to existing user preferences."""
    return JsonResponse({
        'redirect': '/cuenta/',  # 🇪🇸 Migrado
        'message': 'Notification preferences are managed in account settings'
    })

@login_required
@tenant_required(require_owner=True)
def advanced_settings(request: HttpRequest) -> JsonResponse:
    """Info about advanced settings."""
    return JsonResponse({
        'message': 'Advanced settings are managed via Django admin and environment variables'
    })

@login_required
@tenant_required(require_owner=True)
def update_advanced(request: HttpRequest) -> JsonResponse:
    """Info about advanced settings update."""
    return JsonResponse({
        'message': 'Contact system administrator for advanced configuration changes'
    })

@login_required
@tenant_required(require_owner=True)
def webhooks_management(request: HttpRequest) -> JsonResponse:
    """Show webhook endpoints information."""
    return JsonResponse({
        'message': 'Webhook endpoints are automatically configured',
        'endpoints': {
            'payment_webhook': '/webhook/mercadopago/',
            'subscription_webhook': '/webhook/mercadopago/'
        }
    })


# ========================================
# BUSINESS INFORMATION (Moved from accounts)
# ========================================

@login_required
@tenant_required(require_owner=True)
@ratelimit(key='user', rate='5/h', method='POST')
@require_http_methods(["POST"])
@transaction.atomic
def update_business_info(request: HttpRequest) -> JsonResponse:
    """Update tenant business information."""
    from core.validators import RFCValidator, PostalCodeValidator
    from core.models import Tenant
    
    tenant = request.tenant
    
    try:
        data = json.loads(request.body)

        # Update name (nombre comercial)
        if 'name' in data:
            name = data['name'].strip()
            if len(name) >= 2 and len(name) <= 255:
                tenant.name = name

        # Update business name (razón social)
        if 'business_name' in data:
            business_name = data['business_name'].strip()
            if len(business_name) >= 3 and len(business_name) <= 255:
                tenant.business_name = business_name

        # Update RFC (con validación - aunque está readonly)
        if 'rfc' in data:
            rfc = RFCValidator.clean(data['rfc'])
            tenant.rfc = rfc

        # Update fiscal regime
        if 'fiscal_regime' in data:
            fiscal_regime = data['fiscal_regime'].strip()
            if fiscal_regime:
                tenant.fiscal_regime = fiscal_regime

        # Update name (nombre comercial)
        if 'name' in data:
            name = data['name'].strip()
            if len(name) >= 2 and len(name) <= 255:
                tenant.name = name

        # Update address fields
        if 'codigo_postal' in data:
            tenant.codigo_postal = PostalCodeValidator.clean(data['codigo_postal'])
        if 'colonia' in data:
            tenant.colonia = data['colonia'].strip()[:255]
        if 'municipio' in data:
            tenant.municipio = data['municipio'].strip()[:255]
        if 'estado' in data:
            tenant.estado = data['estado'].strip()[:255]
        if 'calle' in data:
            tenant.calle = data['calle'].strip()[:255]
        if 'numero_exterior' in data:
            tenant.numero_exterior = data['numero_exterior'].strip()[:20]
        if 'numero_interior' in data:
            tenant.numero_interior = data['numero_interior'].strip()[:50]
        
        tenant.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error updating business info: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ========================================
# CSD MANAGEMENT (Moved from accounts)
# ========================================

@login_required
@tenant_required(require_owner=True)
def csd_management(request: HttpRequest) -> HttpResponse:
    """CSD certificates management page."""
    from invoicing.models import CSDCertificate
    
    tenant = request.tenant
    
    certificates = CSDCertificate.objects.filter(
        tenant=tenant
    ).order_by('-created_at')
    
    context = {
        'tenant': tenant,
        'certificates': certificates,
        'page_title': 'Certificados CSD'
    }
    
    return render(request, 'config/csd_management.html', context)


@login_required
@tenant_required(require_owner=True)
@ratelimit(key='user', rate='5/h', method='POST')
@require_http_methods(["POST"])
@transaction.atomic
def deactivate_csd(request: HttpRequest) -> JsonResponse:
    """Deactivate CSD certificate."""
    from invoicing.models import CSDCertificate
    
    tenant = request.tenant
    
    try:
        data = json.loads(request.body)
        cert_id = data.get('certificate_id')
        
        if not cert_id:
            return JsonResponse({'success': False, 'error': 'ID requerido'}, status=400)
        
        certificate = get_object_or_404(CSDCertificate, id=cert_id, tenant=tenant)
        certificate.is_active = False
        certificate.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Error deactivating CSD: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# ========================================
# CSD UPLOAD FROM SETTINGS (Post-Onboarding)
# ========================================

@login_required
@tenant_required(require_owner=True)
@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='user', rate='10/h', method='POST')
def validate_csd_settings(request: HttpRequest) -> JsonResponse:
    """
    Validate CSD certificate from settings (no onboarding requirement).

    Reuses all validation logic from invoicing including:
    - RFC validation
    - SAT certificate validation
    - Expiration validation
    - Password validation
    """
    import tempfile
    import os
    from invoicing.services import CSDValidationService

    try:
        tenant = request.tenant

        # Get uploaded files
        cert_file = request.FILES.get('certificate_file')
        key_file = request.FILES.get('private_key_file')
        password = request.POST.get('password')

        if not all([cert_file, key_file, password]):
            return JsonResponse({
                'valid': False,
                'error': 'Faltan archivos o contraseña'
            })

        # Create temporary files for validation
        with tempfile.NamedTemporaryFile(delete=False, suffix='.cer') as temp_cert:
            for chunk in cert_file.chunks():
                temp_cert.write(chunk)
            temp_cert_path = temp_cert.name

        with tempfile.NamedTemporaryFile(delete=False, suffix='.key') as temp_key:
            for chunk in key_file.chunks():
                temp_key.write(chunk)
            temp_key_path = temp_key.name

        try:
            # Read file contents
            with open(temp_cert_path, 'rb') as f:
                cert_binary = f.read()

            with open(temp_key_path, 'rb') as f:
                key_binary = f.read()

            # Determine format
            try:
                cert_content = cert_binary.decode('utf-8')
            except UnicodeDecodeError:
                cert_content = cert_binary

            try:
                key_content = key_binary.decode('utf-8')
            except UnicodeDecodeError:
                key_content = key_binary

            # Validate with CSD service (includes RFC validation)
            validation_service = CSDValidationService()
            validation_result = validation_service.validate_certificate_files(
                cert_content, key_content, password, tenant_rfc=tenant.rfc
            )

            return JsonResponse({
                'valid': True,
                'serial_number': validation_result['serial_number'],
                'subject_name': validation_result['subject_name'],
                'valid_from': validation_result['valid_from'].isoformat(),
                'valid_to': validation_result['valid_to'].isoformat()
            })

        finally:
            # Clean up temporary files
            try:
                os.unlink(temp_cert_path)
                os.unlink(temp_key_path)
            except:
                pass

    except ValueError as e:
        return JsonResponse({
            'valid': False,
            'error': str(e)
        })
    except Exception as e:
        logger.error(f"Settings CSD validation error: {str(e)}")
        return JsonResponse({
            'valid': False,
            'error': 'Error validando certificados'
        })


@login_required
@tenant_required(require_owner=True)
@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='user', rate='5/h', method='POST')
def save_csd_settings(request: HttpRequest) -> JsonResponse:
    """
    Save CSD certificate from settings (no onboarding requirement).

    Complete flow including:
    - File upload to DigitalOcean Spaces
    - AES-256-GCM encryption
    - Database persistence
    - FiscalAPI integration (2 files + password)
    - RFC validation
    """
    import uuid
    from core.exceptions import ErrorResponseBuilder
    from invoicing.models import CSDCertificate, FileUpload
    from invoicing.services import FileUploadService, CSDValidationService, CSDEncryptionService

    try:
        tenant = request.tenant

        # Get files and password
        cert_file = request.FILES.get('certificate_file')
        key_file = request.FILES.get('private_key_file')
        password = request.POST.get('password')

        if not all([cert_file, key_file, password]):
            return ErrorResponseBuilder.build_error(
                message='Faltan archivos o contraseña',
                code='validation_error',
                status=400
            )

        # Upload files to secure storage
        upload_service = FileUploadService(tenant)

        # Upload certificate
        cert_result = upload_service.process_upload(
            uploaded_file=cert_file,
            file_type='csd_certificate',
            upload_session=request.POST.get('upload_session', str(uuid.uuid4()))
        )

        if not cert_result['success']:
            raise Exception(cert_result['error'])

        # Upload private key
        key_result = upload_service.process_upload(
            uploaded_file=key_file,
            file_type='csd_private_key',
            upload_session=request.POST.get('upload_session', str(uuid.uuid4()))
        )

        if not key_result['success']:
            raise Exception(key_result['error'])

        # Get uploaded files
        cert_upload = FileUpload.objects.get(
            tenant=tenant,
            upload_token=cert_result['upload_token']
        )
        key_upload = FileUpload.objects.get(
            tenant=tenant,
            upload_token=key_result['upload_token']
        )

        # Read and validate from storage
        with cert_upload.file.open('rb') as f:
            cert_binary = f.read()
        with key_upload.file.open('rb') as f:
            key_binary = f.read()

        try:
            cert_content = cert_binary.decode('utf-8')
        except UnicodeDecodeError:
            cert_content = cert_binary

        try:
            key_content = key_binary.decode('utf-8')
        except UnicodeDecodeError:
            key_content = key_binary

        # Final validation (includes RFC validation)
        validation_service = CSDValidationService()
        validation_result = validation_service.validate_certificate_files(
            cert_content, key_content, password, tenant_rfc=tenant.rfc
        )

        # Encrypt and save
        encryption_service = CSDEncryptionService()
        encrypted_data = encryption_service.encrypt_csd_data(
            cert_content,
            key_content,
            password
        )

        # Create/Update CSD record
        csd_certificate, created = CSDCertificate.objects.update_or_create(
            tenant=tenant,
            serial_number=validation_result['serial_number'],
            defaults={
                'certificate_file': cert_upload.file,
                'private_key_file': key_upload.file,
                'subject_name': validation_result['subject_name'],
                'issuer_name': validation_result['issuer_name'],
                'valid_from': validation_result['valid_from'],
                'valid_to': validation_result['valid_to'],
                'encrypted_certificate': encrypted_data['encrypted_certificate'],
                'encrypted_private_key': encrypted_data['encrypted_private_key'],
                'encrypted_password': encrypted_data['encrypted_password'],
                'encryption_key_id': encrypted_data['encryption_key_id'],
                'is_validated': True,
                'is_active': True
            }
        )

        # Update tenant CSD info
        tenant.csd_serial_number = validation_result['serial_number']
        tenant.csd_valid_from = validation_result['valid_from']
        tenant.csd_valid_to = validation_result['valid_to']
        tenant.save()

        # Upload to FiscalAPI
        try:
            from invoicing.pac_factory import pac_service
            logger.info(f"Settings: Testing PAC connection for tenant {tenant.name}")

            # Test connection
            connection_test = pac_service.test_connection()
            if not connection_test['success']:
                raise Exception(f"PAC connection failed: {connection_test.get('error', 'Unknown error')}")

            logger.info(f"Settings: PAC connection valid, uploading CSD for tenant {tenant.name}")
            pac_result = pac_service.upload_certificate(csd_certificate)

            if not pac_result['success']:
                logger.warning(f"Settings: PAC upload failed for {tenant.name}: {pac_result.get('message', 'Error desconocido')}")

                return JsonResponse({
                    'success': False,
                    'error': f"Certificado guardado localmente pero falló subida a PAC: {pac_result.get('message', 'Error de conexión')}"
                }, status=400)

            logger.info(f"Settings: PAC upload successful for {tenant.name}")

        except Exception as e:
            logger.error(f"Settings: PAC upload exception for {tenant.name}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f"Certificado guardado localmente pero falló conexión con PAC: {str(e)}"
            }, status=400)

        # Mark uploads as processed
        cert_upload.status = 'processed'
        cert_upload.save()
        key_upload.status = 'processed'
        key_upload.save()

        logger.info(f"Settings: CSD certificate saved and uploaded to FiscalAPI for tenant {tenant.name}")

        return JsonResponse({
            'success': True,
            'serial_number': validation_result['serial_number'],
            'pac_uploaded': csd_certificate.pac_uploaded,
            'message': 'Certificado guardado y subido a FiscalAPI exitosamente',
            'created': created
        })

    except Exception as e:
        logger.error(f"Settings: CSD save error: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='validation_error',
            status=400
        )
