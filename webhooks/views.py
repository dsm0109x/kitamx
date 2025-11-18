from __future__ import annotations

"""Webhook views - now using centralized webhook handler.

All webhook logic has been moved to payments.webhook_handler for consistency.
"""
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from django.http import HttpRequest, JsonResponse

from payments.webhook_handler import webhook_handler


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='100/m', method='POST')
def mercadopago_webhook(request: HttpRequest) -> JsonResponse:
    """Handle Mercado Pago webhooks for payment links (user payments).

    This endpoint now delegates to the centralized webhook handler.
    """
    return webhook_handler.handle_webhook(request, webhook_type='payment')


@csrf_exempt
@require_http_methods(["POST"])
@ratelimit(key='ip', rate='100/m', method='POST')
def kita_billing_webhook(request: HttpRequest) -> JsonResponse:
    """Handle Mercado Pago webhooks for Kita subscriptions (billing).

    This endpoint now delegates to the centralized webhook handler.
    """
    return webhook_handler.handle_webhook(request, webhook_type='billing')


# All webhook processing logic has been moved to payments.webhook_handler
# Legacy functions removed to avoid duplication


# ========================================
# POSTMARK EMAIL WEBHOOKS
# ========================================

import json
import logging
from django.http import HttpResponse
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def verify_postmark_webhook(request):
    """Verify webhook is from Postmark using HTTP Basic Auth."""
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')

    if not auth_header.startswith('Basic '):
        return False

    try:
        import base64
        credentials = base64.b64decode(auth_header[6:]).decode('utf-8')
        username, password = credentials.split(':', 1)

        # Verificar credenciales
        expected_username = getattr(settings, 'POSTMARK_WEBHOOK_USERNAME', 'diego')
        expected_password = getattr(settings, 'POSTMARK_WEBHOOK_PASSWORD', '')

        return username == expected_username and password == expected_password

    except Exception as e:
        logger.error(f"Error verifying Postmark webhook: {e}")
        return False


@csrf_exempt
@require_http_methods(["GET", "POST"])
@ratelimit(key='ip', rate='200/m', method='POST')
def postmark_webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook endpoint for Postmark email events.
    Handles: Delivery, Open, Click, Bounce, SpamComplaint

    Accepts GET for Postmark test verification, POST for actual events.
    """
    # GET request: Postmark verification test
    if request.method == 'GET':
        return HttpResponse('Postmark webhook endpoint ready', status=200)

    # POST request: Process webhook event
    try:
        # Verificar autenticación
        if hasattr(settings, 'POSTMARK_WEBHOOK_PASSWORD') and settings.POSTMARK_WEBHOOK_PASSWORD:
            if not verify_postmark_webhook(request):
                logger.warning(f"Unauthorized Postmark webhook attempt from {request.META.get('REMOTE_ADDR')}")
                return JsonResponse({'error': 'Unauthorized'}, status=401)

        # Parse JSON payload
        payload = json.loads(request.body)

        # Extraer tipo de evento
        record_type = payload.get('RecordType')
        message_id = payload.get('MessageID')

        if not message_id:
            logger.error("Postmark webhook missing MessageID")
            return JsonResponse({'error': 'MessageID required'}, status=400)

        logger.info(f"Postmark webhook: {record_type} for message {message_id}")

        # Idempotencia - evitar procesar el mismo evento múltiples veces
        cache_key = f"postmark_webhook_{message_id}_{record_type}_{payload.get('ReceivedAt', '')}"
        if cache.get(cache_key):
            logger.info(f"Duplicate Postmark webhook ignored: {cache_key}")
            return HttpResponse(status=200)

        cache.set(cache_key, True, timeout=3600)  # 1 hora

        # Buscar notification primero para obtener tenant
        from core.models import EmailEvent, Notification

        metadata = payload.get('Metadata', {})
        notification_id = metadata.get('notification_id')
        notification = None
        tenant = None

        # Intentar encontrar notification por metadata
        if notification_id:
            try:
                notification = Notification.objects.get(id=notification_id)
                tenant = notification.tenant
            except Notification.DoesNotExist:
                logger.warning(f"Notification {notification_id} not found")

        # Si no hay notification en metadata, buscar por MessageID
        if not notification:
            notification = Notification.objects.filter(
                postmark_message_id=message_id
            ).first()
            if notification:
                tenant = notification.tenant

        # Si no hay tenant, solo loguear el evento y retornar OK
        if not tenant:
            logger.info(f"Postmark event {record_type} for {message_id} - no tenant found, skipping EmailEvent creation")
            return HttpResponse(status=200)

        # Crear o actualizar EmailEvent con tenant
        email_event, created = EmailEvent.objects.get_or_create(
            message_id=message_id,
            defaults={
                'recipient': payload.get('Recipient', ''),
                'subject': payload.get('Subject', ''),
                'tag': payload.get('Tag', ''),
                'message_stream': payload.get('MessageStream', 'outbound'),
                'metadata': metadata,
                'server_id': payload.get('ServerID'),
                'notification': notification,
                'tenant': tenant,
            }
        )

        # Procesar según tipo de evento
        if record_type == 'Delivery':
            email_event.update_from_webhook('Delivery', payload)
            logger.info(f"Email {message_id} delivered to {email_event.recipient}")

        elif record_type == 'Open':
            email_event.update_from_webhook('Open', payload)
            first_open = payload.get('FirstOpen', False)
            logger.info(f"Email {message_id} opened by {email_event.recipient} (first={first_open}, total={email_event.open_count})")

        elif record_type == 'Click':
            email_event.update_from_webhook('Click', payload)
            logger.info(f"Link clicked in email {message_id}")

        elif record_type == 'Bounce':
            email_event.update_from_webhook('Bounce', payload)

            # Actualizar notification status si existe
            if email_event.notification:
                email_event.notification.status = 'failed'
                bounce_info = f"{payload.get('Type')} - {payload.get('Description', '')}"
                email_event.notification.error_message = f"Bounce: {bounce_info}"
                email_event.notification.save(update_fields=['status', 'error_message'])

            logger.warning(f"Email {message_id} bounced: {payload.get('Type')} - {email_event.recipient}")

        elif record_type == 'SpamComplaint':
            email_event.update_from_webhook('SpamComplaint', payload)

            # Actualizar notification
            if email_event.notification:
                email_event.notification.status = 'failed'
                email_event.notification.error_message = 'Spam complaint'
                email_event.notification.save(update_fields=['status', 'error_message'])

            logger.critical(f"Spam complaint for email {message_id} from {email_event.recipient}")

        else:
            logger.warning(f"Unknown Postmark event type: {record_type}")

        return HttpResponse(status=200)

    except json.JSONDecodeError:
        logger.error("Invalid JSON in Postmark webhook")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    except Exception as e:
        logger.error(f"Error processing Postmark webhook: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)