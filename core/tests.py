"""
Tests for core models, middleware, and utilities.

Tests tenant management, audit logging, analytics, and notifications.
"""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, Mock
import uuid

from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.utils import timezone
from django.http import Http404

from core.models import (
    Tenant, TenantUser, Analytics, AuditLog, Notification
)
from core.middleware import (
    TenantMiddleware, tenant_required, tenant_user_required,
    allow_without_tenant, invalidate_tenant_cache
)
from core.test_utils import KitaTestCase

User = get_user_model()


class TenantModelTestCase(TestCase):
    """Test cases for Tenant model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        cache.clear()
        self.tenant = Tenant.objects.create(
            name='Test Company',
            slug='test-company',
            domain='test.example.com',
            business_name='Test Company LLC',
            rfc='ABC010101ABC',
            email='info@test.com',
            is_active=True
        )

    def test_create_tenant(self) -> None:
        """Test tenant creation."""
        self.assertIsNotNone(self.tenant.id)
        self.assertEqual(self.tenant.name, 'Test Company')
        self.assertEqual(self.tenant.slug, 'test-company')
        self.assertTrue(self.tenant.is_active)

    def test_tenant_queryset_active(self) -> None:
        """Test active tenant filtering."""
        # Create inactive tenant
        Tenant.objects.create(
            name='Inactive Company',
            slug='inactive',
            rfc='XYZ010101XYZ',
            email='inactive@test.com',
            is_active=False
        )

        active_tenants = Tenant.objects.active()
        self.assertEqual(active_tenants.count(), 1)
        self.assertEqual(active_tenants.first(), self.tenant)

    def test_tenant_by_domain(self) -> None:
        """Test tenant lookup by domain."""
        found = Tenant.objects.by_domain('test.example.com')
        self.assertEqual(found, self.tenant)

        not_found = Tenant.objects.by_domain('nonexistent.com')
        self.assertIsNone(not_found)

    def test_tenant_by_slug(self) -> None:
        """Test tenant lookup by slug."""
        found = Tenant.objects.by_slug('test-company')
        self.assertEqual(found, self.tenant)

        not_found = Tenant.objects.by_slug('nonexistent')
        self.assertIsNone(not_found)

    @patch('billing.models.Subscription')
    def test_tenant_subscription_property_cached(self, mock_subscription) -> None:
        """Test subscription property is cached."""
        mock_sub = MagicMock()
        mock_sub.status = 'active'
        mock_subscription.objects.filter.return_value.first.return_value = mock_sub

        # First call - should hit database
        sub1 = self.tenant.subscription
        self.assertEqual(sub1, mock_sub)
        mock_subscription.objects.filter.assert_called_once()

        # Second call - should hit cache
        mock_subscription.objects.filter.reset_mock()
        sub2 = self.tenant.subscription
        self.assertEqual(sub2, mock_sub)
        mock_subscription.objects.filter.assert_not_called()

    def test_invalidate_cache(self) -> None:
        """Test cache invalidation."""
        cache_key = f"tenant:{self.tenant.id}:subscription"
        cache.set(cache_key, {'test': 'data'}, 300)

        self.tenant.invalidate_cache()

        cached = cache.get(cache_key)
        self.assertIsNone(cached)


class TenantUserModelTestCase(KitaTestCase):
    """Test cases for TenantUser model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        # self.tenant_user is already created as an owner in parent class
        self.owner = self.tenant_user

        self.user = TenantUser.objects.create(
            tenant=self.tenant,
            email='user@test.com',
            first_name='Jane',
            last_name='User',
            is_owner=False,
            role='user'
        )

    def test_create_tenant_user(self) -> None:
        """Test tenant user creation."""
        self.assertEqual(self.owner.full_name, 'Test Owner')
        self.assertTrue(self.owner.is_owner)
        self.assertEqual(self.owner.role, 'owner')

    def test_unique_constraint(self) -> None:
        """Test unique constraint on tenant+email."""
        with self.assertRaises(Exception):
            TenantUser.objects.create(
                tenant=self.tenant,
                email='owner@test.com',  # Duplicate
                first_name='Duplicate',
                last_name='User'
            )

    def test_queryset_active(self) -> None:
        """Test active users filtering."""
        # Create inactive user
        TenantUser.objects.create(
            tenant=self.tenant,
            email='inactive@test.com',
            first_name='Inactive',
            last_name='User',
            is_active=False
        )

        active_users = TenantUser.objects.active()
        self.assertEqual(active_users.count(), 2)
        self.assertIn(self.owner, active_users)
        self.assertIn(self.user, active_users)

    def test_queryset_owners(self) -> None:
        """Test owner filtering."""
        owners = TenantUser.objects.owners()
        self.assertEqual(owners.count(), 1)
        self.assertEqual(owners.first(), self.owner)

    def test_queryset_by_role(self) -> None:
        """Test role filtering."""
        users = TenantUser.objects.by_role('user')
        self.assertEqual(users.count(), 1)
        self.assertEqual(users.first(), self.user)

    def test_has_permission(self) -> None:
        """Test permission checking."""
        # Owner has all permissions
        self.assertTrue(self.owner.has_permission('create_links'))
        self.assertTrue(self.owner.has_permission('manage_settings'))
        self.assertTrue(self.owner.has_permission('nonexistent'))

        # Regular user has specific permissions
        self.user.can_create_links = True
        self.user.can_manage_settings = False
        self.assertTrue(self.user.has_permission('create_links'))
        self.assertFalse(self.user.has_permission('manage_settings'))


class AnalyticsModelTestCase(KitaTestCase):
    """Test cases for Analytics model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        self.analytics = Analytics.objects.create(
            tenant=self.tenant,
            date=timezone.now().date(),
            period_type='daily',
            links_created=10,
            payments_successful=5,
            revenue_gross=29900,  # 299.00 pesos in centavos
            revenue_fees=1495,    # 14.95 pesos in centavos
            revenue_net=28405     # 284.05 pesos in centavos
        )

    def test_create_analytics(self) -> None:
        """Test analytics creation."""
        self.assertEqual(self.analytics.links_created, 10)
        self.assertEqual(self.analytics.payments_successful, 5)

    def test_revenue_conversion(self) -> None:
        """Test centavos to pesos conversion."""
        self.assertEqual(self.analytics.revenue_gross_pesos, Decimal('299.00'))
        self.assertEqual(self.analytics.revenue_fees_pesos, Decimal('14.95'))
        self.assertEqual(self.analytics.revenue_net_pesos, Decimal('284.05'))

    def test_unique_constraint(self) -> None:
        """Test unique constraint on tenant+date+period."""
        with self.assertRaises(Exception):
            Analytics.objects.create(
                tenant=self.tenant,
                date=self.analytics.date,
                period_type='daily'  # Duplicate
            )

    def test_increment_metric(self) -> None:
        """Test atomic metric increment."""
        initial_value = self.analytics.links_created
        self.analytics.increment_metric('links_created', 5)

        # Reload from database
        self.analytics.refresh_from_db()
        self.assertEqual(self.analytics.links_created, initial_value + 5)

    def test_queryset_for_period(self) -> None:
        """Test date range filtering."""
        start_date = timezone.now() - timedelta(days=7)
        end_date = timezone.now()

        analytics = Analytics.objects.for_period(
            self.tenant,
            start_date,
            end_date
        )
        self.assertIn(self.analytics, analytics)

    def test_queryset_by_period_type(self) -> None:
        """Test period type filtering."""
        # Create monthly analytics
        monthly = Analytics.objects.create(
            tenant=self.tenant,
            date=timezone.now().date() - timedelta(days=30),
            period_type='monthly'
        )

        daily_stats = Analytics.objects.daily()
        self.assertIn(self.analytics, daily_stats)
        self.assertNotIn(monthly, daily_stats)

        monthly_stats = Analytics.objects.monthly()
        self.assertIn(monthly, monthly_stats)
        self.assertNotIn(self.analytics, monthly_stats)


class AuditLogModelTestCase(KitaTestCase):
    """Test cases for AuditLog model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

    def test_create_audit_log(self) -> None:
        """Test audit log creation."""
        log = AuditLog.objects.log_action(
            tenant=self.tenant,
            user_email='admin@test.com',
            user_name='Admin User',
            action='create_link',
            entity_type='PaymentLink',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            entity_id=uuid.uuid4(),
            notes='Created payment link'
        )

        self.assertIsNotNone(log.id)
        self.assertEqual(log.action, 'create_link')
        self.assertEqual(log.entity_type, 'PaymentLink')

    def test_queryset_by_action(self) -> None:
        """Test filtering by action."""
        log1 = AuditLog.objects.create(
            tenant=self.tenant,
            user_email='user@test.com',
            user_name='User',
            action='login',
            entity_type='Session',
            ip_address='1.1.1.1',
            user_agent='Chrome'
        )

        log2 = AuditLog.objects.create(
            tenant=self.tenant,
            user_email='user@test.com',
            user_name='User',
            action='logout',
            entity_type='Session',
            ip_address='1.1.1.1',
            user_agent='Chrome'
        )

        login_logs = AuditLog.objects.by_action('login')
        self.assertIn(log1, login_logs)
        self.assertNotIn(log2, login_logs)

    def test_queryset_recent(self) -> None:
        """Test recent logs filtering."""
        # Create old log
        old_log = AuditLog.objects.create(
            tenant=self.tenant,
            user_email='user@test.com',
            user_name='User',
            action='old_action',
            entity_type='Test',
            ip_address='1.1.1.1',
            user_agent='Chrome'
        )
        old_log.created_at = timezone.now() - timedelta(days=30)
        old_log.save()

        # Create recent log
        recent_log = AuditLog.objects.create(
            tenant=self.tenant,
            user_email='user@test.com',
            user_name='User',
            action='recent_action',
            entity_type='Test',
            ip_address='1.1.1.1',
            user_agent='Chrome'
        )

        recent = AuditLog.objects.recent(days=7)
        self.assertIn(recent_log, recent)
        self.assertNotIn(old_log, recent)


class NotificationModelTestCase(KitaTestCase):
    """Test cases for Notification model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        self.notification = Notification.objects.create(
            tenant=self.tenant,
            recipient_email='user@test.com',
            recipient_phone='+5215551234567',
            notification_type='payment_received',
            channel='whatsapp',
            subject='Payment Received',
            message='You have received a payment',
            status='pending'
        )

    def test_create_notification(self) -> None:
        """Test notification creation."""
        self.assertEqual(self.notification.status, 'pending')
        self.assertEqual(self.notification.channel, 'whatsapp')
        self.assertEqual(self.notification.retry_count, 0)

    def test_can_retry(self) -> None:
        """Test retry eligibility."""
        # Pending can't retry
        self.assertFalse(self.notification.can_retry())

        # Failed can retry
        self.notification.status = 'failed'
        self.assertTrue(self.notification.can_retry())

        # Max retries reached
        self.notification.retry_count = 3
        self.assertFalse(self.notification.can_retry())

    def test_mark_sent(self) -> None:
        """Test marking notification as sent."""
        self.notification.mark_sent()

        self.assertEqual(self.notification.status, 'sent')
        self.assertIsNotNone(self.notification.sent_at)

    def test_mark_failed(self) -> None:
        """Test marking notification as failed."""
        self.notification.mark_failed('Connection timeout')

        self.assertEqual(self.notification.status, 'failed')
        self.assertEqual(self.notification.error_message, 'Connection timeout')
        self.assertEqual(self.notification.retry_count, 1)

    def test_queryset_pending(self) -> None:
        """Test pending notifications filter."""
        sent = Notification.objects.create(
            tenant=self.tenant,
            recipient_email='sent@test.com',
            notification_type='test',
            channel='email',
            subject='Test',
            message='Test',
            status='sent'
        )

        pending = Notification.objects.pending()
        self.assertIn(self.notification, pending)
        self.assertNotIn(sent, pending)

    def test_queryset_retryable(self) -> None:
        """Test retryable notifications filter."""
        # Failed with retries left
        retryable = Notification.objects.create(
            tenant=self.tenant,
            recipient_email='retry@test.com',
            notification_type='test',
            channel='email',
            subject='Test',
            message='Test',
            status='failed',
            retry_count=1,
            max_retries=3
        )

        # Failed with no retries left
        not_retryable = Notification.objects.create(
            tenant=self.tenant,
            recipient_email='noretry@test.com',
            notification_type='test',
            channel='email',
            subject='Test',
            message='Test',
            status='failed',
            retry_count=3,
            max_retries=3
        )

        retryable_notifs = Notification.objects.retryable()
        self.assertIn(retryable, retryable_notifs)
        self.assertNotIn(not_retryable, retryable_notifs)
        self.assertNotIn(self.notification, retryable_notifs)  # Pending


class TenantMiddlewareTestCase(KitaTestCase):
    """Test cases for TenantMiddleware."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda r: None)

    def test_public_path_no_tenant(self) -> None:
        """Test public paths don't require tenant."""
        request = self.factory.get('/static/test.css')
        request.user = Mock(is_authenticated=False)

        self.middleware.process_request(request)

        self.assertIsNone(request.tenant)
        self.assertIsNone(request.tenant_user)

    def test_authenticated_user_with_tenant(self) -> None:
        """Test authenticated user gets tenant."""
        request = self.factory.get('/panel/')  # 🇪🇸 Migrado
        request.user = self.user

        self.middleware.process_request(request)

        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.tenant_user, self.tenant_user)

    def test_authenticated_user_without_tenant_redirects(self) -> None:
        """Test user without tenant redirects to onboarding."""
        user = User.objects.create_user(
            email='notenant@test.com',
            password='TestPass123!'
        )

        request = self.factory.get('/panel/')  # 🇪🇸 Migrado
        request.user = user

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
        self.assertIn('onboarding', response.url)

    def test_unauthenticated_protected_path_redirects(self) -> None:
        """Test unauthenticated user redirects to login."""
        request = self.factory.get('/panel/')  # 🇪🇸 Migrado
        request.user = Mock(is_authenticated=False)

        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
        self.assertIn('account_login', response.url)

    def test_tenant_user_caching(self) -> None:
        """Test tenant user is cached."""
        request = self.factory.get('/panel/')  # 🇪🇸 Migrado
        request.user = self.user

        # First call - should query database
        with self.assertNumQueries(1):
            self.middleware.process_request(request)

        # Second call - should use cache
        request2 = self.factory.get('/panel/')  # 🇪🇸 Migrado
        request2.user = self.user

        with self.assertNumQueries(0):
            self.middleware.process_request(request2)

        self.assertEqual(request2.tenant, self.tenant)

    def test_invalidate_tenant_cache(self) -> None:
        """Test cache invalidation function."""
        # Cache tenant user
        cache_key = f"tenant_user:{self.user.email}"
        cache.set(cache_key, self.tenant_user, 300)

        # Invalidate
        invalidate_tenant_cache(self.user.email)

        # Check cache is cleared
        cached = cache.get(cache_key)
        self.assertIsNone(cached)


class TenantDecoratorsTestCase(KitaTestCase):
    """Test cases for tenant decorators."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.factory = RequestFactory()

    def test_tenant_required_with_tenant(self) -> None:
        """Test tenant_required passes with tenant."""
        @tenant_required
        def view(request):
            return 'Success'

        request = self.factory.get('/')
        request.tenant = self.tenant

        response = view(request)
        self.assertEqual(response, 'Success')

    def test_tenant_required_without_tenant(self) -> None:
        """Test tenant_required raises 404 without tenant."""
        @tenant_required
        def view(request):
            return 'Success'

        request = self.factory.get('/')
        request.tenant = None

        with self.assertRaises(Http404):
            view(request)

    def test_tenant_user_required_with_user(self) -> None:
        """Test tenant_user_required passes with tenant user."""
        @tenant_user_required
        def view(request):
            return 'Success'

        request = self.factory.get('/')
        request.tenant_user = self.tenant_user

        response = view(request)
        self.assertEqual(response, 'Success')

    def test_tenant_user_required_without_user(self) -> None:
        """Test tenant_user_required raises PermissionDenied."""
        @tenant_user_required
        def view(request):
            return 'Success'

        request = self.factory.get('/')
        request.tenant_user = None

        with self.assertRaises(PermissionDenied):
            view(request)

    def test_allow_without_tenant(self) -> None:
        """Test allow_without_tenant marks view."""
        @allow_without_tenant
        def view(request):
            return 'Success'

        self.assertTrue(hasattr(view, 'allow_without_tenant'))
        self.assertTrue(view.allow_without_tenant)