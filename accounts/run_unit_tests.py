#!/usr/bin/env python
"""Standalone unit test runner for accounts validators."""
import sys
import os
import django

# Configure Django settings for testing
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kita.settings')

if __name__ == '__main__':
    django.setup()

    # Import tests after Django setup
    from accounts.test_validators import (
        E164PhoneValidatorTestCase,
        RFCValidatorTestCase,
        PostalCodeValidatorTestCase,
        FiscalRegimeValidatorTestCase,
        SecureEmailValidatorTestCase
    )

    # Run validator tests only (no DB required)
    import unittest

    suite = unittest.TestSuite()

    # Add validator tests
    for test_case in [
        E164PhoneValidatorTestCase,
        RFCValidatorTestCase,
        PostalCodeValidatorTestCase,
        FiscalRegimeValidatorTestCase,
        SecureEmailValidatorTestCase
    ]:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_case)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)