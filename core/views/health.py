"""
Health check endpoints for monitoring and orchestration.

Provides endpoints for:
- Simple alive check
- Detailed health status
- Kubernetes readiness probe
- Kubernetes liveness probe
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt

from core.health import HealthChecker, HealthStatus


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
@never_cache
def health_check(request):
    """
    Simple health check endpoint.

    Returns 200 if application is alive.
    Used for basic uptime monitoring.
    """
    return JsonResponse({
        'status': 'ok',
        'service': 'kita'
    }, status=200)


@csrf_exempt
@require_http_methods(["GET"])
@never_cache
def health_detailed(request):
    """
    Detailed health check with all components.

    Returns comprehensive health status including:
    - Database connectivity
    - Cache status
    - Celery workers
    - Disk space
    - Memory usage
    """
    health_data = HealthChecker.check_all()

    # Determine HTTP status code
    if health_data['status'] == HealthStatus.HEALTHY:
        status_code = 200
    elif health_data['status'] == HealthStatus.DEGRADED:
        status_code = 200  # Still operational
    else:
        status_code = 503  # Service unavailable

    return JsonResponse(health_data, status=status_code)


@csrf_exempt
@require_http_methods(["GET"])
@never_cache
def health_readiness(request):
    """
    Kubernetes readiness probe.

    Checks if application is ready to serve traffic.
    Returns 200 if ready, 503 if not ready.

    Checks:
    - Database connectivity
    - Cache connectivity
    """
    # Check critical components only
    db_status, db_details = HealthChecker.check_database()
    cache_status, cache_details = HealthChecker.check_cache()

    # Ready if both database and cache are healthy
    if db_status == HealthStatus.HEALTHY and cache_status == HealthStatus.HEALTHY:
        return JsonResponse({
            'status': 'ready',
            'database': db_details,
            'cache': cache_details
        }, status=200)
    else:
        return JsonResponse({
            'status': 'not_ready',
            'database': db_details,
            'cache': cache_details
        }, status=503)


@csrf_exempt
@require_http_methods(["GET"])
@never_cache
def health_liveness(request):
    """
    Kubernetes liveness probe.

    Checks if application is alive and should not be restarted.
    Returns 200 if alive, 503 if should restart.

    Only checks critical failures that would require restart.
    """
    # Check if database is completely dead
    db_status, db_details = HealthChecker.check_database()

    # Alive unless database is completely unreachable
    if db_status == HealthStatus.UNHEALTHY:
        return JsonResponse({
            'status': 'unhealthy',
            'database': db_details
        }, status=503)

    return JsonResponse({
        'status': 'alive'
    }, status=200)