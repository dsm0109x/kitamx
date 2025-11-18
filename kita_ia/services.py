"""Kita IA Service for natural language link creation.

Integrates with DeepInfra API using Meta Llama model for processing
natural language requests to create payment links.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any
import json
import logging
import secrets
from decimal import Decimal
from datetime import timedelta

import requests
from django.utils import timezone
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from .models import Conversation, ChatMessage
from payments.models import PaymentLink
from core.notifications import notification_service
from core.models import AuditLog

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from core.models import Tenant

logger = logging.getLogger(__name__)


class KitaIAService:
    """Service for AI-powered link creation.

    Handles conversation management, AI integration, and payment link creation
    through natural language processing.
    """

    def __init__(self, tenant: Tenant, user: User) -> None:
        """Initialize KitaIA service.

        Args:
            tenant: Current tenant context
            user: Current authenticated user
        """
        self.tenant = tenant
        self.user = user
        self.api_key = getattr(settings, 'DEEPINFRA_API_KEY', None)
        if not self.api_key:
            raise ValueError("DEEPINFRA_API_KEY must be configured in settings")
        self.api_url = "https://api.deepinfra.com/v1/openai/chat/completions"

    @transaction.atomic
    def create_conversation(self, ip_address: str, user_agent: str) -> Conversation:
        """Create new conversation.

        Args:
            ip_address: Client IP address
            user_agent: Client user agent string

        Returns:
            Newly created conversation instance
        """
        conversation = Conversation.objects.create(
            tenant=self.tenant,
            user_email=self.user.email,
            user_name=self.user.get_full_name() or self.user.email,
            ip_address=ip_address,
            user_agent=user_agent
        )

        # Add welcome message
        self.add_system_message(
            conversation,
            "¡Hola! Soy tu asistente de Kita. Puedo ayudarte a crear links de pago usando lenguaje natural. "
            "Por ejemplo: 'Crea un link de $500 para Juan Pérez por consultoría que expire en 3 días'"
        )

        return conversation

    @transaction.atomic
    def process_user_message(self, conversation: Conversation, message: str) -> Dict[str, Any]:
        """Process user message and generate AI response.

        Args:
            conversation: Current conversation instance
            message: User's message text

        Returns:
            Response dictionary with type and content
        """
        # Add user message
        user_msg = ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=conversation,
            message_type='user',
            content=message
        )

        # Check if conversation has pending link data for context
        context_prompt = ""
        if conversation.link_data and not conversation.link_created:
            context_prompt = f"\n\nCONTEXTO ACTUAL: {json.dumps(conversation.link_data, ensure_ascii=False)}"

        # Analyze message with AI
        try:
            ai_response = self._call_deepinfra_api(conversation, message, context_prompt)
            return self._process_ai_response(conversation, ai_response, message)

        except Exception as e:
            logger.error(f"Error processing AI message: {e}")
            error_msg = ChatMessage.objects.create(
                tenant=self.tenant,
                conversation=conversation,
                message_type='assistant',
                content="Lo siento, tuve un problema procesando tu mensaje. ¿Puedes intentar de nuevo?"
            )
            return {'type': 'assistant_message', 'message': error_msg.content}

    def _call_deepinfra_api(
        self,
        conversation: Conversation,
        message: str,
        context_prompt: str = ""
    ) -> str:
        """Call DeepInfra API for natural language processing.

        Args:
            conversation: Current conversation
            message: User message to process
            context_prompt: Additional context for AI

        Returns:
            AI response content

        Raises:
            Exception: If API call fails
        """
        # Check cache for similar recent messages (usando primeros 50 chars como key)
        import hashlib
        message_key = hashlib.md5(message[:50].encode()).hexdigest()
        cache_key = f"kita_ia:api:{self.tenant.id}:{message_key}"
        cached_response = cache.get(cache_key)
        if cached_response and not context_prompt:
            logger.info(f"Cache hit for message: {message[:30]}...")
            return cached_response

        # Get conversation history for context with prefetch
        recent_messages = conversation.messages.filter(
            message_type__in=['user', 'assistant']
        ).order_by('-created_at')[:10]

        messages = [
            {
                "role": "system",
                "content": f"""Asistente Kita: crea links de pago. Responde SOLO JSON válido.

Si tienes título Y monto → CREAR link
Si falta título → PREGUNTAR título
Si falta monto → PREGUNTAR monto

JSON válidos:
{{"action": "create_link", "data": {{"title": "Servicio", "amount": 100}}}}
{{"action": "ask_question", "message": "¿Para qué servicio es el cobro?"}}
{{"action": "update_context", "data": {{"customer_name": "Diego"}}, "message": "Cliente actualizado."}}

Contexto actual: {context_prompt}"""
            }
        ]

        # Add conversation history
        for msg in reversed(recent_messages):
            role = "user" if msg.message_type == "user" else "assistant"
            messages.append({"role": role, "content": msg.content})

        # Add current message
        messages.append({"role": "user", "content": message})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "messages": messages,
            "max_tokens": 300,  # Reduced for faster response
            "temperature": 0.3,  # More deterministic
            "stream": False  # No streaming for faster response
        }

        response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            ai_content = response.json()['choices'][0]['message']['content']
            # Cache successful responses for 1 minute
            if not context_prompt:
                cache.set(cache_key, ai_content, 60)
            return ai_content
        else:
            logger.error(f"DeepInfra API error: {response.status_code} - {response.text}")
            raise Exception("Error de API. Intenta de nuevo.")

    def _process_ai_response(
        self,
        conversation: Conversation,
        ai_response: str,
        original_message: str
    ) -> Dict[str, Any]:
        """Process AI response and determine action.

        Args:
            conversation: Current conversation
            ai_response: Raw AI response text
            original_message: Original user message

        Returns:
            Action response dictionary
        """

        try:
            # Extract JSON from AI response (handle duplicated JSON)
            ai_response_clean = ai_response.strip()

            # Split by newlines and take first valid JSON
            lines = ai_response_clean.split('\n')
            response_data = None

            for line in lines:
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        response_data = json.loads(line)
                        break  # Use first valid JSON
                    except json.JSONDecodeError:
                        continue

            if response_data:
                action = response_data.get('action')

                if action == 'create_link':
                    return self._handle_create_link(conversation, response_data.get('data', {}))
                elif action == 'ask_question':
                    # Sanitizar output del IA
                    import html
                    raw_message = response_data.get('message', 'Pregunta sin contenido')
                    sanitized_message = html.escape(raw_message)

                    assistant_msg = ChatMessage.objects.create(
                        tenant=self.tenant,
                        conversation=conversation,
                        message_type='assistant',
                        content=sanitized_message
                    )
                    return {'type': 'assistant_message', 'message': assistant_msg.content}
                elif action == 'update_context':
                    return self._handle_context_update(conversation, response_data)
                else:
                    # Unknown action
                    logger.warning(f"Unknown action: {action}")
                    assistant_msg = ChatMessage.objects.create(
                        tenant=self.tenant,
                        conversation=conversation,
                        message_type='assistant',
                        content=f"Acción desconocida: {action}"
                    )
                    return {'type': 'assistant_message', 'message': assistant_msg.content}
            else:
                # No valid JSON found
                logger.warning(f"No valid JSON found in AI response: {ai_response}")
                assistant_msg = ChatMessage.objects.create(
                    tenant=self.tenant,
                    conversation=conversation,
                    message_type='assistant',
                    content="No pude procesar tu mensaje. Intenta: 'Link de $500 para consultoría'"
                )
                return {'type': 'assistant_message', 'message': assistant_msg.content}

        except Exception as e:
            logger.error(f"Error processing AI response: {e}")
            assistant_msg = ChatMessage.objects.create(
                tenant=self.tenant,
                conversation=conversation,
                message_type='assistant',
                content="Error procesando respuesta. ¿Puedes intentar de nuevo?"
            )
            return {'type': 'assistant_message', 'message': assistant_msg.content}

    @transaction.atomic
    def _handle_create_link(self, conversation: Conversation, link_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle link creation request.

        Args:
            conversation: Current conversation
            link_data: Link creation data from AI

        Returns:
            Link preview response dictionary
        """
        try:
            # Validate required fields
            if not link_data.get('title') or not link_data.get('amount'):
                raise ValueError("Faltan datos obligatorios")

            # Clean and validate data with explicit defaults
            title = str(link_data.get('title', '')).strip()

            # Validar título
            if not title:
                raise ValueError("Falta el título")
            if len(title) < 3:
                raise ValueError("El título debe tener al menos 3 caracteres")
            if len(title) > 255:
                raise ValueError("El título no puede exceder 255 caracteres")

            amount = Decimal(str(link_data.get('amount', 0)))
            description = str(link_data.get('description', '')).strip()

            # Validar descripción
            if len(description) > 500:
                description = description[:500]

            customer_name = str(link_data.get('customer_name', '')).strip()

            # Validar nombre
            if len(customer_name) > 255:
                customer_name = customer_name[:255]

            customer_email = str(link_data.get('customer_email', '')).strip().lower()

            # Validar email si existe
            if customer_email:
                import re
                if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', customer_email):
                    raise ValueError("Formato de email inválido")
                if len(customer_email) > 254:
                    customer_email = customer_email[:254]

            expires_days = int(link_data.get('expires_days', 3))
            requires_invoice = bool(link_data.get('requires_invoice', False))

            # Validate amount
            if amount <= 0:
                raise ValueError("El monto debe ser mayor a cero")
            if amount > 999999:
                raise ValueError("El monto máximo es $999,999 MXN")

            # Validate expires_days (whitelist)
            if expires_days not in [1, 3, 7]:
                expires_days = 3

            # Store link data in conversation for confirmation
            conversation.link_data = {
                'title': title,
                'amount': float(amount),
                'description': description,
                'customer_name': customer_name,
                'customer_email': customer_email,
                'expires_days': expires_days,
                'requires_invoice': requires_invoice
            }
            conversation.save()

            # Add preview message
            preview_msg = ChatMessage.objects.create(
                tenant=self.tenant,
                conversation=conversation,
                message_type='link_preview',
                content="Vista previa del link de pago",
                metadata=conversation.link_data
            )

            # Add conversation_id to link_data for frontend
            preview_data = conversation.link_data.copy()
            preview_data['conversation_id'] = str(conversation.conversation_id)

            return {
                'type': 'link_preview',
                'link_data': preview_data,
                'conversation_id': str(conversation.conversation_id)
            }

        except Exception as e:
            logger.error(f"Error handling link creation: {e}")
            error_msg = ChatMessage.objects.create(
                tenant=self.tenant,
                conversation=conversation,
                message_type='assistant',
                content=f"Error procesando datos: {str(e)}. ¿Puedes verificar la información?"
            )
            return {'type': 'assistant_message', 'message': error_msg.content}

    @transaction.atomic
    def confirm_link_creation(self, conversation_id: str) -> Dict[str, Any]:
        """Confirm and create the payment link.

        Args:
            conversation_id: UUID of conversation to confirm

        Returns:
            Link creation result dictionary
        """
        try:
            conversation = Conversation.objects.select_related(
                'tenant', 'payment_link'
            ).get(
                conversation_id=conversation_id,
                tenant=self.tenant
            )

            if not conversation.link_data:
                raise ValueError("No hay datos de link para crear")

            # Generate unique token
            token = secrets.token_urlsafe(16)

            # Calculate expiry
            expires_at = timezone.now() + timedelta(days=conversation.link_data['expires_days'])

            # Create payment link
            payment_link = PaymentLink.objects.create(
                tenant=self.tenant,
                token=token,
                title=conversation.link_data['title'],
                description=conversation.link_data['description'],
                amount=conversation.link_data['amount'],
                customer_name=conversation.link_data['customer_name'],
                customer_email=conversation.link_data['customer_email'],
                requires_invoice=conversation.link_data['requires_invoice'],
                expires_at=expires_at
            )

            # Update conversation and clear context for next link
            conversation.payment_link = payment_link
            conversation.link_created = True
            conversation.status = 'completed'
            conversation.link_data = {}  # Clear context for new links
            conversation.save()

            # Send notification if customer email provided
            if payment_link.customer_email:
                try:
                    notification_service.send_payment_link_created(
                        payment_link,
                        recipient_email=payment_link.customer_email
                    )
                except Exception as e:
                    logger.error(f"Failed to send notification: {e}")

            # Log audit action
            AuditLog.objects.create(
                tenant=self.tenant,
                user_email=self.user.email,
                user_name=self.user.get_full_name() or self.user.email,
                action='create',
                entity_type='PaymentLink',
                entity_id=payment_link.id,
                entity_name=payment_link.title,
                ip_address=conversation.ip_address,
                user_agent=conversation.user_agent,
                new_values=conversation.link_data,
                notes='Payment link created via Kita IA'
            )

            # Add success message
            success_msg = ChatMessage.objects.create(
                tenant=self.tenant,
                conversation=conversation,
                message_type='link_created',
                content="Link creado exitosamente",
                metadata={
                    'link_id': str(payment_link.id),
                    'token': payment_link.token,
                    'url': f"{settings.APP_BASE_URL}/hola/{payment_link.token}/"
                }
            )

            return {
                'type': 'link_created',
                'link_data': {
                    'id': str(payment_link.id),
                    'token': payment_link.token,
                    'url': f"{settings.APP_BASE_URL}/hola/{payment_link.token}/",
                    'title': payment_link.title,
                    'amount': float(payment_link.amount)
                }
            }

        except Exception as e:
            logger.error(f"Error confirming link creation: {e}")
            return {'type': 'error', 'message': str(e)}

    @transaction.atomic
    def _handle_context_update(
        self,
        conversation: Conversation,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle context update (modify existing link data).

        Args:
            conversation: Current conversation
            response_data: Update data from AI

        Returns:
            Update response dictionary
        """
        try:
            # Merge new data with existing context
            current_data = conversation.link_data or {}
            new_data = response_data.get('data', {})

            # Update context
            current_data.update(new_data)
            conversation.link_data = current_data
            conversation.save()

            # Add assistant response (sanitizado)
            import html
            raw_message = response_data.get('message', 'Contexto actualizado.')
            sanitized_message = html.escape(raw_message)

            assistant_msg = ChatMessage.objects.create(
                tenant=self.tenant,
                conversation=conversation,
                message_type='assistant',
                content=sanitized_message
            )

            return {'type': 'assistant_message', 'message': assistant_msg.content}

        except Exception as e:
            logger.error(f"Error updating context: {e}")
            return {'type': 'assistant_message', 'message': 'Error actualizando contexto. Intenta de nuevo.'}

    @transaction.atomic
    def _handle_confirm_context(
        self,
        conversation: Conversation,
        response_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle context confirmation (show preview).

        Args:
            conversation: Current conversation
            response_data: Confirmation data from AI

        Returns:
            Confirmation response dictionary
        """
        try:
            # Update final context if provided
            if response_data.get('data'):
                current_data = conversation.link_data or {}
                current_data.update(response_data['data'])
                conversation.link_data = current_data
                conversation.save()

            return self._handle_create_link(conversation, conversation.link_data)

        except Exception as e:
            logger.error(f"Error confirming context: {e}")
            return {'type': 'assistant_message', 'message': 'Error confirmando contexto. Intenta de nuevo.'}

    def add_system_message(self, conversation: Conversation, content: str) -> ChatMessage:
        """Add system message to conversation.

        Args:
            conversation: Target conversation
            content: System message content

        Returns:
            Created ChatMessage instance
        """
        return ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=conversation,
            message_type='system',
            content=content
        )