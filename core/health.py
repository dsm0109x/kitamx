"""
Health check system for monitoring application status.

Provides health checks for all critical components:
- Database connectivity
- Cache (Redis/Valkey)
- Celery workers
- Disk space
- Memory usage
"""
from __future__ import annotations
from typing import Dict, Any, Tuple
from datetime import datetime
import psutil
import logging

from django.db import connection
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger(__name__)


class HealthStatus:
    """Health status constants."""
    HEALTHY = 'healthy'
    DEGRADED = 'degraded'
    UNHEALTHY = 'unhealthy'


class HealthChecker:
    """System health check with multiple components."""

    @staticmethod
    def check_database() -> Tuple[str, Dict[str, Any]]:
        """
        Check database connectivity and response time.

        Returns:
            Tuple of (status, details)
        """
        try:
            import time
            start = time.time()

            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            response_time = (time.time() - start) * 1000  # ms

            # Check connection pool
            db_config = settings.DATABASES['default']

            details = {
                'status': HealthStatus.HEALTHY,
                'response_time_ms': round(response_time, 2),
                'database': db_config.get('NAME', 'unknown'),
                'host': db_config.get('HOST', 'localhost'),
            }

            # Degraded if slow
            if response_time > 100:
                details['status'] = HealthStatus.DEGRADED
                details['message'] = f'Slow response: {response_time:.2f}ms'

            return details['status'], details

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return HealthStatus.UNHEALTHY, {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'message': 'Database connection failed'
            }

    @staticmethod
    def check_cache() -> Tuple[str, Dict[str, Any]]:
        """
        Check Redis/Valkey connectivity.

        Returns:
            Tuple of (status, details)
        """
        try:
            import time
            test_key = 'health_check_test'
            test_value = datetime.now().isoformat()

            start = time.time()

            # Test set
            cache.set(test_key, test_value, timeout=10)

            # Test get
            result = cache.get(test_key)

            # Test delete
            cache.delete(test_key)

            response_time = (time.time() - start) * 1000  # ms

            if result != test_value:
                return HealthStatus.UNHEALTHY, {
                    'status': HealthStatus.UNHEALTHY,
                    'error': 'Cache get/set mismatch',
                    'message': 'Cache integrity check failed'
                }

            details = {
                'status': HealthStatus.HEALTHY,
                'response_time_ms': round(response_time, 2),
                'backend': settings.CACHES['default']['BACKEND'],
            }

            # Degraded if slow
            if response_time > 50:
                details['status'] = HealthStatus.DEGRADED
                details['message'] = f'Slow response: {response_time:.2f}ms'

            return details['status'], details

        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return HealthStatus.UNHEALTHY, {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'message': 'Cache connection failed'
            }

    @staticmethod
    def check_celery() -> Tuple[str, Dict[str, Any]]:
        """
        Check Celery workers status.

        Returns:
            Tuple of (status, details)
        """
        try:
            from kita.celery import app

            # Get worker stats
            inspect = app.control.inspect()
            stats = inspect.stats()
            active = inspect.active()

            if not stats:
                return HealthStatus.UNHEALTHY, {
                    'status': HealthStatus.UNHEALTHY,
                    'message': 'No Celery workers found',
                    'workers': 0
                }

            worker_count = len(stats)
            active_tasks = sum(len(tasks) for tasks in (active or {}).values())

            details = {
                'status': HealthStatus.HEALTHY,
                'workers': worker_count,
                'active_tasks': active_tasks,
            }

            # Degraded if low workers
            if worker_count < 2:
                details['status'] = HealthStatus.DEGRADED
                details['message'] = f'Only {worker_count} worker(s) active'

            return details['status'], details

        except Exception as e:
            logger.warning(f"Celery health check failed: {e}")
            # Not critical - return degraded instead of unhealthy
            return HealthStatus.DEGRADED, {
                'status': HealthStatus.DEGRADED,
                'error': str(e),
                'message': 'Celery status check failed (workers may be down)'
            }

    @staticmethod
    def check_disk_space() -> Tuple[str, Dict[str, Any]]:
        """
        Check available disk space.

        Returns:
            Tuple of (status, details)
        """
        try:
            disk = psutil.disk_usage('/')

            percent_used = disk.percent

            details = {
                'status': HealthStatus.HEALTHY,
                'percent_used': percent_used,
                'total_gb': round(disk.total / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2),
            }

            # Thresholds
            if percent_used > 90:
                details['status'] = HealthStatus.UNHEALTHY
                details['message'] = f'Critical: {percent_used}% disk used'
            elif percent_used > 80:
                details['status'] = HealthStatus.DEGRADED
                details['message'] = f'Warning: {percent_used}% disk used'

            return details['status'], details

        except Exception as e:
            logger.error(f"Disk space check failed: {e}")
            return HealthStatus.DEGRADED, {
                'status': HealthStatus.DEGRADED,
                'error': str(e),
                'message': 'Disk space check unavailable'
            }

    @staticmethod
    def check_memory() -> Tuple[str, Dict[str, Any]]:
        """
        Check memory usage.

        Returns:
            Tuple of (status, details)
        """
        try:
            memory = psutil.virtual_memory()

            percent_used = memory.percent

            details = {
                'status': HealthStatus.HEALTHY,
                'percent_used': percent_used,
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
            }

            # Thresholds
            if percent_used > 95:
                details['status'] = HealthStatus.UNHEALTHY
                details['message'] = f'Critical: {percent_used}% memory used'
            elif percent_used > 85:
                details['status'] = HealthStatus.DEGRADED
                details['message'] = f'Warning: {percent_used}% memory used'

            return details['status'], details

        except Exception as e:
            logger.error(f"Memory check failed: {e}")
            return HealthStatus.DEGRADED, {
                'status': HealthStatus.DEGRADED,
                'error': str(e),
                'message': 'Memory check unavailable'
            }

    @classmethod
    def check_all(cls) -> Dict[str, Any]:
        """
        Run all health checks.

        Returns:
            Dictionary with overall status and component details
        """
        checks = {
            'database': cls.check_database(),
            'cache': cls.check_cache(),
            'celery': cls.check_celery(),
            'disk': cls.check_disk_space(),
            'memory': cls.check_memory(),
        }

        # Determine overall status
        statuses = [status for status, _ in checks.values()]

        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        return {
            'status': overall,
            'timestamp': datetime.now().isoformat(),
            'checks': {
                name: details for name, (_, details) in checks.items()
            }
        }