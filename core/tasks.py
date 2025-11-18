from __future__ import annotations

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import Tenant
from .cache import kita_cache
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_notification_email(self, tenant_id, recipient_email, subject, message, template=None):
    """
    Send notification email with retry logic
    Queue: default
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)

        # Use tenant-specific from email if available
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Kita <hi@kita.mx>')
        if tenant.email:
            from_email = f"{tenant.name} <{tenant.email}>"

        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient_email],
            fail_silently=False,
        )

        # Cache notification sent
        from core.cache import KitaRedisCache
        cache_key = KitaRedisCache.generate_global_key('notifications', 'email_sent', f"{recipient_email}_{subject}")
        kita_cache.set(tenant_id, cache_key, str(timezone.now()), 86400)

        logger.info(f"Email sent to {recipient_email} for tenant {tenant.name}")
        return {"status": "sent", "recipient": recipient_email}

    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found for email notification")
        return {"status": "failed", "error": "Tenant not found"}

    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_email}: {str(exc)}")
        if self.request.retries < self.max_retries:
            # Exponential backoff: 60s, 180s, 420s
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=countdown, exc=exc)
        return {"status": "failed", "error": str(exc)}


@shared_task
def cleanup_expired_cache_keys():
    """
    Cleanup task for expired cache entries
    Queue: low
    """
    try:
        # This is handled automatically by Redis TTL, but we can add custom cleanup logic
        logger.info("Cache cleanup task completed")
        return {"status": "completed"}
    except Exception as exc:
        logger.error(f"Cache cleanup failed: {str(exc)}")
        return {"status": "failed", "error": str(exc)}


@shared_task
def update_tenant_analytics(tenant_id):
    """
    Update tenant analytics in cache
    Queue: low
    """
    try:
        tenant = Tenant.objects.get(id=tenant_id)

        # Calculate and cache analytics
        analytics_data = {
            "last_updated": str(timezone.now()),
            "total_links": 0,  # Will be calculated when payment links are implemented
            "total_payments": 0,
            "total_invoices": 0,
        }

        kita_cache.set(tenant_id, "analytics", analytics_data, 3600)  # 1 hour

        logger.info(f"Analytics updated for tenant {tenant.name}")
        return {"status": "updated", "tenant": tenant.name}

    except Tenant.DoesNotExist:
        logger.error(f"Tenant {tenant_id} not found for analytics update")
        return {"status": "failed", "error": "Tenant not found"}

    except Exception as exc:
        logger.error(f"Failed to update analytics for tenant {tenant_id}: {str(exc)}")
        return {"status": "failed", "error": str(exc)}


@shared_task
def check_trial_expiration():
    """
    Check for trial expiration and send notifications
    Queue: low
    """
    try:
        from datetime import timedelta

        # Find subscriptions with trials expiring in 3 days using new billing system
        from billing.models import Subscription
        warning_date = timezone.now() + timedelta(days=3)
        expiring_subscriptions = Subscription.objects.filter(
            status='trial',
            trial_ends_at__lte=warning_date,
            trial_ends_at__gte=timezone.now(),
            tenant__is_active=True
        ).select_related('tenant')

        notifications_sent = 0
        for subscription in expiring_subscriptions:
            tenant = subscription.tenant
            # Check if warning was already sent
            cache_key = f"trial_warning_sent:{tenant.id}"
            if not kita_cache.exists(tenant.id, cache_key):
                # Send trial expiration warning
                send_notification_email.delay(
                    tenant_id=str(tenant.id),
                    recipient_email=tenant.email,
                    subject="Tu trial de Kita expira pronto",
                    message=f"Hola {tenant.name},\n\nTu trial expira el {subscription.trial_ends_at.strftime('%d/%m/%Y')}."
                )
                # Mark warning as sent (valid for 7 days)
                kita_cache.set(tenant.id, cache_key, "sent", 604800)
                notifications_sent += 1

        logger.info(f"Trial expiration check completed. {notifications_sent} warnings sent.")
        return {"status": "completed", "warnings_sent": notifications_sent}

    except Exception as exc:
        logger.error(f"Trial expiration check failed: {str(exc)}")
        return {"status": "failed", "error": str(exc)}


@shared_task(name='core.collect_daily_analytics')
def collect_daily_analytics():
    from core.analytics import AnalyticsCollector

    date = timezone.now().date()
    AnalyticsCollector.collect_all_tenants_daily(date)
    logger.info(f"Daily analytics collected for {date}")
    return {"status": "completed", "date": str(date)}


@shared_task(name='core.collect_monthly_analytics')
def collect_monthly_analytics():
    from core.analytics import AnalyticsCollector

    now = timezone.now()

    tenants = Tenant.objects.filter(is_active=True)
    collected = 0
    errors = 0

    for tenant in tenants:
        try:
            AnalyticsCollector.collect_monthly_metrics(tenant, now.year, now.month)
            collected += 1
        except Exception as e:
            logger.error(f"Error collecting monthly analytics for tenant {tenant.id}: {e}")
            errors += 1

    logger.info(f"Monthly analytics collected: {collected} successes, {errors} errors")
    return {"status": "completed", "collected": collected, "errors": errors}


@shared_task(name='core.warm_tenant_caches')
def warm_tenant_caches():
    from core.cache_warming import CacheWarmer

    results = CacheWarmer.warm_all_active_tenants()
    logger.info(f"Cache warming: {results['success']} tenants warmed, {results['errors']} errors")
    return results


@shared_task(name='core.cleanup_old_audit_logs')
def cleanup_old_audit_logs():
    """
    Delete audit logs older than retention period (90 days).

    Queue: low
    Schedule: Daily at 3:00 AM
    """
    from datetime import timedelta
    from core.models import AuditLog
    from accounts.constants import AuditConstants

    try:
        cutoff_date = timezone.now() - timedelta(days=AuditConstants.AUDIT_LOG_RETENTION_DAYS)

        old_logs = AuditLog.objects.filter(created_at__lt=cutoff_date)
        count = old_logs.count()

        if count == 0:
            logger.info("No old audit logs to delete")
            return {"status": "completed", "deleted": 0}

        # Delete old logs (bypassing immutability check with QuerySet.delete())
        deleted_count, _ = old_logs.delete()

        logger.info(f"Deleted {deleted_count} audit logs older than {AuditConstants.AUDIT_LOG_RETENTION_DAYS} days")
        return {"status": "completed", "deleted": deleted_count, "cutoff_date": str(cutoff_date)}

    except Exception as exc:
        logger.error(f"Failed to cleanup old audit logs: {str(exc)}")
        return {"status": "failed", "error": str(exc)}


@shared_task(name='core.healthcheck_heartbeat')
def healthcheck_heartbeat():
    """
    Heartbeat ping to Healthchecks.io para verificar que Celery Beat está vivo.

    Queue: low
    Schedule: Every 5 minutes
    """
    import requests

    try:
        response = requests.get(
            'https://hc-ping.com/bd6b2453-9d25-44cd-8703-87956e4d349a',
            timeout=10
        )

        if response.status_code == 200:
            logger.info("Healthcheck heartbeat ping sent successfully")
            return {"status": "success", "timestamp": str(timezone.now())}
        else:
            logger.warning(f"Healthcheck ping returned status {response.status_code}")
            return {"status": "warning", "status_code": response.status_code}

    except Exception as exc:
        logger.error(f"Failed to send healthcheck heartbeat: {str(exc)}")
        # No retries - this is just a heartbeat
        return {"status": "failed", "error": str(exc)}