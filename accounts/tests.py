"""
Test suite for accounts app.

This module imports all test cases for easier discovery by Django's test runner.
Usage: python manage.py test accounts
"""

# Import all test cases for Django test discovery
from .test_models import (
    UserModelTestCase,
    UserProfileModelTestCase,
    UserSessionModelTestCase,
    UserManagerTestCase,
)

from .test_validators import (
    E164PhoneValidatorTestCase,
    RFCValidatorTestCase,
    PostalCodeValidatorTestCase,
    FiscalRegimeValidatorTestCase,
    SecureEmailValidatorTestCase,
)

from .test_cache import (
    CacheManagerTestCase,
    UserCacheTestCase,
    TenantCacheTestCase,
    CachedCounterTestCase,
    SessionCacheTestCase,
    CachedMethodDecoratorTestCase,
    WarmCacheTestCase,
)

# Re-export for convenience
__all__ = [
    # Model tests
    'UserModelTestCase',
    'UserProfileModelTestCase',
    'UserSessionModelTestCase',
    'UserManagerTestCase',
    # Validator tests
    'E164PhoneValidatorTestCase',
    'RFCValidatorTestCase',
    'PostalCodeValidatorTestCase',
    'FiscalRegimeValidatorTestCase',
    'SecureEmailValidatorTestCase',
    # Cache tests
    'CacheManagerTestCase',
    'UserCacheTestCase',
    'TenantCacheTestCase',
    'CachedCounterTestCase',
    'SessionCacheTestCase',
    'CachedMethodDecoratorTestCase',
    'WarmCacheTestCase',
]