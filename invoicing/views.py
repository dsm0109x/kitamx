from __future__ import annotations

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpRequest, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.utils import timezone
from django.db.models import Q
from django_ratelimit.decorators import ratelimit
from datetime import datetime
import json
import uuid
import tempfile
import os

from core.security import SecureIPDetector
from core.exceptions import ErrorResponseBuilder
from core.query_optimizations import QueryOptimizer
from core.decorators import rate_limit_with_response
from accounts.decorators import tenant_required
from .models import FileUpload, CSDCertificate, Invoice
from .services import FileUploadService, CSDValidationService, CSDEncryptionService
import logging

logger = logging.getLogger(__name__)


@login_required
@tenant_required(require_owner=True)
@csrf_protect
@require_http_methods(["POST"])
@rate_limit_with_response(key='user', rate='10/h', method='POST')
def validate_csd_local(request: HttpRequest) -> JsonResponse:
    """
    Validate CSD (Digital Certificate) files locally before storage upload.

    Performs comprehensive validation of Mexican tax authority (SAT) digital
    certificates including format verification, password validation, and
    certificate chain verification. Critical for CFDI invoice compliance.

    Args:
        request: HTTP POST request with files and form data:
                - certificate_file: .cer certificate file
                - private_key_file: .key private key file
                - password: Private key password

    Returns:
        JsonResponse: Validation result with certificate details:
                     - valid: Boolean validation status
                     - serial_number: Certificate serial number
                     - subject_name: Certificate subject information
                     - valid_from/valid_to: Certificate validity period
                     - error: Error message if validation fails

    Raises:
        429: If rate limit exceeded (10 requests/hour)
        400: If required files or password missing
        500: If validation process fails
    """
    try:
        # Use tenant_user injected by @tenant_required decorator
        tenant_user = request.tenant_user
        tenant = request.tenant

        # Get uploaded files from request
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
        logger.error(f"Local CSD validation error: {str(e)}")
        return JsonResponse({
            'valid': False,
            'error': 'Error validando certificados'
        })


@login_required
@tenant_required(require_owner=True)
@csrf_protect
@require_http_methods(["POST"])
@rate_limit_with_response(key='user', rate='5/h', method='POST')
def save_csd_complete(request: HttpRequest) -> JsonResponse:
    """
    Complete CSD certificate upload and integration with FiscalAPI PAC.

    Handles the full CSD integration workflow including secure file upload,
    encryption for storage, database persistence, and PAC (FiscalAPI) upload
    for CFDI stamping capabilities. Critical for invoice generation compliance.

    Args:
        request: HTTP POST request with files and form data:
                - certificate_file: Validated .cer certificate file
                - private_key_file: Validated .key private key file
                - password: Private key password
                - upload_session: Session identifier for file tracking

    Returns:
        JsonResponse: Integration result with:
                     - success: Boolean operation status
                     - serial_number: Certificate serial number
                     - pac_uploaded: FiscalAPI upload status
                     - message: Success/error message
                     - error: Detailed error if operation fails

    Raises:
        429: If rate limit exceeded (5 requests/hour)
        400: If files missing, validation fails, or PAC upload fails
        500: If encryption, storage, or integration fails
    """
    try:
        # Use tenant_user injected by @tenant_required decorator
        tenant_user = request.tenant_user
        tenant = request.tenant

        # BUG FIX #24: Validate upload_session against session-stored value
        upload_session = request.POST.get('upload_session')
        expected_session = request.session.get('csd_upload_session')

        if not upload_session or not expected_session:
            return ErrorResponseBuilder.build_error(
                message='Sesión de upload inválida. Por favor recarga la página.',
                code='invalid_session',
                status=400
            )

        if upload_session != expected_session:
            logger.warning(f"Upload session mismatch for tenant {tenant.name}: received={upload_session}, expected={expected_session}")
            return ErrorResponseBuilder.build_error(
                message='Sesión de upload no válida. Por favor recarga la página e intenta de nuevo.',
                code='session_mismatch',
                status=403
            )

        # Get files and password from request
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

        # Get uploaded files for processing
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

        # Encrypt and save (handle both binary and text content)
        encryption_service = CSDEncryptionService()
        encrypted_data = encryption_service.encrypt_csd_data(
            cert_content,  # Already handled as binary or string
            key_content,   # Already handled as binary or string
            password
        )

        # Create CSD record
        csd_certificate, created = CSDCertificate.objects.update_or_create(
            tenant=tenant,
            defaults={
                'certificate_file': cert_upload.file,
                'private_key_file': key_upload.file,
                'serial_number': validation_result['serial_number'],
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

        # Upload certificate to PAC provider
        try:
            from .pac_factory import pac_service
            logger.info(f"Testing PAC connection for tenant {tenant.name}")

            # Test PAC connection
            connection_test = pac_service.test_connection()
            if not connection_test['success']:
                raise Exception(f"PAC connection failed: {connection_test.get('error', 'Unknown error')}")

            logger.info(f"PAC connection valid, uploading CSD for tenant {tenant.name}")
            pac_result = pac_service.upload_certificate(csd_certificate)

            if not pac_result['success']:
                # PAC upload failed - mark in database but continue
                logger.warning(f"PAC upload failed for {tenant.name}: {pac_result.get('message', 'Error desconocido')}")

                return JsonResponse({
                    'success': False,
                    'error': f"Certificado guardado localmente pero falló subida a PAC: {pac_result.get('message', 'Error de conexión')}"
                }, status=400)

            logger.info(f"PAC upload successful for {tenant.name}")

        except Exception as e:
            logger.error(f"PAC upload exception for {tenant.name}: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f"Certificado guardado localmente pero falló conexión con PAC: {str(e)}"
            }, status=400)

        # Mark uploads as processed
        cert_upload.status = 'processed'
        cert_upload.save()
        key_upload.status = 'processed'
        key_upload.save()

        logger.info(f"CSD certificate saved and uploaded to FiscalAPI for tenant {tenant.name}")

        return JsonResponse({
            'success': True,
            'serial_number': validation_result['serial_number'],
            'pac_uploaded': csd_certificate.pac_uploaded,
            'message': 'Certificado guardado y subido a FiscalAPI exitosamente'
        })

    except Exception as e:
        logger.error(f"CSD complete save error: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='validation_error',
            status=400
        )


@login_required
@tenant_required()
@csrf_protect
@require_http_methods(["POST"])
@rate_limit_with_response(key='user', rate='20/h', method='POST')
def upload_file(request: HttpRequest) -> JsonResponse:
    """
    Handle secure file uploads via Dropzone interface.

    Processes file uploads with comprehensive security validation,
    virus scanning, file type verification, and secure storage.
    Supports various file types for invoicing workflows.

    Args:
        request: HTTP POST request with file and metadata:
                - file: Uploaded file object
                - file_type: Type classification ('csd_certificate', 'csd_private_key', 'other')
                - upload_session: Session identifier for tracking

    Returns:
        JsonResponse: Upload result with:
                     - success: Boolean upload status
                     - upload_token: Unique file identifier
                     - error: Error message if upload fails

    Raises:
        429: If rate limit exceeded (20 requests/hour)
        400: If no file provided or validation fails
        500: If upload processing fails
    """
    try:
        # Use tenant_user injected by @tenant_required decorator
        tenant_user = request.tenant_user
        tenant = request.tenant

        # BUG FIX #24: Validate upload_session for CSD uploads only (optional for other uploads)
        file_type = request.POST.get('file_type', 'other')
        upload_session = request.POST.get('upload_session')

        # For CSD files, validate session strictly
        if file_type in ['csd_certificate', 'csd_private_key']:
            expected_session = request.session.get('csd_upload_session')

            if not upload_session or not expected_session:
                return ErrorResponseBuilder.build_error(
                    message='Sesión de upload inválida. Por favor recarga la página.',
                    code='invalid_session',
                    status=400
                )

            if upload_session != expected_session:
                logger.warning(f"Upload session mismatch for tenant {tenant.name}: received={upload_session}, expected={expected_session}")
                return ErrorResponseBuilder.build_error(
                    message='Sesión de upload no válida. Por favor recarga la página.',
                    code='session_mismatch',
                    status=403
                )

        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return ErrorResponseBuilder.build_error(
                message='No file uploaded',
                code='validation_error',
                status=400
            )

        logger.info(f"Processing upload for tenant: {tenant.name}")

        # Use FileUploadService for secure processing
        upload_service = FileUploadService(tenant)
        result = upload_service.process_upload(
            uploaded_file=uploaded_file,
            file_type=file_type,
            upload_session=upload_session or str(uuid.uuid4())
        )

        if result['success']:
            return JsonResponse(result)
        else:
            return ErrorResponseBuilder.build_error(
                message=result['error'],
                code='csd_error',
                status=400
            )

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
@csrf_protect
@require_http_methods(["DELETE"])
@ratelimit(key='user', rate='30/h', method='POST')
def delete_file(request: HttpRequest, upload_token: str) -> JsonResponse:
    """
    Securely delete uploaded file from storage.

    Removes uploaded files from both database records and physical storage
    with proper cleanup and audit logging. Ensures no orphaned files
    remain in the system.

    Args:
        request: HTTP DELETE request from authenticated tenant user
        upload_token: Unique identifier of the file to delete

    Returns:
        JsonResponse: Deletion result with success status and message

    Raises:
        429: If rate limit exceeded (30 requests/hour)
        404: If file not found or not owned by tenant
        500: If deletion process fails
    """
    try:
        # Use tenant_user injected by @tenant_required decorator
        tenant_user = request.tenant_user
        tenant = request.tenant

        upload_service = FileUploadService(tenant)
        result = upload_service.delete_upload(upload_token)

        return JsonResponse(result)

    except Exception as e:
        logger.error(f"Delete error: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='server_error',
            status=500
        )


@login_required
@tenant_required()
def facturacion_index(request: HttpRequest) -> HttpResponse:
    """
    Main CFDI invoice management dashboard.

    Renders the primary invoicing interface with comprehensive statistics,
    invoice status breakdown, and DataTables integration for invoice
    management. Central hub for Mexican tax compliance and invoice operations.

    Args:
        request: HTTP request from authenticated tenant user

    Returns:
        HttpResponse: Invoice management dashboard with statistics:
                     - total_invoices: All-time invoice count
                     - month_invoices: Current month invoice count
                     - stamped_invoices: Successfully stamped invoice count
                     - cancelled_invoices: Cancelled invoice count

    Raises:
        403: If user lacks tenant access
    """
    # Use tenant_user injected by @tenant_required decorator
    user = request.user
    tenant_user = request.tenant_user
    tenant = request.tenant

    # Get basic stats for cards
    today = timezone.now().date()
    current_month_start = today.replace(day=1)

    # Optimized: single aggregation query instead of 4 separate counts
    from django.db.models import Count, Q
    stats = Invoice.objects.filter(tenant=tenant).aggregate(
        total_invoices=Count('id'),
        month_invoices=Count('id', filter=Q(created_at__date__gte=current_month_start)),
        stamped_invoices=Count('id', filter=Q(status='stamped')),
        cancelled_invoices=Count('id', filter=Q(status='cancelled'))
    )

    total_invoices = stats['total_invoices']
    month_invoices = stats['month_invoices']
    stamped_invoices = stats['stamped_invoices']
    cancelled_invoices = stats['cancelled_invoices']

    context = {
        'user': user,
        'tenant': tenant,
        'tenant_user': tenant_user,
        'page_title': 'Facturación',
        'stats': {
            'total_invoices': total_invoices,
            'month_invoices': month_invoices,
            'stamped_invoices': stamped_invoices,
            'cancelled_invoices': cancelled_invoices,
        }
    }

    return render(request, 'invoicing/index.html', context)


@login_required
@tenant_required()
def ajax_invoices(request: HttpRequest) -> JsonResponse:
    """
    DataTables AJAX endpoint for invoice management with advanced filtering.

    Provides server-side processing for invoices table with comprehensive
    search, filtering, sorting, and pagination capabilities. Includes
    optimized queries for performance and multiple filter criteria
    for tax compliance and business analysis.

    Args:
        request: HTTP GET request with DataTables parameters:
                - draw: Request counter for DataTables
                - start: Starting record index
                - length: Number of records per page
                - search[value]: Global search term
                - status: Filter by invoice status
                - date_from/date_to: Date range filters
                - customer: Customer name/RFC filter

    Returns:
        JsonResponse: DataTables format with invoice data including:
                     - serie_folio: Invoice series and folio
                     - customer information and RFC
                     - amounts, currency, and status
                     - timestamps and UUID
                     - action capabilities (cancel, download)

    Raises:
        403: If user lacks tenant access
    """
    from django.db.models import Q

    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    # Get parameters
    draw = int(request.GET.get('draw', 1))
    start = int(request.GET.get('start', 0))
    length = int(request.GET.get('length', 25))
    search_value = request.GET.get('search[value]', '')

    # Filters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    customer_filter = request.GET.get('customer', '')

    # Base queryset with optimizations
    invoices = QueryOptimizer.optimize_invoices(
        Invoice.objects.filter(tenant=tenant)
    )

    # Apply filters
    if status_filter:
        invoices = invoices.filter(status=status_filter)

    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        invoices = invoices.filter(created_at__date__gte=date_from)

    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        invoices = invoices.filter(created_at__date__lte=date_to)

    if customer_filter:
        invoices = invoices.filter(
            Q(customer_name__icontains=customer_filter) |
            Q(customer_rfc__icontains=customer_filter)
        )

    # Search
    if search_value:
        invoices = invoices.filter(
            Q(folio__icontains=search_value) |
            Q(serie__icontains=search_value) |
            Q(uuid__icontains=search_value) |
            Q(customer_name__icontains=search_value) |
            Q(customer_rfc__icontains=search_value)
        )

    # Total records
    total_records = invoices.count()

    # Order and paginate
    invoices = invoices.order_by('-created_at')[start:start + length]

    # Format data for DataTables
    data = []
    for invoice in invoices:
        data.append({
            'id': str(invoice.id),
            'serie_folio': invoice.serie_folio,
            'customer_name': invoice.customer_name,
            'customer_rfc': invoice.customer_rfc,
            'total': float(invoice.total),
            'currency': invoice.currency,
            'status': invoice.status,
            'status_display': invoice.get_status_display(),
            'created_at': invoice.created_at.strftime('%d/%m/%Y %H:%M'),
            'stamped_at': invoice.stamped_at.strftime('%d/%m/%Y %H:%M') if invoice.stamped_at else '',
            'uuid': str(invoice.uuid) if invoice.uuid else '',
            'can_cancel': invoice.is_valid_for_cancellation,
            'has_xml': bool(invoice.xml_file),
            'has_pdf': bool(invoice.pdf_file),
        })

    return JsonResponse({
        'draw': draw,
        'recordsTotal': total_records,
        'recordsFiltered': total_records,
        'data': data
    })


@login_required
@tenant_required()
def ajax_invoice_stats(request: HttpRequest) -> JsonResponse:
    """
    Real-time invoice statistics API for dashboard analytics.

    Provides comprehensive invoice metrics including count breakdowns,
    total amounts, status distributions, and period-specific analytics.
    Essential for tax compliance monitoring and business intelligence.

    Args:
        request: HTTP GET request with optional parameters:
                - date_from: Filter start date (YYYY-MM-DD)
                - date_to: Filter end date (YYYY-MM-DD)
                Default: Current month if no dates provided

    Returns:
        JsonResponse: Statistics object with:
                     - total_invoices: Invoice count in period
                     - total_amount: Sum of invoice amounts
                     - status breakdowns (stamped, cancelled, error)
                     - status_breakdown: Detailed count by status

    Raises:
        403: If user lacks tenant access
    """
    from django.db.models import Sum, Count
    from datetime import datetime

    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    # Get date range
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    # Default to current month
    if not date_from or not date_to:
        today = timezone.now().date()
        date_from = today.replace(day=1)
        date_to = today
    else:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

    # Get invoices in date range
    invoices = Invoice.objects.filter(
        tenant=tenant,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to
    )

    # Calculate stats
    stats = invoices.aggregate(
        total_count=Count('id'),
        total_amount=Sum('total'),
        stamped_count=Count('id', filter=Q(status='stamped')),
        cancelled_count=Count('id', filter=Q(status='cancelled')),
        error_count=Count('id', filter=Q(status='error')),
    )

    # Status breakdown
    status_breakdown = {}
    for status, display in Invoice.STATUS_CHOICES:
        count = invoices.filter(status=status).count()
        status_breakdown[status] = {
            'count': count,
            'display': display
        }

    return JsonResponse({
        'success': True,
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'stats': {
            'total_invoices': stats['total_count'] or 0,
            'total_amount': float(stats['total_amount'] or 0),
            'stamped_invoices': stats['stamped_count'] or 0,
            'cancelled_invoices': stats['cancelled_count'] or 0,
            'error_invoices': stats['error_count'] or 0,
        },
        'status_breakdown': status_breakdown
    })


@login_required
@tenant_required()
def invoice_detail(request: HttpRequest, invoice_id: str) -> HttpResponse:
    """
    Invoice detail panel with comprehensive CFDI information.

    Renders detailed view of an invoice including all CFDI data,
    tax calculations, customer information, and related documents
    (XML/PDF). Used for invoice review and customer service.

    Args:
        request: HTTP request from authenticated tenant user
        invoice_id: UUID of the invoice to display

    Returns:
        HttpResponse: Detailed invoice panel template with complete
                     invoice information and available actions

    Raises:
        404: If invoice not found or not owned by tenant
    """
    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    invoice = get_object_or_404(Invoice, id=invoice_id, tenant=tenant)

    context = {
        'invoice': invoice,
        'tenant': tenant
    }

    return render(request, 'invoicing/invoice_detail.html', context)


@login_required
@tenant_required()
@require_http_methods(["POST"])
def cancel_invoice(request: HttpRequest) -> JsonResponse:
    """
    Cancel CFDI invoice through PAC with SAT compliance validation.

    Submits invoice cancellation request to PAC (FiscalAPI) following
    Mexican tax authority requirements. Includes business rule validation
    for cancellation eligibility and comprehensive audit logging.

    Args:
        request: HTTP POST request with JSON body:
                - invoice_id: UUID of invoice to cancel
                - reason: Cancellation reason code (default: '02')

    Returns:
        JsonResponse: Cancellation result with:
                     - success: Boolean operation status
                     - task_id: Background task identifier
                     - message: Status message
                     - error: Error details if cancellation fails

    Raises:
        400: If invoice cannot be cancelled (outside calendar month)
        404: If invoice not found
        500: If cancellation submission fails
    """
    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id')
        reason = data.get('reason', '02')  # Default: "02 - Devolución de mercancías"

        invoice = get_object_or_404(Invoice, id=invoice_id, tenant=tenant)

        # Validate cancellation
        if not invoice.is_valid_for_cancellation:
            return JsonResponse({
                'success': False,
                'error': 'La factura no puede cancelarse (fuera del mes calendario)'
            })

        if invoice.status == 'cancelled':
            return JsonResponse({
                'success': False,
                'error': 'La factura ya está cancelada'
            })

        # Submit cancellation task
        from .tasks import cancel_invoice_task
        task = cancel_invoice_task.delay(str(invoice.id), reason)

        # Log audit action
        from core.models import AuditLog
        AuditLog.objects.create(
            tenant=tenant,
            user_email=request.user.email,
            user_name=request.user.get_full_name() or request.user.email,
            action='cancel',
            entity_type='Invoice',
            entity_id=invoice.id,
            entity_name=invoice.serie_folio,
            ip_address=SecureIPDetector.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            notes=f'Cancellation reason: {reason}'
        )

        return JsonResponse({
            'success': True,
            'task_id': task.id,
            'message': 'Solicitud de cancelación enviada al PAC'
        })

    except Exception as e:
        logger.error(f"Error cancelling invoice: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='cancellation_error',
            status=500
        )


@login_required
@tenant_required()
@require_http_methods(["POST"])
def resend_invoice(request: HttpRequest) -> JsonResponse:
    """
    Resend stamped invoice to customer via email or WhatsApp.

    Delivers CFDI invoice documents to customers through notification
    service with multiple delivery methods. Improves customer service
    and ensures invoice delivery compliance.

    Args:
        request: HTTP POST request with JSON body:
                - invoice_id: UUID of invoice to resend
                - method: Delivery method ('email' or 'whatsapp')

    Returns:
        JsonResponse: Delivery result with:
                     - success: Boolean delivery status
                     - message: Confirmation or error message
                     - error: Detailed error if delivery fails

    Raises:
        400: If invoice is not stamped or invalid method
        404: If invoice not found
        500: If notification service fails
    """
    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoice_id')
        method = data.get('method', 'email')  # email or whatsapp

        invoice = get_object_or_404(Invoice, id=invoice_id, tenant=tenant)

        if invoice.status != 'stamped':
            return JsonResponse({
                'success': False,
                'error': 'Solo se pueden reenviar facturas timbradas'
            })

        # Send via notification service
        from core.notifications import notification_service

        if method == 'email':
            result = notification_service.send_invoice_email(invoice)
        else:
            result = notification_service.send_invoice_whatsapp(invoice)

        if result.get('success'):
            return JsonResponse({
                'success': True,
                'message': f'Factura enviada por {method}'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Error enviando factura')
            })

    except Exception as e:
        logger.error(f"Error resending invoice: {str(e)}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='cancellation_error',
            status=500
        )


@login_required
@tenant_required()
def download_file(request: HttpRequest, invoice_id: str, file_type: str) -> HttpResponse:
    """
    Secure download of invoice XML or PDF documents.

    Provides authenticated access to CFDI documents with proper security
    validation and content-type headers. Essential for tax compliance
    and customer document delivery.

    Args:
        request: HTTP request from authenticated tenant user
        invoice_id: UUID of the invoice containing documents
        file_type: Document type ('xml' for CFDI XML, 'pdf' for visual PDF)

    Returns:
        HttpResponse: FileResponse with proper content-type and filename
                     for secure document download

    Raises:
        404: If invoice or requested file type not found
        403: If user lacks access to invoice
    """
    from django.http import FileResponse, Http404

    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    invoice = get_object_or_404(Invoice, id=invoice_id, tenant=tenant)

    # Get file based on type
    if file_type == 'xml' and invoice.xml_file:
        file_field = invoice.xml_file
        content_type = 'application/xml'
        filename = f"{invoice.serie_folio}.xml"
    elif file_type == 'pdf' and invoice.pdf_file:
        file_field = invoice.pdf_file
        content_type = 'application/pdf'
        filename = f"{invoice.serie_folio}.pdf"
    else:
        raise Http404("File not found")

    response = FileResponse(
        file_field.open('rb'),
        content_type=content_type,
        filename=filename
    )

    return response


@login_required
@tenant_required()
def export_invoices(request: HttpRequest) -> HttpResponse:
    """
    Export invoice data in CSV or XLSX format for business analysis.

    Provides comprehensive invoice export functionality with filtering
    options for accounting, tax compliance, and business intelligence.
    Includes all essential CFDI fields and status information.

    Args:
        request: HTTP GET request with optional parameters:
                - format: Export format ('csv' or 'xlsx')
                - status: Filter by invoice status
                - date_from: Filter start date (YYYY-MM-DD)
                - date_to: Filter end date (YYYY-MM-DD)

    Returns:
        HttpResponse: File download with invoice data including:
                     - Serie-Folio, UUID, customer information
                     - Amounts, currency, status, timestamps
                     - Cancellation status and dates

    Raises:
        403: If user lacks tenant access
        500: If export generation fails
    """
    from django.http import HttpResponse
    import csv
    from datetime import datetime

    # Use tenant_user injected by @tenant_required decorator
    tenant_user = request.tenant_user
    tenant = request.tenant

    # Get parameters
    export_format = request.GET.get('format', 'csv')
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    # Base queryset with optimizations
    invoices = QueryOptimizer.optimize_invoices(
        Invoice.objects.filter(tenant=tenant)
    )

    # Apply filters
    if status_filter:
        invoices = invoices.filter(status=status_filter)

    if date_from:
        date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        invoices = invoices.filter(created_at__date__gte=date_from)

    if date_to:
        date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        invoices = invoices.filter(created_at__date__lte=date_to)

    invoices = invoices.order_by('-created_at')

    # Generate filename
    today_str = timezone.now().strftime('%Y%m%d')
    filename = f"facturas_kita_{today_str}.{export_format}"

    if export_format == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow([
            'Serie-Folio', 'UUID', 'Cliente', 'RFC', 'Total', 'Moneda',
            'Estado', 'Fecha Creación', 'Fecha Timbrado', 'Cancelada'
        ])

        for invoice in invoices:
            writer.writerow([
                invoice.serie_folio,
                str(invoice.uuid) if invoice.uuid else '',
                invoice.customer_name,
                invoice.customer_rfc,
                float(invoice.total),
                invoice.currency,
                invoice.get_status_display(),
                invoice.created_at.strftime('%d/%m/%Y %H:%M'),
                invoice.stamped_at.strftime('%d/%m/%Y %H:%M') if invoice.stamped_at else '',
                'Sí' if invoice.status == 'cancelled' else 'No'
            ])

        return response

    else:  # XLSX
        import io
        output = io.BytesIO()

        # Create workbook and worksheet
        import xlsxwriter
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Facturas')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D7E4BC',
            'border': 1
        })

        # Write headers
        headers = [
            'Serie-Folio', 'UUID', 'Cliente', 'RFC', 'Total', 'Moneda',
            'Estado', 'Fecha Creación', 'Fecha Timbrado', 'Cancelada'
        ]

        for col, header in enumerate(headers):
            worksheet.write(0, col, header, header_format)

        # Write data
        for row, invoice in enumerate(invoices, 1):
            worksheet.write(row, 0, invoice.serie_folio)
            worksheet.write(row, 1, str(invoice.uuid) if invoice.uuid else '')
            worksheet.write(row, 2, invoice.customer_name)
            worksheet.write(row, 3, invoice.customer_rfc)
            worksheet.write(row, 4, float(invoice.total))
            worksheet.write(row, 5, invoice.currency)
            worksheet.write(row, 6, invoice.get_status_display())
            worksheet.write(row, 7, invoice.created_at.strftime('%d/%m/%Y %H:%M'))
            worksheet.write(row, 8, invoice.stamped_at.strftime('%d/%m/%Y %H:%M') if invoice.stamped_at else '')
            worksheet.write(row, 9, 'Sí' if invoice.status == 'cancelled' else 'No')

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response