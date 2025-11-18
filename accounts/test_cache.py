"""Tests for accounts caching functionality."""
from __future__ import annotations
from unittest.mock import patch, MagicMock
from uuid import uuid4

from django.core.cache import cache

from core.test_utils import KitaTestCase
from accounts.cache import (
    CacheManager,
    UserCache,
    TenantCache,
    SessionCache,
    CachedCounter,
    cached_method,
    warm_cache_for_user,
)
from accounts.models import UserSession


class CacheManagerTestCase(KitaTestCase):
    """Test cases for CacheManager."""

    def setUp(self) -> None:
        """Clear cache before each test."""
        cache.clear()

    def test_make_key(self) -> None:
        """Test cache key generation."""
        key = CacheManager.make_key('test:', 'identifier')
        self.assertIn('test:', key)
        self.assertIn('identifier', key)
        self.assertTrue(key.startswith('v1:'))  # Version prefix

    def test_make_key_with_long_identifier(self) -> None:
        """Test key generation with long identifier."""
        long_id = 'x' * 300  # Very long identifier
        key = CacheManager.make_key('test:', long_id)

        # Should be hashed
        self.assertLess(len(key), 100)
        self.assertTrue(key.startswith('v1:test:'))

    def test_get_or_set(self) -> None:
        """Test get_or_set functionality."""
        # First call should compute value
        def compute_value():
            return 'computed_value'

        result = CacheManager.get_or_set('test_key', compute_value, 60)
        self.assertEqual(result, 'computed_value')

        # Second call should get from cache
        with patch.object(compute_value, '__call__', return_value='new_value'):
            result = CacheManager.get_or_set('test_key', compute_value, 60)
            self.assertEqual(result, 'computed_value')  # Still cached

    def test_invalidate_user_cache(self) -> None:
        """Test user cache invalidation."""
        user_id = uuid4()

        # Set some cache values
        profile_key = CacheManager.make_key('user:profile:', user_id)
        tenants_key = CacheManager.make_key('user:tenants:', user_id)

        cache.set(profile_key, {'test': 'data'}, 300)
        cache.set(tenants_key, ['tenant1', 'tenant2'], 300)

        # Invalidate
        CacheManager.invalidate_user_cache(user_id)

        # Check cleared
        self.assertIsNone(cache.get(profile_key))
        self.assertIsNone(cache.get(tenants_key))


class UserCacheTestCase(KitaTestCase):
    """Test cases for UserCache."""

    def setUp(self) -> None:
        """Extend setup to use the inherited user and clear cache."""
        super().setUp()
        # Use the inherited user from KitaTestCase - no need to create another

    def test_profile_cache(self) -> None:
        """Test profile caching."""
        profile_data = {
            'timezone': 'America/Mexico_City',
            'language': 'es',
            'theme': 'dark'
        }

        # Set cache
        UserCache.set_profile(self.user.id, profile_data)

        # Get from cache
        cached_data = UserCache.get_profile(self.user.id)
        self.assertEqual(cached_data, profile_data)

    def test_tenants_cache(self) -> None:
        """Test tenants caching."""
        tenants_data = [
            {'id': '123', 'name': 'Tenant 1'},
            {'id': '456', 'name': 'Tenant 2'},
        ]

        # Set cache
        UserCache.set_tenants(self.user.email, tenants_data)

        # Get from cache
        cached_data = UserCache.get_tenants(self.user.email)
        self.assertEqual(cached_data, tenants_data)

    def test_permissions_cache(self) -> None:
        """Test permissions caching."""
        tenant_id = uuid4()
        permissions = {
            'can_edit': True,
            'can_delete': False,
            'is_owner': True,
        }

        # Set cache
        UserCache.set_permissions(self.user.id, tenant_id, permissions)

        # Get from cache
        cached_perms = UserCache.get_permissions(self.user.id, tenant_id)
        self.assertEqual(cached_perms, permissions)


class TenantCacheTestCase(KitaTestCase):
    """Test cases for TenantCache."""

    def setUp(self) -> None:
        """Clear cache before tests."""
        cache.clear()

    def test_tenant_user_cache(self) -> None:
        """Test tenant user relationship caching."""
        tenant_id = uuid4()
        email = 'user@example.com'
        tenant_user_data = {
            'role': 'admin',
            'is_owner': True,
            'permissions': ['all'],
        }

        # Set cache
        TenantCache.set_tenant_user(email, tenant_id, tenant_user_data)

        # Get from cache
        cached_data = TenantCache.get_tenant_user(email, tenant_id)
        self.assertEqual(cached_data, tenant_user_data)


class CachedCounterTestCase(KitaTestCase):
    """Test cases for CachedCounter."""

    def setUp(self) -> None:
        """Clear cache and create counter."""
        cache.clear()
        self.counter = CachedCounter('test_counter')

    def test_increment(self) -> None:
        """Test counter increment."""
        self.assertEqual(self.counter.get(), 0)

        self.counter.increment()
        self.assertEqual(self.counter.get(), 1)

        self.counter.increment(5)
        self.assertEqual(self.counter.get(), 6)

    def test_decrement(self) -> None:
        """Test counter decrement."""
        self.counter.increment(10)

        self.counter.decrement()
        self.assertEqual(self.counter.get(), 9)

        self.counter.decrement(4)
        self.assertEqual(self.counter.get(), 5)

    def test_reset(self) -> None:
        """Test counter reset."""
        self.counter.increment(10)
        self.assertEqual(self.counter.get(), 10)

        self.counter.reset()
        self.assertEqual(self.counter.get(), 0)


class SessionCacheTestCase(KitaTestCase):
    """Test cases for SessionCache."""

    def setUp(self) -> None:
        """Extend setup to use the inherited user and clear cache."""
        super().setUp()
        # Use the inherited user from KitaTestCase - no need to create another

    def test_active_sessions_count(self) -> None:
        """Test active sessions counting."""
        # Create sessions
        from datetime import timedelta
        from django.utils import timezone

        for i in range(3):
            UserSession.objects.create(
                user=self.user,
                session_key=f'session_{i}',
                ip_address='192.168.1.1',
                user_agent='Test',
                expires_at=timezone.now() + timedelta(hours=1),
                is_active=True
            )

        # Get count (should compute and cache)
        count = SessionCache.get_active_sessions_count(self.user.id)
        self.assertEqual(count, 3)

        # Create another session
        UserSession.objects.create(
            user=self.user,
            session_key='session_new',
            ip_address='192.168.1.1',
            user_agent='Test',
            expires_at=timezone.now() + timedelta(hours=1),
            is_active=True
        )

        # Count should still be cached (3)
        count = SessionCache.get_active_sessions_count(self.user.id)
        self.assertEqual(count, 3)

        # Invalidate and recount
        SessionCache.invalidate_session_count(self.user.id)
        count = SessionCache.get_active_sessions_count(self.user.id)
        self.assertEqual(count, 4)


class CachedMethodDecoratorTestCase(KitaTestCase):
    """Test cases for cached_method decorator."""

    def setUp(self) -> None:
        """Clear cache before tests."""
        cache.clear()

    def test_method_caching(self) -> None:
        """Test method result caching."""
        call_count = 0

        class TestClass:
            def __init__(self, id):
                self.id = id

            @cached_method(timeout=60)
            def expensive_method(self):
                nonlocal call_count
                call_count += 1
                return f'result_{self.id}'

        obj = TestClass('test_id')

        # First call should compute
        result = obj.expensive_method()
        self.assertEqual(result, 'result_test_id')
        self.assertEqual(call_count, 1)

        # Second call should use cache
        result = obj.expensive_method()
        self.assertEqual(result, 'result_test_id')
        self.assertEqual(call_count, 1)  # Not incremented

    def test_method_caching_with_vary_on(self) -> None:
        """Test method caching with varying parameters."""
        call_count = 0

        class TestClass:
            def __init__(self, id):
                self.id = id

            @cached_method(timeout=60, vary_on=['param'])
            def method_with_param(self, param):
                nonlocal call_count
                call_count += 1
                return f'{self.id}_{param}'

        obj = TestClass('test')

        # Different params should have different cache entries
        result1 = obj.method_with_param(param='a')
        self.assertEqual(result1, 'test_a')
        self.assertEqual(call_count, 1)

        result2 = obj.method_with_param(param='b')
        self.assertEqual(result2, 'test_b')
        self.assertEqual(call_count, 2)

        # Same param should use cache
        result3 = obj.method_with_param(param='a')
        self.assertEqual(result3, 'test_a')
        self.assertEqual(call_count, 2)  # Not incremented


class WarmCacheTestCase(KitaTestCase):
    """Test cases for cache warming."""

    @patch('accounts.cache.TenantUser')
    def test_warm_cache_for_user(self, mock_tenant_user) -> None:
        """Test cache warming for new user."""
        user = self.user  # Use the inherited user from KitaTestCase

        # Mock tenant data
        mock_tenant = MagicMock()
        mock_tenant.id = uuid4()
        mock_tenant.name = 'Test Tenant'
        mock_tenant.slug = 'test-tenant'

        mock_tu = MagicMock()
        mock_tu.tenant = mock_tenant
        mock_tu.is_owner = True
        mock_tu.role = 'owner'

        mock_tenant_user.objects.filter.return_value.select_related.return_value = [mock_tu]

        # Warm cache
        warm_cache_for_user(user.id, user.email)

        # Check profile cached
        cached_profile = UserCache.get_profile(user.id)
        self.assertIsNotNone(cached_profile)
        self.assertEqual(cached_profile['timezone'], 'America/Mexico_City')

        # Check tenants cached
        cached_tenants = UserCache.get_tenants(user.email)
        self.assertIsNotNone(cached_tenants)
        self.assertEqual(len(cached_tenants), 1)