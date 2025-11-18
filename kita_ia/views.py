"""Views for Kita IA - AI-powered payment link creation.

Handles SSE streaming, message processing, and link confirmation
for natural language payment link creation.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Generator
import json
import time
import logging

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from django_ratelimit.decorators import ratelimit

from core.models import TenantUser
from core.security import SecureIPDetector
from core.exceptions import ErrorResponseBuilder
from accounts.decorators import tenant_required
from .models import Conversation
from .services import KitaIAService

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


@login_required
@tenant_required()
@cache_page(60 * 5)  # Cache for 5 minutes
def kita_ia_index(request: HttpRequest) -> HttpResponse:
    """Kita IA main page.

    Args:
        request: HTTP request object

    Returns:
        Rendered Kita IA chat interface
    """
    user = request.user
    tenant_user = TenantUser.objects.select_related('tenant').filter(
        email=user.email,
        is_owner=True
    ).first()

    if not tenant_user:
        return redirect('onboarding:start')

    # Cache conversation stats
    cache_key = f"kita_ia:stats:{tenant_user.tenant.id}:{user.email}"
    stats = cache.get(cache_key)

    if stats is None:
        stats = {
            'total_conversations': Conversation.objects.filter(
                tenant=tenant_user.tenant,
                user_email=user.email
            ).count(),
            'links_created': Conversation.objects.filter(
                tenant=tenant_user.tenant,
                user_email=user.email,
                link_created=True
            ).count(),
        }
        cache.set(cache_key, stats, 300)  # Cache for 5 minutes

    context = {
        'user': user,
        'tenant': tenant_user.tenant,
        'tenant_user': tenant_user,
        'page_title': 'Kita IA',
        'stats': stats
    }

    return render(request, 'kita_ia/index.html', context)


@login_required
@tenant_required()
def chat_stream(request: HttpRequest) -> StreamingHttpResponse:
    """SSE endpoint for chat streaming.

    Server-Sent Events stream for real-time chat updates.

    Args:
        request: HTTP request object

    Returns:
        Streaming HTTP response with SSE events
    """
    tenant_user = TenantUser.objects.select_related('tenant').filter(
        email=request.user.email,
        is_owner=True
    ).first()

    if not tenant_user:
        return ErrorResponseBuilder.build_error(
            message='No tenant found',
            code='tenant_not_found',
            status=400
        )

    def event_stream() -> Generator[str, None, None]:
        """Generator for SSE events.

        Yields:
            SSE formatted event strings
        """
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'timestamp': timezone.now().isoformat()})}\n\n"

        # Keep connection alive and listen for new messages
        last_check = timezone.now()
        last_activity = timezone.now()
        TIMEOUT_MINUTES = 5  # Close connection after 5 min of inactivity

        while True:
            try:
                # Send all IA responses via SSE
                conversations = Conversation.objects.filter(
                    tenant=tenant_user.tenant,
                    user_email=request.user.email,
                    updated_at__gt=last_check
                ).prefetch_related('messages')

                for conversation in conversations:
                    # Get all new messages for SSE
                    new_messages = conversation.messages.filter(
                        created_at__gt=last_check,
                        message_type__in=['assistant', 'link_preview', 'link_created']
                    ).order_by('created_at')

                    for message in new_messages:
                        event_data = {
                            'type': message.message_type,
                            'message': message.content,
                            'timestamp': message.created_at.isoformat(),
                            'conversation_id': str(conversation.conversation_id)
                        }

                        if message.metadata:
                            event_data.update(message.metadata)

                        yield f"data: {json.dumps(event_data)}\n\n"

                # Update activity if there were new messages
                if conversations.exists():
                    last_activity = timezone.now()

                last_check = timezone.now()

                # Check for timeout
                idle_time = (timezone.now() - last_activity).total_seconds() / 60
                if idle_time > TIMEOUT_MINUTES:
                    yield f"data: {json.dumps({'type': 'timeout', 'message': 'Conexión cerrada por inactividad'})}\n\n"
                    break

                # Keep alive ping every 2 seconds for faster response
                yield f"data: {json.dumps({'type': 'ping', 'timestamp': last_check.isoformat()})}\n\n"

                time.sleep(2)

            except Exception as e:
                logger.error(f"Error in SSE stream: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': 'Connection error'})}\n\n"
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'  # Disable nginx buffering

    return response


@login_required
@tenant_required()
@require_http_methods(["POST"])
@ratelimit(key='user', rate='30/m', method='POST')
@transaction.atomic
def send_message(request: HttpRequest) -> JsonResponse:
    """Send message to AI chat.

    Processes user message and triggers AI response generation.
    Rate limited to 30 messages per minute per user.

    Args:
        request: HTTP request with message in JSON body

    Returns:
        JSON response with conversation ID
    """
    tenant_user = TenantUser.objects.select_related('tenant').filter(
        email=request.user.email,
        is_owner=True
    ).first()

    if not tenant_user:
        return ErrorResponseBuilder.build_error(
            message='No tenant found',
            code='tenant_not_found',
            status=400
        )

    try:
        data = json.loads(request.body)
        message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')

        if not message:
            return ErrorResponseBuilder.build_error(
                message='Mensaje vacío',
                code='validation_error',
                status=400
            )

        if len(message) > 500:
            return ErrorResponseBuilder.build_error(
                message='Mensaje muy largo (máximo 500 caracteres)',
                code='validation_error',
                status=400
            )

        # Check active conversations limit (anti-abuse)
        if not conversation_id:
            active_count = Conversation.objects.filter(
                tenant=tenant_user.tenant,
                user_email=request.user.email,
                status='active'
            ).count()

            if active_count >= 20:
                return ErrorResponseBuilder.build_error(
                    message='Límite de conversaciones activas alcanzado (máximo 20). Completa o limpia algunas conversaciones.',
                    code='limit_exceeded',
                    status=429
                )

        # Get or create conversation with select_related
        conversation: Optional[Conversation] = None
        if conversation_id:
            try:
                conversation = Conversation.objects.select_related(
                    'tenant', 'payment_link'
                ).get(
                    conversation_id=conversation_id,
                    tenant=tenant_user.tenant
                )
            except Conversation.DoesNotExist:
                conversation = None

        if not conversation:
            # Create new conversation
            kita_ia = KitaIAService(tenant_user.tenant, request.user)
            conversation = kita_ia.create_conversation(
                ip_address=SecureIPDetector.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        else:
            kita_ia = KitaIAService(tenant_user.tenant, request.user)

        # Process message
        result = kita_ia.process_user_message(conversation, message)

        return JsonResponse({
            'success': True,
            'conversation_id': str(conversation.conversation_id)
            # No immediate_response - all responses via SSE only
        })

    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='ai_error',
            status=500
        )


@login_required
@tenant_required()
@require_http_methods(["POST"])
@ratelimit(key='user', rate='10/m', method='POST')
@transaction.atomic
def confirm_link(request: HttpRequest) -> JsonResponse:
    """Confirm link creation.

    Confirms and creates the payment link from conversation data.
    Rate limited to 10 confirmations per minute per user.

    Args:
        request: HTTP request with conversation_id and action

    Returns:
        JSON response with created link details
    """
    tenant_user = TenantUser.objects.select_related('tenant').filter(
        email=request.user.email,
        is_owner=True
    ).first()

    if not tenant_user:
        return ErrorResponseBuilder.build_error(
            message='No tenant found',
            code='tenant_not_found',
            status=400
        )

    try:
        data = json.loads(request.body)
        conversation_id = data.get('conversation_id')
        action = data.get('action')

        if action != 'confirm':
            return ErrorResponseBuilder.build_error(
                message='Acción inválida',
                code='validation_error',
                status=400
            )

        kita_ia = KitaIAService(tenant_user.tenant, request.user)
        result = kita_ia.confirm_link_creation(conversation_id)

        return JsonResponse({
            'success': True,
            'result': result
        })

    except Exception as e:
        logger.error(f"Error confirming link: {e}")
        return ErrorResponseBuilder.build_error(
            message=str(e),
            code='confirmation_error',
            status=500
        )