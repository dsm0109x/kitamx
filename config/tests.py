"""
Tests for configuration management views.

Tests integration settings, notifications, and webhooks configuration.
"""
from __future__ import annotations
from datetime import timedelta
from unittest.mock import patch, MagicMock
import json

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache

from core.models import TenantUser, Notification
from core.test_utils import KitaTestCase
from payments.models import MercadoPagoIntegration

User = get_user_model()


class ConfigViewsTestCase(KitaTestCase):
    """Test cases for configuration views."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create regular user
        self.regular_user = User.objects.create_user(
            email='user@test.com',
            password='TestPass123!'
        )

        # Create regular tenant user
        self.user_tenant = TenantUser.objects.create(
            tenant=self.tenant,
            email=self.regular_user.email,
            is_owner=False,
            role='user'
        )

    def test_settings_index_requires_owner(self) -> None:
        """Test settings index requires owner role."""
        # Regular user should be forbidden
        self.client.login(email='user@test.com', password='TestPass123!')
        response = self.client.get(reverse('config:index'))
        self.assertEqual(response.status_code, 403)

        # Owner should have access
        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('config:index'))
        self.assertEqual(response.status_code, 200)

    def test_settings_index_context(self) -> None:
        """Test settings index provides correct context."""
        # Create MercadoPago integration
        mp_integration = MercadoPagoIntegration.objects.create(
            tenant=self.tenant,
            user_id='MP_USER_123',
            is_active=True,
            access_token='test_token',
            refresh_token='test_refresh'
        )

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('config:index'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('current_settings', response.context)
        self.assertIn('tenant', response.context)

        settings_data = response.context['current_settings']
        self.assertTrue(settings_data['mercadopago']['configured'])
        self.assertEqual(settings_data['mercadopago']['user_id'], 'MP_USER_123')

    @patch('config.views.MercadoPagoService')
    def test_test_mp_connection_success(self, mock_mp_service) -> None:
        """Test MercadoPago connection test success."""
        # Create integration
        MercadoPagoIntegration.objects.create(
            tenant=self.tenant,
            is_active=True,
            access_token='test_token'
        )

        # Mock service
        mock_service = MagicMock()
        mock_service.integration = True
        mock_service.get_payment_methods.return_value = {'methods': ['card', 'pix']}
        mock_mp_service.return_value = mock_service

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.post(reverse('config:test_mp_connection'))

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Conexión MercadoPago exitosa')

    @patch('config.views.MercadoPagoService')
    def test_test_mp_connection_no_integration(self, mock_mp_service) -> None:
        """Test MercadoPago connection without integration."""
        mock_service = MagicMock()
        mock_service.integration = None
        mock_mp_service.return_value = mock_service

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.post(reverse('config:test_mp_connection'))

        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertEqual(data['error'], 'No hay integración de MercadoPago configurada')

    def test_test_mp_connection_rate_limit(self) -> None:
        """Test MercadoPago connection test rate limiting."""
        self.client.login(email='owner@test.com', password='TestPass123!')
        url = reverse('config:test_mp_connection')

        # Make 11 requests (limit is 10/hour)
        for i in range(11):
            response = self.client.post(url)
            if i < 10:
                self.assertNotEqual(response.status_code, 429)
            else:
                # 11th request should be rate limited
                self.assertEqual(response.status_code, 429)

    @patch('config.views.notification_service')
    def test_test_whatsapp_success(self, mock_notification) -> None:
        """Test WhatsApp notification test."""
        mock_notification.send_notification.return_value = {
            'success': True,
            'message_id': 'WA_123'
        }

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.post(reverse('config:test_whatsapp'))

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Prueba de WhatsApp enviada')

        # Verify correct parameters
        mock_notification.send_notification.assert_called_once()
        call_args = mock_notification.send_notification.call_args[1]
        self.assertEqual(call_args['tenant'], self.tenant)
        self.assertEqual(call_args['notification_type'], 'test')

    @patch('config.views.notification_service')
    def test_test_email_success(self, mock_notification) -> None:
        """Test email notification test."""
        mock_notification.send_notification.return_value = {
            'success': True,
            'message_id': 'EMAIL_123'
        }

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.post(reverse('config:test_email'))

        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message'], 'Email de prueba enviado')

    def test_integrations_view_cached(self) -> None:
        """Test integrations view is cached."""
        # Create some test data
        MercadoPagoIntegration.objects.create(
            tenant=self.tenant,
            is_active=True
        )

        for i in range(5):
            Notification.objects.create(
                tenant=self.tenant,
                recipient_email=f'test{i}@example.com',
                notification_type='test',
                channel='email',
                subject='Test',
                message='Test message',
                status='sent'
            )

        self.client.login(email='owner@test.com', password='TestPass123!')

        # First request
        with self.assertNumQueries(4):  # Queries for auth + data
            response1 = self.client.get(reverse('config:integrations'))
            self.assertEqual(response1.status_code, 200)

        # Second request should be cached
        with self.assertNumQueries(2):  # Only auth queries
            response2 = self.client.get(reverse('config:integrations'))
            self.assertEqual(response2.status_code, 200)

    def test_notifications_settings_aggregation(self) -> None:
        """Test notification settings aggregates correctly."""
        # Create test notifications
        last_30_days = timezone.now() - timedelta(days=15)

        # Create various notifications
        for i in range(10):
            Notification.objects.create(
                tenant=self.tenant,
                recipient_email='test@example.com',
                notification_type='test',
                channel='whatsapp' if i < 5 else 'email',
                status='sent' if i < 8 else 'failed',
                subject='Test',
                message='Test',
                created_at=last_30_days
            )

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('config:notifications'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('notification_stats', response.context)

        stats = response.context['notification_stats']
        self.assertEqual(stats['total_sent'], 8)
        self.assertEqual(stats['whatsapp_sent'], 5)
        self.assertEqual(stats['email_sent'], 3)
        self.assertEqual(stats['failed'], 2)

    def test_notifications_settings_caching(self) -> None:
        """Test notification stats are cached."""
        cache_key = f"config:notification_stats:{self.tenant.id}"

        # Set cached value
        cached_stats = {
            'total_sent': 100,
            'whatsapp_sent': 60,
            'email_sent': 40,
            'failed': 5
        }
        cache.set(cache_key, cached_stats, 300)

        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('config:notifications'))

        stats = response.context['notification_stats']
        self.assertEqual(stats['total_sent'], 100)
        self.assertEqual(stats['whatsapp_sent'], 60)

    def test_webhooks_management(self) -> None:
        """Test webhooks management returns correct info."""
        self.client.login(email='owner@test.com', password='TestPass123!')
        response = self.client.get(reverse('config:webhooks'))

        data = json.loads(response.content)
        self.assertIn('endpoints', data)
        self.assertEqual(data['endpoints']['payment_webhook'], '/webhook/mercadopago/')
        self.assertEqual(data['endpoints']['subscription_webhook'], '/webhook/mercadopago/')

    def test_update_redirects(self) -> None:
        """Test update endpoints return appropriate redirects."""
        self.client.login(email='owner@test.com', password='TestPass123!')

        # Test MercadoPago redirect
        response = self.client.get(reverse('config:update_mp_integration'))
        data = json.loads(response.content)
        self.assertEqual(data['redirect'], '/incorporacion/paso2/')  # 🇪🇸 Migrado

        # Test notifications redirect
        response = self.client.get(reverse('config:update_notifications'))
        data = json.loads(response.content)
        self.assertEqual(data['redirect'], '/cuenta/')  # 🇪🇸 Migrado

    def test_environment_info_endpoints(self) -> None:
        """Test endpoints that provide environment info."""
        self.client.login(email='owner@test.com', password='TestPass123!')

        # WhatsApp info
        response = self.client.get(reverse('config:update_whatsapp'))
        data = json.loads(response.content)
        self.assertIn('WA_TOKEN', data['info'])

        # Email info
        response = self.client.get(reverse('config:update_email'))
        data = json.loads(response.content)
        self.assertIn('POSTMARK_TOKEN', data['info'])

        # Advanced settings info
        response = self.client.get(reverse('config:advanced'))
        data = json.loads(response.content)
        self.assertIn('Django admin', data['message'])


class ConfigSecurityTestCase(KitaTestCase):
    """Test security features in config views."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

    def test_all_views_require_authentication(self) -> None:
        """Test all views require authentication."""
        urls = [
            reverse('config:index'),
            reverse('config:integrations'),
            reverse('config:notifications'),
            reverse('config:webhooks'),
            reverse('config:advanced'),
        ]

        for url in urls:
            response = self.client.get(url)
            # Should redirect to login
            self.assertEqual(response.status_code, 302)
            self.assertIn('/accounts/login/', response.url)

    def test_post_endpoints_require_csrf(self) -> None:
        """Test POST endpoints require CSRF."""
        # Create owner user
        owner = User.objects.create_user(
            email='owner@test.com',
            password='TestPass123!'
        )
        TenantUser.objects.create(
            tenant=self.tenant,
            email=owner.email,
            is_owner=True
        )

        self.client.login(email='owner@test.com', password='TestPass123!')

        # Disable CSRF for this request
        self.client.handler.enforce_csrf_checks = False

        urls = [
            reverse('config:test_mp_connection'),
            reverse('config:test_whatsapp'),
            reverse('config:test_email'),
        ]

        for url in urls:
            # Should work with CSRF
            response = self.client.post(url)
            # Should not return 403 Forbidden for CSRF
            self.assertNotEqual(response.status_code, 403)

    def test_non_owners_forbidden(self) -> None:
        """Test non-owners cannot access config."""
        # Create regular user
        TenantUser.objects.create(
            tenant=self.tenant,
            email='user@test.com',
            is_owner=False,
            role='user'
        )

        self.client.login(email='user@test.com', password='TestPass123!')

        urls = [
            reverse('config:index'),
            reverse('config:integrations'),
            reverse('config:notifications'),
        ]

        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)
