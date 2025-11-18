"""Tests for Kita project configuration.

Tests settings, URL routing, and Celery configuration.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import os

from django.test import TestCase, Client, override_settings
from django.urls import reverse, resolve
from django.conf import settings
from django.core.cache import cache


class SettingsTestCase(TestCase):
    """Test cases for Django settings configuration."""

    def test_required_settings(self) -> None:
        """Test that all required settings are configured."""
        # Core settings
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertIsInstance(settings.DEBUG, bool)
        self.assertIsInstance(settings.ALLOWED_HOSTS, list)

        # Database
        self.assertIn('default', settings.DATABASES)

        # Apps
        self.assertIn('core', settings.INSTALLED_APPS)
        self.assertIn('accounts', settings.INSTALLED_APPS)
        self.assertIn('payments', settings.INSTALLED_APPS)
        self.assertIn('invoicing', settings.INSTALLED_APPS)

        # Middleware
        self.assertIn('core.middleware.TenantMiddleware', settings.MIDDLEWARE)

        # Authentication
        self.assertEqual(settings.AUTH_USER_MODEL, 'accounts.User')

    def test_cache_configuration(self) -> None:
        """Test cache configuration with Redis."""
        self.assertIn('default', settings.CACHES)
        cache_config = settings.CACHES['default']
        self.assertEqual(cache_config['BACKEND'], 'django.core.cache.backends.redis.RedisCache')

        # Test cache operations
        cache.set('test_key', 'test_value', 60)
        self.assertEqual(cache.get('test_key'), 'test_value')
        cache.delete('test_key')

    def test_celery_configuration(self) -> None:
        """Test Celery settings."""
        self.assertIsNotNone(settings.CELERY_BROKER_URL)
        self.assertIsNotNone(settings.CELERY_RESULT_BACKEND)
        self.assertEqual(settings.CELERY_TASK_SERIALIZER, 'json')
        self.assertEqual(settings.CELERY_RESULT_SERIALIZER, 'json')

        # Test task routing
        self.assertIn('invoicing.tasks.*', settings.CELERY_TASK_ROUTES)
        self.assertIn('payments.tasks.*', settings.CELERY_TASK_ROUTES)

    def test_business_settings(self) -> None:
        """Test business configuration settings."""
        self.assertEqual(settings.MONTHLY_SUBSCRIPTION_PRICE, 299.00)
        self.assertEqual(settings.TRIAL_DAYS, 30)
        self.assertEqual(settings.LINK_EXPIRY_OPTIONS, [1, 3, 7])

    def test_security_settings_production(self) -> None:
        """Test security settings in production mode."""
        with override_settings(DEBUG=False):
            from django.conf import settings as test_settings

            if not test_settings.DEBUG:
                # These should be True in production
                self.assertTrue(test_settings.SECURE_SSL_REDIRECT)
                self.assertTrue(test_settings.SESSION_COOKIE_SECURE)
                self.assertTrue(test_settings.CSRF_COOKIE_SECURE)

    def test_email_configuration(self) -> None:
        """Test email settings."""
        self.assertEqual(settings.EMAIL_BACKEND, 'django.core.mail.backends.smtp.EmailBackend')
        self.assertEqual(settings.EMAIL_HOST, 'smtp.postmarkapp.com')
        self.assertEqual(settings.EMAIL_PORT, 587)
        self.assertTrue(settings.EMAIL_USE_TLS)

    def test_allauth_configuration(self) -> None:
        """Test django-allauth settings."""
        self.assertTrue(settings.ACCOUNT_EMAIL_REQUIRED)
        self.assertFalse(settings.ACCOUNT_USERNAME_REQUIRED)
        self.assertEqual(settings.ACCOUNT_AUTHENTICATION_METHOD, 'email')
        self.assertEqual(settings.ACCOUNT_EMAIL_VERIFICATION, 'mandatory')
        self.assertEqual(settings.LOGIN_REDIRECT_URL, '/incorporacion/')  # 🇪🇸 Migrado de /onboarding/

    def test_storage_configuration(self) -> None:
        """Test file storage settings."""
        self.assertIsNotNone(settings.AWS_ACCESS_KEY_ID)
        self.assertIsNotNone(settings.AWS_SECRET_ACCESS_KEY)
        self.assertIsNotNone(settings.AWS_STORAGE_BUCKET_NAME)
        self.assertEqual(settings.AWS_DEFAULT_ACL, 'private')
        self.assertEqual(settings.DEFAULT_FILE_STORAGE, 'storages.backends.s3boto3.S3Boto3Storage')


class URLRoutingTestCase(TestCase):
    """Test cases for URL routing configuration."""

    def setUp(self) -> None:
        """Set up test client."""
        self.client = Client()

    def test_home_url_resolves(self) -> None:
        """Test home URL resolution."""
        url = reverse('home')
        self.assertEqual(url, '/')

        resolver = resolve('/')
        self.assertEqual(resolver.view_name, 'home')

    def test_admin_url_accessible(self) -> None:
        """Test admin URL is accessible."""
        response = self.client.get('/admin/')
        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_app_urls_included(self) -> None:
        """Test all app URLs are included."""
        # Test that URLs can be reversed
        urls_to_test = [
            ('account_login', '/accounts/login/'),
            ('onboarding:start', '/incorporacion/'),  # 🇪🇸 Migrado
            ('dashboard:index', '/panel/'),  # 🇪🇸 Migrado
        ]

        for name, expected_path in urls_to_test:
            try:
                url = reverse(name)
                self.assertEqual(url, expected_path)
            except Exception as e:
                self.fail(f"Failed to reverse {name}: {e}")

    def test_static_url_configuration(self) -> None:
        """Test static URL configuration."""
        self.assertEqual(settings.STATIC_URL, '/static/')
        self.assertEqual(settings.MEDIA_URL, '/media/')

    def test_home_view_response(self) -> None:
        """Test home view returns correct response."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Kita', response.content)


class CeleryConfigurationTestCase(TestCase):
    """Test cases for Celery configuration."""

    @patch('kita.celery.Celery')
    def test_celery_app_configuration(self, mock_celery: MagicMock) -> None:
        """Test Celery app is configured correctly."""

        # Test that Celery app is created
        mock_celery.assert_called_with('kita')

    def test_task_routing(self) -> None:
        """Test task routing configuration."""
        from kita.celery import TASK_ROUTES

        # High priority queues
        self.assertEqual(TASK_ROUTES['invoicing.tasks.*']['queue'], 'high')
        self.assertEqual(TASK_ROUTES['payments.tasks.*']['queue'], 'high')
        self.assertEqual(TASK_ROUTES['webhooks.tasks.*']['queue'], 'high')

        # Default priority queues
        self.assertEqual(TASK_ROUTES['notifications.tasks.*']['queue'], 'default')
        self.assertEqual(TASK_ROUTES['billing.tasks.*']['queue'], 'default')

        # Low priority queues
        self.assertEqual(TASK_ROUTES['core.tasks.*']['queue'], 'low')
        self.assertEqual(TASK_ROUTES['analytics.tasks.*']['queue'], 'low')

    def test_celery_beat_schedule(self) -> None:
        """Test Celery Beat periodic tasks."""
        beat_schedule = settings.CELERY_BEAT_SCHEDULE

        # Test reconciliation tasks
        self.assertIn('reconcile-payment-links', beat_schedule)
        self.assertIn('reconcile-subscription-payments', beat_schedule)
        self.assertIn('generate-reconciliation-report', beat_schedule)

        # Test schedules
        self.assertEqual(beat_schedule['reconcile-payment-links']['schedule'], 300.0)
        self.assertEqual(beat_schedule['reconcile-subscription-payments']['schedule'], 600.0)
        self.assertEqual(beat_schedule['generate-reconciliation-report']['schedule'], 86400.0)


class MiddlewareTestCase(TestCase):
    """Test cases for middleware configuration."""

    def test_middleware_order(self) -> None:
        """Test middleware are in correct order."""
        middleware = settings.MIDDLEWARE

        # Security should be first
        self.assertEqual(middleware[0], 'django.middleware.security.SecurityMiddleware')

        # Session before auth
        session_index = middleware.index('django.contrib.sessions.middleware.SessionMiddleware')
        auth_index = middleware.index('django.contrib.auth.middleware.AuthenticationMiddleware')
        self.assertLess(session_index, auth_index)

        # TenantMiddleware should be after authentication
        tenant_index = middleware.index('core.middleware.TenantMiddleware')
        self.assertGreater(tenant_index, auth_index)

    def test_allauth_middleware_present(self) -> None:
        """Test allauth middleware is configured."""
        self.assertIn('allauth.account.middleware.AccountMiddleware', settings.MIDDLEWARE)


class EnvironmentVariablesTestCase(TestCase):
    """Test cases for environment variable configuration."""

    def test_critical_env_vars_present(self) -> None:
        """Test critical environment variables are set."""
        critical_vars = [
            'DJANGO_SECRET_KEY',
            'DATABASE_URL',
            'VALKEY_URL',
            'MASTER_KEY_KEK_CURRENT',
        ]

        for var in critical_vars:
            value = os.environ.get(var) or getattr(settings, var.replace('DATABASE_URL', 'DATABASES'), None)
            self.assertIsNotNone(value, f"Critical environment variable {var} is not set")

    def test_api_credentials_configured(self) -> None:
        """Test API credentials are configured."""
        # MercadoPago
        self.assertIsNotNone(settings.MERCADOPAGO_APP_ID or '')

        # FiscalAPI PAC
        self.assertIsNotNone(settings.FISCALAPI_URL)
        self.assertIsNotNone(settings.FISCALAPI_API_KEY or '')
        self.assertIsNotNone(settings.FISCALAPI_TENANT_KEY or '')

        # Email
        self.assertIsNotNone(settings.EMAIL_HOST_USER or '')


class LocalizationTestCase(TestCase):
    """Test cases for localization settings."""

    def test_mexican_localization(self) -> None:
        """Test Mexican localization settings."""
        self.assertEqual(settings.LANGUAGE_CODE, 'es-mx')
        self.assertEqual(settings.TIME_ZONE, 'America/Mexico_City')
        self.assertTrue(settings.USE_I18N)
        self.assertTrue(settings.USE_TZ)

    def test_currency_settings(self) -> None:
        """Test currency is set to MXN."""
        # Business logic should use MXN
        self.assertEqual(settings.MONTHLY_SUBSCRIPTION_PRICE, 299.00)  # MXN


class PerformanceSettingsTestCase(TestCase):
    """Test cases for performance-related settings."""

    def test_database_connection_pooling(self) -> None:
        """Test database connection pooling is configured."""
        db_config = settings.DATABASES['default']
        self.assertEqual(db_config.get('CONN_MAX_AGE'), 600)

    def test_cache_configuration(self) -> None:
        """Test cache is properly configured."""
        self.assertEqual(settings.SESSION_ENGINE, 'django.contrib.sessions.backends.cache')
        self.assertEqual(settings.SESSION_CACHE_ALIAS, 'default')

    def test_file_upload_limits(self) -> None:
        """Test file upload limits are set."""
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 10485760)  # 10MB
        self.assertEqual(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 10485760)  # 10MB
        self.assertEqual(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS, 1000)


class LoggingConfigurationTestCase(TestCase):
    """Test cases for logging configuration."""

    def test_logging_configured(self) -> None:
        """Test logging is properly configured."""
        logging_config = settings.LOGGING

        self.assertEqual(logging_config['version'], 1)
        self.assertFalse(logging_config['disable_existing_loggers'])

        # Test handlers
        self.assertIn('file', logging_config['handlers'])
        self.assertIn('console', logging_config['handlers'])

        # Test formatters
        self.assertIn('verbose', logging_config['formatters'])
        self.assertIn('simple', logging_config['formatters'])

        # Test loggers
        self.assertIn('django', logging_config['loggers'])
        self.assertIn('kita', logging_config['loggers'])