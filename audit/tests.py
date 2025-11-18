"""
Tests for audit module.

Tests audit logging, statistics, and export functionality.
"""
from __future__ import annotations
from datetime import timedelta
from uuid import uuid4
import json

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.test_utils import KitaTestCase
from core.models import AuditLog, Tenant
from audit.views import AuditStatsCalculator, validate_date_range

User = get_user_model()


class AuditLogTestCase(KitaTestCase):
    """Test cases for audit log functionality using common test base."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create non-owner user for testing permissions
        self.regular_user, self.regular_tenant_user = self.create_additional_user(
            email='user@test.com',
            is_owner=False
        )

        # Create sample audit logs
        self.create_sample_logs()

    def create_sample_logs(self) -> None:
        """Create sample audit logs for testing."""
        now = timezone.now()

        for i in range(15):
            AuditLog.objects.create(
                tenant=self.tenant,
                user_email=f'user{i % 3}@test.com',
                user_name=f'User {i % 3}',
                action=['login', 'update', 'create', 'delete'][i % 4],
                entity_type=['Invoice', 'Payment', 'User'][i % 3],
                entity_id=uuid4(),
                entity_name=f'Entity {i}',
                ip_address=f'192.168.1.{i}',
                user_agent='Mozilla/5.0',
                notes=f'Test note {i}',
                created_at=now - timedelta(days=i)
            )

    def test_audit_index_requires_login(self) -> None:
        """Test audit index requires authentication."""
        url = reverse('audit:index')
        self.assert_requires_authentication(url)

    def test_audit_index_requires_owner(self) -> None:
        """Test only owners can access audit logs."""
        url = reverse('audit:index')
        self.assert_requires_owner(url)

    def test_audit_index_owner_access(self) -> None:
        """Test owners can access audit logs."""
        url = reverse('audit:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('stats', response.context)
        self.assert_tenant_context(response)

    def test_ajax_logs_pagination(self) -> None:
        """Test AJAX logs endpoint with pagination."""
        url = reverse('audit:ajax_logs')
        response = self.client.get(url, {
            'draw': 1,
            'start': 0,
            'length': 10
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertIn('data', data)
        self.assertIn('recordsTotal', data)
        self.assertEqual(len(data['data']), 10)  # Should return 10 records

    def test_ajax_logs_search(self) -> None:
        """Test AJAX logs search functionality."""
        url = reverse('audit:ajax_logs')
        response = self.client.get(url, {
            'draw': 1,
            'start': 0,
            'length': 10,
            'search[value]': 'Invoice'
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Should only return Invoice-related logs
        for log in data['data']:
            self.assertIn('Invoice', [log['entity_type'], log['notes']])

    def test_ajax_logs_date_filter(self) -> None:
        """Test AJAX logs with date filtering."""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        url = reverse('audit:ajax_logs')
        response = self.client.get(url, {
            'draw': 1,
            'start': 0,
            'length': 100,
            'date_from': week_ago.isoformat(),
            'date_to': today.isoformat()
        })

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        # Should return logs from last 7 days
        self.assertLessEqual(len(data['data']), 8)  # 0-7 days ago

    def test_export_logs_csv(self) -> None:
        """Test CSV export functionality."""
        url = reverse('audit:export_logs')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('audit_logs_test-company', response['Content-Disposition'])

        # Check CSV content
        content = response.content.decode('utf-8')
        lines = content.split('\n')
        self.assertGreater(len(lines), 1)  # Header + data

    def test_export_rate_limiting(self) -> None:
        """Test export is rate limited."""
        url = reverse('audit:export_logs')

        # Make 11 requests (limit is 10/hour)
        for i in range(11):
            response = self.client.get(url)
            if i < 10:
                self.assertEqual(response.status_code, 200)
            else:
                # 11th request should be rate limited
                self.assertEqual(response.status_code, 429)

    def test_log_detail_view(self) -> None:
        """Test audit log detail view."""
        log = AuditLog.objects.filter(tenant=self.tenant).first()
        url = reverse('audit:log_detail', args=[log.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('log', response.context)
        self.assertEqual(response.context['log'].id, log.id)

    def test_log_detail_cross_tenant_protection(self) -> None:
        """Test cannot access logs from other tenants."""
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name='Other Company',
            slug='other-company',
            rfc='XYZ010101XYZ'
        )

        # Create log in other tenant
        other_log = AuditLog.objects.create(
            tenant=other_tenant,
            user_email='other@test.com',
            user_name='Other User',
            action='secret',
            entity_type='Confidential',
            entity_id=uuid4(),
            ip_address='10.0.0.1',
            user_agent='Chrome'
        )

        url = reverse('audit:log_detail', args=[other_log.id])
        response = self.client.get(url)

        # Should return 404, not the log from another tenant
        self.assertEqual(response.status_code, 404)


class AuditStatsCalculatorTestCase(KitaTestCase):
    """Test cases for audit statistics calculator."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create logs with different actions
        now = timezone.now()
        for i in range(20):
            AuditLog.objects.create(
                tenant=self.tenant,
                user_email=f'user{i % 4}@test.com',
                user_name=f'User {i % 4}',
                action=['login', 'logout', 'update', 'create'][i % 4],
                entity_type=['Invoice', 'Payment'][i % 2],
                entity_id=uuid4(),
                ip_address='192.168.1.1',
                user_agent='Test',
                created_at=now - timedelta(days=i)
            )

    def test_calculate_stats(self) -> None:
        """Test statistics calculation."""
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)

        stats = AuditStatsCalculator.calculate(
            self.tenant, month_ago, today
        )

        self.assertIn('total_logs', stats)
        self.assertIn('unique_users', stats)
        self.assertIn('actions_breakdown', stats)
        self.assertIn('entities_breakdown', stats)
        self.assertIn('users_breakdown', stats)
        self.assertIn('daily_activity', stats)

        self.assertEqual(stats['total_logs'], 20)
        self.assertEqual(stats['unique_users'], 4)

    def test_stats_caching(self) -> None:
        """Test statistics are cached."""
        today = timezone.now().date()
        month_ago = today - timedelta(days=30)

        # First call should calculate
        with self.assertNumQueries(6):  # Multiple aggregation queries
            stats1 = AuditStatsCalculator.calculate(
                self.tenant, month_ago, today
            )

        # Second call should use cache
        with self.assertNumQueries(0):  # No queries
            stats2 = AuditStatsCalculator.calculate(
                self.tenant, month_ago, today
            )

        self.assertEqual(stats1, stats2)

    def test_stats_cache_key_uniqueness(self) -> None:
        """Test cache keys are unique per tenant and date range."""
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        key1 = AuditStatsCalculator.get_stats_cache_key(
            str(self.tenant.id), month_ago, today
        )
        key2 = AuditStatsCalculator.get_stats_cache_key(
            str(self.tenant.id), week_ago, today
        )
        key3 = AuditStatsCalculator.get_stats_cache_key(
            'other-id', month_ago, today
        )

        # All keys should be different
        self.assertNotEqual(key1, key2)  # Different date range
        self.assertNotEqual(key1, key3)  # Different tenant
        self.assertNotEqual(key2, key3)


class ValidateDateRangeTestCase(KitaTestCase):
    """Test cases for date range validation."""

    def test_valid_date_range(self) -> None:
        """Test valid date range parsing."""
        start, end = validate_date_range('2024-01-01', '2024-01-31')

        self.assertEqual(start.year, 2024)
        self.assertEqual(start.month, 1)
        self.assertEqual(start.day, 1)
        self.assertEqual(end.day, 31)

    def test_default_date_range(self) -> None:
        """Test default date range when not provided."""
        start, end = validate_date_range(None, None)

        today = timezone.now().date()
        expected_start = today - timedelta(days=30)

        self.assertEqual(end, today)
        self.assertEqual(start, expected_start)

    def test_invalid_date_format(self) -> None:
        """Test invalid date format raises error."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            validate_date_range('invalid', '2024-01-31')

        with self.assertRaises(ValidationError):
            validate_date_range('2024-01-01', 'invalid')

    def test_inverted_date_range(self) -> None:
        """Test start date after end date raises error."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            validate_date_range('2024-01-31', '2024-01-01')

        self.assertIn('Start date must be before end date', str(context.exception))

    def test_excessive_date_range(self) -> None:
        """Test excessive date range raises error."""
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError) as context:
            validate_date_range('2020-01-01', '2024-12-31', max_days=365)

        self.assertIn('Date range cannot exceed 365 days', str(context.exception))

    def test_future_dates_adjusted(self) -> None:
        """Test future dates are adjusted to today."""
        future = (timezone.now().date() + timedelta(days=30)).isoformat()
        past = (timezone.now().date() - timedelta(days=10)).isoformat()

        start, end = validate_date_range(past, future)

        # End date should be adjusted to today
        self.assertEqual(end, timezone.now().date())