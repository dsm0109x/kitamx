"""Django settings for Kita project.

Production-ready configuration with environment-based settings.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Any
import environ
import ssl

# Environment
env = environ.Env(
    DEBUG=(bool, False),
)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Read environment
environ.Env.read_env(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.sitemaps',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',  # Google OAuth
    'django_eventstream',
    'storages',
    'anymail',  # Email backend with tracking
]

LOCAL_APPS = [
    'core',
    'accounts',
    'audit',
    'onboarding',
    'dashboard',
    'links',
    'kita_ia',
    'billing',
    'payments',
    'invoicing',
    'webhooks',
    'legal',
]

INSTALLED_APPS: List[str] = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Add debug_toolbar only in DEBUG mode
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.TenantMiddleware',
]

# Add debug_toolbar middleware only in DEBUG mode
if DEBUG:
    MIDDLEWARE.insert(1, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# CSP middleware temporarily disabled

ROOT_URLCONF = 'kita.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.logo_context',  # Logo selector
                'core.context_processors.seo_defaults',  # SEO metadata defaults
            ],
        },
    },
]

WSGI_APPLICATION = 'kita.wsgi.application'

# Database
DATABASES = {
    'default': {
        **env.db(),
        'CONN_MAX_AGE': 600,  # Connection pooling
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = env('TIME_ZONE', default='America/Mexico_City')
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Caching and Redis
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('VALKEY_URL'),
        'TIMEOUT': 300,  # Default timeout: 5 minutes (prevents infinite cache)
        'OPTIONS': {
            # SSL verification enabled for security
            # DigitalOcean Managed Valkey uses valid SSL certificates
        },
        'KEY_PREFIX': 'kita',  # Prevent key collisions
        'VERSION': 1,
    }
}

# Session storage
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'

# Celery Configuration with SSL settings for Valkey
CELERY_BROKER_URL = env('VALKEY_URL')
CELERY_RESULT_BACKEND = env('VALKEY_URL')

# SSL configuration for rediss:// URLs with proper verification
CELERY_REDIS_BACKEND_USE_SSL = {
    'ssl_cert_reqs': ssl.CERT_REQUIRED,  # Verify SSL certificates
    'ssl_check_hostname': True,  # Verify hostname
}
CELERY_BROKER_USE_SSL = {
    'ssl_cert_reqs': ssl.CERT_REQUIRED,  # Verify SSL certificates
    'ssl_check_hostname': True,  # Verify hostname
}
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ROUTES = {
    'invoicing.tasks.*': {'queue': 'high'},
    'payments.tasks.*': {'queue': 'high'},
    'notifications.tasks.*': {'queue': 'default'},
    'core.tasks.*': {'queue': 'low'},
}

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'reconcile-payment-links': {
        'task': 'payments.tasks.reconcile_payment_links',
        'schedule': 300.0,
        'options': {'queue': 'high'},
        'kwargs': {'hours_back': 2}
    },
    'reconcile-subscription-payments': {
        'task': 'payments.tasks.reconcile_subscription_payments',
        'schedule': 600.0,
        'options': {'queue': 'high'},
        'kwargs': {'hours_back': 4}
    },
    'generate-reconciliation-report': {
        'task': 'payments.tasks.generate_reconciliation_report',
        'schedule': 86400.0,
        'options': {'queue': 'default'}
    },
    'collect-daily-analytics': {
        'task': 'core.collect_daily_analytics',
        'schedule': crontab(hour=1, minute=0),
        'options': {'queue': 'low'}
    },
    'collect-monthly-analytics': {
        'task': 'core.collect_monthly_analytics',
        'schedule': crontab(hour=2, minute=0, day_of_month=1),
        'options': {'queue': 'low'}
    },
    'warm-tenant-caches': {
        'task': 'core.warm_tenant_caches',
        'schedule': crontab(hour='*/2', minute=0),
        'options': {'queue': 'low'}
    },
    'cleanup-old-audit-logs': {
        'task': 'core.cleanup_old_audit_logs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
        'options': {'queue': 'low'}
    },

    # Invoice automation (NEW - previously orphaned tasks)
    'process-expired-links': {
        'task': 'invoicing.tasks.process_expired_links',
        'schedule': 300.0,  # Every 5 minutes
        'options': {'queue': 'high'}
    },
    'send-payment-reminders': {
        'task': 'invoicing.tasks.send_payment_reminders',
        'schedule': crontab(hour=9, minute=0),  # Daily 9 AM
        'options': {'queue': 'default'}
    },
    'update-analytics': {
        'task': 'invoicing.tasks.update_analytics',
        'schedule': crontab(hour=1, minute=30),  # Daily 1:30 AM
        'options': {'queue': 'low'}
    },
    'cleanup-old-uploads': {
        'task': 'invoicing.tasks.cleanup_old_uploads',
        'schedule': crontab(hour=2, minute=0),  # Daily 2 AM
        'options': {'queue': 'low'}
    },
    'cleanup-orphaned-uploads': {
        'task': 'invoicing.tasks.cleanup_orphaned_uploads',
        'schedule': crontab(hour='*/6', minute=0),  # Every 6 hours
        'options': {'queue': 'low'}
    },
    'check-certificate-expiration': {
        'task': 'invoicing.tasks.check_certificate_expiration',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),  # Monday 8 AM
        'options': {'queue': 'default'}
    },

    # Healthcheck heartbeat - verifica que Celery Beat está vivo
    'healthcheck-heartbeat': {
        'task': 'core.healthcheck_heartbeat',
        'schedule': 300.0,  # Every 5 minutes
        'options': {'queue': 'low'}
    },
}

# django-allauth
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SITE_ID = 1

ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False  # ✅ No auto-login después de signup (evita session issues)
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/ingresar/'  # 🇪🇸 Migrado de /accounts/login/ → /ingresar/
LOGIN_REDIRECT_URL = '/incorporacion/'  # 🇪🇸 Migrado de /onboarding/ → /incorporacion/

# Custom forms for styling and security (Turnstile)
ACCOUNT_FORMS = {
    'signup': 'accounts.forms.KitaSignupForm',
    'login': 'accounts.forms.KitaLoginForm',
    'reset_password': 'accounts.forms.KitaResetPasswordForm',
}

# Disable allauth automatic messages to prevent duplication
ACCOUNT_SESSION_REMEMBER = None
ACCOUNT_LOGIN_ON_GET = False

# Custom adapters
ACCOUNT_ADAPTER = 'accounts.adapters.NoMessagesAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'accounts.adapters.KitaSocialAccountAdapter'

# Email confirmation settings
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
ACCOUNT_LOGOUT_ON_GET = False
ACCOUNT_UNIQUE_EMAIL = True

# Rate limiting (replaces deprecated ACCOUNT_LOGIN_ATTEMPTS_*)
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/5m',  # 5 attempts per 5 minutes
}

# Google OAuth Configuration
# SECURITY: No defaults - fail fast if missing in .env
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        # NOTE: APP config is in database (SocialApp model)
        # Configured via migration: accounts/0006_setup_google_oauth.py
        # Do NOT add 'APP' key here - causes MultipleObjectsReturned error
    }
}

# Social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True  # Auto-crear cuenta con Google
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'  # Google ya verificó el email
SOCIALACCOUNT_QUERY_EMAIL = False  # No pedir email extra
SOCIALACCOUNT_LOGIN_ON_GET = True  # ✅ Redirect directo a Google (sin pantalla intermedia)

# Email Configuration - Anymail with Postmark
EMAIL_BACKEND = 'anymail.backends.postmark.EmailBackend'
DEFAULT_FROM_EMAIL = env('EMAIL_FROM')

# Anymail Configuration
ANYMAIL = {
    'POSTMARK_SERVER_TOKEN': env('POSTMARK_TOKEN'),
}

# Postmark Webhook Configuration
POSTMARK_WEBHOOK_USERNAME = env('POSTMARK_WEBHOOK_USERNAME')
POSTMARK_WEBHOOK_PASSWORD = env('POSTMARK_WEBHOOK_PASSWORD')

# DigitalOcean Spaces configuration (force setup)
AWS_ACCESS_KEY_ID = env('DO_SPACES_KEY')
AWS_SECRET_ACCESS_KEY = env('DO_SPACES_SECRET')
AWS_STORAGE_BUCKET_NAME = env('DO_SPACES_BUCKET')
AWS_S3_ENDPOINT_URL = env('DO_SPACES_ENDPOINT')
AWS_S3_REGION_NAME = env('DO_SPACES_REGION')
AWS_DEFAULT_ACL = 'private'  # CSD files should be private
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_S3_FILE_OVERWRITE = False
AWS_S3_VERIFY = True

# Force DigitalOcean Spaces for ALL file storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Static files local in development, Spaces in production
if not DEBUG:
    STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'

# Security Configuration - Temporarily disabled for UI/UX development
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
# All other security headers disabled temporarily
# SECURE_BROWSER_XSS_FILTER = True
# SECURE_CONTENT_TYPE_NOSNIFF = True
# X_FRAME_OPTIONS = 'DENY'

# CSP Configuration - Completely disabled for development

# CSRF Configuration
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS')

# Production vs Development Settings
if not DEBUG:
    # Production security settings
    ALLOWED_HOSTS = ['kita.mx', '161.35.136.252']
    STATIC_ROOT = '/opt/staticfiles'

    # Enable security headers in production
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'

    # HSTS settings
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# django-eventstream
EVENTSTREAM_ALLOW_ORIGIN = env('EVENTSTREAM_ALLOW_ORIGIN', default='*')
EVENTSTREAM_REDIS_URL = env('EVENTSTREAM_REDIS_URL')

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Business Settings
MONTHLY_SUBSCRIPTION_PRICE: float = 299.00  # MXN including VAT
TRIAL_DAYS: int = 30
LINK_EXPIRY_OPTIONS: List[int] = [1, 3, 7]  # days

# Performance Settings
DATA_UPLOAD_MAX_MEMORY_SIZE: int = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE: int = 10485760  # 10MB
DATA_UPLOAD_MAX_NUMBER_FIELDS: int = 1000

# Cache key prefixes
CACHE_KEY_PREFIX: str = 'kita'

# Database connection pooling
CONN_MAX_AGE: int = 600  # 10 minutes

# Base URL for callbacks and webhooks
APP_BASE_URL = env('APP_BASE_URL', default='http://127.0.0.1:8000')

# Encryption Keys for CSD
MASTER_KEY_KEK_CURRENT = env('MASTER_KEY_KEK_CURRENT')
MASTER_KEY_KEK_NEXT = env('MASTER_KEY_KEK_NEXT', default='')

# Mercado Pago - Kita Account (for subscription payments)
KITA_MP_PUBLIC_KEY = env('KITA_MP_PUBLIC_KEY', default='')
KITA_MP_ACCESS_TOKEN = env('KITA_MP_ACCESS_TOKEN', default='')
KITA_MP_USER_ID = env('KITA_MP_USER_ID', default='')

# Mercado Pago OAuth App (for tenant integrations)
MERCADOPAGO_APP_ID = env('MERCADOPAGO_APP_ID', default='')
MERCADOPAGO_CLIENT_SECRET = env('MERCADOPAGO_CLIENT_SECRET', default='')

# MercadoPago API URLs (centralized to avoid hardcoding)
MERCADOPAGO_BASE_URL = 'https://api.mercadopago.com'
MERCADOPAGO_AUTH_URL = 'https://auth.mercadopago.com.mx/authorization'
MERCADOPAGO_TOKEN_URL = 'https://api.mercadopago.com/oauth/token'
MERCADOPAGO_USERS_URL = 'https://api.mercadopago.com/users'
MERCADOPAGO_PREFERENCES_URL = 'https://api.mercadopago.com/checkout/preferences'
MERCADOPAGO_PAYMENTS_URL = 'https://api.mercadopago.com/v1/payments'
MERCADOPAGO_WEBHOOK_SECRET = env('MERCADOPAGO_WEBHOOK_SECRET', default='')

# WhatsApp Cloud API
WA_TOKEN = env('WA_TOKEN', default='')
WA_PHONE_ID = env('WA_PHONE_ID', default='')
WA_BUSINESS_ID = env('WA_BUSINESS_ID', default='')

# ========================================
# PAC CONFIGURATION (Proveedor Autorizado de Certificación)
# FiscalAPI - Proveedor único de Kita
# ========================================
FISCALAPI_URL = env('FISCALAPI_URL', default='https://test.fiscalapi.com')
FISCALAPI_API_KEY = env('FISCALAPI_API_KEY', default='')
FISCALAPI_TENANT_KEY = env('FISCALAPI_TENANT_KEY', default='')
FISCALAPI_TIMEOUT = env.int('FISCALAPI_TIMEOUT', default=30)

# Cloudflare Turnstile (Anti-bot protection)
TURNSTILE_SITE_KEY = env('TURNSTILE_SITE_KEY')
TURNSTILE_SECRET_KEY = env('TURNSTILE_SECRET_KEY')
TURNSTILE_VERIFY_URL = 'https://challenges.cloudflare.com/turnstile/v0/siteverify'
TURNSTILE_TIMEOUT = 10  # seconds

# DeepInfra AI API
DEEPINFRA_API_KEY = env('DEEPINFRA_API_KEY', default='')

# Sentry
if env('SENTRY_DSN', default=''):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration

    sentry_sdk.init(
        dsn=env('SENTRY_DSN'),
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
        ],
        traces_sample_rate=env.float('SENTRY_TRACES_SAMPLE_RATE', default=0.1),
        send_default_pii=False
    )

# Debug Toolbar
if DEBUG:
    INTERNAL_IPS = [
        '127.0.0.1',
        'localhost',
    ]

# Logging configuration (avoid duplicate definition)
if DEBUG:
    LOG_LEVEL = 'DEBUG'
    LOG_FILE = BASE_DIR / 'logs' / 'kita.log'
else:
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/kita/kita.log'

LOGGING: Dict[str, Any] = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': LOG_LEVEL,
            'class': 'logging.FileHandler',
            'filename': LOG_FILE,
            'formatter': 'verbose',
        },
        'console': {
            'level': LOG_LEVEL,
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'kita': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
