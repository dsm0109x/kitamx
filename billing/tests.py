"""
Tests for billing and subscription management.

Tests subscription lifecycle, payments, and usage tracking.
"""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock
import json

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from dateutil.relativedelta import relativedelta

from core.models import TenantUser
from core.test_utils import KitaTestCase
from billing.models import Subscription, BillingPayment
from billing.views import UsageStatsCalculator

User = get_user_model()


class SubscriptionModelTestCase(KitaTestCase):
    """Test cases for Subscription model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create subscription
        self.subscription = Subscription.objects.create(
            tenant=self.tenant,
            plan_name='Kita Pro',
            monthly_price=Decimal('299.00'),
            currency='MXN',
            status='trial',
            trial_ends_at=timezone.now() + timedelta(days=30)
        )

    def test_create_subscription(self) -> None:
        """Test subscription creation."""
        self.assertIsNotNone(self.subscription.id)
        self.assertEqual(self.subscription.tenant, self.tenant)
        self.assertEqual(self.subscription.plan_name, 'Kita Pro')
        self.assertEqual(self.subscription.monthly_price, Decimal('299.00'))

    def test_subscription_status_properties(self) -> None:
        """Test subscription status helper properties."""
        self.assertTrue(self.subscription.is_trial)
        self.assertFalse(self.subscription.is_active)
        self.assertFalse(self.subscription.is_past_due)
        self.assertFalse(self.subscription.is_cancelled)

        # Change status
        self.subscription.status = 'active'
        self.assertFalse(self.subscription.is_trial)
        self.assertTrue(self.subscription.is_active)

    def test_days_until_trial_end(self) -> None:
        """Test trial days calculation."""
        # Set trial to end in 10 days
        self.subscription.trial_ends_at = timezone.now() + timedelta(days=10)
        self.assertEqual(self.subscription.days_until_trial_end, 10)

        # Set trial as expired
        self.subscription.trial_ends_at = timezone.now() - timedelta(days=1)
        self.assertEqual(self.subscription.days_until_trial_end, 0)

    def test_is_trial_expired(self) -> None:
        """Test trial expiration check."""
        # Future trial end
        self.subscription.trial_ends_at = timezone.now() + timedelta(days=1)
        self.assertFalse(self.subscription.is_trial_expired)

        # Past trial end
        self.subscription.trial_ends_at = timezone.now() - timedelta(days=1)
        self.assertTrue(self.subscription.is_trial_expired)

    def test_can_use_features(self) -> None:
        """Test feature access based on subscription status."""
        # Trial can use features
        self.subscription.status = 'trial'
        self.assertTrue(self.subscription.can_use_features)

        # Active can use features
        self.subscription.status = 'active'
        self.assertTrue(self.subscription.can_use_features)

        # Past due cannot
        self.subscription.status = 'past_due'
        self.assertFalse(self.subscription.can_use_features)

        # Cancelled cannot
        self.subscription.status = 'cancelled'
        self.assertFalse(self.subscription.can_use_features)

    def test_activate_subscription(self) -> None:
        """Test subscription activation."""
        self.subscription.activate_subscription()

        self.assertEqual(self.subscription.status, 'active')
        self.assertIsNotNone(self.subscription.current_period_start)
        self.assertIsNotNone(self.subscription.current_period_end)
        self.assertIsNotNone(self.subscription.next_billing_date)
        self.assertEqual(self.subscription.failed_payment_attempts, 0)

    def test_cancel_subscription_immediate(self) -> None:
        """Test immediate subscription cancellation."""
        self.subscription.status = 'active'
        self.subscription.cancel_subscription(reason='Test cancel', immediate=True)

        self.assertEqual(self.subscription.status, 'cancelled')
        self.assertIsNotNone(self.subscription.cancelled_at)
        self.assertEqual(self.subscription.cancellation_reason, 'Test cancel')

    def test_cancel_subscription_at_period_end(self) -> None:
        """Test subscription cancellation at period end."""
        self.subscription.status = 'active'
        self.subscription.cancel_subscription(reason='Test cancel', immediate=False)

        self.assertEqual(self.subscription.status, 'active')  # Still active
        self.assertTrue(self.subscription.cancel_at_period_end)
        self.assertEqual(self.subscription.cancellation_reason, 'Test cancel')

    def test_mark_payment_failed(self) -> None:
        """Test payment failure handling."""
        self.subscription.mark_payment_failed()
        self.assertEqual(self.subscription.failed_payment_attempts, 1)
        self.assertIsNotNone(self.subscription.last_failed_payment_date)

        # Multiple failures
        self.subscription.mark_payment_failed()
        self.subscription.mark_payment_failed()
        self.assertEqual(self.subscription.failed_payment_attempts, 3)
        self.assertEqual(self.subscription.status, 'past_due')

        # Too many failures
        self.subscription.mark_payment_failed()
        self.subscription.mark_payment_failed()
        self.assertEqual(self.subscription.failed_payment_attempts, 5)
        self.assertEqual(self.subscription.status, 'suspended')

    def test_mark_payment_successful(self) -> None:
        """Test successful payment handling."""
        amount = Decimal('299.00')
        self.subscription.failed_payment_attempts = 3
        self.subscription.status = 'past_due'

        self.subscription.mark_payment_successful(amount)

        self.assertEqual(self.subscription.status, 'active')
        self.assertEqual(self.subscription.failed_payment_attempts, 0)
        self.assertEqual(self.subscription.last_payment_amount, amount)
        self.assertIsNotNone(self.subscription.last_payment_date)
        self.assertIsNotNone(self.subscription.current_period_start)
        self.assertIsNotNone(self.subscription.current_period_end)

    def test_unique_tenant_constraint(self) -> None:
        """Test only one subscription per tenant."""
        with self.assertRaises(Exception):
            Subscription.objects.create(
                tenant=self.tenant,
                trial_ends_at=timezone.now() + timedelta(days=30)
            )

    def test_cache_key_generation(self) -> None:
        """Test cache key generation."""
        key = self.subscription.get_cache_key()
        self.assertIn(str(self.tenant.id), key)

        key_with_suffix = self.subscription.get_cache_key('stats')
        self.assertIn('stats', key_with_suffix)


class BillingPaymentModelTestCase(KitaTestCase):
    """Test cases for BillingPayment model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        self.subscription = Subscription.objects.create(
            tenant=self.tenant,
            trial_ends_at=timezone.now() + timedelta(days=30)
        )

        # Create payment
        now = timezone.now()
        self.payment = BillingPayment.objects.create(
            tenant=self.tenant,
            subscription=self.subscription,
            amount=Decimal('299.00'),
            currency='MXN',
            payment_method='mercadopago',
            status='pending',
            billing_period_start=now,
            billing_period_end=now + relativedelta(months=1)
        )

    def test_create_payment(self) -> None:
        """Test payment creation."""
        self.assertIsNotNone(self.payment.id)
        self.assertEqual(self.payment.tenant, self.tenant)
        self.assertEqual(self.payment.subscription, self.subscription)
        self.assertEqual(self.payment.amount, Decimal('299.00'))

    def test_payment_status_properties(self) -> None:
        """Test payment status helper properties."""
        self.assertFalse(self.payment.is_successful)
        self.assertFalse(self.payment.is_failed)

        self.payment.status = 'completed'
        self.assertTrue(self.payment.is_successful)

        self.payment.status = 'failed'
        self.assertTrue(self.payment.is_failed)

    def test_can_retry(self) -> None:
        """Test retry eligibility check."""
        # Pending payment cannot retry
        self.assertFalse(self.payment.can_retry)

        # Failed payment can retry
        self.payment.status = 'failed'
        self.assertTrue(self.payment.can_retry)

        # Max retries reached
        self.payment.retry_count = 3
        self.assertFalse(self.payment.can_retry)

    def test_mark_completed(self) -> None:
        """Test marking payment as completed."""
        self.payment.mark_completed()

        self.assertEqual(self.payment.status, 'completed')
        self.assertIsNotNone(self.payment.processed_at)
        self.assertEqual(self.subscription.status, 'active')

    def test_mark_failed(self) -> None:
        """Test marking payment as failed."""
        self.payment.mark_failed('Insufficient funds')

        self.assertEqual(self.payment.status, 'failed')
        self.assertEqual(self.payment.failure_reason, 'Insufficient funds')
        self.assertIsNotNone(self.payment.processed_at)
        self.assertEqual(self.subscription.failed_payment_attempts, 1)

    def test_payment_queryset_filters(self) -> None:
        """Test custom queryset methods."""
        # Create additional payments
        BillingPayment.objects.create(
            tenant=self.tenant,
            subscription=self.subscription,
            amount=Decimal('299.00'),
            status='completed',
            billing_period_start=timezone.now(),
            billing_period_end=timezone.now() + relativedelta(months=1)
        )

        BillingPayment.objects.create(
            tenant=self.tenant,
            subscription=self.subscription,
            amount=Decimal('299.00'),
            status='failed',
            retry_count=1,
            billing_period_start=timezone.now(),
            billing_period_end=timezone.now() + relativedelta(months=1)
        )

        # Test filters
        self.assertEqual(BillingPayment.objects.successful().count(), 1)
        self.assertEqual(BillingPayment.objects.failed().count(), 1)
        self.assertEqual(BillingPayment.objects.pending().count(), 1)
        self.assertEqual(BillingPayment.objects.retryable().count(), 1)


class BillingViewsTestCase(KitaTestCase):
    """Test cases for billing views."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create subscription
        self.subscription = Subscription.objects.create(
            tenant=self.tenant,
            trial_ends_at=timezone.now() + timedelta(days=30)
        )

    def test_subscription_index_requires_login(self) -> None:
        """Test subscription index requires authentication."""
        url = reverse('billing:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_subscription_index_requires_owner(self) -> None:
        """Test only owners can access billing."""
        # Create non-owner user
        regular_user = User.objects.create_user(
            email='user@test.com',
            password='TestPass123!'
        )
        TenantUser.objects.create(
            tenant=self.tenant,
            email=regular_user.email,
            is_owner=False,
            role='user'
        )

        self.client.login(email='user@test.com', password='TestPass123!')
        url = reverse('billing:index')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)  # Forbidden

    def test_subscription_index_success(self) -> None:
        """Test successful access to subscription index."""
        self.client.login(email='owner@test.com', password='TestPass123!')
        url = reverse('billing:index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('subscription', response.context)
        self.assertIn('usage_stats', response.context)
        self.assertIn('warnings', response.context)

    @patch('billing.views.KitaBillingService')
    def test_activate_subscription(self, mock_billing_service) -> None:
        """Test subscription activation."""
        mock_service = MagicMock()
        mock_service.create_subscription_preference.return_value = {
            'success': True,
            'init_point': 'https://payment.url',
            'preference_id': 'test_preference_123'
        }
        mock_billing_service.return_value = mock_service

        self.client.login(email='owner@test.com', password='TestPass123!')
        url = reverse('billing:activate')

        response = self.client.post(url)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertIn('payment_url', data)
        self.assertEqual(data['preference_id'], 'test_preference_123')

    def test_cancel_subscription(self) -> None:
        """Test subscription cancellation."""
        self.subscription.status = 'active'
        self.subscription.save()

        self.client.login(email='owner@test.com', password='TestPass123!')
        url = reverse('billing:cancel')

        response = self.client.post(
            url,
            data=json.dumps({
                'immediate': True,
                'reason': 'Test cancellation'
            }),
            content_type='application/json'
        )

        data = json.loads(response.content)
        self.assertTrue(data['success'])

        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, 'cancelled')
        self.assertEqual(self.subscription.cancellation_reason, 'Test cancellation')

    def test_cancel_subscription_rate_limit(self) -> None:
        """Test cancellation rate limiting."""
        self.client.login(email='owner@test.com', password='TestPass123!')
        url = reverse('billing:cancel')

        # Make 6 requests (limit is 5/day)
        for i in range(6):
            response = self.client.post(
                url,
                data=json.dumps({'immediate': False}),
                content_type='application/json'
            )
            if i < 5:
                self.assertNotEqual(response.status_code, 429)
            else:
                # 6th request should be rate limited
                self.assertEqual(response.status_code, 429)

    def test_subscription_stats(self) -> None:
        """Test subscription stats endpoint."""
        self.client.login(email='owner@test.com', password='TestPass123!')
        url = reverse('billing:stats')

        response = self.client.get(url)
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertIn('stats', data)
        stats = data['stats']
        self.assertIn('status', stats)
        self.assertIn('can_use_features', stats)


class UsageStatsCalculatorTestCase(KitaTestCase):
    """Test cases for usage stats calculator."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

    @patch('billing.views.PaymentLink')
    @patch('billing.views.Invoice')
    @patch('billing.views.Notification')
    def test_calculate_stats(self, mock_notif, mock_invoice, mock_payment) -> None:
        """Test usage stats calculation."""
        # Mock counts
        mock_payment.objects.filter.return_value.count.return_value = 10
        mock_invoice.objects.filter.return_value.count.return_value = 5
        mock_notif.objects.filter.return_value.count.return_value = 15

        # Mock revenue
        mock_aggregate = MagicMock()
        mock_aggregate.aggregate.return_value = {'total': Decimal('1500.00')}
        mock_payment.objects.filter.return_value = mock_aggregate

        stats = UsageStatsCalculator.calculate(self.tenant)

        self.assertIn('links_created', stats)
        self.assertIn('invoices_generated', stats)
        self.assertIn('notifications_sent', stats)
        self.assertIn('total_revenue', stats)

    def test_stats_caching(self) -> None:
        """Test stats are cached."""
        cache_key = UsageStatsCalculator.get_cache_key(str(self.tenant.id))

        # Set cached value
        cached_stats = {'test': 'cached'}
        cache.set(cache_key, cached_stats, 3600)

        # Should return cached value
        stats = UsageStatsCalculator.calculate(self.tenant)
        self.assertEqual(stats, cached_stats)

    def test_cache_key_generation(self) -> None:
        """Test cache key includes date."""
        today = timezone.now().date()
        key = UsageStatsCalculator.get_cache_key('test_tenant', 'month')

        self.assertIn('test_tenant', key)
        self.assertIn('month', key)
        self.assertIn(str(today), key)