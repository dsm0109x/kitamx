from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime

from core.analytics import AnalyticsCollector
from accounts.models import Tenant


class Command(BaseCommand):
    help = 'Collect analytics metrics for all tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to collect analytics for (YYYY-MM-DD)',
        )
        parser.add_argument(
            '--tenant',
            type=int,
            help='Tenant ID to collect analytics for (optional)',
        )
        parser.add_argument(
            '--period',
            type=str,
            choices=['daily', 'monthly'],
            default='daily',
            help='Period type to collect',
        )

    def handle(self, *args, **options):
        date_str = options.get('date')
        tenant_id = options.get('tenant')
        period = options.get('period')

        if date_str:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = timezone.now().date()

        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                if period == 'daily':
                    analytics = AnalyticsCollector.collect_daily_metrics(tenant, date)
                    self.stdout.write(self.style.SUCCESS(
                        f'Collected daily analytics for {tenant.name} on {date}'
                    ))
                else:
                    analytics = AnalyticsCollector.collect_monthly_metrics(
                        tenant, date.year, date.month
                    )
                    self.stdout.write(self.style.SUCCESS(
                        f'Collected monthly analytics for {tenant.name} for {date.year}-{date.month}'
                    ))
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Tenant {tenant_id} not found'))
        else:
            if period == 'daily':
                AnalyticsCollector.collect_all_tenants_daily(date)
                self.stdout.write(self.style.SUCCESS(
                    f'Collected daily analytics for all tenants on {date}'
                ))
            else:
                tenants = Tenant.objects.filter(is_active=True)
                for tenant in tenants:
                    try:
                        AnalyticsCollector.collect_monthly_metrics(
                            tenant, date.year, date.month
                        )
                        self.stdout.write(self.style.SUCCESS(
                            f'Collected monthly analytics for {tenant.name}'
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(
                            f'Error collecting analytics for {tenant.name}: {e}'
                        ))