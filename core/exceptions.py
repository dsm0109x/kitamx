"""
Centralized exception handling for the Kita application.

This module provides custom exceptions and error handlers
to standardize error responses across the application.
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any
from django.core.exceptions import ValidationError, PermissionDenied
from django.http import JsonResponse, HttpRequest
from django.utils.translation import gettext_lazy as _
from core.security import SecureIPDetector

logger = logging.getLogger(__name__)


# Custom Exception Classes
class KitaBaseException(Exception):
    """Base exception for all Kita custom exceptions."""
    default_message = _("An error occurred")
    default_code = "error"
    status_code = 400

    def __init__(
        self,
        message: Optional[str] = None,
        code: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.extra = extra or {}
        super().__init__(self.message)


class TenantNotFoundError(KitaBaseException):
    """Raised when tenant is not found or not accessible."""
    default_message = _("Tenant not found")
    default_code = "tenant_not_found"
    status_code = 404


class PaymentError(KitaBaseException):
    """Base class for payment-related errors."""
    default_message = _("Payment processing error")
    default_code = "payment_error"
    status_code = 400


class MercadoPagoError(PaymentError):
    """MercadoPago specific errors."""
    default_message = _("MercadoPago error")
    default_code = "mercadopago_error"


class InvoiceError(KitaBaseException):
    """Invoice generation or processing errors."""
    default_message = _("Invoice processing error")
    default_code = "invoice_error"
    status_code = 400


class CFDIError(InvoiceError):
    """CFDI specific errors."""
    default_message = _("CFDI generation error")
    default_code = "cfdi_error"


class RateLimitError(KitaBaseException):
    """Rate limit exceeded error."""
    default_message = _("Rate limit exceeded. Please try again later.")
    default_code = "rate_limit_exceeded"
    status_code = 429


class WebhookError(KitaBaseException):
    """Webhook processing errors."""
    default_message = _("Webhook processing error")
    default_code = "webhook_error"
    status_code = 400


class ValidationError(KitaBaseException):
    """Custom validation error."""
    default_message = _("Validation error")
    default_code = "validation_error"
    status_code = 400


class AuthenticationError(KitaBaseException):
    """Authentication failed error."""
    default_message = _("Authentication required")
    default_code = "authentication_required"
    status_code = 401


class PermissionError(KitaBaseException):
    """Permission denied error."""
    default_message = _("Permission denied")
    default_code = "permission_denied"
    status_code = 403


class SubscriptionError(KitaBaseException):
    """Subscription-related errors."""
    default_message = _("Subscription error")
    default_code = "subscription_error"
    status_code = 402  # Payment Required


# Error Handlers
def handle_kita_exception(exc: KitaBaseException, request: Optional[HttpRequest] = None) -> JsonResponse:
    """
    Handle KitaBaseException and return standardized JSON response.

    Args:
        exc: KitaBaseException instance
        request: Optional HTTP request

    Returns:
        JsonResponse with error details
    """
    error_data = {
        "error": True,
        "code": exc.code,
        "message": str(exc.message),
        "details": exc.extra
    }

    # Log the error
    logger.error(
        f"KitaException: {exc.code} - {exc.message}",
        extra={
            "code": exc.code,
            "details": exc.extra,
            "request_path": request.path if request else None,
            "user": request.user.id if request and request.user.is_authenticated else None
        }
    )

    return JsonResponse(error_data, status=exc.status_code)


def handle_validation_error(exc: ValidationError, request: Optional[HttpRequest] = None) -> JsonResponse:
    """
    Handle Django ValidationError and return standardized JSON response.

    Args:
        exc: ValidationError instance
        request: Optional HTTP request

    Returns:
        JsonResponse with validation errors
    """
    if hasattr(exc, 'message_dict'):
        errors = exc.message_dict
    elif hasattr(exc, 'messages'):
        errors = {"non_field_errors": exc.messages}
    else:
        errors = {"non_field_errors": [str(exc)]}

    error_data = {
        "error": True,
        "code": "validation_error",
        "message": _("Validation failed"),
        "errors": errors
    }

    return JsonResponse(error_data, status=400)


def handle_permission_denied(exc: PermissionDenied, request: Optional[HttpRequest] = None) -> JsonResponse:
    """
    Handle Django PermissionDenied and return standardized JSON response.

    Args:
        exc: PermissionDenied instance
        request: Optional HTTP request

    Returns:
        JsonResponse with permission error
    """
    error_data = {
        "error": True,
        "code": "permission_denied",
        "message": str(exc) or _("You do not have permission to perform this action")
    }

    logger.warning(
        f"Permission denied: {request.path if request else 'Unknown path'}",
        extra={
            "user": request.user.id if request and request.user.is_authenticated else None,
            "path": request.path if request else None
        }
    )

    return JsonResponse(error_data, status=403)


def handle_generic_exception(exc: Exception, request: Optional[HttpRequest] = None) -> JsonResponse:
    """
    Handle generic exceptions and return standardized JSON response.

    Args:
        exc: Exception instance
        request: Optional HTTP request

    Returns:
        JsonResponse with error details
    """
    # Log the full exception
    logger.exception(
        "Unhandled exception occurred",
        extra={
            "request_path": request.path if request else None,
            "user": request.user.id if request and request.user.is_authenticated else None
        }
    )

    # Don't expose internal errors in production
    from django.conf import settings
    if settings.DEBUG:
        message = str(exc)
    else:
        message = _("An internal error occurred. Please try again later.")

    error_data = {
        "error": True,
        "code": "internal_error",
        "message": message
    }

    return JsonResponse(error_data, status=500)


# Commented out - requires djangorestframework package
# def custom_exception_handler(exc, context):
#     """
#     Custom exception handler for Django REST Framework.
#
#     Args:
#         exc: Exception instance
#         context: DRF context
#
#     Returns:
#         Response object
#     """
#     # Call DRF's default exception handler first
#     response = drf_exception_handler(exc, context)
#
#     if response is not None:
#         # Customize the response format
#         custom_response_data = {
#             "error": True,
#             "code": getattr(exc, 'default_code', 'error'),
#             "message": getattr(exc, 'detail', str(exc)),
#         }
#
#         if hasattr(exc, 'get_full_details'):
#             custom_response_data["details"] = exc.get_full_details()
#
#         response.data = custom_response_data
#
#     return response


# Error Response Builders
class ErrorResponseBuilder:
    """Helper class to build consistent error responses."""

    @staticmethod
    def build_error(
        message: str,
        code: str = "error",
        status: int = 400,
        details: Optional[Dict[str, Any]] = None
    ) -> JsonResponse:
        """
        Build a standardized error response.

        Args:
            message: Error message
            code: Error code
            status: HTTP status code
            details: Additional error details

        Returns:
            JsonResponse with error
        """
        error_data = {
            "error": True,
            "code": code,
            "message": message
        }

        if details:
            error_data["details"] = details

        return JsonResponse(error_data, status=status)

    @staticmethod
    def build_validation_error(
        errors: Dict[str, Any],
        message: str = "Validation failed"
    ) -> JsonResponse:
        """
        Build a validation error response.

        Args:
            errors: Field errors
            message: Overall error message

        Returns:
            JsonResponse with validation errors
        """
        return JsonResponse({
            "error": True,
            "code": "validation_error",
            "message": message,
            "errors": errors
        }, status=400)

    @staticmethod
    def build_success(
        data: Dict[str, Any],
        message: Optional[str] = None
    ) -> JsonResponse:
        """
        Build a success response.

        Args:
            data: Response data
            message: Optional success message

        Returns:
            JsonResponse with success data
        """
        response_data = {
            "success": True,
            "data": data
        }

        if message:
            response_data["message"] = message

        return JsonResponse(response_data, status=200)


# Decorators for exception handling
def handle_exceptions(default_message: str = "An error occurred"):
    """
    Decorator to handle exceptions in views.

    Args:
        default_message: Default error message

    Returns:
        Decorated function
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            try:
                return func(request, *args, **kwargs)
            except KitaBaseException as e:
                return handle_kita_exception(e, request)
            except ValidationError as e:
                return handle_validation_error(e, request)
            except PermissionDenied as e:
                return handle_permission_denied(e, request)
            except Exception as e:
                return handle_generic_exception(e, request)

        return wrapper
    return decorator


# Utility functions
def log_exception(
    exc: Exception,
    request: Optional[HttpRequest] = None,
    extra: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log an exception with context.

    Args:
        exc: Exception to log
        request: Optional HTTP request
        extra: Additional context
    """
    log_extra = {
        "exception_type": type(exc).__name__,
        "exception_message": str(exc)
    }

    if request:
        log_extra.update({
            "request_path": request.path,
            "request_method": request.method,
            "user": request.user.id if request.user.is_authenticated else None,
            "ip_address": SecureIPDetector.get_client_ip(request)
        })

    if extra:
        log_extra.update(extra)

    logger.exception(
        f"Exception: {type(exc).__name__}: {exc}",
        extra=log_extra
    )