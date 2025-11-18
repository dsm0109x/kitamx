"""
Celery tasks for payment reconciliation and monitoring
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from datetime import timedelta
import requests
from decimal import Decimal

from .models import Payment, MercadoPagoIntegration
from billing.models import BillingPayment
from core.models import AuditLog

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def reconcile_payment_links(self, hours_back=24):
    """
    Reconcile payment links with MercadoPago API
    Queue: high
    """
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours_back)

        # Get recent payments that need reconciliation
        payments_to_check = Payment.objects.filter(
            Q(mp_updated_at__gte=cutoff_time) | Q(mp_updated_at__isnull=True),
            mp_payment_id__isnull=False
        ).select_related('tenant', 'payment_link')

        reconciled_count = 0
        discrepancy_count = 0

        for payment in payments_to_check:
            try:
                # Get MP integration for tenant
                mp_integration = MercadoPagoIntegration.objects.filter(
                    tenant=payment.tenant,
                    is_active=True
                ).first()

                if not mp_integration:
                    logger.warning(f"No MP integration for tenant {payment.tenant.id}")
                    continue

                # Query MP API
                mp_data = get_payment_from_mp_api(payment.mp_payment_id, mp_integration.access_token)

                if not mp_data:
                    logger.warning(f"Payment {payment.mp_payment_id} not found in MP API")
                    continue

                # Compare status and amount
                mp_status = mp_data.get('status')
                mp_amount = Decimal(str(mp_data.get('transaction_amount', 0)))

                discrepancy_found = False
                discrepancy_details = []

                # Check status discrepancy
                if payment.status != mp_status:
                    discrepancy_found = True
                    discrepancy_details.append(f"Status: DB={payment.status}, MP={mp_status}")

                # Check amount discrepancy
                if payment.amount != mp_amount:
                    discrepancy_found = True
                    discrepancy_details.append(f"Amount: DB={payment.amount}, MP={mp_amount}")

                # Update payment with latest MP data
                payment.mp_updated_at = timezone.now()
                payment.webhook_data = mp_data

                # Update status if different
                if payment.status != mp_status:
                    old_status = payment.status
                    payment.status = mp_status
                    logger.info(f"Updated payment {payment.mp_payment_id} status: {old_status} → {mp_status}")

                payment.save()

                # Log discrepancy if found
                if discrepancy_found:
                    discrepancy_count += 1
                    AuditLog.objects.create(
                        tenant=payment.tenant,
                        user_email='system@kita.mx',
                        user_name='Reconciliation System',
                        action='reconcile_discrepancy',
                        entity_type='Payment',
                        entity_id=payment.id,
                        entity_name=f'Payment {payment.mp_payment_id}',
                        notes=f"Discrepancies found: {'; '.join(discrepancy_details)}"
                    )

                reconciled_count += 1

            except Exception as e:
                logger.error(f"Error reconciling payment {payment.mp_payment_id}: {str(e)}")
                continue

        result = {
            'reconciled_count': reconciled_count,
            'discrepancy_count': discrepancy_count,
            'hours_back': hours_back
        }

        logger.info(f"Payment reconciliation completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Payment reconciliation failed: {str(exc)}")
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=countdown, exc=exc)
        return {'error': str(exc)}


@shared_task(bind=True, max_retries=3)
def reconcile_subscription_payments(self, hours_back=24):
    """
    Reconcile subscription payments with Kita's MercadoPago account
    Queue: high
    """
    try:
        cutoff_time = timezone.now() - timedelta(hours=hours_back)

        # Get recent billing payments that need reconciliation
        billing_payments = BillingPayment.objects.filter(
            Q(updated_at__gte=cutoff_time) | Q(processed_at__isnull=True),
            external_payment_id__isnull=False
        ).select_related('tenant', 'subscription')

        reconciled_count = 0
        discrepancy_count = 0

        for billing_payment in billing_payments:
            try:
                # Query Kita's MP account directly
                mp_data = get_kita_payment_from_mp_api(billing_payment.external_payment_id)

                if not mp_data:
                    logger.warning(f"Billing payment {billing_payment.external_payment_id} not found in Kita MP API")
                    continue

                # Compare status and amount
                mp_status = mp_data.get('status')
                mp_amount = Decimal(str(mp_data.get('transaction_amount', 0)))

                # Map MP status to billing payment status
                billing_status_map = {
                    'approved': 'completed',
                    'authorized': 'completed',
                    'pending': 'pending',
                    'in_process': 'processing',
                    'rejected': 'failed',
                    'cancelled': 'failed',
                    'refunded': 'refunded'
                }
                expected_status = billing_status_map.get(mp_status, 'pending')

                discrepancy_found = False
                discrepancy_details = []

                # Check status discrepancy
                if billing_payment.status != expected_status:
                    discrepancy_found = True
                    discrepancy_details.append(f"Status: DB={billing_payment.status}, Expected={expected_status} (MP={mp_status})")

                # Check amount discrepancy
                if billing_payment.amount != mp_amount:
                    discrepancy_found = True
                    discrepancy_details.append(f"Amount: DB={billing_payment.amount}, MP={mp_amount}")

                # Update billing payment with latest MP data
                billing_payment.external_payment_data = mp_data

                # Update status if completed in MP
                if mp_status in ['approved', 'authorized'] and billing_payment.status != 'completed':
                    billing_payment.mark_completed()
                    logger.info(f"Marked billing payment {billing_payment.external_payment_id} as completed")
                elif mp_status in ['rejected', 'cancelled'] and billing_payment.status not in ['failed']:
                    billing_payment.mark_failed(f"MP status: {mp_status}")
                    logger.info(f"Marked billing payment {billing_payment.external_payment_id} as failed")
                else:
                    billing_payment.save()

                # Log discrepancy if found
                if discrepancy_found:
                    discrepancy_count += 1
                    AuditLog.objects.create(
                        tenant=billing_payment.tenant,
                        user_email='system@kita.mx',
                        user_name='Reconciliation System',
                        action='reconcile_discrepancy',
                        entity_type='BillingPayment',
                        entity_id=billing_payment.id,
                        entity_name=f'Billing Payment {billing_payment.external_payment_id}',
                        notes=f"Discrepancies found: {'; '.join(discrepancy_details)}"
                    )

                reconciled_count += 1

            except Exception as e:
                logger.error(f"Error reconciling billing payment {billing_payment.external_payment_id}: {str(e)}")
                continue

        result = {
            'reconciled_count': reconciled_count,
            'discrepancy_count': discrepancy_count,
            'hours_back': hours_back
        }

        logger.info(f"Billing payment reconciliation completed: {result}")
        return result

    except Exception as exc:
        logger.error(f"Billing payment reconciliation failed: {str(exc)}")
        if self.request.retries < self.max_retries:
            countdown = 60 * (2 ** self.request.retries)
            raise self.retry(countdown=countdown, exc=exc)
        return {'error': str(exc)}


@shared_task
def generate_reconciliation_report(date_from=None, date_to=None):
    """
    Generate daily reconciliation report
    Queue: default
    """
    try:
        if not date_from:
            date_from = (timezone.now() - timedelta(days=1)).date()
        if not date_to:
            date_to = timezone.now().date()

        # Get all discrepancies in date range
        discrepancy_logs = AuditLog.objects.filter(
            action='reconcile_discrepancy',
            created_at__date__gte=date_from,
            created_at__date__lte=date_to
        ).select_related('tenant')

        # Group by tenant
        tenant_discrepancies = {}
        for log in discrepancy_logs:
            tenant_name = log.tenant.name if log.tenant else 'Unknown'
            if tenant_name not in tenant_discrepancies:
                tenant_discrepancies[tenant_name] = []
            tenant_discrepancies[tenant_name].append(log)

        # Generate report data
        report_data = {
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
            'total_discrepancies': len(discrepancy_logs),
            'tenants_affected': len(tenant_discrepancies),
            'discrepancies_by_tenant': {
                tenant: len(logs) for tenant, logs in tenant_discrepancies.items()
            },
            'details': [
                {
                    'tenant': log.tenant.name if log.tenant else 'Unknown',
                    'entity_type': log.entity_type,
                    'entity_id': log.entity_id,
                    'entity_name': log.entity_name,
                    'discrepancy': log.notes,
                    'timestamp': log.created_at.isoformat()
                }
                for log in discrepancy_logs
            ]
        }

        logger.info(f"Reconciliation report generated: {len(discrepancy_logs)} discrepancies found")
        return report_data

    except Exception as e:
        logger.error(f"Error generating reconciliation report: {str(e)}")
        return {'error': str(e)}


def get_payment_from_mp_api(payment_id, access_token):
    """
    Get payment information from MercadoPago API using tenant's access token.

    This is a wrapper for backward compatibility.
    Uses the consolidated implementation from MercadoPagoService.
    """
    from .services import MercadoPagoService
    try:
        return MercadoPagoService.get_payment_from_mp_api(payment_id, access_token)
    except ValueError as e:
        logger.error(f"MP API error for payment {payment_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error querying MP API for payment {payment_id}: {str(e)}")
        return None


def get_kita_payment_from_mp_api(payment_id):
    """
    Get payment information from Kita's MercadoPago account
    """
    try:
        headers = {
            "Authorization": f"Bearer {settings.KITA_MP_ACCESS_TOKEN}",
            "Accept": "application/json"
        }

        response = requests.get(
            f"{settings.MERCADOPAGO_PAYMENTS_URL}/{payment_id}",
            headers=headers,
            timeout=30
        )

        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Kita MP API error for payment {payment_id}: {response.status_code}")
            return None

    except Exception as e:
        logger.error(f"Error querying Kita MP API for payment {payment_id}: {str(e)}")
        return None


@shared_task
def cleanup_old_reconciliation_logs():
    """
    Cleanup old reconciliation audit logs (older than 90 days)
    Queue: low
    """
    try:
        cutoff_date = timezone.now() - timedelta(days=90)

        deleted_count = AuditLog.objects.filter(
            action='reconcile_discrepancy',
            created_at__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Cleaned up {deleted_count} old reconciliation logs")
        return {'deleted_count': deleted_count}

    except Exception as e:
        logger.error(f"Error cleaning up reconciliation logs: {str(e)}")
        return {'error': str(e)}