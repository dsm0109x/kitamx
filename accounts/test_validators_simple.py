#!/usr/bin/env python
"""Simple unit tests for validators without Django test framework."""
import sys
sys.path.insert(0, '/home/diego/x99/kita')

from django.core.exceptions import ValidationError
from accounts.validators import (
    E164PhoneValidator,
    RFCValidator,
    PostalCodeValidator,
    FiscalRegimeValidator,
)


def test_phone_validator():
    """Test E164 phone validator."""
    validator = E164PhoneValidator()

    print("Testing E164PhoneValidator...")

    # Valid phones
    valid_phones = [
        ('5512345678', '+525512345678'),
        ('+525512345678', '+525512345678'),
        ('55 1234 5678', '+525512345678'),
    ]

    for input_phone, expected in valid_phones:
        result = validator(input_phone)
        assert result == expected, f"Phone {input_phone} should format to {expected}, got {result}"
        print(f"  ✓ {input_phone} -> {result}")

    # Invalid phones
    invalid_phones = ['123', 'abc', '00000000000']
    for phone in invalid_phones:
        try:
            validator(phone)
            assert False, f"Phone {phone} should be invalid"
        except ValidationError:
            print(f"  ✓ {phone} correctly rejected")

    print("E164PhoneValidator: PASSED\n")


def test_rfc_validator():
    """Test RFC validator."""
    validator = RFCValidator()

    print("Testing RFCValidator...")

    # Valid RFCs
    valid_rfcs = [
        'GODE561231GR8',  # Persona física
        'ABC010101AB1',   # Persona moral
    ]

    for rfc in valid_rfcs:
        try:
            validator(rfc)
            print(f"  ✓ {rfc} is valid")
        except ValidationError:
            assert False, f"RFC {rfc} should be valid"

    # Invalid RFCs
    invalid_rfcs = [
        'XAXX010101000',  # Generic
        'ABC123',         # Too short
    ]

    for rfc in invalid_rfcs:
        try:
            validator(rfc)
            assert False, f"RFC {rfc} should be invalid"
        except ValidationError:
            print(f"  ✓ {rfc} correctly rejected")

    print("RFCValidator: PASSED\n")


def test_postal_code_validator():
    """Test postal code validator."""
    validator = PostalCodeValidator()

    print("Testing PostalCodeValidator...")

    # Valid codes
    valid_codes = ['01000', '64000', '44100']

    for code in valid_codes:
        try:
            validator(code)
            print(f"  ✓ {code} is valid")
        except ValidationError:
            assert False, f"Postal code {code} should be valid"

    # Invalid codes
    invalid_codes = ['123', '00000', 'ABCDE']

    for code in invalid_codes:
        try:
            validator(code)
            assert False, f"Postal code {code} should be invalid"
        except ValidationError:
            print(f"  ✓ {code} correctly rejected")

    print("PostalCodeValidator: PASSED\n")


def test_fiscal_regime_validator():
    """Test fiscal regime validator."""
    validator = FiscalRegimeValidator()

    print("Testing FiscalRegimeValidator...")

    # Valid regimes
    valid_regimes = ['601', '605', '612', '626']

    for regime in valid_regimes:
        try:
            validator(regime)
            print(f"  ✓ Regime {regime} is valid")
        except ValidationError:
            assert False, f"Regime {regime} should be valid"

    # Invalid regimes
    invalid_regimes = ['000', '999', 'ABC']

    for regime in invalid_regimes:
        try:
            validator(regime)
            assert False, f"Regime {regime} should be invalid"
        except ValidationError:
            print(f"  ✓ Regime {regime} correctly rejected")

    print("FiscalRegimeValidator: PASSED\n")


if __name__ == '__main__':
    print("=" * 50)
    print("Running Validator Unit Tests")
    print("=" * 50 + "\n")

    try:
        test_phone_validator()
        test_rfc_validator()
        test_postal_code_validator()
        test_fiscal_regime_validator()

        print("=" * 50)
        print("ALL TESTS PASSED ✅")
        print("=" * 50)
        sys.exit(0)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)