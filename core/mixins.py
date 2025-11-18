"""
Centralized model mixins for the Kita application.

This module provides reusable model mixins to reduce code duplication
and ensure consistency across all models.
"""
from __future__ import annotations
import uuid
from typing import Optional, Dict, Any, TYPE_CHECKING
from django.db import models
from django.utils import timezone
from django.core.cache import cache

if TYPE_CHECKING:
    pass


class UUIDPrimaryKeyMixin(models.Model):
    """Mixin to add UUID primary key to models."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        db_index=True
    )

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    """Mixin to add created_at and updated_at timestamps."""

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp when record was last updated"
    )

    class Meta:
        abstract = True


class SoftDeleteMixin(models.Model):
    """Mixin to add soft delete functionality."""

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when record was soft deleted"
    )
    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether record is soft deleted"
    )

    class Meta:
        abstract = True

    def soft_delete(self):
        """Soft delete this record."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        """Restore soft deleted record."""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])


class StatusMixin(models.Model):
    """Mixin to add status field with common patterns."""

    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_PENDING = 'pending'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
        (STATUS_PENDING, 'Pending'),
        (STATUS_ARCHIVED, 'Archived'),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
        help_text="Current status of the record"
    )

    class Meta:
        abstract = True

    def is_active(self) -> bool:
        """Check if status is active."""
        return self.status == self.STATUS_ACTIVE

    def activate(self):
        """Set status to active."""
        self.status = self.STATUS_ACTIVE
        self.save(update_fields=['status'])

    def deactivate(self):
        """Set status to inactive."""
        self.status = self.STATUS_INACTIVE
        self.save(update_fields=['status'])

    def archive(self):
        """Set status to archived."""
        self.status = self.STATUS_ARCHIVED
        self.save(update_fields=['status'])


class MetadataMixin(models.Model):
    """Mixin to add JSON metadata field."""

    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata as JSON"
    )

    class Meta:
        abstract = True

    def set_metadata(self, key: str, value: Any) -> None:
        """Set a metadata key-value pair."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata[key] = value
        self.save(update_fields=['metadata'])

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get a metadata value by key."""
        if self.metadata is None:
            return default
        return self.metadata.get(key, default)

    def update_metadata(self, data: Dict[str, Any]) -> None:
        """Update multiple metadata keys."""
        if self.metadata is None:
            self.metadata = {}
        self.metadata.update(data)
        self.save(update_fields=['metadata'])


class IPAddressMixin(models.Model):
    """Mixin to track IP address and user agent."""

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        db_index=True,
        help_text="IP address of the request"
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        help_text="User agent string"
    )

    class Meta:
        abstract = True


class CacheableMixin:
    """Mixin to add caching functionality to models."""

    CACHE_TIMEOUT = 3600  # 1 hour default

    def get_cache_key(self, suffix: str = '') -> str:
        """Generate cache key for this model instance."""
        tenant_id = getattr(self, 'tenant_id', 'global')
        pk = getattr(self, 'pk', 'new')
        key = f"{self.__class__.__name__.lower()}:{tenant_id}:{pk}"
        if suffix:
            key = f"{key}:{suffix}"
        return key

    def cache_get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        cache_key = self.get_cache_key(key)
        return cache.get(cache_key, default)

    def cache_set(self, key: str, value: Any, timeout: Optional[int] = None) -> None:
        """Set value in cache."""
        cache_key = self.get_cache_key(key)
        cache.set(cache_key, value, timeout or self.CACHE_TIMEOUT)

    def cache_delete(self, key: str) -> None:
        """Delete value from cache."""
        cache_key = self.get_cache_key(key)
        cache.delete(cache_key)

    def invalidate_cache(self) -> None:
        """Invalidate all cache entries for this instance."""
        # This is a basic implementation - override for specific needs
        cache_key = self.get_cache_key()
        cache.delete(cache_key)


class OrderingMixin(models.Model):
    """Mixin to add ordering/position field."""

    order = models.IntegerField(
        default=0,
        db_index=True,
        help_text="Order/position for sorting"
    )

    class Meta:
        abstract = True
        ordering = ['order', '-created_at']


class ActivatableMixin(models.Model):
    """Mixin to add is_active field with activation methods."""

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether record is active"
    )
    activated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when record was activated"
    )
    deactivated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when record was deactivated"
    )

    class Meta:
        abstract = True

    def activate(self):
        """Activate this record."""
        self.is_active = True
        self.activated_at = timezone.now()
        self.deactivated_at = None
        self.save(update_fields=['is_active', 'activated_at', 'deactivated_at'])

    def deactivate(self):
        """Deactivate this record."""
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=['is_active', 'deactivated_at'])


class AuditMixin(models.Model):
    """Mixin to track who created/modified records."""

    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        help_text="User who created this record"
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        help_text="User who last updated this record"
    )

    class Meta:
        abstract = True


class VersionMixin(models.Model):
    """Mixin to add version tracking for optimistic locking."""

    version = models.IntegerField(
        default=1,
        help_text="Version number for optimistic locking"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Increment version on save."""
        if self.pk:  # Only increment on update
            self.version += 1
        super().save(*args, **kwargs)


class ExternalReferenceMixin(models.Model):
    """Mixin to track external system references."""

    external_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="ID in external system"
    )
    external_system = models.CharField(
        max_length=50,
        blank=True,
        help_text="Name of external system"
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['external_system', 'external_id'], name='idx_%(class)s_ext_ref'),
        ]


class TenantScopedMixin(models.Model):
    """Mixin to scope records to a tenant."""

    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
        db_index=True,
        help_text="Tenant this record belongs to"
    )

    class Meta:
        abstract = True
        indexes = [
            models.Index(fields=['tenant', '-created_at'], name='idx_%(class)s_tenant_created'),
        ]


class PublishableMixin(models.Model):
    """Mixin for content that can be published/unpublished."""

    is_published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether record is published"
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Timestamp when record was published"
    )
    unpublished_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when record was unpublished"
    )

    class Meta:
        abstract = True

    def publish(self):
        """Publish this record."""
        self.is_published = True
        self.published_at = timezone.now()
        self.unpublished_at = None
        self.save(update_fields=['is_published', 'published_at', 'unpublished_at'])

    def unpublish(self):
        """Unpublish this record."""
        self.is_published = False
        self.unpublished_at = timezone.now()
        self.save(update_fields=['is_published', 'unpublished_at'])


class SlugMixin(models.Model):
    """Mixin to add slug field."""

    slug = models.SlugField(
        max_length=255,
        db_index=True,
        help_text="URL-friendly slug"
    )

    class Meta:
        abstract = True


class DescriptionMixin(models.Model):
    """Mixin to add name and description fields."""

    name = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Name of the record"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of the record"
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


# Composite mixins for common combinations
class FullAuditMixin(TimestampMixin, AuditMixin, VersionMixin):
    """Complete audit trail with timestamps, users, and versions."""

    class Meta:
        abstract = True


class TenantOwnedMixin(TenantScopedMixin, TimestampMixin):
    """Tenant-scoped record with timestamps."""

    class Meta:
        abstract = True


class PublishableContentMixin(
    TimestampMixin,
    PublishableMixin,
    SlugMixin,
    DescriptionMixin,
    MetadataMixin
):
    """Complete mixin for publishable content."""

    class Meta:
        abstract = True


class SoftDeletableModelMixin(TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Soft-deletable model with full audit trail."""

    class Meta:
        abstract = True


# Export all mixins
__all__ = [
    'UUIDPrimaryKeyMixin',
    'TimestampMixin',
    'SoftDeleteMixin',
    'StatusMixin',
    'MetadataMixin',
    'IPAddressMixin',
    'CacheableMixin',
    'OrderingMixin',
    'ActivatableMixin',
    'AuditMixin',
    'VersionMixin',
    'ExternalReferenceMixin',
    'TenantScopedMixin',
    'PublishableMixin',
    'SlugMixin',
    'DescriptionMixin',
    'FullAuditMixin',
    'TenantOwnedMixin',
    'PublishableContentMixin',
    'SoftDeletableModelMixin',
]