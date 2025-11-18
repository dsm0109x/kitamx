from __future__ import annotations
from typing import Dict, Any, List
import logging

from django.db.models import Sum, Count, Q
from django.utils import timezone

from core.cache import kita_cache
from accounts.models import Tenant
from payments.models import Payment, PaymentLink
from invoicing.models import Invoice

logger = logging.getLogger(__name__)


class CacheWarmer:

    CACHE_TTL_SHORT = 300
    CACHE_TTL_MEDIUM = 3600
    CACHE_TTL_LONG = 86400

    @staticmethod
    def warm_dashboard_stats(tenant: Tenant) -> Dict[str, Any]:
        cache_key = 'dashboard:stats'

        if kita_cache and kita_cache.exists(str(tenant.id), cache_key):
            logger.debug(f"Cache hit for dashboard stats (tenant {tenant.id})")
            return None

        today = timezone.now().date()
        month_start = today.replace(day=1)

        payment_stats = Payment.objects.filter(
            tenant=tenant,
            created_at__gte=month_start
        ).aggregate(
            total_payments=Count('id'),
            approved_payments=Count('id', filter=Q(status='approved')),
            total_revenue=Sum('amount', filter=Q(status='approved')),
        )

        link_stats = PaymentLink.objects.filter(
            tenant=tenant
        ).aggregate(
            total_links=Count('id'),
            active_links=Count('id', filter=Q(status='active')),
            paid_links=Count('id', filter=Q(status='paid')),
        )

        invoice_stats = Invoice.objects.filter(
            tenant=tenant,
            created_at__gte=month_start
        ).aggregate(
            total_invoices=Count('id'),
            stamped_invoices=Count('id', filter=Q(status='stamped')),
        )

        stats = {
            'payment_stats': payment_stats,
            'link_stats': link_stats,
            'invoice_stats': invoice_stats,
            'warmed_at': timezone.now().isoformat(),
        }

        if kita_cache:
            kita_cache.set(str(tenant.id), cache_key, str(stats), CacheWarmer.CACHE_TTL_SHORT)
            logger.info(f"Warmed dashboard stats for tenant {tenant.id}")

        return stats

    @staticmethod
    def warm_recent_payments(tenant: Tenant, limit: int = 10) -> List[Dict[str, Any]]:
        cache_key = f'dashboard:recent_payments:{limit}'

        if kita_cache and kita_cache.exists(str(tenant.id), cache_key):
            logger.debug(f"Cache hit for recent payments (tenant {tenant.id})")
            return None

        recent_payments = Payment.objects.filter(
            tenant=tenant
        ).select_related('payment_link').order_by('-created_at')[:limit]

        payments_data = []
        for payment in recent_payments:
            payments_data.append({
                'id': str(payment.id),
                'amount': float(payment.amount),
                'status': payment.status,
                'created_at': payment.created_at.isoformat(),
                'payer_email': payment.payer_email,
            })

        if kita_cache:
            kita_cache.set(str(tenant.id), cache_key, str(payments_data), CacheWarmer.CACHE_TTL_SHORT)
            logger.info(f"Warmed recent payments for tenant {tenant.id}")

        return payments_data

    @staticmethod
    def warm_active_links(tenant: Tenant, limit: int = 10) -> List[Dict[str, Any]]:
        cache_key = f'dashboard:active_links:{limit}'

        if kita_cache and kita_cache.exists(str(tenant.id), cache_key):
            logger.debug(f"Cache hit for active links (tenant {tenant.id})")
            return None

        active_links = PaymentLink.objects.filter(
            tenant=tenant,
            status='active'
        ).order_by('-created_at')[:limit]

        links_data = []
        for link in active_links:
            links_data.append({
                'id': str(link.id),
                'slug': link.slug,
                'amount': float(link.amount),
                'customer_name': link.customer_name,
                'created_at': link.created_at.isoformat(),
                'expires_at': link.expires_at.isoformat() if link.expires_at else None,
            })

        if kita_cache:
            kita_cache.set(str(tenant.id), cache_key, str(links_data), CacheWarmer.CACHE_TTL_SHORT)
            logger.info(f"Warmed active links for tenant {tenant.id}")

        return links_data

    @staticmethod
    def warm_tenant_cache(tenant: Tenant) -> Dict[str, bool]:
        results = {}

        try:
            CacheWarmer.warm_dashboard_stats(tenant)
            results['dashboard_stats'] = True
        except Exception as e:
            logger.error(f"Failed to warm dashboard stats: {e}")
            results['dashboard_stats'] = False

        try:
            CacheWarmer.warm_recent_payments(tenant)
            results['recent_payments'] = True
        except Exception as e:
            logger.error(f"Failed to warm recent payments: {e}")
            results['recent_payments'] = False

        try:
            CacheWarmer.warm_active_links(tenant)
            results['active_links'] = True
        except Exception as e:
            logger.error(f"Failed to warm active links: {e}")
            results['active_links'] = False

        return results

    @staticmethod
    def warm_all_active_tenants() -> Dict[str, int]:
        tenants = Tenant.objects.filter(is_active=True)

        success_count = 0
        error_count = 0

        for tenant in tenants:
            try:
                CacheWarmer.warm_tenant_cache(tenant)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to warm cache for tenant {tenant.id}: {e}")
                error_count += 1

        logger.info(f"Cache warming completed: {success_count} successes, {error_count} errors")

        return {
            'success': success_count,
            'errors': error_count,
            'total': success_count + error_count,
        }


class CacheInvalidator:

    @staticmethod
    def invalidate_dashboard(tenant: Tenant) -> bool:
        if not kita_cache:
            return False

        keys = [
            'dashboard:stats',
            'dashboard:recent_payments:10',
            'dashboard:active_links:10',
        ]

        for key in keys:
            kita_cache.delete(str(tenant.id), key)

        logger.info(f"Invalidated dashboard cache for tenant {tenant.id}")
        return True

    @staticmethod
    def invalidate_payment_caches(tenant: Tenant) -> bool:
        if not kita_cache:
            return False

        keys = [
            'dashboard:stats',
            'dashboard:recent_payments:10',
        ]

        for key in keys:
            kita_cache.delete(str(tenant.id), key)

        logger.info(f"Invalidated payment caches for tenant {tenant.id}")
        return True

    @staticmethod
    def invalidate_link_caches(tenant: Tenant) -> bool:
        if not kita_cache:
            return False

        keys = [
            'dashboard:stats',
            'dashboard:active_links:10',
        ]

        for key in keys:
            kita_cache.delete(str(tenant.id), key)

        logger.info(f"Invalidated link caches for tenant {tenant.id}")
        return True

    @staticmethod
    def invalidate_invoice_caches(tenant: Tenant) -> bool:
        if not kita_cache:
            return False

        keys = [
            'dashboard:stats',
        ]

        for key in keys:
            kita_cache.delete(str(tenant.id), key)

        logger.info(f"Invalidated invoice caches for tenant {tenant.id}")
        return True