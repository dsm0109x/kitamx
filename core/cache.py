from __future__ import annotations
from typing import Any, Optional, Generator
from contextlib import contextmanager
import logging

import redis
import environ
from django.conf import settings

# Initialize environ
env = environ.Env()
logger = logging.getLogger(__name__)


class KitaRedisCache:
    """
    Custom Redis cache wrapper for Kita with tenant isolation.

    Provides tenant-scoped caching with automatic key prefixing.
    """

    DEFAULT_TIMEOUT = 300  # 5 minutes
    LOCK_TIMEOUT = 60  # 1 minute

    def __init__(self) -> None:
        """Initialize Redis client with SSL configuration."""
        self.redis_client = self._get_redis_client()
        self._key_prefix = getattr(settings, 'CACHE_KEY_PREFIX', 'kita')

    @staticmethod
    def generate_standard_key(module: str, tenant_id: str, key_type: str, identifier: str = '') -> str:
        """
        Generate standardized cache key for consistency across the app.

        Args:
            module: Module name (e.g., 'audit', 'dashboard', 'payments')
            tenant_id: Tenant ID for scoping
            key_type: Type of data (e.g., 'stats', 'webhook', 'oauth')
            identifier: Additional identifier (optional)

        Returns:
            Standardized cache key

        Example:
            generate_standard_key('audit', '123', 'stats', '2024-01-15_2024-01-31')
            -> 'kita:audit:tenant:123:stats:2024-01-15_2024-01-31'
        """
        parts = ['kita', module, 'tenant', tenant_id, key_type]
        if identifier:
            parts.append(identifier)
        return ':'.join(parts)

    @staticmethod
    def generate_global_key(module: str, key_type: str, identifier: str = '') -> str:
        """
        Generate standardized global cache key (not tenant-specific).

        Args:
            module: Module name
            key_type: Type of data
            identifier: Additional identifier (optional)

        Returns:
            Standardized global cache key

        Example:
            generate_global_key('webhook', 'processed', 'payment_12345')
            -> 'kita:global:webhook:processed:payment_12345'
        """
        parts = ['kita', 'global', module, key_type]
        if identifier:
            parts.append(identifier)
        return ':'.join(parts)

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client with SSL configuration for DigitalOcean Valkey."""
        try:
            url = settings.CELERY_BROKER_URL
        except AttributeError:
            # Fallback to environment variable
            url = env('VALKEY_URL', default='redis://localhost:6379/0')

        try:
            client = redis.from_url(
                url,
                ssl_cert_reqs=None,
                ssl_check_hostname=False,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            # Test connection
            client.ping()
            logger.info("Redis connection established successfully")
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Don't raise - allow app to continue without cache
            return None

    def _make_tenant_key(self, tenant_id: str, key: str) -> str:
        """Create tenant-scoped cache key."""
        return f"{self._key_prefix}:tenant:{tenant_id}:{key}"

    def set(self, tenant_id: str, key: str, value: Any, timeout: Optional[int] = None) -> bool:
        """Set cache value with tenant isolation."""
        tenant_key = self._make_tenant_key(tenant_id, key)
        timeout = timeout or self.DEFAULT_TIMEOUT
        try:
            return self.redis_client.setex(tenant_key, timeout, value)
        except Exception as e:
            logger.error(f"Cache set failed for {tenant_key}: {e}")
            return False

    def get(self, tenant_id: str, key: str, default: Any = None) -> Any:
        """Get cache value with tenant isolation."""
        tenant_key = self._make_tenant_key(tenant_id, key)
        try:
            value = self.redis_client.get(tenant_key)
            return value if value is not None else default
        except Exception as e:
            logger.error(f"Cache get failed for {tenant_key}: {e}")
            return default

    def delete(self, tenant_id: str, key: str) -> bool:
        """Delete cache value with tenant isolation."""
        tenant_key = self._make_tenant_key(tenant_id, key)
        try:
            return bool(self.redis_client.delete(tenant_key))
        except Exception as e:
            logger.error(f"Cache delete failed for {tenant_key}: {e}")
            return False

    def exists(self, tenant_id: str, key: str) -> bool:
        """Check if cache key exists with tenant isolation."""
        tenant_key = self._make_tenant_key(tenant_id, key)
        try:
            return bool(self.redis_client.exists(tenant_key))
        except Exception as e:
            logger.error(f"Cache exists check failed for {tenant_key}: {e}")
            return False

    def flush_tenant(self, tenant_id: str) -> int:
        """Flush all cache keys for a specific tenant."""
        pattern = f"{self._key_prefix}:tenant:{tenant_id}:*"
        try:
            # Use SCAN for better performance on large datasets
            keys = []
            cursor = 0
            while True:
                cursor, batch = self.redis_client.scan(cursor, match=pattern, count=100)
                keys.extend(batch)
                if cursor == 0:
                    break

            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Failed to flush cache for tenant {tenant_id}: {e}")
            return 0

    def get_lock(self, tenant_id: str, key: str, timeout: Optional[int] = None) -> redis.lock.Lock:
        """Get distributed lock with tenant isolation."""
        lock_key = self._make_tenant_key(tenant_id, f"lock:{key}")
        timeout = timeout or self.LOCK_TIMEOUT
        return self.redis_client.lock(lock_key, timeout=timeout, blocking_timeout=30)

    @contextmanager
    def distributed_lock(
        self,
        tenant_id: str,
        key: str,
        timeout: Optional[int] = None
    ) -> Generator[redis.lock.Lock, None, None]:
        """Context manager for distributed locks."""
        lock = self.get_lock(tenant_id, key, timeout)
        acquired = False
        try:
            acquired = lock.acquire(blocking=True)
            if not acquired:
                raise TimeoutError(f"Could not acquire lock for {key}")
            yield lock
        finally:
            if acquired:
                try:
                    lock.release()
                except redis.lock.LockNotOwnedError:
                    # Lock might have expired or been released
                    logger.debug(f"Lock {key} already released or expired")
                except Exception as e:
                    logger.error(f"Error releasing lock {key}: {e}")


class IdempotencyManager:
    """
    Manage idempotency for webhooks and critical operations using Redis.

    Ensures operations are processed exactly once within the TTL window.
    """

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self, cache: Optional[KitaRedisCache] = None) -> None:
        """Initialize with optional cache instance."""
        self.cache = cache or KitaRedisCache()

    def is_processed(self, tenant_id: str, idempotency_key: str) -> bool:
        """Check if operation was already processed."""
        key = f"idempotency:{idempotency_key}"
        return self.cache.exists(tenant_id, key)

    def mark_processed(
        self,
        tenant_id: str,
        idempotency_key: str,
        result: Any = None,
        ttl: Optional[int] = None
    ) -> bool:
        """Mark operation as processed with optional result."""
        key = f"idempotency:{idempotency_key}"
        value = result or "processed"
        ttl = ttl or self.DEFAULT_TTL
        return self.cache.set(tenant_id, key, value, ttl)

    def get_result(self, tenant_id: str, idempotency_key: str) -> Any:
        """Get result of previously processed operation."""
        key = f"idempotency:{idempotency_key}"
        return self.cache.get(tenant_id, key)

    @contextmanager
    def ensure_idempotency(
        self,
        tenant_id: str,
        idempotency_key: str,
        ttl: Optional[int] = None
    ) -> Generator[IdempotencyHandler, None, None]:
        """
        Context manager to ensure operation idempotency.

        Usage:
            with idempotency.ensure_idempotency(tenant_id, key) as handler:
                if handler.is_duplicate:
                    return handler.previous_result
                # Do operation
                result = process_payment()
                handler.set_result(result)
                return result
        """
        ttl = ttl or self.DEFAULT_TTL
        handler = IdempotencyHandler(self, tenant_id, idempotency_key, ttl)
        yield handler


class IdempotencyHandler:
    """Handler for idempotent operations."""

    def __init__(
        self,
        manager: IdempotencyManager,
        tenant_id: str,
        key: str,
        ttl: int
    ) -> None:
        """Initialize handler."""
        self.manager = manager
        self.tenant_id = tenant_id
        self.key = key
        self.ttl = ttl
        self.is_duplicate = manager.is_processed(tenant_id, key)
        self.previous_result = None
        if self.is_duplicate:
            self.previous_result = manager.get_result(tenant_id, key)

    def set_result(self, result: Any) -> bool:
        """Set the result of the operation."""
        return self.manager.mark_processed(self.tenant_id, self.key, result, self.ttl)


# Global instances
try:
    kita_cache = KitaRedisCache()
    idempotency = IdempotencyManager(kita_cache)
    logger.info("Cache and idempotency managers initialized")
except Exception as e:
    logger.error(f"Failed to initialize cache managers: {e}")
    # Create dummy implementations for testing
    kita_cache = None
    idempotency = None