"""
AJAX-Aware Authentication Views - Enhanced Version
===================================================

Custom views que manejan tanto requests AJAX (JSON) como tradicionales (HTML).
Elimina el problema de inconsistencia en responses y mejora la UX.

Features:
- ✅ Detección automática de AJAX via X-Requested-With header
- ✅ JSON responses consistentes y estructurados para AJAX
- ✅ HTML fallback para requests tradicionales
- ✅ Error messages accionables con tipos específicos
- ✅ Help links contextuales según tipo de error
- ✅ Password suggestions para errores de contraseña
- ✅ Audit logging automático
- ✅ Manejo de rate limiting
- ✅ Support para email verification flow

Author: Kita Team
Created: 2025-10-19
Updated: 2025-10-20 - Enhanced with actionable errors
Version: 2.0
"""
from __future__ import annotations

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.contrib.auth import login as auth_login
from django.core.exceptions import ValidationError
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from allauth.account.views import LoginView, SignupView
from allauth.account.utils import perform_login

import logging

logger = logging.getLogger(__name__)


def is_ajax(request: HttpRequest) -> bool:
    """
    Verificar si es request AJAX.

    Django 4.0+ removió request.is_ajax(), así que verificamos
    manualmente el header X-Requested-With.
    """
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


class AjaxLoginView(LoginView):
    """
    Login view con soporte para AJAX.

    Si el request es AJAX, devuelve JSON response.
    Si es request normal, usa el comportamiento default de allauth.
    """

    @method_decorator(csrf_protect)
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        """Override dispatch para detectar AJAX."""
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        """
        Manejo de formulario inválido.

        Si es AJAX: devuelve JSON con errores
        Si no: usa template default de allauth
        """
        if is_ajax(self.request):
            # Convertir errores del form a dict
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(e) for e in error_list]

            # Determinar tipo de error y mensaje específico
            error_type, error_msg = self._get_error_details(form)

            # Help link contextual según tipo de error
            help_link = None
            help_text = None

            if error_type == 'invalid_credentials':
                help_link = '/recuperar-contrasena/'
                help_text = '¿Olvidaste tu contraseña?'
            elif error_type == 'email_not_verified':
                help_link = '/verificar-email/'
                help_text = 'Reenviar email de verificación'
            elif error_type == 'account_inactive':
                help_link = 'mailto:soporte@kita.mx'
                help_text = 'Contactar soporte'

            # Log para analytics
            logger.warning(
                f"Login failed: {error_type}",
                extra={
                    'email': form.data.get('login', 'unknown'),
                    'error_type': error_type,
                    'ip': self.request.META.get('REMOTE_ADDR')
                }
            )

            response_data = {
                'success': False,
                'errors': errors,
                'error': error_msg,
                'error_type': error_type,
            }

            # Agregar help link si existe
            if help_link:
                response_data['help_link'] = help_link
                response_data['help_text'] = help_text

            return JsonResponse(response_data, status=400)

        return super().form_invalid(form)

    def form_valid(self, form):
        """
        Manejo de formulario válido.

        Si es AJAX: login + devuelve JSON con redirect URL
        Si no: usa comportamiento default de allauth
        """
        if is_ajax(self.request):
            # Realizar login usando allauth's perform_login
            # Esto maneja remember me, signals, etc.
            ret = perform_login(
                self.request,
                form.user,
                email_verification=form.cleaned_data.get('email_verification', 'optional'),
                redirect_url=self.get_success_url(),
                signal_kwargs=None
            )

            # Log audit action
            logger.info(
                f"User {form.user.email} logged in successfully via AJAX",
                extra={
                    'user_id': form.user.id,
                    'email': form.user.email,
                    'ip': self.request.META.get('REMOTE_ADDR')
                }
            )

            # Determinar redirect correcto
            # Si usuario no tiene tenant o no completó onboarding → /incorporacion/
            # Si tiene tenant y completó → /panel/
            from core.models import TenantUser

            redirect_url = '/incorporacion/'  # Default para usuarios nuevos 🇪🇸

            tenant_user = TenantUser.objects.filter(
                email=form.user.email,
                is_owner=True
            ).first()

            if tenant_user and form.user.onboarding_completed:
                redirect_url = '/panel/'  # 🇪🇸 Migrado de /dashboard/

            return JsonResponse({
                'success': True,
                'redirect_url': redirect_url,
                'message': '¡Sesión iniciada exitosamente!'
            })

        return super().form_valid(form)

    def _get_error_details(self, form) -> tuple[str, str]:
        """
        Extraer tipo de error y mensaje user-friendly.

        Args:
            form: Form con errores

        Returns:
            Tuple (error_type, error_message)
        """
        # Mensajes default
        error_msg = 'Email o contraseña incorrectos'
        error_type = 'invalid_credentials'

        # Check non-field errors primero
        if form.non_field_errors():
            raw_error = str(form.non_field_errors()[0]).lower()

            if 'incorrect' in raw_error or 'invalid' in raw_error:
                error_msg = 'Email o contraseña incorrectos'
                error_type = 'invalid_credentials'
            elif 'not verified' in raw_error or 'verificar' in raw_error:
                error_msg = 'Por favor verifica tu email antes de iniciar sesión'
                error_type = 'email_not_verified'
            elif 'inactive' in raw_error or 'disabled' in raw_error or 'desactivada' in raw_error:
                error_msg = 'Esta cuenta está desactivada. Contacta a soporte.'
                error_type = 'account_inactive'
            elif 'limit' in raw_error or 'many' in raw_error:
                error_msg = 'Demasiados intentos. Espera unos minutos.'
                error_type = 'rate_limited'
            else:
                error_msg = str(form.non_field_errors()[0])
                error_type = 'auth_error'

        # Check field-specific errors
        elif 'login' in form.errors:
            error_msg = 'Ingresa un email válido'
            error_type = 'invalid_email'
        elif 'password' in form.errors:
            error_msg = 'La contraseña es requerida'
            error_type = 'missing_password'
        elif 'cf_turnstile_response' in form.errors:
            error_msg = 'Error en la verificación de seguridad. Recarga la página.'
            error_type = 'turnstile_failed'

        return error_type, error_msg


class AjaxSignupView(SignupView):
    """
    Signup view con soporte para AJAX.

    Maneja creación de cuentas con respuestas JSON para requests AJAX.
    """

    @method_decorator(csrf_protect)
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        """Override dispatch para detectar AJAX."""
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        """
        Manejo de formulario inválido.

        Si es AJAX: devuelve JSON con errores detallados
        Si no: usa template default
        """
        if is_ajax(self.request):
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(e) for e in error_list]

            # Determinar tipo de error y mensaje
            error_type, error_msg = self._get_signup_error_details(form)

            # Response data base
            response_data = {
                'success': False,
                'errors': errors,
                'error': error_msg,
                'error_type': error_type,
            }

            # Agregar help links contextuales
            if error_type == 'email_exists':
                response_data['help_link'] = '/ingresar/'
                response_data['help_text'] = '¿Ya tienes cuenta? Inicia sesión'
            elif error_type == 'weak_password':
                response_data['suggestions'] = [
                    'Usa al menos 8 caracteres',
                    'Incluye mayúsculas y minúsculas',
                    'Añade números o símbolos',
                ]
            elif error_type == 'terms_not_accepted':
                response_data['help_link'] = '/legal/terms/'
                response_data['help_text'] = 'Leer términos y condiciones'

            # Log para analytics
            logger.warning(
                f"Signup failed: {error_type}",
                extra={
                    'email': form.data.get('email', 'unknown'),
                    'error_type': error_type,
                    'ip': self.request.META.get('REMOTE_ADDR')
                }
            )

            return JsonResponse(response_data, status=400)

        return super().form_invalid(form)

    def form_valid(self, form):
        """
        Manejo de formulario válido.

        Si es AJAX: crea usuario + devuelve JSON
        Si no: usa comportamiento default
        """
        if is_ajax(self.request):
            # Crear usuario usando save() del form
            # Esto maneja todos los campos custom (first_name, phone, etc.)
            try:
                user = form.save(self.request)
            except ValidationError as e:
                # Manejar error de save() (ej: email duplicado)
                return JsonResponse({
                    'success': False,
                    'errors': {
                        '__all__': [str(e.message) if hasattr(e, 'message') else str(e)]
                    }
                }, status=400)

            # NO hacer perform_login aquí - causa error BufferedReader en sesión
            # Solo enviar email de confirmación
            from allauth.account.utils import send_email_confirmation
            send_email_confirmation(self.request, user, signup=True)

            # Log audit action
            logger.info(
                f"New user registered successfully via AJAX: {user.email}",
                extra={
                    'user_id': user.id,
                    'email': user.email,
                    'ip': self.request.META.get('REMOTE_ADDR')
                }
            )

            # Redirect a página de verificación de email
            redirect_url = '/verificar-email/'

            return JsonResponse({
                'success': True,
                'redirect_url': redirect_url,
                'message': '¡Cuenta creada exitosamente!',
                'requires_email_verification': True
            })

        return super().form_valid(form)

    def _get_signup_error_details(self, form) -> tuple[str, str]:
        """
        Extraer tipo de error y mensaje user-friendly para signup.

        Args:
            form: Form con errores

        Returns:
            Tuple (error_type, error_message)
        """
        error_msg = 'Por favor corrige los errores en el formulario'
        error_type = 'validation_error'

        # Check email errors
        if 'email' in form.errors:
            error_text = ' '.join(str(e) for e in form.errors['email']).lower()
            if 'already' in error_text or 'existe' in error_text or 'registrado' in error_text:
                error_msg = 'Este email ya está registrado'
                error_type = 'email_exists'
            else:
                error_msg = 'Ingresa un email válido'
                error_type = 'invalid_email'

        # Check password errors
        elif 'password1' in form.errors or 'password2' in form.errors:
            password_errors = form.errors.get('password1', []) + form.errors.get('password2', [])
            error_text = ' '.join(str(e) for e in password_errors).lower()

            if 'weak' in error_text or 'débil' in error_text or 'common' in error_text or 'similar' in error_text:
                error_msg = 'Tu contraseña es muy débil'
                error_type = 'weak_password'
            elif 'match' in error_text or 'coincid' in error_text:
                error_msg = 'Las contraseñas no coinciden'
                error_type = 'password_mismatch'
            elif 'short' in error_text or 'corta' in error_text:
                error_msg = 'La contraseña debe tener al menos 8 caracteres'
                error_type = 'password_too_short'
            else:
                error_msg = 'La contraseña no cumple los requisitos'
                error_type = 'invalid_password'

        # Check required fields
        elif 'first_name' in form.errors or 'last_name' in form.errors:
            error_msg = 'Completa todos los campos requeridos'
            error_type = 'missing_required_fields'

        # Check terms acceptance
        elif 'terms_accepted' in form.errors or 'privacy_accepted' in form.errors:
            error_msg = 'Debes aceptar los términos y el aviso de privacidad'
            error_type = 'terms_not_accepted'

        # Check Turnstile
        elif 'cf_turnstile_response' in form.errors:
            error_msg = 'Error en la verificación de seguridad. Recarga la página.'
            error_type = 'turnstile_failed'

        # Check non-field errors
        elif form.non_field_errors():
            error_msg = str(form.non_field_errors()[0])
            error_type = 'form_error'

        return error_type, error_msg


@require_http_methods(["POST"])
@csrf_protect
def check_email_availability(request: HttpRequest) -> JsonResponse:
    """
    Check if email is available for signup.

    AJAX endpoint para validación en tiempo real de email.

    POST /accounts/check-email/
    Body: { "email": "user@example.com" }

    Returns:
        JSON: {
            "available": true/false,
            "message": "Email disponible" | "Email ya registrado"
        }
    """
    import json
    from accounts.models import User

    try:
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()

        if not email:
            return JsonResponse({
                'available': False,
                'message': 'Email es requerido'
            }, status=400)

        # Check si email existe
        exists = User.objects.filter(email__iexact=email).exists()

        if exists:
            return JsonResponse({
                'available': False,
                'message': 'Este email ya está registrado'
            })
        else:
            return JsonResponse({
                'available': True,
                'message': 'Email disponible'
            })

    except json.JSONDecodeError:
        return JsonResponse({
            'available': False,
            'message': 'Error en request'
        }, status=400)
    except Exception as e:
        logger.error(f"Email check error: {str(e)}")
        return JsonResponse({
            'available': True,  # Default a disponible en caso de error
            'message': 'No se pudo verificar email'
        }, status=500)


# Exportar las vistas para usar en urls.py
__all__ = [
    'AjaxLoginView',
    'AjaxSignupView',
    'check_email_availability'
]
