"""
Views for accounts app with enhanced security and optimizations.

This module handles user account management with rate limiting,
proper permission checking, and security validations.
"""
from __future__ import annotations
import json
import logging

from django.shortcuts import render, get_object_or_404
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django_ratelimit.decorators import ratelimit

from .models import UserProfile, UserSession
from .forms import PasswordChangeForm
from .decorators import (
    tenant_required,
    verified_email_required,
    session_security_required,
    secure_ajax_required,
)
from .validators import E164PhoneValidator
from .utils import (
    log_audit,
    SessionSecurityHelper,
    DataSanitizer,
)

logger = logging.getLogger(__name__)


@verified_email_required
@tenant_required()
def account_index(request: HttpRequest) -> HttpResponse:
    """
    Account management main page with optimized queries.

    Returns:
        Rendered account index page
    """
    user = request.user
    tenant = request.tenant
    tenant_user = request.tenant_user

    # Get or create user profile with select_related for optimization
    profile, created = UserProfile.objects.get_or_create(user=user)

    # Get recent sessions for security display
    recent_sessions = UserSession.objects.filter(
        user=user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).only(
        'ip_address',
        'country',
        'city',
        'last_activity'
    ).order_by('-last_activity')[:5]

    context = {
        'user': user,
        'tenant': tenant,
        'tenant_user': tenant_user,
        'profile': profile,
        'recent_sessions': recent_sessions,
        'page_title': 'Mi Cuenta'
    }

    return render(request, 'accounts/index.html', context)


@secure_ajax_required
@tenant_required()
@ratelimit(key='user', rate='10/h', method='POST')
@csrf_protect
@require_http_methods(["POST"])
@transaction.atomic
def update_profile(request: HttpRequest) -> JsonResponse:
    """
    Update user profile with enhanced validation and rate limiting.

    Rate limit: 10 updates per hour per user

    Returns:
        JSON response with success status
    """
    user = request.user
    phone_validator = E164PhoneValidator()

    try:
        data = json.loads(request.body)

        # Store old values for audit
        old_values = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': user.phone,
        }

        # Update user basic info with sanitization
        user.first_name = DataSanitizer.sanitize_html(
            data.get('first_name', user.first_name)
        )[:150]
        user.last_name = DataSanitizer.sanitize_html(
            data.get('last_name', user.last_name)
        )[:150]

        # Validate and update phone
        phone = data.get('phone', '')
        if phone:
            user.phone = phone_validator(phone)

        user.save(update_fields=['first_name', 'last_name', 'phone'])

        # Update or create profile with optimized query
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'timezone': 'America/Mexico_City'}
        )

        # Update profile fields with sanitization
        profile.bio = DataSanitizer.sanitize_html(data.get('bio', profile.bio))[:500]
        profile.location = DataSanitizer.sanitize_html(
            data.get('location', profile.location)
        )[:100]
        profile.website = data.get('website', profile.website)[:200]
        profile.timezone = data.get('timezone', profile.timezone)
        profile.language = data.get('language', profile.language)
        profile.theme = data.get('theme', profile.theme)
        profile.email_notifications = bool(
            data.get('email_notifications', profile.email_notifications)
        )
        profile.push_notifications = bool(
            data.get('push_notifications', profile.push_notifications)
        )
        profile.sms_notifications = bool(
            data.get('sms_notifications', profile.sms_notifications)
        )

        profile.save()

        # Log audit action
        log_audit(
            request=request,
            action='update',
            entity_type='UserProfile',
            entity_id=profile.id,
            entity_name=f'Profile for {user.email}',
            old_values=old_values,
            new_values={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
            },
            notes='User profile updated successfully'
        )

        return JsonResponse({
            'success': True,
            'message': 'Perfil actualizado correctamente'
        })

    except ValidationError as e:
        return JsonResponse({
            'success': False,
            'error': str(e.message) if hasattr(e, 'message') else str(e)
        }, status=400)

    except Exception as e:
        logger.error(f"Error updating profile for user {user.email}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al actualizar el perfil'
        }, status=500)


@secure_ajax_required
@session_security_required
@ratelimit(key='user', rate='3/10m', method='POST')
@csrf_protect
@require_http_methods(["POST"])
@transaction.atomic
def change_password(request: HttpRequest) -> JsonResponse:
    """
    Change user password with rate limiting.

    Rate limit: 3 attempts per 10 minutes per user

    Returns:
        JSON response with success status
    """
    user = request.user

    try:
        data = json.loads(request.body)
        form = PasswordChangeForm(user, data)

        if form.is_valid():
            form.save()
            update_session_auth_hash(request, user)  # Keep user logged in

            # Recreate session fingerprint after password change
            SessionSecurityHelper.create_session_fingerprint(request)

            # Invalidate other sessions for security
            UserSession.objects.filter(
                user=user,
                is_active=True
            ).exclude(
                session_key=request.session.session_key
            ).update(is_active=False)

            # Log audit action
            log_audit(
                request=request,
                action='change_password',
                entity_type='User',
                entity_id=user.id,
                entity_name=user.email,
                notes='Password changed successfully, other sessions invalidated'
            )

            return JsonResponse({
                'success': True,
                'message': 'Contraseña actualizada correctamente'
            })
        else:
            # Log failed attempt
            log_audit(
                request=request,
                action='change_password_failed',
                entity_type='User',
                entity_id=user.id,
                entity_name=user.email,
                notes='Password change failed: validation errors'
            )

            return JsonResponse({
                'success': False,
                'error': 'Datos inválidos',
                'errors': form.errors
            }, status=400)

    except Exception as e:
        logger.error(f"Error changing password for user {user.email}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al cambiar la contraseña'
        }, status=500)


@verified_email_required
@session_security_required
def user_sessions(request: HttpRequest) -> HttpResponse:
    """
    Display user active sessions with security info.

    Returns:
        Rendered sessions page
    """
    user = request.user

    # Get active sessions with optimized query
    active_sessions = UserSession.objects.filter(
        user=user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).only(
        'id',
        'session_key',
        'ip_address',
        'user_agent',
        'country',
        'city',
        'created_at',
        'last_activity',
        'expires_at'
    ).order_by('-last_activity')

    # Mark current session
    current_session_key = request.session.session_key
    for session in active_sessions:
        session.is_current = (session.session_key == current_session_key)

    context = {
        'user': user,
        'active_sessions': active_sessions,
        'page_title': 'Sesiones Activas'
    }

    return render(request, 'accounts/sessions.html', context)


@secure_ajax_required
@ratelimit(key='user', rate='10/h', method='POST')
@csrf_protect
@require_http_methods(["POST"])
@transaction.atomic
def revoke_session(request: HttpRequest) -> JsonResponse:
    """
    Revoke user session with audit logging.

    Rate limit: 10 revocations per hour

    Returns:
        JSON response with success status
    """
    user = request.user

    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')

        if not session_id:
            return JsonResponse({
                'success': False,
                'error': 'ID de sesión requerido'
            }, status=400)

        # Get session and verify ownership
        session = get_object_or_404(
            UserSession,
            id=session_id,
            user=user
        )

        # Don't allow revoking current session
        if session.session_key == request.session.session_key:
            return JsonResponse({
                'success': False,
                'error': 'No puedes revocar tu sesión actual'
            }, status=400)

        # Deactivate session
        session.is_active = False
        session.save(update_fields=['is_active'])

        # Log audit action
        log_audit(
            request=request,
            action='revoke_session',
            entity_type='UserSession',
            entity_id=session.id,
            entity_name=f'Session from {session.ip_address}',
            notes=f'User revoked session from {session.ip_address}'
        )

        return JsonResponse({
            'success': True,
            'message': 'Sesión revocada correctamente'
        })

    except Exception as e:
        logger.error(f"Error revoking session {session_id}: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error al revocar la sesión'
        }, status=500)


@require_http_methods(["GET"])
def password_reset_done_redirect(request: HttpRequest) -> HttpResponse:
    """
    Custom view for password reset completion.

    Instead of showing a 'done' page, redirect to login with success toast.
    This eliminates an unnecessary screen and improves UX.

    Args:
        request: HTTP request object

    Returns:
        Redirect to login with success message
    """
    from django.contrib import messages
    from django.shortcuts import redirect

    # Add success message (will be shown as toast in login page)
    messages.success(
        request,
        '¡Contraseña cambiada exitosamente! Ahora puedes acceder con tu nueva contraseña.'
    )

    # Redirect to login
    return redirect('account_login')


@require_http_methods(["GET"])
def email_confirm_redirect(request: HttpRequest, key: str) -> HttpResponse:
    """
    Custom view for email confirmation with redirect.

    Confirms email and redirects to login with toast instead of showing
    intermediate page.

    Args:
        request: HTTP request object
        key: Email confirmation key

    Returns:
        Redirect to appropriate page with success message
    """
    from django.contrib import messages
    from django.shortcuts import redirect
    from allauth.account.models import EmailConfirmation, EmailConfirmationHMAC
    from allauth.account.utils import perform_login
    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        # Try HMAC first (newer allauth versions)
        try:
            emailconfirmation = EmailConfirmationHMAC.from_key(key)
            if not emailconfirmation:
                # Try old-style confirmation
                emailconfirmation = EmailConfirmation.objects.get(key=key.lower())
        except:
            emailconfirmation = EmailConfirmation.objects.get(key=key.lower())

        # Confirm the email
        emailconfirmation.confirm(request)

        # Get the user
        user = emailconfirmation.email_address.user

        # If user is not authenticated, log them in automatically
        if not request.user.is_authenticated:
            # Perform login (allauth helper)
            perform_login(
                request,
                user,
                email_verification='none',  # Already verified
                redirect_url=None
            )

            messages.success(
                request,
                f'¡Email confirmado! Bienvenido/a {user.first_name}, tu cuenta está activa.'
            )

            # Redirect to onboarding for new users
            return redirect('onboarding:start')
        else:
            messages.success(
                request,
                '¡Email confirmado exitosamente!'
            )

            # Redirect to dashboard if already logged in
            return redirect('dashboard:index')

    except Exception as e:
        # If confirmation fails, show error message
        messages.error(
            request,
            'El enlace de confirmación es inválido o ya fue utilizado.'
        )

        # Redirect to login
        return redirect('account_login')


# Export views for URL configuration
__all__ = [
    'account_index',
    'update_profile',
    'change_password',
    'user_sessions',
    'revoke_session',
    'password_reset_done_redirect',  # Custom password reset flow
    'email_confirm_redirect',  # Custom email confirmation flow
]