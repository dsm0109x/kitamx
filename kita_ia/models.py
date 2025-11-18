"""Models for Kita IA - AI-powered payment link creation.

Handles conversation tracking and natural language processing for
creating payment links through AI chat interface.
"""
from __future__ import annotations
from typing import Optional
import uuid

from django.db import models
from django.db.models import QuerySet, Manager
from django.utils import timezone

from core.models import TenantModel


class ConversationQuerySet(models.QuerySet):
    """Custom QuerySet for Conversation model."""

    def active(self) -> QuerySet[Conversation]:
        """Get active conversations."""
        return self.filter(status='active')

    def completed(self) -> QuerySet[Conversation]:
        """Get completed conversations."""
        return self.filter(status='completed')

    def by_user(self, email: str) -> QuerySet[Conversation]:
        """Filter conversations by user email."""
        return self.filter(user_email=email)

    def with_messages(self) -> QuerySet[Conversation]:
        """Prefetch related messages."""
        return self.prefetch_related('messages')

    def recent(self, hours: int = 24) -> QuerySet[Conversation]:
        """Get recent conversations within specified hours."""
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(hours=hours)
        return self.filter(created_at__gte=cutoff)


class ConversationManager(Manager):
    """Custom manager for Conversation model."""

    def get_queryset(self) -> ConversationQuerySet:
        return ConversationQuerySet(self.model, using=self._db)

    def active(self) -> QuerySet[Conversation]:
        return self.get_queryset().active()

    def completed(self) -> QuerySet[Conversation]:
        return self.get_queryset().completed()


class Conversation(TenantModel):
    """Chat conversation with Kita IA"""

    conversation_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    user_email = models.EmailField()
    user_name = models.CharField(max_length=255)

    # Conversation state
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('abandoned', 'Abandoned'),
        ],
        default='active'
    )

    # Link creation context
    link_data = models.JSONField(default=dict, blank=True)
    link_created = models.BooleanField(default=False)
    payment_link = models.ForeignKey(
        'payments.PaymentLink',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )

    # Metadata
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()

    objects = ConversationManager()

    class Meta:
        db_table = 'kita_ia_conversations'
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['conversation_id']),
            models.Index(fields=['user_email']),
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['tenant', 'user_email', '-created_at']),
        ]
        ordering = ['-created_at']
        verbose_name = 'IA Conversation'
        verbose_name_plural = 'IA Conversations'

    def __str__(self) -> str:
        return f"Conversation {self.conversation_id} - {self.user_name}"

    def get_message_count(self) -> int:
        """Get total number of messages in conversation."""
        return self.messages.count()

    def get_last_message(self) -> Optional[ChatMessage]:
        """Get the last message in the conversation."""
        return self.messages.order_by('-created_at').first()

    def mark_completed(self) -> None:
        """Mark conversation as completed."""
        self.status = 'completed'
        self.save(update_fields=['status', 'updated_at'])


class ChatMessageQuerySet(models.QuerySet):
    """Custom QuerySet for ChatMessage model."""

    def user_messages(self) -> QuerySet[ChatMessage]:
        """Get user messages only."""
        return self.filter(message_type='user')

    def assistant_messages(self) -> QuerySet[ChatMessage]:
        """Get assistant messages only."""
        return self.filter(message_type='assistant')

    def processed(self) -> QuerySet[ChatMessage]:
        """Get processed messages."""
        return self.filter(processed=True)

    def by_conversation(self, conversation_id: uuid.UUID) -> QuerySet[ChatMessage]:
        """Filter messages by conversation."""
        return self.filter(conversation__conversation_id=conversation_id)


class ChatMessageManager(Manager):
    """Custom manager for ChatMessage model."""

    def get_queryset(self) -> ChatMessageQuerySet:
        return ChatMessageQuerySet(self.model, using=self._db)

    def user_messages(self) -> QuerySet[ChatMessage]:
        return self.get_queryset().user_messages()

    def assistant_messages(self) -> QuerySet[ChatMessage]:
        return self.get_queryset().assistant_messages()


class ChatMessage(TenantModel):
    """Individual messages in chat conversation"""

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )

    # Message content
    message_type = models.CharField(
        max_length=20,
        choices=[
            ('user', 'User Message'),
            ('assistant', 'Assistant Message'),
            ('system', 'System Message'),
            ('link_preview', 'Link Preview'),
            ('link_created', 'Link Created'),
        ]
    )

    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)

    # Processing
    processed = models.BooleanField(default=False)
    processing_time = models.FloatField(null=True, blank=True)  # seconds

    objects = ChatMessageManager()

    class Meta:
        db_table = 'kita_ia_chat_messages'
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['conversation', 'message_type']),
            models.Index(fields=['processed']),
        ]
        ordering = ['created_at']
        verbose_name = 'Chat Message'
        verbose_name_plural = 'Chat Messages'

    def __str__(self) -> str:
        return f"{self.message_type}: {self.content[:50]}..."

    def mark_processed(self, processing_time: float = 0.0) -> None:
        """Mark message as processed."""
        self.processed = True
        self.processing_time = processing_time
        self.save(update_fields=['processed', 'processing_time', 'updated_at'])

    def get_formatted_content(self) -> str:
        """Get formatted content for display."""
        if self.message_type == 'link_preview':
            return "Vista previa del enlace de pago"
        elif self.message_type == 'link_created':
            return "¡Enlace creado exitosamente!"
        return self.content