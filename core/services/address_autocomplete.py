"""
Address Autocomplete Service - Multi-layer system.

Combines 2 data sources for optimal UX:
1. Local SEPOMEX Database - Official SAT postal code data (primary)
2. OpenStreetMap Nominatim - Street name suggestions
3. Hardcoded fallback - Common CDMX postal codes

Author: Kita Team
Date: 2025-10-19
"""
from __future__ import annotations
import requests
import logging
from typing import Optional, Dict, List
from django.core.cache import cache
from .postal_code_fallback import lookup_postal_code_fallback
from .sepomex_enterprise import SepomexEnterpriseService

logger = logging.getLogger(__name__)


class SepomexService:
    """
    Local SEPOMEX database integration for Mexican postal codes.

    Uses local PostgreSQL database with official SEPOMEX data.
    Fast, reliable, and completely offline.
    """

    CACHE_TTL = 86400  # 24 hours (postal codes don't change often)

    @classmethod
    def lookup_postal_code(cls, codigo_postal: str) -> Dict:
        """
        Lookup postal code information from local database.

        Priority:
        1. Local SEPOMEX DB - primary source
        2. Hardcoded fallback - for common CPs if DB is empty

        Args:
            codigo_postal: 5-digit Mexican postal code

        Returns:
            dict with postal code data
        """
        if not codigo_postal or len(codigo_postal) != 5:
            return {'success': False, 'error': 'Código postal debe tener 5 dígitos'}

        # Check cache first
        cache_key = f"sepomex:cp:{codigo_postal}"
        cached = cache.get(cache_key)
        if cached:
            logger.debug(f"SEPOMEX cache hit for CP {codigo_postal}")
            return cached

        # Try local SEPOMEX database
        try:
            result = SepomexEnterpriseService.lookup_postal_code(codigo_postal)
            if result.get('success'):
                # Cache result
                cache.set(cache_key, result, cls.CACHE_TTL)
                logger.info(f"SEPOMEX local DB lookup success for CP {codigo_postal}")
                return result
        except Exception as e:
            logger.warning(f"SEPOMEX local lookup failed: {str(e)}")

        # Fallback to hardcoded data
        logger.info(f"Using fallback for CP {codigo_postal}")
        return lookup_postal_code_fallback(codigo_postal)

    @classmethod
    def validate_colonia(cls, codigo_postal: str, colonia: str) -> bool:
        """
        Validate that a colonia exists for given postal code.

        Args:
            codigo_postal: 5-digit postal code
            colonia: Colonia name to validate

        Returns:
            bool: True if valid, False otherwise
        """
        result = cls.lookup_postal_code(codigo_postal)

        if not result.get('success'):
            return False

        colonias = result.get('colonias', [])
        return colonia in colonias


class NominatimService:
    """
    OpenStreetMap Nominatim integration for address suggestions.

    Free geocoding service with fair use policy (1 req/second).
    """

    BASE_URL = 'https://nominatim.openstreetmap.org'
    USER_AGENT = 'KitaApp/1.0 (contact@kita.mx)'
    CACHE_TTL = 3600  # 1 hour

    @classmethod
    def search_street(cls, query: str, codigo_postal: str = None, colonia: str = None) -> List[Dict]:
        """
        Search for street names matching query.

        Args:
            query: Street name to search (e.g., "Paseo de la Reforma")
            codigo_postal: Optional postal code to narrow results
            colonia: Optional neighborhood to narrow results

        Returns:
            List of matching addresses with structured data
        """
        if not query or len(query) < 3:
            return []

        # Build search query
        search_parts = [query]
        if colonia:
            search_parts.append(colonia)
        if codigo_postal:
            search_parts.append(codigo_postal)
        search_parts.append('Mexico')

        search_query = ', '.join(search_parts)

        # Check cache
        cache_key = f"nominatim:search:{search_query}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            params = {
                'q': search_query,
                'format': 'json',
                'addressdetails': 1,
                'limit': 5,
                'countrycodes': 'mx'
            }

            headers = {
                'User-Agent': cls.USER_AGENT
            }

            response = requests.get(
                f"{cls.BASE_URL}/search",
                params=params,
                headers=headers,
                timeout=3
            )
            response.raise_for_status()

            results = response.json()

            # Parse results
            suggestions = []
            for item in results:
                addr = item.get('address', {})
                suggestions.append({
                    'display_name': item.get('display_name', ''),
                    'calle': addr.get('road', ''),
                    'numero': addr.get('house_number', ''),
                    'colonia': addr.get('neighbourhood', addr.get('suburb', '')),
                    'municipio': addr.get('city', addr.get('town', '')),
                    'estado': addr.get('state', ''),
                    'codigo_postal': addr.get('postcode', ''),
                    'lat': item.get('lat'),
                    'lon': item.get('lon')
                })

            # Cache results
            cache.set(cache_key, suggestions, cls.CACHE_TTL)

            return suggestions

        except Exception as e:
            logger.error(f"Nominatim search error: {str(e)}")
            return []

    @classmethod
    def reverse_geocode(cls, lat: float, lon: float) -> Optional[Dict]:
        """
        Reverse geocode coordinates to address.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Dict with address components or None if failed
        """
        cache_key = f"nominatim:reverse:{lat},{lon}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        try:
            params = {
                'lat': lat,
                'lon': lon,
                'format': 'json',
                'addressdetails': 1,
                'zoom': 18  # Building level
            }

            headers = {
                'User-Agent': cls.USER_AGENT
            }

            response = requests.get(
                f"{cls.BASE_URL}/reverse",
                params=params,
                headers=headers,
                timeout=3
            )
            response.raise_for_status()

            data = response.json()
            addr = data.get('address', {})

            result = {
                'calle': addr.get('road', ''),
                'numero': addr.get('house_number', 'S/N'),
                'colonia': addr.get('neighbourhood', addr.get('suburb', '')),
                'municipio': addr.get('city', addr.get('town', addr.get('municipality', ''))),
                'estado': addr.get('state', ''),
                'codigo_postal': addr.get('postcode', ''),
                'display_name': data.get('display_name', '')
            }

            # Cache result
            cache.set(cache_key, result, cls.CACHE_TTL)

            return result

        except Exception as e:
            logger.error(f"Nominatim reverse geocode error: {str(e)}")
            return None


class AddressAutocompleteService:
    """
    Unified address autocomplete service.

    Combines local SEPOMEX DB (SAT compliance) + Nominatim (UX) for best results.
    """

    @staticmethod
    def lookup_by_postal_code(codigo_postal: str) -> Dict:
        """
        Lookup address data by postal code using official SAT data from local DB.

        Args:
            codigo_postal: 5-digit postal code

        Returns:
            dict: Address data from SEPOMEX local database
        """
        return SepomexService.lookup_postal_code(codigo_postal)

    @staticmethod
    def suggest_streets(query: str, codigo_postal: str = None, colonia: str = None) -> List[Dict]:
        """
        Suggest street names as user types.

        Args:
            query: Partial street name
            codigo_postal: Optional CP to narrow results
            colonia: Optional colonia to narrow results

        Returns:
            List[dict]: Street suggestions from OSM
        """
        return NominatimService.search_street(query, codigo_postal, colonia)

    @staticmethod
    def reverse_from_coords(lat: float, lon: float) -> Optional[Dict]:
        """
        Get address from GPS coordinates.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            dict: Address components or None
        """
        return NominatimService.reverse_geocode(lat, lon)

    @staticmethod
    def validate_and_normalize(address_data: Dict) -> Dict:
        """
        Validate address using local SEPOMEX DB and normalize to SAT format.

        Args:
            address_data: Dict with address components

        Returns:
            dict with:
                - valid: bool
                - normalized: Dict (if valid)
                - errors: List[str] (if invalid)
        """
        errors = []

        # Validate postal code with local SEPOMEX
        cp = address_data.get('codigo_postal', '')
        if not cp or len(cp) != 5:
            errors.append('Código postal inválido')
            return {'valid': False, 'errors': errors}

        sepomex_data = SepomexService.lookup_postal_code(cp)

        if not sepomex_data.get('success'):
            errors.append('Código postal no encontrado')
            return {'valid': False, 'errors': errors}

        # Validate colonia exists for this CP
        colonia = address_data.get('colonia', '')
        if colonia not in sepomex_data.get('colonias', []):
            errors.append(f"Colonia '{colonia}' no corresponde al CP {cp}")
            return {'valid': False, 'errors': errors}

        # Normalize using official names
        normalized = {
            'calle': address_data.get('calle', ''),
            'numero_exterior': address_data.get('numero_exterior', 'S/N'),
            'numero_interior': address_data.get('numero_interior', ''),
            'colonia': colonia,  # Already validated
            'codigo_postal': cp,
            'municipio': sepomex_data['municipio'],  # Official name
            'estado': sepomex_data['estado'],  # Official name
            'pais': 'México',
            'localidad': sepomex_data.get('ciudad', '')
        }

        return {'valid': True, 'normalized': normalized}
