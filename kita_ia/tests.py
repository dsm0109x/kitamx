"""Tests for Kita IA module.

Comprehensive test coverage for AI-powered payment link creation,
including conversation management, SSE streaming, and AI integration.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import json
import uuid
from unittest.mock import patch, Mock
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.test_utils import KitaTestCase
from payments.models import PaymentLink
from .models import Conversation, ChatMessage
from .services import KitaIAService

if TYPE_CHECKING:
    from django.contrib.auth.models import User

User = get_user_model()


class ConversationModelTests(KitaTestCase):
    """Tests for Conversation model."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            user_email="test@example.com",
            user_name="Test User",
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )

    def test_conversation_creation(self) -> None:
        """Test conversation is created with correct defaults."""
        self.assertIsNotNone(self.conversation.conversation_id)
        self.assertEqual(self.conversation.status, 'active')
        self.assertFalse(self.conversation.link_created)
        self.assertEqual(self.conversation.link_data, {})

    def test_conversation_str(self) -> None:
        """Test string representation."""
        expected = f"Conversation {self.conversation.conversation_id} - Test User"
        self.assertEqual(str(self.conversation), expected)

    def test_get_message_count(self) -> None:
        """Test message count method."""
        self.assertEqual(self.conversation.get_message_count(), 0)

        ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='user',
            content='Test message'
        )

        self.assertEqual(self.conversation.get_message_count(), 1)

    def test_get_last_message(self) -> None:
        """Test getting last message."""
        self.assertIsNone(self.conversation.get_last_message())

        msg1 = ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='user',
            content='First message'
        )

        msg2 = ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='assistant',
            content='Second message'
        )

        self.assertEqual(self.conversation.get_last_message(), msg2)

    def test_mark_completed(self) -> None:
        """Test marking conversation as completed."""
        self.assertEqual(self.conversation.status, 'active')
        self.conversation.mark_completed()
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, 'completed')

    def test_queryset_active(self) -> None:
        """Test active conversations queryset."""
        active = Conversation.objects.active().count()
        self.assertEqual(active, 1)

        self.conversation.status = 'completed'
        self.conversation.save()

        active = Conversation.objects.active().count()
        self.assertEqual(active, 0)

    def test_queryset_completed(self) -> None:
        """Test completed conversations queryset."""
        completed = Conversation.objects.completed().count()
        self.assertEqual(completed, 0)

        self.conversation.status = 'completed'
        self.conversation.save()

        completed = Conversation.objects.completed().count()
        self.assertEqual(completed, 1)

    def test_queryset_by_user(self) -> None:
        """Test filtering by user email."""
        conversations = Conversation.objects.by_user('test@example.com').count()
        self.assertEqual(conversations, 1)

        conversations = Conversation.objects.by_user('other@example.com').count()
        self.assertEqual(conversations, 0)

    def test_queryset_recent(self) -> None:
        """Test recent conversations queryset."""
        recent = Conversation.objects.recent(hours=1).count()
        self.assertEqual(recent, 1)

        # Create old conversation
        old_conversation = Conversation.objects.create(
            tenant=self.tenant,
            user_email="old@example.com",
            user_name="Old User",
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )
        old_conversation.created_at = timezone.now() - timedelta(hours=25)
        old_conversation.save()

        recent = Conversation.objects.recent(hours=24).count()
        self.assertEqual(recent, 1)  # Only new conversation


class ChatMessageModelTests(KitaTestCase):
    """Tests for ChatMessage model."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.conversation = Conversation.objects.create(
            tenant=self.tenant,
            user_email="test@example.com",
            user_name="Test User",
            ip_address="127.0.0.1",
            user_agent="Test Agent"
        )
        self.message = ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='user',
            content='Test message content'
        )

    def test_message_creation(self) -> None:
        """Test message is created with correct defaults."""
        self.assertFalse(self.message.processed)
        self.assertIsNone(self.message.processing_time)
        self.assertEqual(self.message.metadata, {})

    def test_message_str(self) -> None:
        """Test string representation."""
        self.assertEqual(str(self.message), "user: Test message content...")

    def test_mark_processed(self) -> None:
        """Test marking message as processed."""
        self.assertFalse(self.message.processed)
        self.message.mark_processed(processing_time=1.5)
        self.message.refresh_from_db()
        self.assertTrue(self.message.processed)
        self.assertEqual(self.message.processing_time, 1.5)

    def test_get_formatted_content(self) -> None:
        """Test formatted content for different message types."""
        self.assertEqual(self.message.get_formatted_content(), 'Test message content')

        preview_msg = ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='link_preview',
            content='Preview content'
        )
        self.assertEqual(preview_msg.get_formatted_content(), 'Vista previa del enlace de pago')

        created_msg = ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='link_created',
            content='Created content'
        )
        self.assertEqual(created_msg.get_formatted_content(), '¡Enlace creado exitosamente!')

    def test_queryset_user_messages(self) -> None:
        """Test filtering user messages."""
        ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='assistant',
            content='Assistant message'
        )

        user_messages = ChatMessage.objects.user_messages().count()
        self.assertEqual(user_messages, 1)

    def test_queryset_assistant_messages(self) -> None:
        """Test filtering assistant messages."""
        ChatMessage.objects.create(
            tenant=self.tenant,
            conversation=self.conversation,
            message_type='assistant',
            content='Assistant message'
        )

        assistant_messages = ChatMessage.objects.assistant_messages().count()
        self.assertEqual(assistant_messages, 1)

    def test_queryset_processed(self) -> None:
        """Test filtering processed messages."""
        processed = ChatMessage.objects.processed().count()
        self.assertEqual(processed, 0)

        self.message.mark_processed()
        processed = ChatMessage.objects.processed().count()
        self.assertEqual(processed, 1)


class KitaIAServiceTests(KitaTestCase):
    """Tests for KitaIA service."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()
        self.service = KitaIAService(self.tenant, self.user)

    def test_service_initialization(self) -> None:
        """Test service initialization."""
        self.assertEqual(self.service.tenant, self.tenant)
        self.assertEqual(self.service.user, self.user)
        self.assertIsNotNone(self.service.api_key)
        self.assertIsNotNone(self.service.api_url)

    def test_create_conversation(self) -> None:
        """Test conversation creation."""
        conversation = self.service.create_conversation(
            ip_address='127.0.0.1',
            user_agent='Test Agent'
        )

        self.assertIsNotNone(conversation)
        self.assertEqual(conversation.tenant, self.tenant)
        self.assertEqual(conversation.user_email, self.user.email)
        self.assertEqual(conversation.ip_address, '127.0.0.1')

        # Check welcome message was added
        messages = conversation.messages.filter(message_type='system')
        self.assertEqual(messages.count(), 1)

    @patch('kita_ia.services.requests.post')
    def test_call_deepinfra_api_success(self, mock_post: Mock) -> None:
        """Test successful API call to DeepInfra."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': '{"action": "ask_question", "message": "¿Cuál es el monto?"}'
                }
            }]
        }
        mock_post.return_value = mock_response

        conversation = self.service.create_conversation('127.0.0.1', 'Test Agent')
        result = self.service._call_deepinfra_api(conversation, 'Crear link')

        self.assertIn('action', result)
        mock_post.assert_called_once()

    @patch('kita_ia.services.requests.post')
    def test_call_deepinfra_api_failure(self, mock_post: Mock) -> None:
        """Test API call failure handling."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = 'Internal Server Error'
        mock_post.return_value = mock_response

        conversation = self.service.create_conversation('127.0.0.1', 'Test Agent')

        with self.assertRaises(Exception) as context:
            self.service._call_deepinfra_api(conversation, 'Test message')

        self.assertIn('Error de API', str(context.exception))

    def test_handle_create_link_valid(self) -> None:
        """Test handling valid link creation."""
        conversation = self.service.create_conversation('127.0.0.1', 'Test Agent')

        link_data = {
            'title': 'Test Service',
            'amount': 500,
            'description': 'Test description',
            'customer_name': 'John Doe',
            'customer_email': 'john@example.com',
            'expires_days': 3,
            'requires_invoice': True
        }

        result = self.service._handle_create_link(conversation, link_data)

        self.assertEqual(result['type'], 'link_preview')
        self.assertIn('link_data', result)
        self.assertEqual(result['link_data']['title'], 'Test Service')
        self.assertEqual(result['link_data']['amount'], 500)

        conversation.refresh_from_db()
        self.assertEqual(conversation.link_data['title'], 'Test Service')

    def test_handle_create_link_invalid(self) -> None:
        """Test handling invalid link creation."""
        conversation = self.service.create_conversation('127.0.0.1', 'Test Agent')

        # Missing required fields
        link_data = {'description': 'Test'}

        result = self.service._handle_create_link(conversation, link_data)

        self.assertEqual(result['type'], 'assistant_message')
        self.assertIn('Error', result['message'])

    @patch('kita_ia.services.notification_service.send_payment_link_created')
    def test_confirm_link_creation(self, mock_notify: Mock) -> None:
        """Test confirming and creating payment link."""
        conversation = self.service.create_conversation('127.0.0.1', 'Test Agent')
        conversation.link_data = {
            'title': 'Test Service',
            'amount': 500,
            'description': 'Test',
            'customer_name': 'John',
            'customer_email': 'john@example.com',
            'expires_days': 3,
            'requires_invoice': False
        }
        conversation.save()

        result = self.service.confirm_link_creation(str(conversation.conversation_id))

        self.assertEqual(result['type'], 'link_created')
        self.assertIn('link_data', result)
        self.assertIn('token', result['link_data'])
        self.assertIn('url', result['link_data'])

        conversation.refresh_from_db()
        self.assertTrue(conversation.link_created)
        self.assertEqual(conversation.status, 'completed')
        self.assertIsNotNone(conversation.payment_link)

        # Check payment link was created
        payment_link = PaymentLink.objects.get(id=conversation.payment_link.id)
        self.assertEqual(payment_link.title, 'Test Service')
        self.assertEqual(payment_link.amount, 500)

    def test_handle_context_update(self) -> None:
        """Test updating conversation context."""
        conversation = self.service.create_conversation('127.0.0.1', 'Test Agent')
        conversation.link_data = {'title': 'Original'}
        conversation.save()

        response_data = {
            'data': {'amount': 1000},
            'message': 'Monto actualizado'
        }

        result = self.service._handle_context_update(conversation, response_data)

        self.assertEqual(result['type'], 'assistant_message')
        self.assertEqual(result['message'], 'Monto actualizado')

        conversation.refresh_from_db()
        self.assertEqual(conversation.link_data['title'], 'Original')
        self.assertEqual(conversation.link_data['amount'], 1000)


class KitaIAViewTests(KitaTestCase):
    """Tests for Kita IA views using common test base."""

    def test_kita_ia_index_view(self) -> None:
        """Test main Kita IA page."""
        url = reverse('kita_ia:index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kita IA')
        self.assertIn('stats', response.context)

    def test_kita_ia_index_redirect_no_tenant(self) -> None:
        """Test redirect when user has no tenant."""
        self.tenant_user.delete()
        url = reverse('kita_ia:index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/incorporacion/', response.url)  # 🇪🇸 Migrado (onboarding:start)

    @patch('kita_ia.services.KitaIAService.process_user_message')
    def test_send_message_success(self, mock_process: Mock) -> None:
        """Test sending message successfully."""
        mock_process.return_value = {
            'type': 'assistant_message',
            'message': 'Test response'
        }

        url = reverse('kita_ia:send_message')
        data = {'message': 'Create a link for $500'}

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        self.assertIn('conversation_id', result)

    def test_send_message_empty(self) -> None:
        """Test sending empty message."""
        url = reverse('kita_ia:send_message')
        data = {'message': ''}

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result['success'])
        self.assertIn('Mensaje vacío', result['error'])

    @patch('kita_ia.services.KitaIAService.confirm_link_creation')
    def test_confirm_link_success(self, mock_confirm: Mock) -> None:
        """Test confirming link creation."""
        mock_confirm.return_value = {
            'type': 'link_created',
            'link_data': {
                'token': 'test_token',
                'url': 'http://example.com/link'
            }
        }

        url = reverse('kita_ia:confirm_link')
        data = {
            'conversation_id': str(uuid.uuid4()),
            'action': 'confirm'
        }

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        self.assertIn('result', result)

    def test_confirm_link_invalid_action(self) -> None:
        """Test confirming link with invalid action."""
        url = reverse('kita_ia:confirm_link')
        data = {
            'conversation_id': str(uuid.uuid4()),
            'action': 'invalid'
        }

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertFalse(result['success'])
        self.assertIn('Acción inválida', result['error'])

    def test_chat_stream_sse(self) -> None:
        """Test SSE streaming endpoint."""
        url = reverse('kita_ia:chat_stream')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        self.assertEqual(response['Cache-Control'], 'no-cache')


class KitaIAIntegrationTests(KitaTestCase):
    """Integration tests for complete Kita IA flow."""

    def setUp(self) -> None:
        """Set up test data."""
        super().setUp()

    @patch('kita_ia.services.requests.post')
    @patch('kita_ia.services.notification_service.send_payment_link_created')
    def test_complete_link_creation_flow(self, mock_notify: Mock, mock_api: Mock) -> None:
        """Test complete flow from message to link creation."""
        # Mock AI responses
        mock_api.return_value.status_code = 200
        mock_api.return_value.json.return_value = {
            'choices': [{
                'message': {
                    'content': json.dumps({
                        'action': 'create_link',
                        'data': {
                            'title': 'Consultoría',
                            'amount': 500,
                            'description': 'Servicio de consultoría',
                            'customer_name': 'Juan Pérez',
                            'expires_days': 3
                        }
                    })
                }
            }]
        }

        # Step 1: Send initial message
        url = reverse('kita_ia:send_message')
        data = {'message': 'Crear link de $500 para consultoría de Juan Pérez'}

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])
        conversation_id = result['conversation_id']

        # Verify conversation was created
        conversation = Conversation.objects.get(conversation_id=conversation_id)
        self.assertEqual(conversation.status, 'active')
        self.assertIn('title', conversation.link_data)
        self.assertEqual(conversation.link_data['title'], 'Consultoría')

        # Step 2: Confirm link creation
        url = reverse('kita_ia:confirm_link')
        data = {
            'conversation_id': conversation_id,
            'action': 'confirm'
        }

        response = self.client.post(
            url,
            json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertTrue(result['success'])

        # Verify link was created
        conversation.refresh_from_db()
        self.assertTrue(conversation.link_created)
        self.assertEqual(conversation.status, 'completed')
        self.assertIsNotNone(conversation.payment_link)

        payment_link = conversation.payment_link
        self.assertEqual(payment_link.title, 'Consultoría')
        self.assertEqual(payment_link.amount, 500)
        self.assertEqual(payment_link.customer_name, 'Juan Pérez')