"""Celery tasks for invoice processing and maintenance.

Handles asynchronous invoice operations including cancellation,
link expiration, reminders, and analytics updates.
"""
from __future__ import annotations
from datetime import date, timedelta
import logging

from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db import transaction

from .models import Invoice
from core.query_optimizations import BulkOperationHelper

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def cancel_invoice_task(self, invoice_id: str, reason: str = "02") -> str:
    """Cancel CFDI invoice.

    Args:
        invoice_id: UUID of invoice to cancel
        reason: SAT cancellation reason code

    Returns:
        Status message
    """
    try:
        invoice = Invoice.objects.select_related('tenant').get(id=invoice_id)

        # Check if invoice can be cancelled
        if not invoice.is_valid_for_cancellation:
            return "Invoice cannot be cancelled (outside calendar month)"

        # Cancel with PAC provider
        from .pac_factory import pac_service
        cancel_result = pac_service.cancel_cfdi(
            str(invoice.uuid),
            invoice.tenant.rfc,
            str(invoice.tenant.id)
        )

        if cancel_result['success']:
            # Update invoice status
            invoice.mark_cancelled(reason)
            logger.info(f"Invoice {invoice_id} cancelled successfully")
            return f"Invoice cancelled: {invoice.uuid}"
        else:
            error_msg = cancel_result.get('error', 'Unknown error')
            logger.error(f"Failed to cancel invoice {invoice_id}: {error_msg}")

            # Update invoice with error
            invoice.status = 'error'
            invoice.pac_response = cancel_result.get('sw_response', {})
            invoice.save(update_fields=['status', 'pac_response'])

            return f"Failed to cancel invoice: {error_msg}"

    except Exception as e:
        logger.error(f"Error cancelling invoice {invoice_id}: {e}")
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60
            raise self.retry(countdown=countdown, exc=e)
        else:
            return f"Failed after {self.max_retries} retries: {str(e)}"


@shared_task
def process_expired_links() -> str:
    """Process expired payment links.

    Returns:
        Status message with count
    """
    from payments.models import PaymentLink

    # Use select_for_update to avoid race conditions
    with transaction.atomic():
        expired_links = PaymentLink.objects.select_for_update().filter(
            status='active',
            expires_at__lt=timezone.now()
        ).select_related('tenant')

        # Optimize: Use bulk update instead of individual saves
        count = BulkOperationHelper.bulk_update_status(expired_links, 'expired')

        # Send notifications ONLY for links with notify_on_expiry enabled
        notifications_sent = 0
        for link in expired_links.filter(
            notifications_enabled=True,
            notify_on_expiry=True,
            customer_email__isnull=False
        ).exclude(customer_email=''):
            try:
                from core.notifications import notification_service
                result = notification_service.send_link_expired(link)

                if result.get('success'):
                    # Increment notification counter
                    link.notification_count += 1
                    link.save(update_fields=['notification_count'])
                    notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to send expiration notification for link {link.id}: {e}")

    logger.info(f"Processed {count} expired payment links, sent {notifications_sent} expiration notifications")
    return f"Processed {count} expired links, sent {notifications_sent} notifications"


@shared_task
def send_payment_reminders() -> str:
    """Send payment reminders for active links based on their configuration.

    Returns:
        Status message with count
    """
    from payments.models import PaymentLink

    now = timezone.now()

    # Get links with reminders enabled and not yet sent
    # IMPORTANTE: Solo links ACTIVOS (no pagados, no expirados, no cancelados)
    links_for_reminder = PaymentLink.objects.filter(
        status='active',  # ← Clave: solo activos
        notifications_enabled=True,
        send_reminders=True,
        reminder_sent=False,
        customer_email__isnull=False
    ).exclude(
        customer_email=''
    ).select_related('tenant')

    reminders_sent = 0
    errors = 0

    for link in links_for_reminder:
        # Calculate reminder time based on link configuration
        reminder_time = link.expires_at - timedelta(hours=link.reminder_hours_before)

        # Send if we've reached the reminder time
        if now >= reminder_time and not link.reminder_sent:
            try:
                from core.notifications import notification_service
                result = notification_service.send_payment_reminder(link)

                if result.get('success'):
                    # Mark as sent and increment counter
                    link.reminder_sent = True
                    link.notification_count += 1
                    link.save(update_fields=['reminder_sent', 'notification_count'])
                    reminders_sent += 1
                    logger.info(f"Reminder sent for link {link.id} ({link.reminder_hours_before}h before expiry)")
                else:
                    errors += 1
                    logger.warning(f"Reminder failed for link {link.id}: {result.get('error')}")
            except Exception as e:
                errors += 1
                logger.error(f"Failed to send reminder for link {link.id}: {e}")

    logger.info(f"Payment reminders task completed: {reminders_sent} sent, {errors} errors")
    return f"Sent {reminders_sent} reminders ({errors} errors)"


@shared_task
def update_analytics() -> str:
    """Update analytics data for all active tenants.

    Returns:
        Status message
    """
    from core.models import Analytics, Tenant
    from payments.models import PaymentLink, Payment

    today = date.today()
    yesterday = today - timedelta(days=1)

    for tenant in Tenant.objects.filter(is_active=True).iterator(chunk_size=100):
        try:
            # Calculate daily analytics with aggregation
            link_stats = PaymentLink.objects.filter(
                tenant=tenant,
                created_at__date=yesterday
            ).aggregate(
                total=Count('id'),
                active=Count('id', filter=Q(status='active')),
                paid=Count('id', filter=Q(status='paid')),
                expired=Count('id', filter=Q(status='expired'))
            )

            payment_stats = Payment.objects.filter(
                tenant=tenant,
                created_at__date=yesterday
            ).aggregate(
                total=Count('id'),
                successful=Count('id', filter=Q(status='approved')),
                failed=Count('id', filter=Q(status='rejected')),
                revenue=Sum('amount', filter=Q(status='approved'))
            )

            with transaction.atomic():
                analytics, created = Analytics.objects.update_or_create(
                    tenant=tenant,
                    date=yesterday,
                    period_type='daily',
                    defaults={
                        'links_created': link_stats['total'] or 0,
                        'links_active': link_stats['active'] or 0,
                        'links_paid': link_stats['paid'] or 0,
                        'links_expired': link_stats['expired'] or 0,
                        'payments_attempted': payment_stats['total'] or 0,
                        'payments_successful': payment_stats['successful'] or 0,
                        'payments_failed': payment_stats['failed'] or 0,
                        'revenue_gross': int((payment_stats['revenue'] or 0) * 100),  # Convert to centavos
                    }
                )

            logger.info(f"Updated analytics for {tenant.name} - {yesterday}")

        except Exception as e:
            logger.error(f"Error updating analytics for tenant {tenant.id}: {e}")

    return f"Updated analytics for {yesterday}"


@shared_task
def process_subscription_payments() -> str:
    """Process subscription payments for tenants using new billing system.

    Returns:
        Status message with count
    """
    from billing.models import Subscription
    from payments.billing import KitaBillingService

    # Find subscriptions with trials ending today
    subscriptions_due = Subscription.objects.filter(
        status='trial',
        trial_ends_at__date=timezone.now().date(),
        tenant__is_active=True
    ).select_related('tenant').prefetch_related(
        'tenant__tenantuser_set'
    )

    billing_service = KitaBillingService()

    for subscription in subscriptions_due:
        tenant = subscription.tenant
        try:
            result = billing_service.create_subscription_preference(tenant)
            if result['success']:
                logger.info(f"Subscription preference created for tenant {tenant.name}")
                # Here you could send notification with payment link
            else:
                logger.warning(f"Failed to create subscription preference for {tenant.name}: {result.get('error')}")
        except Exception as e:
            logger.error(f"Error processing subscription for tenant {tenant.id}: {e}")

    return f"Processed {subscriptions_due.count()} subscription payments"


@shared_task
def cleanup_old_uploads() -> str:
    """Clean up old file uploads.

    Deletes uploaded files older than 30 days that are in 'deleted' status.

    Returns:
        Status message with count
    """
    from .models import FileUpload

    cutoff_date = timezone.now() - timedelta(days=30)

    old_uploads = FileUpload.objects.filter(
        status='deleted',
        updated_at__lt=cutoff_date
    )

    count = 0
    for upload in old_uploads.iterator(chunk_size=100):
        try:
            # Delete the actual file
            if upload.file:
                upload.file.delete(save=False)
            upload.delete()
            count += 1
        except Exception as e:
            logger.error(f"Error deleting old upload {upload.id}: {e}")

    logger.info(f"Cleaned up {count} old file uploads")
    return f"Cleaned up {count} old uploads"


@shared_task
def cleanup_orphaned_uploads() -> str:
    """BUG FIX #26: Clean up orphaned file uploads.

    Deletes uploaded files that were never processed (user abandoned upload).
    Files with status='uploaded' older than 24 hours are considered orphaned.

    This prevents storage leaks from users who:
    - Upload files but close browser before saving
    - Upload files but never click "Guardar"
    - Start upload process but abandon midway

    Returns:
        Status message with count of cleaned files
    """
    from .models import FileUpload

    # Files uploaded but never processed for 24 hours
    cutoff_date = timezone.now() - timedelta(hours=24)

    orphaned_uploads = FileUpload.objects.filter(
        status='uploaded',
        created_at__lt=cutoff_date
    )

    count = 0
    for upload in orphaned_uploads.iterator(chunk_size=100):
        try:
            # Delete the actual file from storage
            if upload.file:
                upload.file.delete(save=False)

            # Delete the database record
            upload.delete()
            count += 1

            logger.info(f"Cleaned orphaned upload: {upload.original_filename} (tenant: {upload.tenant.name})")

        except Exception as e:
            logger.error(f"Error deleting orphaned upload {upload.id}: {e}")

    logger.info(f"Cleaned up {count} orphaned file uploads")
    return f"Cleaned up {count} orphaned uploads (24h+ old, status='uploaded')"


@shared_task
def check_certificate_expiration() -> str:
    """Check for expiring CSD certificates.

    Sends notifications for certificates expiring in 30 days.

    Returns:
        Status message
    """
    from .models import CSDCertificate
    from core.notifications import notification_service

    expiring_soon = CSDCertificate.objects.expiring_soon(days=30).select_related('tenant')

    for csd in expiring_soon:
        try:
            # Send notification to tenant owner
            tenant_users = csd.tenant.tenantuser_set.filter(is_owner=True)
            for user in tenant_users:
                notification_service.send_certificate_expiring(
                    csd, user.email
                )
            logger.info(f"Sent expiration notice for CSD {csd.serial_number}")
        except Exception as e:
            logger.error(f"Error sending CSD expiration notice: {e}")

    return f"Checked {expiring_soon.count()} expiring certificates"