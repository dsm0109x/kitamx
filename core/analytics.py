from __future__ import annotations
from typing import Optional
from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Sum, Count, Q

from core.models import Analytics
from accounts.models import Tenant
from payments.models import Payment, PaymentLink
from invoicing.models import Invoice


class AnalyticsCollector:

    @staticmethod
    def collect_daily_metrics(tenant: Tenant, date: Optional[datetime.date] = None) -> Analytics:
        if date is None:
            date = timezone.now().date()

        start_datetime = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_datetime = timezone.make_aware(datetime.combine(date, datetime.max.time()))

        payment_links = PaymentLink.objects.filter(
            tenant=tenant,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )

        payments = Payment.objects.filter(
            tenant=tenant,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )

        invoices = Invoice.objects.filter(
            tenant=tenant,
            created_at__gte=start_datetime,
            created_at__lte=end_datetime
        )

        link_metrics = payment_links.aggregate(
            total=Count('id'),
            active=Count('id', filter=Q(status='active')),
            paid=Count('id', filter=Q(status='paid')),
            expired=Count('id', filter=Q(status='expired')),
        )

        payment_metrics = payments.aggregate(
            attempted=Count('id'),
            successful=Count('id', filter=Q(status='approved')),
            failed=Count('id', filter=Q(status='rejected')),
            refunded=Count('id', filter=Q(status='refunded')),
            revenue_gross=Sum('amount', filter=Q(status='approved')),
        )

        invoice_metrics = invoices.aggregate(
            generated=Count('id'),
            sent=Count('id', filter=Q(status='stamped')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            failed=Count('id', filter=Q(status='error')),
        )

        revenue_gross_centavos = 0
        if payment_metrics['revenue_gross']:
            revenue_gross_centavos = int(payment_metrics['revenue_gross'] * 100)

        analytics, created = Analytics.objects.update_or_create(
            tenant=tenant,
            date=date,
            period_type='daily',
            defaults={
                'links_created': link_metrics['total'] or 0,
                'links_active': link_metrics['active'] or 0,
                'links_paid': link_metrics['paid'] or 0,
                'links_expired': link_metrics['expired'] or 0,
                'payments_attempted': payment_metrics['attempted'] or 0,
                'payments_successful': payment_metrics['successful'] or 0,
                'payments_failed': payment_metrics['failed'] or 0,
                'payments_refunded': payment_metrics['refunded'] or 0,
                'revenue_gross': revenue_gross_centavos,
                'revenue_net': revenue_gross_centavos,
                'invoices_generated': invoice_metrics['generated'] or 0,
                'invoices_sent': invoice_metrics['sent'] or 0,
                'invoices_cancelled': invoice_metrics['cancelled'] or 0,
                'invoices_failed': invoice_metrics['failed'] or 0,
            }
        )

        return analytics

    @staticmethod
    def collect_monthly_metrics(tenant: Tenant, year: int, month: int) -> Analytics:
        date = datetime(year, month, 1).date()
        start_datetime = timezone.make_aware(datetime(year, month, 1))

        if month == 12:
            end_datetime = timezone.make_aware(datetime(year + 1, 1, 1)) - timedelta(seconds=1)
        else:
            end_datetime = timezone.make_aware(datetime(year, month + 1, 1)) - timedelta(seconds=1)

        daily_analytics = Analytics.objects.filter(
            tenant=tenant,
            date__gte=start_datetime.date(),
            date__lte=end_datetime.date(),
            period_type='daily'
        ).aggregate(
            links_created=Sum('links_created'),
            links_paid=Sum('links_paid'),
            links_expired=Sum('links_expired'),
            payments_attempted=Sum('payments_attempted'),
            payments_successful=Sum('payments_successful'),
            payments_failed=Sum('payments_failed'),
            payments_refunded=Sum('payments_refunded'),
            revenue_gross=Sum('revenue_gross'),
            revenue_net=Sum('revenue_net'),
            invoices_generated=Sum('invoices_generated'),
            invoices_sent=Sum('invoices_sent'),
            invoices_cancelled=Sum('invoices_cancelled'),
            invoices_failed=Sum('invoices_failed'),
            notifications_sent=Sum('notifications_sent'),
        )

        links_active = PaymentLink.objects.filter(
            tenant=tenant,
            status='active'
        ).count()

        analytics, created = Analytics.objects.update_or_create(
            tenant=tenant,
            date=date,
            period_type='monthly',
            defaults={
                'links_created': daily_analytics['links_created'] or 0,
                'links_active': links_active,
                'links_paid': daily_analytics['links_paid'] or 0,
                'links_expired': daily_analytics['links_expired'] or 0,
                'payments_attempted': daily_analytics['payments_attempted'] or 0,
                'payments_successful': daily_analytics['payments_successful'] or 0,
                'payments_failed': daily_analytics['payments_failed'] or 0,
                'payments_refunded': daily_analytics['payments_refunded'] or 0,
                'revenue_gross': daily_analytics['revenue_gross'] or 0,
                'revenue_net': daily_analytics['revenue_net'] or 0,
                'invoices_generated': daily_analytics['invoices_generated'] or 0,
                'invoices_sent': daily_analytics['invoices_sent'] or 0,
                'invoices_cancelled': daily_analytics['invoices_cancelled'] or 0,
                'invoices_failed': daily_analytics['invoices_failed'] or 0,
                'notifications_sent': daily_analytics['notifications_sent'] or 0,
            }
        )

        return analytics

    @staticmethod
    def collect_all_tenants_daily(date: Optional[datetime.date] = None):
        if date is None:
            date = timezone.now().date()

        tenants = Tenant.objects.filter(is_active=True)

        for tenant in tenants:
            try:
                AnalyticsCollector.collect_daily_metrics(tenant, date)
            except Exception as e:
                from logging import getLogger
                logger = getLogger(__name__)
                logger.error(f"Error collecting analytics for tenant {tenant.id}: {e}")
                continue