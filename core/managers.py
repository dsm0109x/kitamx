"""
Centralized managers and querysets for the Kita application.

This module provides reusable managers and querysets to reduce duplication
and optimize database queries across all models.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from django.db import models
from django.db.models import QuerySet, Q
from django.core.exceptions import ValidationError
from django.utils import timezone

if TYPE_CHECKING:
    pass


class SoftDeleteQuerySet(QuerySet):
    """QuerySet for models with soft delete."""

    def active(self):
        """Return only non-deleted records."""
        return self.filter(is_deleted=False)

    def deleted(self):
        """Return only deleted records."""
        return self.filter(is_deleted=True)

    def with_deleted(self):
        """Return all records including deleted."""
        return self.all()

    def delete(self):
        """Soft delete all records in queryset."""
        return self.update(
            is_deleted=True,
            deleted_at=timezone.now()
        )

    def hard_delete(self):
        """Permanently delete records."""
        return super().delete()

    def restore(self):
        """Restore soft deleted records."""
        return self.update(
            is_deleted=False,
            deleted_at=None
        )


class TenantQuerySet(QuerySet):
    """QuerySet for tenant-scoped models."""

    def for_tenant(self, tenant):
        """Filter records for specific tenant."""
        if tenant is None:
            raise ValidationError("Tenant is required")
        return self.filter(tenant=tenant)

    def for_tenant_id(self, tenant_id):
        """Filter records for specific tenant ID."""
        if tenant_id is None:
            raise ValidationError("Tenant ID is required")
        return self.filter(tenant_id=tenant_id)


class ActiveQuerySet(QuerySet):
    """QuerySet for models with is_active field."""

    def active(self):
        """Return only active records."""
        return self.filter(is_active=True)

    def inactive(self):
        """Return only inactive records."""
        return self.filter(is_active=False)


class StatusQuerySet(QuerySet):
    """QuerySet for models with status field."""

    def with_status(self, status: str):
        """Filter by specific status."""
        return self.filter(status=status)

    def active(self):
        """Return records with active status."""
        return self.filter(status='active')

    def pending(self):
        """Return records with pending status."""
        return self.filter(status='pending')

    def archived(self):
        """Return records with archived status."""
        return self.filter(status='archived')


class PublishableQuerySet(QuerySet):
    """QuerySet for publishable models."""

    def published(self):
        """Return only published records."""
        return self.filter(is_published=True)

    def unpublished(self):
        """Return only unpublished records."""
        return self.filter(is_published=False)

    def publish_all(self):
        """Publish all records in queryset."""
        return self.update(
            is_published=True,
            published_at=timezone.now()
        )

    def unpublish_all(self):
        """Unpublish all records in queryset."""
        return self.update(
            is_published=False,
            unpublished_at=timezone.now()
        )


class TimestampQuerySet(QuerySet):
    """QuerySet for models with timestamps."""

    def created_after(self, date):
        """Filter records created after date."""
        return self.filter(created_at__gte=date)

    def created_before(self, date):
        """Filter records created before date."""
        return self.filter(created_at__lte=date)

    def updated_after(self, date):
        """Filter records updated after date."""
        return self.filter(updated_at__gte=date)

    def created_today(self):
        """Filter records created today."""
        today = timezone.now().date()
        return self.filter(created_at__date=today)

    def created_this_month(self):
        """Filter records created this month."""
        now = timezone.now()
        return self.filter(
            created_at__year=now.year,
            created_at__month=now.month
        )

    def recent(self, days: int = 7):
        """Filter records created in the last N days."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class CombinedTenantQuerySet(TenantQuerySet, TimestampQuerySet, ActiveQuerySet):
    """Combined queryset for tenant-scoped models with common filters."""
    pass


class SoftDeletableTenantQuerySet(SoftDeleteQuerySet, TenantQuerySet, TimestampQuerySet):
    """Combined queryset for soft-deletable tenant-scoped models."""
    pass


# Managers
class SoftDeleteManager(models.Manager):
    """Manager for models with soft delete."""

    def get_queryset(self):
        """Return queryset excluding soft deleted records by default."""
        return SoftDeleteQuerySet(self.model, using=self._db).active()

    def all_with_deleted(self):
        """Get all records including soft deleted."""
        return SoftDeleteQuerySet(self.model, using=self._db).with_deleted()

    def deleted_only(self):
        """Get only soft deleted records."""
        return SoftDeleteQuerySet(self.model, using=self._db).deleted()


class TenantManager(models.Manager):
    """Manager for tenant-scoped models."""

    def get_queryset(self):
        return TenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant):
        """Get records for specific tenant."""
        return self.get_queryset().for_tenant(tenant)

    def for_tenant_id(self, tenant_id):
        """Get records for specific tenant ID."""
        return self.get_queryset().for_tenant_id(tenant_id)


class ActiveManager(models.Manager):
    """Manager for models with is_active field."""

    def get_queryset(self):
        return ActiveQuerySet(self.model, using=self._db).active()

    def all_with_inactive(self):
        """Get all records including inactive."""
        return ActiveQuerySet(self.model, using=self._db)


class StatusManager(models.Manager):
    """Manager for models with status field."""

    def get_queryset(self):
        return StatusQuerySet(self.model, using=self._db)

    def active(self):
        """Get active records."""
        return self.get_queryset().active()

    def pending(self):
        """Get pending records."""
        return self.get_queryset().pending()


class PublishableManager(models.Manager):
    """Manager for publishable models."""

    def get_queryset(self):
        return PublishableQuerySet(self.model, using=self._db)

    def published(self):
        """Get published records."""
        return self.get_queryset().published()

    def unpublished(self):
        """Get unpublished records."""
        return self.get_queryset().unpublished()


class CombinedTenantManager(models.Manager):
    """Combined manager for tenant-scoped models."""

    def get_queryset(self):
        return CombinedTenantQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant):
        """Get records for specific tenant."""
        return self.get_queryset().for_tenant(tenant)

    def active(self):
        """Get active records."""
        return self.get_queryset().active()

    def recent(self, days: int = 7):
        """Get recent records."""
        return self.get_queryset().recent(days)


class OptimizedQuerySetMixin:
    """Mixin to add common query optimizations."""

    def with_related(self):
        """
        Apply common select_related optimizations.
        Override in specific querysets.
        """
        return self

    def with_prefetch(self):
        """
        Apply common prefetch_related optimizations.
        Override in specific querysets.
        """
        return self

    def optimized(self):
        """Apply all optimizations."""
        return self.with_related().with_prefetch()


class PaymentLinkQuerySet(TenantQuerySet, TimestampQuerySet, ActiveQuerySet, OptimizedQuerySetMixin):
    """Optimized queryset for PaymentLink model."""

    def with_related(self):
        """Optimize for common joins."""
        return self.select_related('tenant')

    def with_prefetch(self):
        """Optimize for common prefetches."""
        return self.prefetch_related('payments', 'analytics')

    def pending_payment(self):
        """Get links awaiting payment."""
        return self.filter(status='active', uses_count=0)

    def paid(self):
        """Get paid links."""
        return self.filter(status='paid')

    def expired(self):
        """Get expired links."""
        now = timezone.now()
        return self.filter(
            Q(expires_at__lte=now) | Q(status='expired')
        )


class PaymentQuerySet(TenantQuerySet, TimestampQuerySet, OptimizedQuerySetMixin):
    """Optimized queryset for Payment model."""

    def with_related(self):
        """Optimize for common joins."""
        return self.select_related('tenant', 'payment_link', 'invoice')

    def approved(self):
        """Get approved payments."""
        return self.filter(status='approved')

    def pending(self):
        """Get pending payments."""
        return self.filter(status='pending')

    def failed(self):
        """Get failed payments."""
        return self.filter(status__in=['rejected', 'cancelled'])

    def with_amount_gte(self, amount):
        """Filter by minimum amount."""
        return self.filter(amount__gte=amount)


class InvoiceQuerySet(TenantQuerySet, TimestampQuerySet, OptimizedQuerySetMixin):
    """Optimized queryset for Invoice model."""

    def with_related(self):
        """Optimize for common joins."""
        return self.select_related('tenant', 'payment')

    def stamped(self):
        """Get stamped invoices."""
        return self.filter(status='stamped')

    def pending_stamp(self):
        """Get invoices pending stamp."""
        return self.filter(status='pending')

    def cancelled(self):
        """Get cancelled invoices."""
        return self.filter(status='cancelled')

    def for_date_range(self, start_date, end_date):
        """Filter by date range."""
        return self.filter(
            created_at__gte=start_date,
            created_at__lte=end_date
        )


class SubscriptionQuerySet(TenantQuerySet, TimestampQuerySet, OptimizedQuerySetMixin):
    """Optimized queryset for Subscription model."""

    def with_related(self):
        """Optimize for common joins."""
        return self.select_related('tenant')

    def with_prefetch(self):
        """Optimize for common prefetches."""
        return self.prefetch_related('billingpayment_set')

    def active_subscriptions(self):
        """Get active subscriptions."""
        return self.filter(status='active')

    def trial_subscriptions(self):
        """Get trial subscriptions."""
        now = timezone.now()
        return self.filter(
            status='trial',
            trial_ends_at__gte=now
        )

    def expired_trials(self):
        """Get expired trial subscriptions."""
        now = timezone.now()
        return self.filter(
            status='trial',
            trial_ends_at__lt=now
        )

    def past_due(self):
        """Get past due subscriptions."""
        now = timezone.now()
        return self.filter(
            status='past_due',
            next_payment_date__lt=now
        )


class AuditLogQuerySet(TenantQuerySet, TimestampQuerySet):
    """Optimized queryset for AuditLog model."""

    def for_user(self, user):
        """Filter by user."""
        return self.filter(user=user)

    def for_action(self, action):
        """Filter by action."""
        return self.filter(action=action)

    def for_entity(self, entity_type, entity_id=None):
        """Filter by entity type and optional ID."""
        qs = self.filter(entity_type=entity_type)
        if entity_id:
            qs = qs.filter(entity_id=entity_id)
        return qs

    def for_ip(self, ip_address):
        """Filter by IP address."""
        return self.filter(ip_address=ip_address)


# Export all querysets and managers
__all__ = [
    'SoftDeleteQuerySet',
    'TenantQuerySet',
    'ActiveQuerySet',
    'StatusQuerySet',
    'PublishableQuerySet',
    'TimestampQuerySet',
    'CombinedTenantQuerySet',
    'SoftDeletableTenantQuerySet',
    'SoftDeleteManager',
    'TenantManager',
    'ActiveManager',
    'StatusManager',
    'PublishableManager',
    'CombinedTenantManager',
    'OptimizedQuerySetMixin',
    'PaymentLinkQuerySet',
    'PaymentQuerySet',
    'InvoiceQuerySet',
    'SubscriptionQuerySet',
    'AuditLogQuerySet',
]