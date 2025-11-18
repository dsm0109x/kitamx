"""Centralized validators for the Kita application.

This module provides unified validation logic for common data types
to ensure consistency across the entire application.
"""
from __future__ import annotations
from typing import Tuple, Optional
import re
import logging

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class RFCValidator:
    """Centralized RFC (Registro Federal de Contribuyentes) validation for Mexican tax IDs.

    Handles validation for both:
    - Persona Moral (companies): 12 characters
    - Persona Física (individuals): 13 characters
    """

    # RFC patterns according to SAT specifications
    RFC_MORAL_PATTERN = re.compile(
        r'^[A-ZÑ&]{3}\d{6}[A-Z0-9]{3}$',
        re.IGNORECASE
    )
    RFC_FISICA_PATTERN = re.compile(
        r'^[A-ZÑ&]{4}\d{6}[A-Z0-9]{3}$',
        re.IGNORECASE
    )

    # Generic RFC pattern for more flexible validation
    RFC_GENERIC_PATTERN = re.compile(
        r'^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$',
        re.IGNORECASE
    )

    @classmethod
    def validate(cls, rfc: str) -> Tuple[bool, str]:
        """Validate RFC format - ONLY Persona Física (13 chars).

        Args:
            rfc: RFC string to validate

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if RFC is valid
            - error_message: Empty string if valid, error description if invalid
        """
        if not rfc:
            return False, _("RFC es requerido")

        # Normalize RFC
        rfc = rfc.strip().upper()

        # Check length - ONLY 13 characters (Persona Física)
        if len(rfc) != 13:
            return False, _("RFC debe tener exactamente 13 caracteres (solo personas físicas)")

        # Validate Persona Física format
        if not cls.RFC_FISICA_PATTERN.match(rfc):
            return False, _("RFC inválido - Formato: 4 letras + 6 dígitos (fecha) + 3 caracteres")

        # Additional validation for known invalid patterns
        if cls._is_invalid_pattern(rfc):
            return False, _("RFC con formato inválido")

        return True, ""

    @classmethod
    def _is_invalid_pattern(cls, rfc: str) -> bool:
        """Check for known invalid RFC patterns.

        Args:
            rfc: Normalized RFC string

        Returns:
            True if RFC matches known invalid patterns
        """
        # Check for generic RFCs (e.g., XAXX010101000)
        generic_patterns = [
            'XAXX010101000',  # Generic RFC
            'XEXX010101000',  # Foreign RFC
            'AAA010101AAA',   # Test RFC
        ]

        if rfc in generic_patterns:
            return True

        # Check for all zeros in date
        if '000000' in rfc:
            return True

        return False

    @classmethod
    def check_uniqueness(cls, rfc: str, exclude_tenant=None) -> bool:
        """Check if RFC is unique in database.

        Args:
            rfc: RFC to check
            exclude_tenant: Tenant to exclude from check (for updates)

        Returns:
            True if RFC is unique (not in use)
        """
        from core.models import Tenant

        rfc = rfc.strip().upper()
        query = Tenant.objects.filter(rfc=rfc)

        if exclude_tenant:
            query = query.exclude(id=exclude_tenant.id)

        return not query.exists()

    @classmethod
    def clean(cls, rfc: str) -> str:
        """Clean and normalize RFC.

        Args:
            rfc: RFC string to clean

        Returns:
            Cleaned and normalized RFC

        Raises:
            ValidationError if RFC is invalid
        """
        if not rfc:
            raise ValidationError(_("RFC es requerido"))

        rfc = rfc.strip().upper()

        # Validate
        is_valid, error_message = cls.validate(rfc)
        if not is_valid:
            raise ValidationError(error_message)

        return rfc


class PhoneValidator:
    """Centralized phone number validation and formatting.

    Handles Mexican phone numbers with proper E.164 formatting.
    """

    # Mexican phone number pattern in E.164 format
    MEXICO_E164_PATTERN = re.compile(r'^\+52[1-9]\d{9}$')

    # Mexican mobile number pattern (starts with specific prefixes)
    MEXICO_MOBILE_PATTERN = re.compile(r'^\+52(33|55|56|81|442|443|444|449|461|462|473|477|612|614|618|624|631|656|662|664|667|686|722|729|744|747|755|771|773|774|775|777|779|782|783|784|785|786|833|834|844|867|868|871|872|873|878|899|919|921|922|923|924|938|951|953|954|958|961|962|963|964|965|966|967|968|969|971|981|982|983|984|985|986|987|988|991|992|993|994|995|996|997|998|999)\d{7}$')

    # Pattern for cleaning phone numbers
    CLEAN_PATTERN = re.compile(r'[^\d+]')

    @classmethod
    def clean_number(cls, phone: str) -> str:
        """Clean and normalize phone number.

        Args:
            phone: Phone number to clean

        Returns:
            Cleaned phone number with country code
        """
        if not phone:
            return ""

        # Remove all non-digit characters except +
        phone = cls.CLEAN_PATTERN.sub('', phone)

        # Remove leading zeros
        phone = phone.lstrip('0')

        # Handle different formats
        if phone.startswith('+'):
            # Already has country code
            pass
        elif phone.startswith('52') and len(phone) == 12:
            # Has country code without +
            phone = f"+{phone}"
        elif phone.startswith('1') and len(phone) == 10:
            # Mexican mobile starting with 1 (old format)
            phone = f"+52{phone}"
        elif len(phone) == 10 and phone[0] in '23456789':
            # Mexican number without country code
            phone = f"+52{phone}"
        elif len(phone) == 8:
            # Might be a local number, assume Mexico City
            phone = f"+5255{phone}"

        return phone

    @classmethod
    def validate_mexico(cls, phone: str) -> Tuple[bool, str]:
        """Validate Mexican phone number.

        Args:
            phone: Phone number to validate

        Returns:
            Tuple of (is_valid, cleaned_number_or_error)
            - If valid: (True, cleaned_number)
            - If invalid: (False, error_message)
        """
        if not phone:
            return False, _("Número de teléfono es requerido")

        cleaned = cls.clean_number(phone)

        if not cleaned:
            return False, _("Número de teléfono inválido")

        # Check E.164 format
        if not cls.MEXICO_E164_PATTERN.match(cleaned):
            return False, _("Número de teléfono mexicano inválido (10 dígitos)")

        # Check if it's a valid Mexican number prefix
        # This is optional but helps catch invalid numbers
        # if not cls.MEXICO_MOBILE_PATTERN.match(cleaned):
        #     return False, _("Prefijo de número mexicano inválido")

        return True, cleaned

    @classmethod
    def format_display(cls, phone: str) -> str:
        """Format phone number for display.

        Args:
            phone: Phone number to format

        Returns:
            Formatted phone number for display
            Example: +52 (55) 1234-5678
        """
        if not phone:
            return ""

        cleaned = cls.clean_number(phone)

        if len(cleaned) == 13 and cleaned.startswith('+52'):
            # Format: +52 (XX) XXXX-XXXX or +52 (XXX) XXX-XXXX
            country = cleaned[:3]

            # Determine if it's a 2 or 3 digit area code
            # Major cities have 2-digit codes (55, 33, 81)
            area_codes_2 = ['55', '33', '81', '56']
            potential_area = cleaned[3:5]

            if potential_area in area_codes_2:
                # 2-digit area code
                area = cleaned[3:5]
                first = cleaned[5:9]
                second = cleaned[9:]
                return f"{country} ({area}) {first}-{second}"
            else:
                # 3-digit area code
                area = cleaned[3:6]
                first = cleaned[6:9]
                second = cleaned[9:]
                return f"{country} ({area}) {first}-{second}"

        return phone

    @classmethod
    def clean(cls, phone: str) -> str:
        """Clean and validate phone number.

        Args:
            phone: Phone number to clean

        Returns:
            Cleaned phone number in E.164 format

        Raises:
            ValidationError if phone is invalid
        """
        if not phone:
            raise ValidationError(_("Número de teléfono es requerido"))

        is_valid, result = cls.validate_mexico(phone)

        if not is_valid:
            raise ValidationError(result)

        return result


class PostalCodeValidator:
    """Validator for Mexican postal codes."""

    # Mexican postal code pattern (5 digits)
    POSTAL_CODE_PATTERN = re.compile(r'^\d{5}$')

    # Valid postal code ranges for Mexican states
    POSTAL_CODE_RANGES = {
        # Format: (min, max) for each state
        'AGS': (20000, 20999),  # Aguascalientes
        'BCN': (21000, 22999),  # Baja California
        'BCS': (23000, 23999),  # Baja California Sur
        'CAM': (24000, 24999),  # Campeche
        'CHP': (29000, 30999),  # Chiapas
        'CHH': (31000, 33999),  # Chihuahua
        'COA': (25000, 27999),  # Coahuila
        'COL': (28000, 28999),  # Colima
        'CDMX': (1000, 16999),  # Ciudad de México
        'DUR': (34000, 35999),  # Durango
        'GUA': (36000, 38999),  # Guanajuato
        'GRO': (39000, 41999),  # Guerrero
        'HID': (42000, 43999),  # Hidalgo
        'JAL': (44000, 49999),  # Jalisco
        'MEX': (50000, 57999),  # Estado de México
        'MIC': (58000, 61999),  # Michoacán
        'MOR': (62000, 62999),  # Morelos
        'NAY': (63000, 63999),  # Nayarit
        'NLE': (64000, 67999),  # Nuevo León
        'OAX': (68000, 71999),  # Oaxaca
        'PUE': (72000, 75999),  # Puebla
        'QUE': (76000, 76999),  # Querétaro
        'ROO': (77000, 77999),  # Quintana Roo
        'SLP': (78000, 79999),  # San Luis Potosí
        'SIN': (80000, 82999),  # Sinaloa
        'SON': (83000, 85999),  # Sonora
        'TAB': (86000, 86999),  # Tabasco
        'TAM': (87000, 89999),  # Tamaulipas
        'TLA': (90000, 90999),  # Tlaxcala
        'VER': (91000, 97999),  # Veracruz
        'YUC': (97000, 97999),  # Yucatán
        'ZAC': (98000, 99999),  # Zacatecas
    }

    @classmethod
    def validate(cls, postal_code: str) -> Tuple[bool, str]:
        """Validate Mexican postal code.

        Args:
            postal_code: Postal code to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not postal_code:
            return False, _("Código postal es requerido")

        # Clean postal code
        postal_code = postal_code.strip()

        # Check pattern
        if not cls.POSTAL_CODE_PATTERN.match(postal_code):
            return False, _("Código postal debe ser de 5 dígitos")

        # Check if it's in valid range
        code_num = int(postal_code)

        # Check if code is in any valid state range
        valid = False
        for state, (min_code, max_code) in cls.POSTAL_CODE_RANGES.items():
            if min_code <= code_num <= max_code:
                valid = True
                break

        if not valid:
            return False, _("Código postal no válido para México")

        return True, ""

    @classmethod
    def get_state(cls, postal_code: str) -> Optional[str]:
        """Get state code from postal code.

        Args:
            postal_code: Valid postal code

        Returns:
            State code or None if not found
        """
        if not postal_code or not postal_code.isdigit():
            return None

        code_num = int(postal_code)

        for state, (min_code, max_code) in cls.POSTAL_CODE_RANGES.items():
            if min_code <= code_num <= max_code:
                return state

        return None

    @classmethod
    def clean(cls, postal_code: str) -> str:
        """Clean and validate postal code.

        Args:
            postal_code: Postal code to clean

        Returns:
            Cleaned postal code

        Raises:
            ValidationError if postal code is invalid
        """
        if not postal_code:
            raise ValidationError(_("Código postal es requerido"))

        postal_code = postal_code.strip()

        is_valid, error_message = cls.validate(postal_code)
        if not is_valid:
            raise ValidationError(error_message)

        return postal_code


class BusinessNameValidator:
    """Validator for business names (Razón Social)."""

    # Minimum and maximum length for business names
    MIN_LENGTH = 3
    MAX_LENGTH = 255

    # Pattern for valid characters in business name
    VALID_CHARS_PATTERN = re.compile(
        r'^[A-Za-zÀ-ÿÑñ0-9\s\-.,&\'\"()]+$',
        re.UNICODE
    )

    # Reserved or invalid business names
    RESERVED_NAMES = [
        'test', 'prueba', 'demo', 'example', 'ejemplo',
        'admin', 'administrator', 'root', 'system'
    ]

    @classmethod
    def clean_business_name(cls, name: str) -> str:
        """Clean and normalize business name.

        Args:
            name: Business name to clean

        Returns:
            Cleaned business name
        """
        if not name:
            return ""

        # Strip whitespace
        name = name.strip()

        # Normalize multiple spaces
        name = ' '.join(name.split())

        # Capitalize properly (preserve existing capitalization)
        # Don't force capitalization as business names can have specific formats

        return name

    @classmethod
    def validate(cls, name: str) -> Tuple[bool, str]:
        """Validate business name.

        Args:
            name: Business name to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not name:
            return False, _("Razón social es requerida")

        # Clean first
        name = cls.clean_business_name(name)

        # Check length
        if len(name) < cls.MIN_LENGTH:
            return False, _(f"Razón social debe tener al menos {cls.MIN_LENGTH} caracteres")

        if len(name) > cls.MAX_LENGTH:
            return False, _(f"Razón social no puede exceder {cls.MAX_LENGTH} caracteres")

        # Check valid characters
        if not cls.VALID_CHARS_PATTERN.match(name):
            return False, _("Razón social contiene caracteres inválidos")

        # Check reserved names
        name_lower = name.lower()
        if any(reserved in name_lower for reserved in cls.RESERVED_NAMES):
            return False, _("Razón social contiene palabras reservadas")

        return True, ""

    @classmethod
    def clean(cls, name: str) -> str:
        """Clean and validate business name.

        Args:
            name: Business name to clean and validate

        Returns:
            Cleaned business name

        Raises:
            ValidationError if name is invalid
        """
        if not name:
            raise ValidationError(_("Razón social es requerida"))

        name = cls.clean_business_name(name)

        is_valid, error_message = cls.validate(name)
        if not is_valid:
            raise ValidationError(error_message)

        return name


# Convenience function for Django forms
def validate_rfc(value):
    """Django form validator for RFC."""
    RFCValidator.clean(value)


def validate_phone(value):
    """Django form validator for phone number."""
    PhoneValidator.clean(value)


def validate_postal_code(value):
    """Django form validator for postal code."""
    PostalCodeValidator.clean(value)


def validate_business_name(value):
    """Django form validator for business name."""
    BusinessNameValidator.clean(value)