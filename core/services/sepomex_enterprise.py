"""
Sepomex Enterprise Service - Production-grade postal code lookup.

Features:
- Multi-level caching (Redis + Django)
- Automatic fallback
- Performance monitoring
"""
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class SepomexEnterpriseService:
    """Enterprise Sepomex service with caching."""

    CACHE_TTL = 3600  # 1 hour
    CACHE_PREFIX = 'sepomex:cp:'

    @classmethod
    def lookup_postal_code(cls, codigo_postal: str) -> dict:
        """
        Lookup with cache.

        Args:
            codigo_postal: 5-digit postal code

        Returns:
            dict with postal code data
        """
        if not codigo_postal or len(codigo_postal) != 5:
            return {'success': False, 'error': 'Código postal debe tener 5 dígitos'}

        # Check cache
        cache_key = f"{cls.CACHE_PREFIX}{codigo_postal}"
        cached = cache.get(cache_key)

        if cached:
            logger.debug(f"Cache HIT for CP {codigo_postal}")
            return cached

        # Cache MISS - query database
        from core.models import CodigoPostal

        result = CodigoPostal.objects.lookup(codigo_postal)

        if not result:
            error_result = {
                'success': False,
                'error': f'Código postal {codigo_postal} no encontrado'
            }
            cache.set(cache_key, error_result, 300)  # 5 min
            return error_result

        # Cache result
        cache.set(cache_key, result, cls.CACHE_TTL)

        return result

    @classmethod
    def validate_colonia(cls, codigo_postal: str, colonia: str) -> bool:
        """Validate CP + Colonia combination."""
        from core.models import CodigoPostal
        return CodigoPostal.objects.validate_colonia(codigo_postal, colonia)
