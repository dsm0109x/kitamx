"""
Query optimization helpers for the Kita application.

This module provides pre-configured query optimizations to reduce N+1 queries
and improve database performance.
"""
from __future__ import annotations
from django.db.models import Prefetch, Count, Sum, Q
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet


class QueryOptimizer:
    """Helper class for common query optimizations."""

    @staticmethod
    def optimize_payment_links(queryset) -> QuerySet:
        """
        Optimize PaymentLink queryset to avoid N+1 queries.

        Adds:
        - select_related for tenant
        - prefetch_related for payments and analytics
        - annotations for common aggregations
        """
        from payments.models import Payment

        return queryset.select_related(
            'tenant'
        ).prefetch_related(
            Prefetch(
                'payments',
                queryset=Payment.objects.select_related('invoice').order_by('-created_at')
            )
        ).annotate(
            payment_count=Count('payments'),
            total_amount=Sum('payments__amount', filter=Q(payments__status='approved'))
        )

    @staticmethod
    def optimize_payments(queryset) -> QuerySet:
        """
        Optimize Payment queryset to avoid N+1 queries.

        Adds:
        - select_related for tenant, payment_link, and invoice
        """
        return queryset.select_related(
            'tenant',
            'payment_link',
            'invoice'
        )

    @staticmethod
    def optimize_invoices(queryset) -> QuerySet:
        """
        Optimize Invoice queryset to avoid N+1 queries.

        Adds:
        - select_related for tenant and payment
        """
        return queryset.select_related(
            'tenant'
        )
        # ✅ Removido: 'payment' y 'payment__payment_link' (relación OneToOne inversa)
        # ✅ Removido: 'invoiceitem_set' (no existe en modelo Invoice)

    @staticmethod
    def optimize_subscriptions(queryset) -> QuerySet:
        """
        Optimize Subscription queryset to avoid N+1 queries.

        Adds:
        - select_related for tenant
        - prefetch_related for billing payments
        """
        from billing.models import BillingPayment

        return queryset.select_related(
            'tenant'
        ).prefetch_related(
            Prefetch(
                'billingpayment_set',
                queryset=BillingPayment.objects.order_by('-created_at')[:5]
            )
        ).annotate(
            payment_count=Count('billingpayment'),
            total_paid=Sum('billingpayment__amount', filter=Q(billingpayment__status='approved'))
        )

    @staticmethod
    def optimize_tenants(queryset) -> QuerySet:
        """
        Optimize Tenant queryset to avoid N+1 queries.

        Adds:
        - prefetch_related for users and subscription
        - annotations for common counts
        """
        return queryset.prefetch_related(
            'tenantuser_set',
            'subscription_set'
        ).annotate(
            user_count=Count('tenantuser'),
            payment_link_count=Count('paymentlink'),
            invoice_count=Count('invoice')
        )

    @staticmethod
    def optimize_audit_logs(queryset) -> QuerySet:
        """
        Optimize AuditLog queryset to avoid N+1 queries.

        Adds:
        - select_related for user and tenant
        """
        return queryset.select_related(
            'user',
            'tenant'
        )

    @staticmethod
    def optimize_tenant_users(queryset) -> QuerySet:
        """
        Optimize TenantUser queryset to avoid N+1 queries.

        Adds:
        - select_related for tenant
        """
        return queryset.select_related(
            'tenant'
        )


class StatsCalculator:
    """Helper class for calculating common statistics efficiently."""

    @staticmethod
    def get_payment_link_stats(tenant):
        """
        Get payment link statistics for a tenant.

        Uses a single aggregation query instead of multiple count queries.
        """
        from payments.models import PaymentLink
        from django.db.models import Count, Sum, Q

        stats = PaymentLink.objects.filter(tenant=tenant).aggregate(
            total=Count('id'),
            paid=Count('id', filter=Q(status='paid')),
            active=Count('id', filter=Q(status='active')),
            expired=Count('id', filter=Q(status='expired')),
            revenue=Sum('payments__amount', filter=Q(
                status='paid',
                payments__status='approved'
            ))
        )

        return {
            'total': stats['total'] or 0,
            'paid': stats['paid'] or 0,
            'active': stats['active'] or 0,
            'expired': stats['expired'] or 0,
            'revenue': stats['revenue'] or 0
        }

    @staticmethod
    def get_invoice_stats(tenant, start_date=None, end_date=None):
        """
        Get invoice statistics for a tenant.

        Args:
            tenant: Tenant instance
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            Dictionary with invoice statistics
        """
        from invoicing.models import Invoice
        from django.db.models import Count, Sum, Q

        qs = Invoice.objects.filter(tenant=tenant)

        if start_date:
            qs = qs.filter(created_at__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__lte=end_date)

        stats = qs.aggregate(
            total=Count('id'),
            stamped=Count('id', filter=Q(status='stamped')),
            pending=Count('id', filter=Q(status='pending')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            total_amount=Sum('total')
        )

        return {
            'total': stats['total'] or 0,
            'stamped': stats['stamped'] or 0,
            'pending': stats['pending'] or 0,
            'cancelled': stats['cancelled'] or 0,
            'total_amount': stats['total_amount'] or 0
        }

    @staticmethod
    def get_subscription_stats(tenant):
        """
        Get subscription statistics for a tenant.

        Returns:
            Dictionary with subscription information
        """
        from billing.models import Subscription
        from django.db.models import Sum, Count, Q

        subscription = Subscription.objects.filter(tenant=tenant).first()

        if not subscription:
            return {
                'status': 'none',
                'has_subscription': False
            }

        payments_stats = subscription.billingpayment_set.aggregate(
            total_paid=Sum('amount', filter=Q(status='approved')),
            payment_count=Count('id'),
            successful_count=Count('id', filter=Q(status='approved'))
        )

        return {
            'status': subscription.status,
            'has_subscription': True,
            'trial_ends_at': subscription.trial_ends_at,
            'next_payment_date': subscription.next_payment_date,
            'last_payment_date': subscription.last_payment_date,
            'total_paid': payments_stats['total_paid'] or 0,
            'payment_count': payments_stats['payment_count'] or 0,
            'successful_count': payments_stats['successful_count'] or 0
        }

    @staticmethod
    def get_dashboard_stats(tenant):
        """
        Get comprehensive dashboard statistics for a tenant.

        Optimized to use as few queries as possible.
        """
        payment_stats = StatsCalculator.get_payment_link_stats(tenant)
        invoice_stats = StatsCalculator.get_invoice_stats(tenant)
        subscription_stats = StatsCalculator.get_subscription_stats(tenant)

        return {
            'payments': payment_stats,
            'invoices': invoice_stats,
            'subscription': subscription_stats
        }


class BulkOperationHelper:
    """Helper class for efficient bulk operations."""

    @staticmethod
    def bulk_update_status(queryset, status):
        """
        Bulk update status for queryset.

        More efficient than updating one by one.
        """
        from django.utils import timezone

        return queryset.update(
            status=status,
            updated_at=timezone.now()
        )

    # Removed unused bulk operations methods:
    # - bulk_soft_delete: No soft delete usage patterns found in application
    # - bulk_activate: No bulk activation patterns found in application
    # - bulk_deactivate: No bulk deactivation patterns found in application
    # Only bulk_update_status is actually needed and used in production


class CacheHelper:
    """Helper class for query result caching."""

    @staticmethod
    def get_cached_stats(tenant, cache_key_suffix, calculator_func, timeout=300):
        """
        Get statistics with caching.

        Args:
            tenant: Tenant instance
            cache_key_suffix: Suffix for cache key
            calculator_func: Function to calculate stats
            timeout: Cache timeout in seconds

        Returns:
            Statistics dictionary
        """
        from django.core.cache import cache

        cache_key = f"stats:{tenant.id}:{cache_key_suffix}"
        stats = cache.get(cache_key)

        if stats is None:
            stats = calculator_func(tenant)
            cache.set(cache_key, stats, timeout)

        return stats

    @staticmethod
    def invalidate_tenant_stats(tenant):
        """
        Invalidate all cached statistics for a tenant.

        Args:
            tenant: Tenant instance
        """
        from django.core.cache import cache

        cache_keys = [
            f"stats:{tenant.id}:payments",
            f"stats:{tenant.id}:invoices",
            f"stats:{tenant.id}:subscription",
            f"stats:{tenant.id}:dashboard"
        ]

        for key in cache_keys:
            cache.delete(key)


# Convenience functions
def optimize_for_list_view(queryset, model_name: str):
    """
    Apply appropriate optimizations for list views.

    Args:
        queryset: QuerySet to optimize
        model_name: Name of the model

    Returns:
        Optimized queryset
    """
    optimizer = QueryOptimizer()

    optimizations = {
        'paymentlink': optimizer.optimize_payment_links,
        'payment': optimizer.optimize_payments,
        'invoice': optimizer.optimize_invoices,
        'subscription': optimizer.optimize_subscriptions,
        'tenant': optimizer.optimize_tenants,
        'auditlog': optimizer.optimize_audit_logs,
        'tenantuser': optimizer.optimize_tenant_users,
    }

    optimize_func = optimizations.get(model_name.lower())

    if optimize_func:
        return optimize_func(queryset)

    return queryset


def get_cached_tenant_stats(tenant, stats_type='dashboard', timeout=300):
    """
    Get cached tenant statistics.

    Args:
        tenant: Tenant instance
        stats_type: Type of stats ('dashboard', 'payments', 'invoices', 'subscription')
        timeout: Cache timeout in seconds

    Returns:
        Statistics dictionary
    """
    calculator_map = {
        'dashboard': StatsCalculator.get_dashboard_stats,
        'payments': StatsCalculator.get_payment_link_stats,
        'invoices': StatsCalculator.get_invoice_stats,
        'subscription': StatsCalculator.get_subscription_stats,
    }

    calculator = calculator_map.get(stats_type, StatsCalculator.get_dashboard_stats)

    return CacheHelper.get_cached_stats(
        tenant,
        stats_type,
        calculator,
        timeout
    )


# Export all helpers
__all__ = [
    'QueryOptimizer',
    'StatsCalculator',
    'BulkOperationHelper',
    'CacheHelper',
    'optimize_for_list_view',
    'get_cached_tenant_stats',
]