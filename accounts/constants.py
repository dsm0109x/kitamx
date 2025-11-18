"""
Constants for accounts app.

Centralizes all constants, choices, and configuration values
to avoid duplication and improve maintainability.
"""
from typing import Final
from django.utils.translation import gettext_lazy as _


# User Model Constants
class UserConstants:
    """Constants for User model."""

    # Field max lengths
    EMAIL_MAX_LENGTH: Final[int] = 254
    NAME_MAX_LENGTH: Final[int] = 150
    PHONE_MAX_LENGTH: Final[int] = 20
    USERNAME_MAX_LENGTH: Final[int] = 150

    # Onboarding steps
    ONBOARDING_STEPS: Final[list] = [
        (1, _('Identidad del Negocio')),
        (2, _('Conectar MercadoPago')),
        (3, _('Datos Fiscales y CSD')),
        (4, _('Suscripción')),
    ]

    ONBOARDING_STEP_BUSINESS: Final[int] = 1
    ONBOARDING_STEP_MERCADOPAGO: Final[int] = 2
    ONBOARDING_STEP_FISCAL: Final[int] = 3
    ONBOARDING_STEP_SUBSCRIPTION: Final[int] = 4
    ONBOARDING_COMPLETED: Final[int] = 4


# Profile Model Constants
class ProfileConstants:
    """Constants for UserProfile model."""

    # Field max lengths
    BIO_MAX_LENGTH: Final[int] = 500
    LOCATION_MAX_LENGTH: Final[int] = 100
    TIMEZONE_MAX_LENGTH: Final[int] = 50
    LANGUAGE_MAX_LENGTH: Final[int] = 10
    THEME_MAX_LENGTH: Final[int] = 10

    # Timezone choices for Mexico
    TIMEZONE_CHOICES: Final[list] = [
        ('America/Mexico_City', _('Ciudad de México (GMT-6)')),
        ('America/Tijuana', _('Tijuana (GMT-8)')),
        ('America/Monterrey', _('Monterrey (GMT-6)')),
        ('America/Cancun', _('Cancún (GMT-5)')),
        ('America/Hermosillo', _('Hermosillo (GMT-7)')),
        ('America/Mazatlan', _('Mazatlán (GMT-7)')),
        ('America/Chihuahua', _('Chihuahua (GMT-6)')),
        ('America/Merida', _('Mérida (GMT-6)')),
    ]

    DEFAULT_TIMEZONE: Final[str] = 'America/Mexico_City'

    # Language choices
    LANGUAGE_CHOICES: Final[list] = [
        ('es', _('Español')),
        ('en', _('English')),
    ]

    DEFAULT_LANGUAGE: Final[str] = 'es'

    # Theme choices
    THEME_CHOICES: Final[list] = [
        ('light', _('Claro')),
        ('dark', _('Oscuro')),
        ('auto', _('Automático')),
    ]

    DEFAULT_THEME: Final[str] = 'auto'


# Session Model Constants
class SessionConstants:
    """Constants for UserSession model."""

    # Field max lengths
    SESSION_KEY_MAX_LENGTH: Final[int] = 40
    COUNTRY_MAX_LENGTH: Final[int] = 100
    CITY_MAX_LENGTH: Final[int] = 100
    DEVICE_TYPE_MAX_LENGTH: Final[int] = 20
    BROWSER_MAX_LENGTH: Final[int] = 50

    # Session timeout (in seconds)
    SESSION_TIMEOUT_SECONDS: Final[int] = 86400  # 24 hours
    SESSION_IDLE_TIMEOUT_SECONDS: Final[int] = 3600  # 1 hour

    # Device type choices
    DEVICE_TYPES: Final[list] = [
        ('desktop', _('Escritorio')),
        ('mobile', _('Móvil')),
        ('tablet', _('Tableta')),
        ('unknown', _('Desconocido')),
    ]

    DEFAULT_DEVICE_TYPE: Final[str] = 'unknown'

    # Max concurrent sessions per user
    MAX_CONCURRENT_SESSIONS: Final[int] = 5


# Rate Limiting Constants
class RateLimitConstants:
    """Constants for rate limiting."""

    # Authentication limits
    LOGIN_RATE_LIMIT: Final[str] = '5/5m'  # 5 attempts per 5 minutes
    PASSWORD_CHANGE_RATE_LIMIT: Final[str] = '3/10m'  # 3 attempts per 10 minutes
    PASSWORD_RESET_RATE_LIMIT: Final[str] = '3/h'  # 3 attempts per hour

    # Profile update limits
    PROFILE_UPDATE_RATE_LIMIT: Final[str] = '10/h'  # 10 updates per hour
    BUSINESS_UPDATE_RATE_LIMIT: Final[str] = '5/h'  # 5 updates per hour

    # Security action limits
    SESSION_REVOKE_RATE_LIMIT: Final[str] = '10/h'  # 10 revocations per hour
    CSD_DEACTIVATE_RATE_LIMIT: Final[str] = '5/h'  # 5 deactivations per hour

    # API limits
    API_DEFAULT_RATE_LIMIT: Final[str] = '100/h'  # 100 requests per hour
    API_BURST_RATE_LIMIT: Final[str] = '20/m'  # 20 requests per minute


# Cache Constants
class CacheConstants:
    """Constants for caching strategies."""

    # Cache key prefixes
    USER_PROFILE_PREFIX: Final[str] = 'user:profile:'
    TENANT_USER_PREFIX: Final[str] = 'tenant:user:'
    USER_TENANTS_PREFIX: Final[str] = 'user:tenants:'
    USER_PERMISSIONS_PREFIX: Final[str] = 'user:permissions:'
    SESSION_FINGERPRINT_PREFIX: Final[str] = 'session:fingerprint:'
    RATE_LIMIT_PREFIX: Final[str] = 'ratelimit:'

    # Cache timeouts (in seconds)
    USER_PROFILE_TIMEOUT: Final[int] = 300  # 5 minutes
    TENANT_USER_TIMEOUT: Final[int] = 600  # 10 minutes
    USER_TENANTS_TIMEOUT: Final[int] = 300  # 5 minutes
    USER_PERMISSIONS_TIMEOUT: Final[int] = 600  # 10 minutes
    SESSION_FINGERPRINT_TIMEOUT: Final[int] = 3600  # 1 hour
    RATE_LIMIT_TIMEOUT: Final[int] = 3600  # 1 hour

    # Cache versions (for invalidation)
    CACHE_VERSION: Final[int] = 1


# Security Constants
class SecurityConstants:
    """Constants for security features."""

    # Password requirements
    MIN_PASSWORD_LENGTH: Final[int] = 8
    PASSWORD_REQUIRE_UPPERCASE: Final[bool] = True
    PASSWORD_REQUIRE_LOWERCASE: Final[bool] = True
    PASSWORD_REQUIRE_NUMBERS: Final[bool] = True
    PASSWORD_REQUIRE_SPECIAL: Final[bool] = False

    # Session security
    SESSION_COOKIE_AGE: Final[int] = 86400  # 24 hours
    SESSION_COOKIE_HTTPONLY: Final[bool] = True
    SESSION_COOKIE_SECURE: Final[bool] = True  # HTTPS only in production
    SESSION_COOKIE_SAMESITE: Final[str] = 'Lax'

    # CSRF settings
    CSRF_COOKIE_AGE: Final[int] = 31449600  # 1 year
    CSRF_COOKIE_HTTPONLY: Final[bool] = False  # Must be readable by JS
    CSRF_COOKIE_SECURE: Final[bool] = True  # HTTPS only in production
    CSRF_COOKIE_SAMESITE: Final[str] = 'Strict'

    # Account security
    EMAIL_VERIFICATION_DAYS: Final[int] = 3
    PASSWORD_RESET_TIMEOUT_DAYS: Final[int] = 1
    ACCOUNT_LOCKOUT_ATTEMPTS: Final[int] = 5
    ACCOUNT_LOCKOUT_DURATION_MINUTES: Final[int] = 30

    # IP tracking
    MAX_IPS_PER_USER: Final[int] = 20  # Max unique IPs to track
    SUSPICIOUS_IP_THRESHOLD: Final[int] = 10  # IPs in 1 hour = suspicious


# Validation Constants
class ValidationConstants:
    """Constants for validation."""

    # Phone validation
    PHONE_MIN_LENGTH: Final[int] = 10
    PHONE_MAX_LENGTH: Final[int] = 15
    DEFAULT_COUNTRY_CODE: Final[str] = '52'  # Mexico

    # RFC validation
    RFC_FISICA_LENGTH: Final[int] = 13
    RFC_MORAL_LENGTH: Final[int] = 12
    RFC_INVALID_PATTERNS: Final[list] = [
        'XAXX010101000',  # Generic RFC
        'XEXX010101000',  # Foreign RFC
        'XXXX000000000',  # Test RFC
        'AAAA000000AAA',  # Invalid pattern
    ]

    # Postal code validation
    POSTAL_CODE_LENGTH: Final[int] = 5
    POSTAL_CODE_MIN: Final[int] = 1000
    POSTAL_CODE_MAX: Final[int] = 99999

    # Email validation
    EMAIL_MAX_LENGTH: Final[int] = 254
    DISPOSABLE_EMAIL_DOMAINS: Final[set] = {
        'guerrillamail.com',
        '10minutemail.com',
        'tempmail.com',
        'throwaway.email',
        'mailinator.com',
        'yopmail.com',
        'temp-mail.org',
        'maildrop.cc',
    }


# Audit Constants
class AuditConstants:
    """Constants for audit logging."""

    # Action types
    ACTION_CREATE: Final[str] = 'create'
    ACTION_UPDATE: Final[str] = 'update'
    ACTION_DELETE: Final[str] = 'delete'
    ACTION_VIEW: Final[str] = 'view'
    ACTION_LOGIN: Final[str] = 'login'
    ACTION_LOGOUT: Final[str] = 'logout'
    ACTION_LOGIN_FAILED: Final[str] = 'login_failed'
    ACTION_PASSWORD_CHANGE: Final[str] = 'password_change'
    ACTION_PASSWORD_RESET: Final[str] = 'password_reset'
    ACTION_EMAIL_VERIFIED: Final[str] = 'email_verified'
    ACTION_PERMISSION_DENIED: Final[str] = 'permission_denied'
    ACTION_RATE_LIMITED: Final[str] = 'rate_limited'

    # Entity types
    ENTITY_USER: Final[str] = 'User'
    ENTITY_PROFILE: Final[str] = 'UserProfile'
    ENTITY_SESSION: Final[str] = 'UserSession'
    ENTITY_TENANT: Final[str] = 'Tenant'
    ENTITY_TENANT_USER: Final[str] = 'TenantUser'
    ENTITY_CSD: Final[str] = 'CSDCertificate'

    # Retention
    AUDIT_LOG_RETENTION_DAYS: Final[int] = 90  # 3 months


# Notification Constants
class NotificationConstants:
    """Constants for notifications."""

    # Channels
    CHANNEL_EMAIL: Final[str] = 'email'
    CHANNEL_SMS: Final[str] = 'sms'
    CHANNEL_WHATSAPP: Final[str] = 'whatsapp'
    CHANNEL_PUSH: Final[str] = 'push'

    DEFAULT_CHANNEL: Final[str] = 'whatsapp'

    # Templates
    TEMPLATE_WELCOME: Final[str] = 'welcome'
    TEMPLATE_EMAIL_VERIFICATION: Final[str] = 'email_verification'
    TEMPLATE_PASSWORD_RESET: Final[str] = 'password_reset'
    TEMPLATE_PASSWORD_CHANGED: Final[str] = 'password_changed'
    TEMPLATE_LOGIN_ALERT: Final[str] = 'login_alert'
    TEMPLATE_SUBSCRIPTION_REMINDER: Final[str] = 'subscription_reminder'


# Error Messages
class ErrorMessages:
    """Centralized error messages for consistency."""

    # Authentication
    INVALID_CREDENTIALS: Final[str] = _('Email o contraseña incorrectos')
    ACCOUNT_LOCKED: Final[str] = _('Cuenta bloqueada temporalmente por seguridad')
    EMAIL_NOT_VERIFIED: Final[str] = _('Por favor verifica tu email primero')
    SESSION_EXPIRED: Final[str] = _('Tu sesión ha expirado')

    # Permissions
    PERMISSION_DENIED: Final[str] = _('No tienes permiso para realizar esta acción')
    TENANT_REQUIRED: Final[str] = _('Debes pertenecer a una empresa')
    OWNER_REQUIRED: Final[str] = _('Solo el propietario puede realizar esta acción')
    SUBSCRIPTION_REQUIRED: Final[str] = _('Suscripción activa requerida')

    # Validation
    INVALID_PHONE: Final[str] = _('Formato de teléfono inválido')
    INVALID_RFC: Final[str] = _('RFC inválido')
    INVALID_POSTAL_CODE: Final[str] = _('Código postal inválido')
    INVALID_EMAIL: Final[str] = _('Email inválido')
    DISPOSABLE_EMAIL: Final[str] = _('Emails temporales no están permitidos')

    # Rate limiting
    RATE_LIMIT_EXCEEDED: Final[str] = _('Demasiados intentos. Intenta más tarde')

    # Generic
    GENERIC_ERROR: Final[str] = _('Ocurrió un error. Intenta nuevamente')
    FIELD_REQUIRED: Final[str] = _('Este campo es requerido')
    INVALID_DATA: Final[str] = _('Datos inválidos')


# Success Messages
class SuccessMessages:
    """Centralized success messages for consistency."""

    # Profile
    PROFILE_UPDATED: Final[str] = _('Perfil actualizado correctamente')
    BUSINESS_INFO_UPDATED: Final[str] = _('Información fiscal actualizada')

    # Security
    PASSWORD_CHANGED: Final[str] = _('Contraseña actualizada correctamente')
    SESSION_REVOKED: Final[str] = _('Sesión revocada correctamente')
    EMAIL_VERIFIED: Final[str] = _('Email verificado exitosamente')

    # CSD
    CSD_UPLOADED: Final[str] = _('Certificado CSD cargado correctamente')
    CSD_DEACTIVATED: Final[str] = _('Certificado desactivado correctamente')


# Export all constants for easy import
__all__ = [
    'UserConstants',
    'ProfileConstants',
    'SessionConstants',
    'RateLimitConstants',
    'CacheConstants',
    'SecurityConstants',
    'ValidationConstants',
    'AuditConstants',
    'NotificationConstants',
    'ErrorMessages',
    'SuccessMessages',
]