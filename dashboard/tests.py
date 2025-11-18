"""
Tests for dashboard views and analytics.

Tests dashboard functionality, analytics calculations, and API endpoints.
"""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
import json

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.models import Tenant
from core.test_utils import KitaTestCase
from payments.models import PaymentLink, Payment
from invoicing.models import Invoice

User = get_user_model()


class DashboardViewTestCase(KitaTestCase):
    """Test cases for main dashboard view."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Update user to have onboarding completed
        self.user.onboarding_completed = True
        self.user.save()

    def test_dashboard_requires_login(self) -> None:
        """Test dashboard requires authentication."""
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_dashboard_requires_onboarding(self) -> None:
        """Test dashboard redirects if onboarding not complete."""
        self.user.onboarding_completed = False
        self.user.save()

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/incorporacion/', response.url)  # 🇪🇸 Migrado

    def test_dashboard_loads_successfully(self) -> None:
        """Test dashboard loads for authenticated user."""
        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('dashboard:index'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('analytics', response.context)
        self.assertIn('tenant', response.context)

    def test_dashboard_date_filtering(self) -> None:
        """Test dashboard with date range filtering."""
        self.client.login(email='owner@test.com', password='TestPass123!')

        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()

        response = self.client.get(
            reverse('dashboard:index'),
            {'start_date': start_date.isoformat(), 'end_date': end_date.isoformat()}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['start_date'], start_date)
        self.assertEqual(response.context['end_date'], end_date)

    def test_dashboard_ajax_request(self) -> None:
        """Test dashboard AJAX request returns JSON."""
        self.client.login(email='owner@test.com', password='TestPass123!')

        response = self.client.get(
            reverse('dashboard:index'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('analytics', data)

    def test_dashboard_analytics_caching(self) -> None:
        """Test dashboard analytics are cached."""
        self.client.login(email='owner@test.com', password='TestPass123!')

        # First request - should calculate analytics
        with self.assertNumQueries(7):  # Approximate query count
            response1 = self.client.get(reverse('dashboard:index'))
            self.assertEqual(response1.status_code, 200)

        # Second request - should use cache
        with self.assertNumQueries(3):  # Only auth queries
            response2 = self.client.get(reverse('dashboard:index'))
            self.assertEqual(response2.status_code, 200)


class DashboardAnalyticsTestCase(KitaTestCase):
    """Test cases for dashboard analytics calculations."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create test data
        self.create_test_payment_links()
        self.create_test_payments()
        self.create_test_invoices()

    def create_test_payment_links(self) -> None:
        """Create test payment links."""
        for i in range(5):
            PaymentLink.objects.create(
                tenant=self.tenant,
                token=f'test-token-{i}',
                title=f'Test Link {i}',
                amount=Decimal('100.00'),
                status='paid' if i < 2 else 'active' if i < 4 else 'expired',
                expires_at=timezone.now() + timedelta(days=7)
            )

    def create_test_payments(self) -> None:
        """Create test payments."""
        link = PaymentLink.objects.first()
        for i in range(3):
            Payment.objects.create(
                tenant=self.tenant,
                payment_link=link,
                mp_payment_id=f'MP{i}',
                amount=Decimal('100.00'),
                status='approved' if i < 2 else 'rejected',
                payer_email=f'payer{i}@test.com'
            )

    def create_test_invoices(self) -> None:
        """Create test invoices."""
        for i in range(4):
            Invoice.objects.create(
                tenant=self.tenant,
                payment_id=f'payment-{i}',
                subtotal=Decimal('100.00'),
                total=Decimal('116.00'),
                status='stamped' if i < 2 else 'error' if i == 2 else 'cancelled'
            )

    def test_calculate_dashboard_analytics(self) -> None:
        """Test analytics calculation."""
        from dashboard.views import calculate_dashboard_analytics

        start_date = timezone.now().date() - timedelta(days=30)
        end_date = timezone.now().date()

        analytics = calculate_dashboard_analytics(
            self.tenant,
            start_date,
            end_date
        )

        self.assertEqual(analytics['total_links'], 5)
        self.assertEqual(analytics['links_paid'], 2)
        self.assertEqual(analytics['links_active'], 2)
        self.assertEqual(analytics['links_expired'], 1)
        self.assertEqual(analytics['successful_payments'], 2)
        self.assertEqual(analytics['total_revenue'], Decimal('200.00'))
        self.assertEqual(analytics['invoices_generated'], 2)
        self.assertEqual(analytics['invoices_failed'], 1)
        self.assertEqual(analytics['invoices_cancelled'], 1)


class DashboardAPITestCase(KitaTestCase):
    """Test cases for dashboard API endpoints."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Update user to have onboarding completed
        self.user.onboarding_completed = True
        self.user.save()

    def test_api_counts_endpoint(self) -> None:
        """Test API counts endpoint."""
        # Create test data
        PaymentLink.objects.create(
            tenant=self.tenant,
            token='test-token',
            title='Test',
            amount=Decimal('100.00'),
            expires_at=timezone.now() + timedelta(days=7)
        )

        response = self.client.get(reverse('dashboard:api_counts'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['links_count'], 1)

    def test_api_counts_cached(self) -> None:
        """Test API counts are cached."""
        # First request
        response1 = self.client.get(reverse('dashboard:api_counts'))
        self.assertEqual(response1.status_code, 200)

        # Create new link
        PaymentLink.objects.create(
            tenant=self.tenant,
            token='new-token',
            title='New',
            amount=Decimal('200.00'),
            expires_at=timezone.now() + timedelta(days=7)
        )

        # Second request should still show cached count
        response2 = self.client.get(reverse('dashboard:api_counts'))
        data = json.loads(response2.content)
        self.assertEqual(data['links_count'], 0)  # Still cached

    def test_create_link_form(self) -> None:
        """Test create link form loads."""
        response = self.client.get(reverse('dashboard:create_link_form'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('tenant', response.context)

    def test_create_link_success(self) -> None:
        """Test successful link creation."""
        data = {
            'title': 'Test Payment',
            'amount': 100.00,
            'description': 'Test description',
            'expires_days': 3,
            'customer_name': 'John Doe',
            'customer_email': 'john@example.com',
            'requires_invoice': False
        }

        response = self.client.post(
            reverse('dashboard:create_link'),
            data=json.dumps(data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('link_id', data)
        self.assertIn('token', data)
        self.assertIn('url', data)

        # Verify link was created
        link = PaymentLink.objects.get(id=data['link_id'])
        self.assertEqual(link.title, 'Test Payment')
        self.assertEqual(link.amount, Decimal('100.00'))

    def test_create_link_rate_limit(self) -> None:
        """Test create link rate limiting."""
        data = {
            'title': 'Test',
            'amount': 100.00,
            'expires_days': 3
        }

        # Make 31 requests (limit is 30/hour)
        for i in range(31):
            response = self.client.post(
                reverse('dashboard:create_link'),
                data=json.dumps(data),
                content_type='application/json'
            )
            if i < 30:
                self.assertNotEqual(response.status_code, 429)
            else:
                # 31st request should be rate limited
                self.assertEqual(response.status_code, 429)

    def test_export_data_csv(self) -> None:
        """Test CSV export functionality."""
        # Create test link
        PaymentLink.objects.create(
            tenant=self.tenant,
            token='export-test',
            title='Export Test',
            amount=Decimal('100.00'),
            expires_at=timezone.now() + timedelta(days=7)
        )

        response = self.client.get(
            reverse('dashboard:export'),
            {'type': 'links', 'format': 'csv'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])


class DashboardDetailViewTestCase(KitaTestCase):
    """Test cases for detail view functionality."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Update user to have onboarding completed
        self.user.onboarding_completed = True
        self.user.save()

        # Create test data
        self.link = PaymentLink.objects.create(
            tenant=self.tenant,
            token='detail-test',
            title='Detail Test',
            amount=Decimal('100.00'),
            expires_at=timezone.now() + timedelta(days=7)
        )

    def test_detail_view_link(self) -> None:
        """Test link detail view."""
        response = self.client.get(
            reverse('dashboard:detail', args=['link', self.link.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('link', response.context)
        self.assertEqual(response.context['link'], self.link)

    def test_detail_view_invalid_type(self) -> None:
        """Test detail view with invalid type."""
        response = self.client.get(
            reverse('dashboard:detail', args=['invalid', self.link.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_detail_view_wrong_tenant(self) -> None:
        """Test detail view blocks cross-tenant access."""
        # Create another tenant and link
        other_tenant = Tenant.objects.create(
            name='Other Company',
            slug='other-company',
            rfc='XYZ010101XYZ'
        )

        other_link = PaymentLink.objects.create(
            tenant=other_tenant,
            token='other-test',
            title='Other',
            amount=Decimal('200.00'),
            expires_at=timezone.now() + timedelta(days=7)
        )

        response = self.client.get(
            reverse('dashboard:detail', args=['link', other_link.id])
        )

        self.assertEqual(response.status_code, 404)