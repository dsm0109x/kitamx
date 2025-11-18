"""
Cache management for accounts app.

Provides efficient caching strategies for frequently accessed data
to reduce database queries and improve performance.
"""
from __future__ import annotations
from typing import Optional, Any, List, Dict, Callable
from functools import wraps
import hashlib
import logging

from django.core.cache import cache
from django.db.models import Model, QuerySet
from django.utils import timezone

from .constants import CacheConstants

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Centralized cache management with versioning and invalidation.
    """

    @staticmethod
    def make_key(prefix: str, identifier: Any, version: int = CacheConstants.CACHE_VERSION) -> str:
        """
        Generate a cache key with version support.

        Args:
            prefix: Cache key prefix
            identifier: Unique identifier (user_id, email, etc.)
            version: Cache version for invalidation

        Returns:
            Versioned cache key
        """
        # Convert identifier to string and hash if too long
        id_str = str(identifier)
        if len(id_str) > 200:
            id_str = hashlib.md5(id_str.encode()).hexdigest()

        return f"v{version}:{prefix}{id_str}"

    @staticmethod
    def get_or_set(
        key: str,
        callable_or_value: Any,
        timeout: Optional[int] = None
    ) -> Any:
        """
        Get from cache or set if not exists.

        Args:
            key: Cache key
            callable_or_value: Value or callable that returns value
            timeout: Cache timeout in seconds

        Returns:
            Cached or computed value
        """
        value = cache.get(key)

        if value is None:
            # Compute value if callable
            if callable(callable_or_value):
                try:
                    value = callable_or_value()
                except Exception as e:
                    logger.error(f"Error computing cache value for {key}: {e}")
                    return None
            else:
                value = callable_or_value

            # Set in cache if we have a value
            if value is not None:
                cache.set(key, value, timeout)

        return value

    @staticmethod
    def delete_pattern(pattern: str) -> int:
        """
        Delete all cache keys matching a pattern.

        Args:
            pattern: Pattern to match (e.g., 'user:profile:*')

        Returns:
            Number of keys deleted
        """
        # This requires cache backend that supports delete_pattern
        # For Redis/Valkey:
        if hasattr(cache, 'delete_pattern'):
            return cache.delete_pattern(f"*{pattern}*")

        # Fallback: can't delete by pattern
        logger.warning(f"Cache backend doesn't support delete_pattern for: {pattern}")
        return 0

    @staticmethod
    def invalidate_user_cache(user_id: Any) -> None:
        """
        Invalidate all cache entries for a user.

        Args:
            user_id: User ID to invalidate
        """
        prefixes = [
            CacheConstants.USER_PROFILE_PREFIX,
            CacheConstants.USER_TENANTS_PREFIX,
            CacheConstants.USER_PERMISSIONS_PREFIX,
        ]

        for prefix in prefixes:
            key = CacheManager.make_key(prefix, user_id)
            cache.delete(key)

        logger.debug(f"Invalidated cache for user: {user_id}")

    @staticmethod
    def invalidate_tenant_cache(tenant_id: Any) -> None:
        """
        Invalidate all cache entries for a tenant.

        Args:
            tenant_id: Tenant ID to invalidate
        """
        # Delete pattern for all tenant-related cache
        CacheManager.delete_pattern(f"tenant:*:{tenant_id}")
        logger.debug(f"Invalidated cache for tenant: {tenant_id}")


class UserCache:
    """
    Cache manager for user-related data.
    """

    @staticmethod
    def get_profile(user_id: Any) -> Optional[Dict[str, Any]]:
        """
        Get cached user profile.

        Args:
            user_id: User ID

        Returns:
            Cached profile data or None
        """
        key = CacheManager.make_key(CacheConstants.USER_PROFILE_PREFIX, user_id)
        return cache.get(key)

    @staticmethod
    def set_profile(user_id: Any, profile_data: Dict[str, Any]) -> None:
        """
        Cache user profile data.

        Args:
            user_id: User ID
            profile_data: Profile data to cache
        """
        key = CacheManager.make_key(CacheConstants.USER_PROFILE_PREFIX, user_id)
        cache.set(key, profile_data, CacheConstants.USER_PROFILE_TIMEOUT)

    @staticmethod
    def get_tenants(user_email: str) -> Optional[List[Dict[str, Any]]]:
        """
        Get cached user tenants.

        Args:
            user_email: User email

        Returns:
            List of tenant data or None
        """
        key = CacheManager.make_key(CacheConstants.USER_TENANTS_PREFIX, user_email)
        return cache.get(key)

    @staticmethod
    def set_tenants(user_email: str, tenants: List[Dict[str, Any]]) -> None:
        """
        Cache user tenants.

        Args:
            user_email: User email
            tenants: List of tenant data
        """
        key = CacheManager.make_key(CacheConstants.USER_TENANTS_PREFIX, user_email)
        cache.set(key, tenants, CacheConstants.USER_TENANTS_TIMEOUT)

    @staticmethod
    def get_permissions(user_id: Any, tenant_id: Any) -> Optional[Dict[str, bool]]:
        """
        Get cached user permissions for a tenant.

        Args:
            user_id: User ID
            tenant_id: Tenant ID

        Returns:
            Permission dictionary or None
        """
        key = CacheManager.make_key(
            CacheConstants.USER_PERMISSIONS_PREFIX,
            f"{user_id}:{tenant_id}"
        )
        return cache.get(key)

    @staticmethod
    def set_permissions(
        user_id: Any,
        tenant_id: Any,
        permissions: Dict[str, bool]
    ) -> None:
        """
        Cache user permissions for a tenant.

        Args:
            user_id: User ID
            tenant_id: Tenant ID
            permissions: Permission dictionary
        """
        key = CacheManager.make_key(
            CacheConstants.USER_PERMISSIONS_PREFIX,
            f"{user_id}:{tenant_id}"
        )
        cache.set(key, permissions, CacheConstants.USER_PERMISSIONS_TIMEOUT)


class TenantCache:
    """
    Cache manager for tenant-related data.
    """

    @staticmethod
    def get_tenant_user(email: str, tenant_id: Any) -> Optional[Dict[str, Any]]:
        """
        Get cached tenant user relationship.

        Args:
            email: User email
            tenant_id: Tenant ID

        Returns:
            TenantUser data or None
        """
        key = CacheManager.make_key(
            CacheConstants.TENANT_USER_PREFIX,
            f"{tenant_id}:{email}"
        )
        return cache.get(key)

    @staticmethod
    def set_tenant_user(
        email: str,
        tenant_id: Any,
        tenant_user_data: Dict[str, Any]
    ) -> None:
        """
        Cache tenant user relationship.

        Args:
            email: User email
            tenant_id: Tenant ID
            tenant_user_data: TenantUser data
        """
        key = CacheManager.make_key(
            CacheConstants.TENANT_USER_PREFIX,
            f"{tenant_id}:{email}"
        )
        cache.set(key, tenant_user_data, CacheConstants.TENANT_USER_TIMEOUT)


def cached_method(
    timeout: int = 300,
    key_prefix: str = '',
    vary_on: Optional[List[str]] = None
) -> Callable:
    """
    Decorator for caching method results.

    Args:
        timeout: Cache timeout in seconds
        key_prefix: Custom key prefix
        vary_on: List of argument names to include in cache key

    Returns:
        Decorated method

    Usage:
        @cached_method(timeout=600, vary_on=['tenant_id'])
        def get_expensive_data(self, tenant_id):
            return expensive_calculation()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Build cache key
            cache_key_parts = [key_prefix or func.__name__]

            # Add instance identifier if available
            if hasattr(self, 'id'):
                cache_key_parts.append(str(self.id))
            elif hasattr(self, 'pk'):
                cache_key_parts.append(str(self.pk))

            # Add varied arguments
            if vary_on:
                for arg_name in vary_on:
                    if arg_name in kwargs:
                        cache_key_parts.append(str(kwargs[arg_name]))

            cache_key = CacheManager.make_key('method:', ':'.join(cache_key_parts))

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                return result

            # Compute and cache
            result = func(self, *args, **kwargs)
            if result is not None:
                cache.set(cache_key, result, timeout)

            return result

        return wrapper
    return decorator


def cache_queryset(
    queryset: QuerySet,
    key: str,
    timeout: int = 300,
    serialize: bool = True
) -> List[Any]:
    """
    Cache a queryset efficiently.

    Args:
        queryset: Django QuerySet
        key: Cache key
        timeout: Cache timeout in seconds
        serialize: Whether to serialize to dict

    Returns:
        List of model instances or dicts

    Usage:
        users = cache_queryset(
            User.objects.filter(is_active=True).select_related('profile'),
            'active_users',
            timeout=600
        )
    """
    cached = cache.get(key)
    if cached is not None:
        return cached

    # Evaluate queryset
    if serialize:
        # Convert to list of dicts for better cache efficiency
        result = list(queryset.values())
    else:
        # Store model instances (less efficient)
        result = list(queryset)

    cache.set(key, result, timeout)
    return result


def invalidate_on_save(sender: type[Model], instance: Model, **kwargs) -> None:
    """
    Signal handler to invalidate cache on model save.

    Connect this to post_save signal:
        from django.db.models.signals import post_save
        post_save.connect(invalidate_on_save, sender=User)
    """
    # Invalidate based on model type
    if hasattr(instance, '__class__'):
        model_name = instance.__class__.__name__

        if model_name == 'User':
            CacheManager.invalidate_user_cache(instance.id)
        elif model_name == 'Tenant':
            CacheManager.invalidate_tenant_cache(instance.id)
        elif model_name == 'TenantUser':
            # Invalidate both user and tenant cache
            UserCache.set_tenants.cache_clear()
            TenantCache.set_tenant_user.cache_clear()


class CachedCounter:
    """
    Efficient counter using cache for high-frequency updates.
    """

    def __init__(self, key: str, timeout: int = 3600):
        """
        Initialize cached counter.

        Args:
            key: Cache key for counter
            timeout: Timeout in seconds
        """
        self.key = f"counter:{key}"
        self.timeout = timeout

    def increment(self, delta: int = 1) -> int:
        """
        Increment counter atomically.

        Args:
            delta: Amount to increment

        Returns:
            New counter value
        """
        try:
            return cache.incr(self.key, delta)
        except ValueError:
            # Key doesn't exist, initialize
            cache.set(self.key, delta, self.timeout)
            return delta

    def decrement(self, delta: int = 1) -> int:
        """
        Decrement counter atomically.

        Args:
            delta: Amount to decrement

        Returns:
            New counter value
        """
        try:
            return cache.decr(self.key, delta)
        except ValueError:
            # Key doesn't exist
            return 0

    def get(self) -> int:
        """
        Get current counter value.

        Returns:
            Counter value or 0
        """
        return cache.get(self.key, 0)

    def reset(self) -> None:
        """Reset counter to 0."""
        cache.delete(self.key)


class SessionCache:
    """
    Cache for session-related data.
    """

    @staticmethod
    def get_active_sessions_count(user_id: Any) -> int:
        """
        Get cached count of active sessions.

        Args:
            user_id: User ID

        Returns:
            Number of active sessions
        """
        key = f"sessions:count:{user_id}"
        count = cache.get(key)

        if count is None:
            # Compute from database
            from .models import UserSession
            count = UserSession.objects.filter(
                user_id=user_id,
                is_active=True,
                expires_at__gt=timezone.now()
            ).count()
            cache.set(key, count, 60)  # Short timeout

        return count

    @staticmethod
    def invalidate_session_count(user_id: Any) -> None:
        """
        Invalidate session count cache.

        Args:
            user_id: User ID
        """
        key = f"sessions:count:{user_id}"
        cache.delete(key)


# Warm cache utility
def warm_cache_for_user(user_id: Any, user_email: str) -> None:
    """
    Pre-populate cache for user to avoid cold start.

    Args:
        user_id: User ID
        user_email: User email
    """
    from .models import User
    from core.models import TenantUser

    try:
        # Get user with profile
        user = User.objects.select_related('profile').get(id=user_id)

        # Cache profile
        if hasattr(user, 'profile'):
            UserCache.set_profile(user_id, {
                'timezone': user.profile.timezone,
                'language': user.profile.language,
                'theme': user.profile.theme,
            })

        # Cache tenants
        tenant_users = TenantUser.objects.filter(
            email=user_email
        ).select_related('tenant')

        tenants = [
            {
                'id': str(tu.tenant.id),
                'name': tu.tenant.name,
                'slug': tu.tenant.slug,
                'is_owner': tu.is_owner,
                'role': tu.role,
            }
            for tu in tenant_users
        ]
        UserCache.set_tenants(user_email, tenants)

        logger.debug(f"Cache warmed for user: {user_id}")

    except Exception as e:
        logger.error(f"Error warming cache for user {user_id}: {e}")


# Export main components
__all__ = [
    'CacheManager',
    'UserCache',
    'TenantCache',
    'cached_method',
    'cache_queryset',
    'invalidate_on_save',
    'CachedCounter',
    'SessionCache',
    'warm_cache_for_user',
]