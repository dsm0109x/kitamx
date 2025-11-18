"""
Security decorators for accounts app.

This module provides decorators for permission validation,
tenant verification, and security checks.
"""
from __future__ import annotations
from functools import wraps
from typing import Callable, Optional
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.utils import timezone
import logging

from core.models import TenantUser
from .utils import SessionSecurityHelper, AuditLogger

logger = logging.getLogger(__name__)


def tenant_required(
    permission: Optional[str] = None,
    require_active: bool = True,
    require_owner: bool = False
) -> Callable:
    """
    Decorator to ensure user has access to a tenant.

    Args:
        permission: Specific permission required (e.g., 'can_create_links')
        require_active: Whether tenant must be active
        require_owner: Whether user must be owner

    Returns:
        Decorated function

    Usage:
        @tenant_required()
        def my_view(request):
            tenant = request.tenant  # Injected by decorator

        @tenant_required(permission='can_manage_settings')
        def settings_view(request):
            ...

        @tenant_required(require_owner=True)
        def owner_only_view(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        @login_required
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            user = request.user

            # Get tenant and tenant_user from request (set by middleware)
            tenant = getattr(request, 'tenant', None)
            tenant_user = getattr(request, 'tenant_user', None)

            # If middleware didn't set them, query database
            if not tenant or not tenant_user:
                # Try to get user's primary tenant (where they're owner)
                tenant_user = TenantUser.objects.filter(
                    email=user.email,
                    is_owner=True
                ).select_related('tenant').first()

                if not tenant_user:
                    # Try any tenant where user is member
                    tenant_user = TenantUser.objects.filter(
                        email=user.email
                    ).select_related('tenant').first()

                if not tenant_user:
                    logger.warning(f"User {user.email} has no tenant access")
                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse(
                            {'error': _('No tienes acceso a ninguna empresa')},
                            status=403
                        )
                    return redirect('onboarding:start')

                tenant = tenant_user.tenant

            # Check tenant is active
            if require_active and not tenant.is_active:
                logger.warning(f"Access denied to inactive tenant {tenant.id}")
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse(
                        {'error': _('Esta empresa está inactiva')},
                        status=403
                    )
                raise PermissionDenied(_('Esta empresa está inactiva'))

            # Check owner requirement
            if require_owner and not tenant_user.is_owner:
                logger.warning(
                    f"Owner access required for user {user.email} on tenant {tenant.id}"
                )
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse(
                        {'error': _('Solo el propietario puede realizar esta acción')},
                        status=403
                    )
                raise PermissionDenied(_('Solo el propietario puede realizar esta acción'))

            # Check specific permission
            if permission and not tenant_user.has_permission(permission):
                logger.warning(
                    f"Permission {permission} denied for user {user.email} on tenant {tenant.id}"
                )
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse(
                        {'error': _('No tienes permiso para realizar esta acción')},
                        status=403
                    )
                raise PermissionDenied(_('No tienes permiso para realizar esta acción'))

            # Check subscription status (for non-trial features)
            if require_active and hasattr(tenant, 'subscription'):
                subscription = tenant.subscription
                if subscription and not subscription.is_active and not subscription.is_trial:
                    logger.warning(f"Subscription required for tenant {tenant.id}")
                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse(
                            {'error': _('Suscripción activa requerida')},
                            status=402  # Payment Required
                        )
                    return redirect('billing:index')

            # Inject tenant and tenant_user into request
            request.tenant = tenant
            request.tenant_user = tenant_user

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def verified_email_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure user has verified their email.

    Checks both User.is_email_verified (custom field) and allauth EmailAddress.verified
    to handle cases where Google OAuth users might not have synced verification status.

    Usage:
        @verified_email_required
        def my_view(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = request.user

        # Check our custom field first
        if user.is_email_verified:
            return view_func(request, *args, **kwargs)

        # Fallback: Check allauth EmailAddress (for Google OAuth users)
        from allauth.account.models import EmailAddress
        email_verified_in_allauth = EmailAddress.objects.filter(
            user=user,
            email__iexact=user.email,
            verified=True
        ).exists()

        if email_verified_in_allauth:
            # Sync the verification status to our User model
            user.is_email_verified = True
            user.email_verified_at = timezone.now()
            user.save(update_fields=['is_email_verified', 'email_verified_at'])

            logger.info(f"Synced email verification from allauth to User model for {user.email}")
            return view_func(request, *args, **kwargs)

        # Email not verified in either system
        logger.info(f"Email verification required for user {user.email}")

        # Log the attempt
        AuditLogger.log_action(
            request=request,
            action='email_verification_required',
            entity_type='User',
            entity_id=user.id,
            entity_name=user.email,
            notes='Attempted to access feature requiring verified email'
        )

        if request.headers.get('Accept') == 'application/json':
            return JsonResponse(
                {'error': _('Debes verificar tu email primero')},
                status=403
            )

        # Redirect to email verification page
        return redirect('account_email_verification_sent')

    return wrapper


def session_security_required(view_func: Callable) -> Callable:
    """
    Decorator to validate session security (anti-hijacking).

    Usage:
        @session_security_required
        def sensitive_view(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not SessionSecurityHelper.validate_session_security(request):
            logger.warning(
                f"Session security validation failed for user {request.user.email}"
            )

            # Log potential hijacking attempt
            AuditLogger.log_action(
                request=request,
                action='session_security_failed',
                entity_type='User',
                entity_id=request.user.id,
                entity_name=request.user.email,
                notes='Session fingerprint mismatch detected'
            )

            # Force re-authentication
            from django.contrib.auth import logout
            logout(request)

            if request.headers.get('Accept') == 'application/json':
                return JsonResponse(
                    {'error': _('Sesión inválida. Por favor inicia sesión nuevamente')},
                    status=401
                )

            return redirect('account_login')

        return view_func(request, *args, **kwargs)

    return wrapper


def onboarding_completed_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure user has completed onboarding.

    Usage:
        @onboarding_completed_required
        def dashboard_view(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        user = request.user

        if not user.onboarding_completed:
            logger.info(f"Onboarding incomplete for user {user.email} at step {user.onboarding_step}")

            if request.headers.get('Accept') == 'application/json':
                return JsonResponse(
                    {
                        'error': _('Debes completar el onboarding primero'),
                        'onboarding_step': user.onboarding_step
                    },
                    status=403
                )

            # Redirect to current onboarding step
            return redirect('onboarding:start')

        return view_func(request, *args, **kwargs)

    return wrapper


def ajax_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure request is AJAX.

    Usage:
        @ajax_required
        def api_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            logger.warning(f"Non-AJAX request to AJAX-only view from {request.user}")
            return JsonResponse(
                {'error': _('Esta vista solo acepta peticiones AJAX')},
                status=400
            )

        return view_func(request, *args, **kwargs)

    return wrapper


def superuser_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure user is superuser.

    Usage:
        @superuser_required
        def admin_view(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if not request.user.is_superuser:
            logger.warning(f"Superuser access denied for user {request.user.email}")

            AuditLogger.log_action(
                request=request,
                action='superuser_access_denied',
                entity_type='User',
                entity_id=request.user.id,
                entity_name=request.user.email,
                notes='Attempted to access superuser-only resource'
            )

            raise PermissionDenied(_('Acceso denegado. Se requieren permisos de superusuario'))

        return view_func(request, *args, **kwargs)

    return wrapper


def trial_or_active_subscription_required(view_func: Callable) -> Callable:
    """
    Decorator to ensure tenant has trial or active subscription.

    Usage:
        @trial_or_active_subscription_required
        def premium_feature_view(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        @tenant_required()
        def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
            tenant = request.tenant

            # Check subscription status
            from billing.models import Subscription
            try:
                subscription = Subscription.objects.get(tenant=tenant)

                if not (subscription.is_trial or subscription.is_active):
                    logger.warning(f"Subscription expired for tenant {tenant.id}")

                    if request.headers.get('Accept') == 'application/json':
                        return JsonResponse(
                            {
                                'error': _('Tu suscripción ha expirado'),
                                'subscription_status': subscription.status
                            },
                            status=402  # Payment Required
                        )

                    return redirect('billing:index')

                # Check trial expiry warning (last 3 days)
                if subscription.is_trial and subscription.days_until_trial_end <= 3:
                    # Add warning to messages
                    from django.contrib import messages
                    messages.warning(
                        request,
                        _(f'Tu periodo de prueba termina en {subscription.days_until_trial_end} días')
                    )

            except Subscription.DoesNotExist:
                logger.error(f"No subscription found for tenant {tenant.id}")
                if request.headers.get('Accept') == 'application/json':
                    return JsonResponse(
                        {'error': _('No se encontró suscripción')},
                        status=402
                    )
                return redirect('billing:subscription')

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator(view_func) if callable(view_func) else decorator


# Composite decorators for common patterns

def owner_action_required(view_func: Callable) -> Callable:
    """
    Composite decorator for owner-only actions with full security.

    Combines:
    - Login required
    - Email verified
    - Session security
    - Tenant owner required
    - Active subscription

    Usage:
        @owner_action_required
        def delete_tenant_view(request):
            ...
    """
    @verified_email_required
    @session_security_required
    @tenant_required(require_owner=True)
    @trial_or_active_subscription_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return view_func(request, *args, **kwargs)

    return wrapper


def secure_ajax_required(view_func: Callable) -> Callable:
    """
    Composite decorator for secure AJAX endpoints.

    Combines:
    - AJAX required
    - Login required
    - Session security

    Usage:
        @secure_ajax_required
        def api_endpoint(request):
            ...
    """
    @ajax_required
    @login_required
    @session_security_required
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        return view_func(request, *args, **kwargs)

    return wrapper


__all__ = [
    'tenant_required',
    'verified_email_required',
    'session_security_required',
    'onboarding_completed_required',
    'ajax_required',
    'superuser_required',
    'trial_or_active_subscription_required',
    'owner_action_required',
    'secure_ajax_required',
]