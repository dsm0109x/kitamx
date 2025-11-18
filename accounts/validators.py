"""
Validators for accounts app with security best practices.

This module delegates to centralized validators in core.validators
while maintaining backward compatibility and adding account-specific validators.
"""
from __future__ import annotations
import re
from typing import Optional
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from core.validators import (
    RFCValidator as CoreRFCValidator,
    PhoneValidator as CorePhoneValidator,
    PostalCodeValidator as CorePostalCodeValidator,
)


class E164PhoneValidator:
    """
    Validates and formats phone numbers to E.164 international standard.

    Delegates to centralized PhoneValidator while maintaining backward compatibility.
    """

    def __init__(self, default_country: str = '52'):
        """
        Initialize validator with default country code.

        Args:
            default_country: Default country code without + (default: '52' for Mexico)
        """
        self.default_country = default_country

    def __call__(self, value: Optional[str]) -> str:
        """
        Validate and format phone number.

        Args:
            value: Phone number to validate

        Returns:
            Formatted phone number in E.164 format

        Raises:
            ValidationError: If phone number is invalid
        """
        if not value:
            return ''

        # Use centralized validator
        return CorePhoneValidator.clean(value)

    @staticmethod
    def clean_for_display(phone: str) -> str:
        """
        Format E.164 phone for display.

        Args:
            phone: E.164 formatted phone

        Returns:
            Human-readable phone format
        """
        # Use centralized formatter
        return CorePhoneValidator.format_display(phone)


class RFCValidator:
    """
    Validates Mexican RFC (Registro Federal de Contribuyentes).

    Delegates to centralized RFCValidator while maintaining backward compatibility.
    """

    def __call__(self, value: Optional[str]) -> str:
        """
        Validate RFC format and basic rules.

        Args:
            value: RFC to validate

        Returns:
            Uppercase RFC

        Raises:
            ValidationError: If RFC is invalid
        """
        if not value:
            return ''

        # Use centralized validator
        return CoreRFCValidator.clean(value)

    @staticmethod
    def get_type(rfc: str) -> str:
        """
        Determine if RFC is for Persona Física or Moral.

        Args:
            rfc: Valid RFC

        Returns:
            'fisica' or 'moral'
        """
        if not rfc:
            return ''
        rfc_len = len(rfc.strip())
        if rfc_len == 13:
            return 'fisica'
        elif rfc_len == 12:
            return 'moral'
        return ''


class PostalCodeValidator:
    """
    Validates Mexican postal codes.

    Delegates to centralized PostalCodeValidator while maintaining backward compatibility.
    """

    def __call__(self, value: Optional[str]) -> str:
        """
        Validate postal code.

        Args:
            value: Postal code to validate

        Returns:
            Cleaned postal code

        Raises:
            ValidationError: If postal code is invalid
        """
        if not value:
            return ''

        # Use centralized validator
        return CorePostalCodeValidator.clean(value)


class FiscalRegimeValidator:
    """
    Validates Mexican SAT fiscal regimes for CFDI 4.0.
    """

    # Valid fiscal regimes for Personas Físicas (individuals)
    VALID_REGIMES_FISICA = {
        '605': 'Sueldos y Salarios e Ingresos Asimilados a Salarios',
        '606': 'Arrendamiento',
        '607': 'Régimen de Enajenación o Adquisición de Bienes',
        '608': 'Demás ingresos',
        '610': 'Residentes en el Extranjero sin Establecimiento Permanente en México',
        '611': 'Ingresos por Dividendos (socios y accionistas)',
        '612': 'Personas Físicas con Actividades Empresariales y Profesionales',
        '614': 'Ingresos por intereses',
        '615': 'Régimen de los ingresos por obtención de premios',
        '616': 'Sin obligaciones fiscales',
        '621': 'Incorporación Fiscal',
        '625': 'Régimen de Actividades Empresariales con ingresos a través de Plataformas Tecnológicas',
        '626': 'Régimen Simplificado de Confianza',
    }

    # Valid fiscal regimes for Personas Morales (companies)
    VALID_REGIMES_MORAL = {
        '601': 'General de Ley Personas Morales',
        '603': 'Personas Morales con Fines no Lucrativos',
        '609': 'Consolidación',
        '620': 'Sociedades Cooperativas de Producción que optan por Diferir sus Ingresos',
        '622': 'Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras',
        '623': 'Opcional para Grupos de Sociedades',
        '624': 'Coordinados',
        '628': 'Hidrocarburos',
        '607': 'Régimen de Enajenación o Adquisición de Bienes',
    }

    ALL_VALID_REGIMES = {**VALID_REGIMES_FISICA, **VALID_REGIMES_MORAL}

    def __call__(self, value: Optional[str], rfc_type: Optional[str] = None) -> str:
        """
        Validate fiscal regime code.

        Args:
            value: Fiscal regime code
            rfc_type: 'fisica' or 'moral' to validate specific type

        Returns:
            Valid regime code

        Raises:
            ValidationError: If regime is invalid
        """
        if not value:
            return ''

        regime = value.strip()

        # Check if regime exists
        if regime not in self.ALL_VALID_REGIMES:
            raise ValidationError(
                _('Régimen fiscal inválido'),
                code='invalid_regime',
                params={'value': value}
            )

        # Validate against RFC type if provided
        if rfc_type == 'fisica' and regime not in self.VALID_REGIMES_FISICA:
            raise ValidationError(
                _('Régimen fiscal no válido para Persona Física'),
                code='invalid_regime_fisica'
            )
        elif rfc_type == 'moral' and regime not in self.VALID_REGIMES_MORAL:
            raise ValidationError(
                _('Régimen fiscal no válido para Persona Moral'),
                code='invalid_regime_moral'
            )

        return regime

    @classmethod
    def get_description(cls, code: str) -> str:
        """Get human-readable description for regime code."""
        return cls.ALL_VALID_REGIMES.get(code, '')


class SecureEmailValidator:
    """
    Enhanced email validator with additional security checks.
    """

    # Suspicious patterns in email addresses
    SUSPICIOUS_PATTERNS = [
        r'\.{2,}',  # Multiple consecutive dots
        r'^\.|\.$',  # Starts or ends with dot
        r'[<>\"\'%;()]',  # SQL/XSS characters
        r'\s',  # Whitespace
    ]

    # Disposable email domains to block (sample list)
    DISPOSABLE_DOMAINS = {
        'guerrillamail.com',
        '10minutemail.com',
        'tempmail.com',
        'throwaway.email',
        'mailinator.com',
    }

    def __call__(self, value: Optional[str]) -> str:
        """
        Validate email with security checks.

        Args:
            value: Email to validate

        Returns:
            Cleaned email

        Raises:
            ValidationError: If email is suspicious or invalid
        """
        if not value:
            raise ValidationError(
                _('Email es requerido'),
                code='required'
            )

        email = value.strip().lower()

        # Check suspicious patterns
        for pattern in self.SUSPICIOUS_PATTERNS:
            if re.search(pattern, email):
                raise ValidationError(
                    _('Email contiene caracteres no permitidos'),
                    code='suspicious_email'
                )

        # Check disposable domains
        domain = email.split('@')[-1] if '@' in email else ''
        if domain in self.DISPOSABLE_DOMAINS:
            raise ValidationError(
                _('Dominios de email temporales no están permitidos'),
                code='disposable_email'
            )

        # Basic format validation
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            raise ValidationError(
                _('Formato de email inválido'),
                code='invalid_email'
            )

        return email


class TurnstileValidator:
    """
    Validates Cloudflare Turnstile challenge responses server-side.

    Turnstile is Cloudflare's CAPTCHA alternative that provides
    bot protection without user interaction in most cases.
    """

    def __call__(self, token: Optional[str], ip_address: Optional[str] = None) -> bool:
        """
        Validate Turnstile token with Cloudflare API.

        Args:
            token: Turnstile response token from client
            ip_address: User's IP address (optional but recommended)

        Returns:
            True if validation succeeds

        Raises:
            ValidationError: If token is invalid or verification fails
        """
        if not token:
            raise ValidationError(
                _('Verificación anti-bot requerida'),
                code='turnstile_missing'
            )

        from django.conf import settings
        import requests
        import logging

        logger = logging.getLogger(__name__)

        # Prepare verification request
        payload = {
            'secret': settings.TURNSTILE_SECRET_KEY,
            'response': token,
        }

        if ip_address:
            payload['remoteip'] = ip_address

        try:
            # Make verification request to Cloudflare
            response = requests.post(
                settings.TURNSTILE_VERIFY_URL,
                data=payload,
                timeout=settings.TURNSTILE_TIMEOUT
            )
            response.raise_for_status()

            result = response.json()

            if result.get('success'):
                logger.info(f"Turnstile validation successful for IP: {ip_address}")
                return True
            else:
                error_codes = result.get('error-codes', [])
                logger.warning(f"Turnstile validation failed: {error_codes}")

                # Map Cloudflare error codes to user-friendly messages
                error_messages = {
                    'missing-input-secret': 'Error de configuración del servidor',
                    'invalid-input-secret': 'Error de configuración del servidor',
                    'missing-input-response': 'Verificación anti-bot requerida',
                    'invalid-input-response': 'Verificación anti-bot expirada o inválida',
                    'bad-request': 'Solicitud inválida',
                    'timeout-or-duplicate': 'Verificación expirada o duplicada',
                }

                # Get first error message or default
                first_error = error_codes[0] if error_codes else 'unknown'
                message = error_messages.get(
                    first_error,
                    'Verificación anti-bot falló. Por favor, intenta de nuevo.'
                )

                raise ValidationError(
                    _(message),
                    code='turnstile_failed'
                )

        except requests.RequestException as e:
            logger.error(f"Turnstile API request failed: {e}")
            raise ValidationError(
                _('Error al verificar protección anti-bot. Por favor, intenta de nuevo.'),
                code='turnstile_network_error'
            )

    @staticmethod
    def get_client_ip(request) -> Optional[str]:
        """
        Extract client IP address from request.

        Args:
            request: Django HttpRequest object

        Returns:
            IP address string or None
        """
        # Check for proxy headers first
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get first IP if multiple
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')

        return ip


# Export validators for easy import
__all__ = [
    'E164PhoneValidator',
    'RFCValidator',
    'PostalCodeValidator',
    'FiscalRegimeValidator',
    'SecureEmailValidator',
    'TurnstileValidator',
]