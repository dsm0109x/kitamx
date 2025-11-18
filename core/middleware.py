from __future__ import annotations
from typing import Optional, Any, Callable
from functools import wraps
import logging

from django.http import HttpRequest, HttpResponse
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect

from .models import TenantUser

logger = logging.getLogger(__name__)


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to handle multi-tenant functionality.

    Optimized with caching and reduced database queries.
    """

    # Cache configuration
    CACHE_TTL = 300  # 5 minutes

    # Static path lists (compiled once)
    PUBLIC_PATHS = frozenset([
        '/',           # Home/Landing
        '/admin/',
        '/accounts/',
        '/static/',
        '/media/',
        '/webhooks/',
        '/hola/',       # Public payment links
        '/facturar/',   # Public billing forms
        '/descargar/',  # Public invoice downloads
        '/exito/',      # Payment success 🇪🇸
        '/error/',      # Payment failure 🇪🇸
        '/pendiente/',  # Payment pending 🇪🇸
        '/legal/',      # Legal pages
    ])

    PROTECTED_PATHS = frozenset([
        '/panel/',          # 🇪🇸 dashboard
        '/enlaces/',        # 🇪🇸 links
        '/ia/',             # ✅ kita-ia (universal)
        '/suscripcion/',    # 🇪🇸 subscription
        '/facturas/',       # 🇪🇸 invoices
        '/cuenta/',         # 🇪🇸 account
        '/negocio/',        # 🇪🇸 business settings
        '/auditoria/',      # 🇪🇸 logs
        '/incorporacion/',  # 🇪🇸 onboarding
    ])

    AUTH_PATHS = frozenset([
        '/incorporacion/',   # 🇪🇸 onboarding
        '/panel/',           # 🇪🇸 dashboard
        '/enlaces/',         # 🇪🇸 links
        '/ia/',              # ✅ kita-ia (universal)
        '/suscripcion/',     # 🇪🇸 subscription
        '/facturas/',        # 🇪🇸 invoices
        '/cuenta/',          # 🇪🇸 account
        '/negocio/',         # 🇪🇸 business settings
        '/auditoria/',       # 🇪🇸 logs
    ])

    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request to set tenant context.
        """
        # Check if this is a public path (optimized with set)
        if self._is_public_path(request.path):
            request.tenant = None
            request.tenant_user = None
            return None

        # For authenticated areas, resolve tenant from user
        if request.user.is_authenticated:
            tenant_user = self._get_tenant_user(request.user.email)

            if tenant_user:
                request.tenant = tenant_user.tenant
                request.tenant_user = tenant_user
            else:
                # User exists but no tenant - redirect to onboarding
                if self._is_protected_path(request.path):
                    return redirect('onboarding:start')

                request.tenant = None
                request.tenant_user = None
        else:
            # Not authenticated - redirect to login for protected areas
            if self._is_protected_path(request.path):
                return redirect('account_login')

            request.tenant = None
            request.tenant_user = None

        return None

    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (optimized)."""
        return any(path.startswith(p) for p in self.PUBLIC_PATHS)

    def _is_protected_path(self, path: str) -> bool:
        """Check if path requires authentication (optimized)."""
        return any(path.startswith(p) for p in self.PROTECTED_PATHS)

    def _is_auth_path(self, path: str) -> bool:
        """Check if path handles its own tenant requirements."""
        return any(path.startswith(p) for p in self.AUTH_PATHS)

    def _get_tenant_user(self, email: str) -> Optional[TenantUser]:
        """
        Get tenant user with caching.
        """
        cache_key = f"tenant_user:{email}"
        tenant_user = None

        # Try cache with error handling
        try:
            tenant_user = cache.get(cache_key)
        except Exception as e:
            logger.debug(f"Cache error (continuing without cache): {e}")
            tenant_user = None

        if tenant_user is None:
            # Cache miss - query database
            tenant_user = (
                TenantUser.objects
                .filter(email=email, is_owner=True)
                .select_related('tenant')
                .only(
                    'id', 'email', 'first_name', 'last_name',
                    'is_owner', 'role', 'is_active',
                    'tenant__id', 'tenant__name', 'tenant__slug',
                    'tenant__is_active'
                )
                .first()
            )

            # Try to cache with error handling
            try:
                if tenant_user:
                    cache.set(cache_key, tenant_user, self.CACHE_TTL)
                else:
                    cache.set(cache_key, False, 60)
            except Exception as e:
                logger.debug(f"Cache set error (continuing): {e}")

        return tenant_user if tenant_user else None

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable,
        view_args: tuple,
        view_kwargs: dict
    ) -> Optional[HttpResponse]:
        """
        Process view to check tenant requirements.
        """
        # Allow views marked as public
        if getattr(view_func, 'allow_without_tenant', False):
            return None

        # Views that handle their own tenant requirements
        if self._is_auth_path(request.path):
            return None

        return None


def allow_without_tenant(view_func: Callable) -> Callable:
    """Decorator to allow view without tenant (public pages)."""
    view_func.allow_without_tenant = True
    return view_func




def tenant_user_required(view_func: Callable) -> Callable:
    """Decorator to require authenticated tenant user."""
    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not hasattr(request, 'tenant_user') or request.tenant_user is None:
            logger.warning(f"Tenant user not found for {request.user.email if request.user.is_authenticated else 'anonymous'}")
            raise PermissionDenied("Access denied")
        return view_func(request, *args, **kwargs)
    return wrapper


def invalidate_tenant_cache(email: str) -> None:
    """
    Invalidate cached tenant user data.

    Call this when tenant user data changes.
    """
    cache_key = f"tenant_user:{email}"
    try:
        cache.delete(cache_key)
        logger.info(f"Invalidated tenant cache for {email}")
    except Exception as e:
        logger.debug(f"Cache invalidation error (continuing): {e}")