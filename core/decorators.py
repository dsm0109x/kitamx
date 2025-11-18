"""
Centralized decorators for the Kita application.

This module consolidates common decorator patterns used across the application
to reduce code duplication and ensure consistency.
"""
from __future__ import annotations
import functools
import logging
from typing import Optional
from django.conf import settings
from django.shortcuts import redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required as django_login_required
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods
from django.db import transaction
from django_ratelimit.decorators import ratelimit

from core.exceptions import (
    handle_generic_exception
)

logger = logging.getLogger(__name__)


def combined_method_decorator(*decorators):
    """
    Combine multiple decorators into one.

    This helps reduce the decorator stack depth and improves readability.

    Example:
        @combined_method_decorator(
            login_required,
            tenant_required(),
            cache_page(60 * 5)
        )
        def my_view(request):
            pass
    """
    def decorator(func):
        for dec in reversed(decorators):
            func = dec(func)
        return func
    return decorator


def require_authenticated_user(redirect_url: Optional[str] = None):
    """
    Require authenticated user with custom redirect.

    Args:
        redirect_url: URL to redirect to if not authenticated

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': True,
                        'code': 'authentication_required',
                        'message': 'Authentication required'
                    }, status=401)
                else:
                    return redirect(redirect_url or settings.LOGIN_URL)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator


def ajax_required(func):
    """
    Decorator to ensure request is AJAX.

    Returns JSON error for non-AJAX requests.
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'error': True,
                'code': 'ajax_required',
                'message': 'AJAX request required'
            }, status=400)
        return func(request, *args, **kwargs)
    return wrapper


def json_required(func):
    """
    Decorator to ensure request has JSON content type.

    Automatically parses JSON body and adds to request.
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        if request.content_type != 'application/json':
            return JsonResponse({
                'error': True,
                'code': 'json_required',
                'message': 'Content-Type must be application/json'
            }, status=400)

        try:
            import json
            request.json = json.loads(request.body) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({
                'error': True,
                'code': 'invalid_json',
                'message': 'Invalid JSON in request body'
            }, status=400)

        return func(request, *args, **kwargs)
    return wrapper


def rate_limit_with_response(
    key: str = 'ip',
    rate: str = '10/m',
    method: Optional[str] = None,
    block: bool = True
):
    """
    Rate limiting decorator with custom JSON response.

    Args:
        key: Rate limit key (ip, user, etc.)
        rate: Rate limit (e.g., '10/m', '100/h')
        method: HTTP method to limit
        block: Whether to block or just log

    Returns:
        Decorated function
    """
    def decorator(func):
        # Use django-ratelimit internally
        rate_limited = ratelimit(key=key, rate=rate, method=method, block=block)
        wrapped = rate_limited(func)

        @functools.wraps(wrapped)
        def wrapper(request, *args, **kwargs):
            # Check if rate limited
            if getattr(request, 'limited', False):
                return JsonResponse({
                    'error': True,
                    'code': 'rate_limit_exceeded',
                    'message': 'Rate limit exceeded. Please try again later.'
                }, status=429)
            return wrapped(request, *args, **kwargs)

        return wrapper
    return decorator


def transaction_with_retry(max_retries: int = 3):
    """
    Database transaction with automatic retry on failure.

    Args:
        max_retries: Maximum number of retry attempts

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            from django.db import IntegrityError, OperationalError
            import time

            retries = 0
            while retries < max_retries:
                try:
                    with transaction.atomic():
                        return func(request, *args, **kwargs)
                except (IntegrityError, OperationalError) as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Transaction failed after {max_retries} retries: {e}")
                        return JsonResponse({
                            'error': True,
                            'code': 'database_error',
                            'message': 'Database operation failed. Please try again.'
                        }, status=500)

                    # Exponential backoff
                    time.sleep(0.1 * (2 ** retries))
                    logger.warning(f"Transaction retry {retries}/{max_retries}: {e}")

            return func(request, *args, **kwargs)
        return wrapper
    return decorator






def handle_errors(
    default_message: str = "An error occurred",
    log_errors: bool = True
):
    """
    Generic error handler decorator.

    Args:
        default_message: Default error message
        log_errors: Whether to log errors

    Returns:
        Decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            try:
                return func(request, *args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.exception(f"Error in {func.__name__}: {e}")

                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'error': True,
                        'code': 'error',
                        'message': str(e) if settings.DEBUG else default_message
                    }, status=500)
                else:
                    return handle_generic_exception(e, request)

        return wrapper
    return decorator


def require_post_json():
    """
    Composite decorator requiring POST method with JSON body.

    Combines require_http_methods(['POST']) and json_required.
    """
    return combined_method_decorator(
        require_http_methods(['POST']),
        json_required
    )


def api_endpoint(
    methods: list[str] = ['GET'],
    auth_required: bool = True,
    rate_limit: Optional[str] = '100/h',
    cache_timeout: Optional[int] = None
):
    """
    Composite decorator for API endpoints.

    Args:
        methods: Allowed HTTP methods
        auth_required: Whether authentication is required
        rate_limit: Rate limit string
        cache_timeout: Cache timeout in seconds

    Returns:
        Decorated function
    """
    decorators = []

    # Add method restriction
    decorators.append(require_http_methods(methods))

    # Add authentication if required
    if auth_required:
        decorators.append(django_login_required)

    # Add rate limiting
    if rate_limit:
        decorators.append(rate_limit_with_response(rate=rate_limit))

    # Add caching for GET requests
    if cache_timeout and 'GET' in methods:
        decorators.append(cache_page(cache_timeout))

    # Add error handling
    decorators.append(handle_errors())

    return combined_method_decorator(*decorators)


# Common decorator combinations for reuse
standard_view = combined_method_decorator(
    django_login_required,
    handle_errors()
)

cached_view = combined_method_decorator(
    django_login_required,
    cache_page(60 * 5),
    handle_errors()
)

ajax_view = combined_method_decorator(
    django_login_required,
    ajax_required,
    json_required,
    handle_errors()
)

api_view = api_endpoint(
    methods=['GET', 'POST'],
    auth_required=True,
    rate_limit='100/h'
)