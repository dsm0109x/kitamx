"""
Decorators for onboarding views.

Provides access control and flow management for the onboarding process.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def onboarding_required(view_func):
    """
    Decorator que bloquea acceso al onboarding si ya fue completado.

    Redirige al dashboard con mensaje informativo si el usuario
    ya completó su onboarding. Esto previene:
    - Modificaciones accidentales de datos fiscales
    - Desconexión involuntaria de integraciones
    - Confusión en la navegación

    Uso:
        @login_required
        @onboarding_required
        def onboarding_step1(request):
            # Solo accesible si onboarding NO completado
            pass

    Args:
        view_func: Vista de onboarding a proteger

    Returns:
        Wrapper function que verifica onboarding_completed
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Check si usuario está autenticado y completó onboarding
        if request.user.is_authenticated:
            if getattr(request.user, 'onboarding_completed', False):
                messages.info(
                    request,
                    '✅ Tu configuración inicial ya está completa. '
                    'Puedes editar tus datos desde Configuración en el dashboard.'
                )
                return redirect('dashboard:index')

        # Si no completó, permitir acceso normal
        return view_func(request, *args, **kwargs)

    return wrapper
