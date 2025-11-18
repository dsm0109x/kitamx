"""Tests for accounts validators."""
from __future__ import annotations

from django.core.exceptions import ValidationError

from core.test_utils import KitaTestCase
from accounts.validators import (
    E164PhoneValidator,
    RFCValidator,
    PostalCodeValidator,
    FiscalRegimeValidator,
    SecureEmailValidator,
)


class E164PhoneValidatorTestCase(KitaTestCase):
    """Test cases for E164 phone validator."""

    def setUp(self) -> None:
        """Set up validator instance."""
        self.validator = E164PhoneValidator()

    def test_valid_mexican_phones(self) -> None:
        """Test valid Mexican phone numbers."""
        valid_phones = [
            '5512345678',  # Mexico City
            '525512345678',  # With country code
            '+525512345678',  # International format
            '55 1234 5678',  # With spaces
            '(55) 1234-5678',  # With formatting
            '044 55 1234 5678',  # Old mobile format
        ]

        for phone in valid_phones:
            try:
                formatted = self.validator(phone)
                self.assertTrue(formatted.startswith('+52'))
            except ValidationError:
                self.fail(f'Phone {phone} should be valid')

    def test_invalid_phones(self) -> None:
        """Test invalid phone numbers."""
        invalid_phones = [
            '123',  # Too short
            'abcdefghij',  # Letters
            '555',  # Too short even for emergency
            '',  # Empty
            '00000000000',  # All zeros
            '+1234567890123456',  # Too long
        ]

        for phone in invalid_phones:
            with self.assertRaises(ValidationError):
                self.validator(phone)

    def test_formatting(self) -> None:
        """Test phone formatting to E.164."""
        test_cases = [
            ('5512345678', '+525512345678'),
            ('525512345678', '+525512345678'),
            ('+525512345678', '+525512345678'),
            ('(55) 1234-5678', '+525512345678'),
            ('55 1234 5678', '+525512345678'),
        ]

        for input_phone, expected in test_cases:
            result = self.validator(input_phone)
            self.assertEqual(result, expected)


class RFCValidatorTestCase(KitaTestCase):
    """Test cases for RFC validator."""

    def setUp(self) -> None:
        """Set up validator instance."""
        self.validator = RFCValidator()

    def test_valid_rfc_fisica(self) -> None:
        """Test valid RFC for individuals."""
        valid_rfcs = [
            'GODE561231GR8',  # Standard format
            'AECS211231AB9',  # Another valid
            'ROCS940815H32',  # With homoclave
        ]

        for rfc in valid_rfcs:
            try:
                self.validator(rfc)
            except ValidationError:
                self.fail(f'RFC {rfc} should be valid')

    def test_valid_rfc_moral(self) -> None:
        """Test valid RFC for companies."""
        valid_rfcs = [
            'ABC010101AB1',  # Standard format
            'XYZ991231ZZ9',  # Another valid
        ]

        for rfc in valid_rfcs:
            try:
                self.validator(rfc)
            except ValidationError:
                self.fail(f'RFC {rfc} should be valid')

    def test_invalid_rfcs(self) -> None:
        """Test invalid RFCs."""
        invalid_rfcs = [
            'XAXX010101000',  # Generic RFC
            'XEXX010101000',  # Foreign RFC
            'XXXX000000000',  # Test RFC
            'ABC123',  # Too short
            'ABCDEFGHIJKLMNOP',  # Too long
            '1234567890123',  # Numbers only
            'AAAA######AAA',  # Invalid format
        ]

        for rfc in invalid_rfcs:
            with self.assertRaises(ValidationError):
                self.validator(rfc)

    def test_case_insensitive(self) -> None:
        """Test RFC validation is case insensitive."""
        rfc_upper = 'GODE561231GR8'
        rfc_lower = 'gode561231gr8'

        self.validator(rfc_upper)
        self.validator(rfc_lower)


class PostalCodeValidatorTestCase(KitaTestCase):
    """Test cases for postal code validator."""

    def setUp(self) -> None:
        """Set up validator instance."""
        self.validator = PostalCodeValidator()

    def test_valid_postal_codes(self) -> None:
        """Test valid Mexican postal codes."""
        valid_codes = [
            '01000',  # Mexico City
            '64000',  # Monterrey
            '44100',  # Guadalajara
            '06600',  # CDMX
            '77500',  # Cancún
        ]

        for code in valid_codes:
            try:
                self.validator(code)
            except ValidationError:
                self.fail(f'Postal code {code} should be valid')

    def test_invalid_postal_codes(self) -> None:
        """Test invalid postal codes."""
        invalid_codes = [
            '123',  # Too short
            '123456',  # Too long
            'ABCDE',  # Letters
            '00000',  # Below range
            '00999',  # Below range
            '100000',  # Above range
        ]

        for code in invalid_codes:
            with self.assertRaises(ValidationError):
                self.validator(code)


class FiscalRegimeValidatorTestCase(KitaTestCase):
    """Test cases for fiscal regime validator."""

    def setUp(self) -> None:
        """Set up validator instance."""
        self.validator = FiscalRegimeValidator()

    def test_valid_regimes(self) -> None:
        """Test valid fiscal regime codes."""
        valid_regimes = [
            '601',  # General de Ley Personas Morales
            '603',  # Personas Morales con Fines no Lucrativos
            '605',  # Sueldos y Salarios
            '606',  # Arrendamiento
            '607',  # Régimen de Enajenación o Adquisición
            '608',  # Demás ingresos
            '612',  # Personas Físicas con Actividades Empresariales
            '621',  # Régimen de Incorporación Fiscal
            '626',  # RESICO
        ]

        for regime in valid_regimes:
            try:
                self.validator(regime)
            except ValidationError:
                self.fail(f'Regime {regime} should be valid')

    def test_invalid_regimes(self) -> None:
        """Test invalid fiscal regime codes."""
        invalid_regimes = [
            '000',  # Not a valid code
            '999',  # Not a valid code
            'ABC',  # Letters
            '60',  # Too short
            '6001',  # Too long
            '',  # Empty
        ]

        for regime in invalid_regimes:
            with self.assertRaises(ValidationError):
                self.validator(regime)


class SecureEmailValidatorTestCase(KitaTestCase):
    """Test cases for secure email validator."""

    def setUp(self) -> None:
        """Set up validator instance."""
        self.validator = SecureEmailValidator()

    def test_valid_emails(self) -> None:
        """Test valid email addresses."""
        valid_emails = [
            'user@example.com',
            'test.user@example.com',
            'user+tag@example.co.uk',
            'user@subdomain.example.com',
            'user123@example.mx',
        ]

        for email in valid_emails:
            try:
                self.validator(email)
            except ValidationError:
                self.fail(f'Email {email} should be valid')

    def test_disposable_emails_blocked(self) -> None:
        """Test disposable email domains are blocked."""
        disposable_emails = [
            'user@guerrillamail.com',
            'test@10minutemail.com',
            'temp@tempmail.com',
            'throwaway@throwaway.email',
            'user@mailinator.com',
        ]

        for email in disposable_emails:
            with self.assertRaises(ValidationError) as context:
                self.validator(email)
            self.assertIn('temporales no están permitidos', str(context.exception))

    def test_invalid_emails(self) -> None:
        """Test invalid email formats."""
        invalid_emails = [
            'notanemail',
            '@example.com',
            'user@',
            'user @example.com',
            'user@example',
            'user..name@example.com',
            'user@.example.com',
        ]

        for email in invalid_emails:
            with self.assertRaises(ValidationError):
                self.validator(email)