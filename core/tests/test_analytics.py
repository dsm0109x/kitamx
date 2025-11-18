import pytest
from django.utils import timezone

from core.analytics import AnalyticsCollector
from core.models import Analytics
from accounts.models import Tenant


@pytest.mark.django_db
class TestAnalyticsCollector:

    @pytest.fixture
    def tenant(self):
        return Tenant.objects.create(
            name='Test Tenant',
            slug='test-tenant',
            email='test@example.com',
            is_active=True
        )

    def test_collect_daily_metrics_creates_analytics(self, tenant):
        today = timezone.now().date()

        analytics = AnalyticsCollector.collect_daily_metrics(tenant, today)

        assert analytics is not None
        assert analytics.tenant == tenant
        assert analytics.date == today
        assert analytics.period_type == 'daily'
        assert analytics.links_created >= 0
        assert analytics.payments_attempted >= 0
        assert analytics.invoices_generated >= 0

    def test_collect_daily_metrics_updates_existing(self, tenant):
        today = timezone.now().date()

        analytics1 = AnalyticsCollector.collect_daily_metrics(tenant, today)
        analytics2 = AnalyticsCollector.collect_daily_metrics(tenant, today)

        assert analytics1.id == analytics2.id
        count = Analytics.objects.filter(tenant=tenant, date=today, period_type='daily').count()
        assert count == 1

    def test_collect_monthly_metrics_aggregates_daily(self, tenant):
        now = timezone.now()

        daily1 = Analytics.objects.create(
            tenant=tenant,
            date=now.date(),
            period_type='daily',
            links_created=5,
            payments_successful=3,
            revenue_gross=10000,
        )

        monthly = AnalyticsCollector.collect_monthly_metrics(tenant, now.year, now.month)

        assert monthly.period_type == 'monthly'
        assert monthly.links_created >= 5
        assert monthly.payments_successful >= 3
        assert monthly.revenue_gross >= 10000