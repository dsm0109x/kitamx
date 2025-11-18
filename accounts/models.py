"""
Optimized User models for accounts app.

This module contains the User, UserProfile, and UserSession models
with performance optimizations, proper indexing, and caching.
"""
from __future__ import annotations
import uuid
from typing import Optional, TYPE_CHECKING
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import QuerySet, Prefetch, F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from core.models import Tenant, TenantUser

from .managers import UserManager
from .constants import (
    UserConstants,
    ProfileConstants,
    SessionConstants,
)
from .cache import UserCache, cached_method, CacheManager


class User(AbstractUser):
    """
    Custom User model with optimized queries and caching.

    Uses email as primary authentication field with proper indexes
    for common query patterns.
    """

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the user"
    )

    # Authentication fields with indexes
    email = models.EmailField(
        _('email address'),
        unique=True,
        db_index=True,
        max_length=UserConstants.EMAIL_MAX_LENGTH,
        help_text="Primary email for authentication and notifications"
    )

    # Personal info
    first_name = models.CharField(
        _('first name'),
        max_length=UserConstants.NAME_MAX_LENGTH,
        db_index=True,  # Index for search
        help_text="User's first name"
    )
    last_name = models.CharField(
        _('last name'),
        max_length=UserConstants.NAME_MAX_LENGTH,
        db_index=True,  # Index for search
        help_text="User's last name"
    )

    # Override username to be optional
    username = models.CharField(
        max_length=UserConstants.USERNAME_MAX_LENGTH,
        blank=True,
        null=True,
        unique=False,
        help_text="Legacy field, not used for auth"
    )

    # Phone with validation
    phone_validator = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone must be in E.164 format: '+999999999'"
    )
    phone = models.CharField(
        max_length=UserConstants.PHONE_MAX_LENGTH,
        blank=True,
        validators=[phone_validator],
        help_text="Phone in E.164 format for WhatsApp"
    )

    # Email verification
    is_email_verified = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether email has been verified"
    )
    email_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of email verification"
    )

    # Onboarding status
    onboarding_completed = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether user completed onboarding"
    )
    onboarding_step = models.PositiveSmallIntegerField(
        default=UserConstants.ONBOARDING_STEP_BUSINESS,
        choices=UserConstants.ONBOARDING_STEPS,
        help_text="Current step in onboarding flow"
    )

    # Legal compliance
    terms_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user accepted terms"
    )
    privacy_accepted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When user accepted privacy policy"
    )

    # Marketing
    accepts_marketing = models.BooleanField(
        default=False,
        db_index=True,  # Index for marketing campaigns
        help_text="Opted in for marketing"
    )

    # Django auth configuration
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()

    class Meta:
        db_table = 'users'
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        indexes = [
            # Composite index for login queries
            models.Index(fields=['email', 'is_active'], name='idx_user_email_active'),
            # Composite index for onboarding queries
            models.Index(fields=['onboarding_completed', '-date_joined'], name='idx_user_onboard_date'),
            # Index for marketing queries
            models.Index(fields=['accepts_marketing', 'is_active'], name='idx_user_marketing'),
            # Index for verification queries
            models.Index(fields=['is_email_verified', '-date_joined'], name='idx_user_verified'),
        ]

    def __str__(self) -> str:
        """Return user's display name."""
        return self.get_full_name() or self.email

    @property
    def full_name(self) -> str:
        """Get user's full name, cached."""
        return f"{self.first_name} {self.last_name}".strip()

    def get_full_name(self) -> str:
        """Django compatibility method."""
        return self.full_name

    def get_short_name(self) -> str:
        """Django compatibility method."""
        return self.first_name

    @cached_method(timeout=300, vary_on=['tenant_id'])
    def get_tenant_user(self, tenant_id: uuid.UUID) -> Optional['TenantUser']:
        """
        Get TenantUser relationship with caching.

        Args:
            tenant_id: Tenant UUID

        Returns:
            TenantUser instance or None
        """
        from core.models import TenantUser

        # Try cache first
        from .cache import TenantCache
        cached = TenantCache.get_tenant_user(self.email, str(tenant_id))
        if cached:
            return TenantUser(**cached)

        # Query with optimization
        tenant_user = TenantUser.objects.filter(
            tenant_id=tenant_id,
            email=self.email
        ).select_related('tenant').first()

        # Cache result
        if tenant_user:
            TenantCache.set_tenant_user(
                self.email,
                str(tenant_id),
                {
                    'id': str(tenant_user.id),
                    'is_owner': tenant_user.is_owner,
                    'role': tenant_user.role,
                    'is_active': tenant_user.is_active,
                }
            )

        return tenant_user

    def get_tenants(self) -> QuerySet['Tenant']:
        """
        Get all tenants for user with optimized query.

        Returns:
            QuerySet of Tenant objects
        """
        from core.models import Tenant

        # Check cache first
        cached = UserCache.get_tenants(self.email)
        if cached:
            # Return tenant IDs for further filtering if needed
            tenant_ids = [t['id'] for t in cached]
            return Tenant.objects.filter(id__in=tenant_ids)

        # Optimized query avoiding N+1
        tenants = Tenant.objects.filter(
            users__email=self.email,
            is_active=True
        ).select_related(
            'subscription'  # Prefetch subscription to avoid N+1
        ).prefetch_related(
            Prefetch(
                'users',
                queryset=TenantUser.objects.filter(email=self.email),
                to_attr='my_tenant_user'
            )
        ).distinct()

        # Cache the result
        tenant_list = [
            {
                'id': str(t.id),
                'name': t.name,
                'slug': t.slug,
                'is_owner': t.my_tenant_user[0].is_owner if t.my_tenant_user else False,
                'role': t.my_tenant_user[0].role if t.my_tenant_user else 'user',
            }
            for t in tenants
        ]
        UserCache.set_tenants(self.email, tenant_list)

        return tenants

    def get_owned_tenants(self) -> QuerySet['Tenant']:
        """
        Get tenants where user is owner, optimized.

        Returns:
            QuerySet of owned Tenants
        """
        from core.models import Tenant

        return Tenant.objects.filter(
            users__email=self.email,
            users__is_owner=True,
            is_active=True
        ).select_related('subscription').distinct()

    def has_tenant_access(self, tenant_id: uuid.UUID) -> bool:
        """
        Check if user has access to tenant (cached).

        Args:
            tenant_id: Tenant UUID

        Returns:
            True if user has access
        """
        tenant_user = self.get_tenant_user(tenant_id)
        return tenant_user is not None and tenant_user.is_active

    @transaction.atomic
    def mark_email_verified(self) -> None:
        """Mark email as verified with proper update."""
        self.is_email_verified = True
        self.email_verified_at = timezone.now()
        self.save(update_fields=['is_email_verified', 'email_verified_at'])

        # Invalidate cache
        CacheManager.invalidate_user_cache(self.id)

    @transaction.atomic
    def accept_terms_and_privacy(self) -> None:
        """Record terms and privacy acceptance."""
        now = timezone.now()
        self.terms_accepted_at = now
        self.privacy_accepted_at = now
        self.save(update_fields=['terms_accepted_at', 'privacy_accepted_at'])

    @transaction.atomic
    def advance_onboarding(self, step: int) -> bool:
        """
        Advance onboarding step with validation.

        Args:
            step: Step number to advance to

        Returns:
            True if advanced successfully
        """
        if step <= self.onboarding_step:
            return False

        self.onboarding_step = step
        if step >= UserConstants.ONBOARDING_COMPLETED:
            self.onboarding_completed = True

        self.save(update_fields=['onboarding_step', 'onboarding_completed'])

        # Invalidate cache
        CacheManager.invalidate_user_cache(self.id)
        return True

    def get_active_sessions_count(self) -> int:
        """
        Get count of active sessions (cached).

        Returns:
            Number of active sessions
        """
        from .cache import SessionCache
        return SessionCache.get_active_sessions_count(self.id)


class UserProfile(models.Model):
    """
    Extended user profile with optimized fields and caching.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )

    # Profile information
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/',
        null=True,
        blank=True,
        help_text="User avatar image"
    )
    bio = models.TextField(
        max_length=ProfileConstants.BIO_MAX_LENGTH,
        blank=True,
        help_text="Short biography"
    )
    location = models.CharField(
        max_length=ProfileConstants.LOCATION_MAX_LENGTH,
        blank=True,
        db_index=True,  # Index for location-based features
        help_text="User location"
    )
    website = models.URLField(
        blank=True,
        help_text="Personal website"
    )

    # Localization
    timezone = models.CharField(
        max_length=ProfileConstants.TIMEZONE_MAX_LENGTH,
        choices=ProfileConstants.TIMEZONE_CHOICES,
        default=ProfileConstants.DEFAULT_TIMEZONE,
        db_index=True,  # Index for timezone-based queries
        help_text="Preferred timezone"
    )
    language = models.CharField(
        max_length=ProfileConstants.LANGUAGE_MAX_LENGTH,
        choices=ProfileConstants.LANGUAGE_CHOICES,
        default=ProfileConstants.DEFAULT_LANGUAGE,
        help_text="Preferred language"
    )
    theme = models.CharField(
        max_length=ProfileConstants.THEME_MAX_LENGTH,
        choices=ProfileConstants.THEME_CHOICES,
        default=ProfileConstants.DEFAULT_THEME,
        help_text="UI theme preference"
    )

    # Notification preferences
    email_notifications = models.BooleanField(
        default=True,
        help_text="Receive email notifications"
    )
    push_notifications = models.BooleanField(
        default=True,
        help_text="Receive push notifications"
    )
    sms_notifications = models.BooleanField(
        default=False,
        help_text="Receive SMS notifications"
    )
    whatsapp_notifications = models.BooleanField(
        default=True,
        help_text="Receive WhatsApp notifications"
    )

    # Activity tracking
    last_activity = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Last recorded activity"
    )
    login_count = models.PositiveIntegerField(
        default=0,
        help_text="Total logins"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'user_profiles'
        verbose_name = _('User Profile')
        verbose_name_plural = _('User Profiles')
        indexes = [
            # Index for activity queries
            models.Index(fields=['-last_activity'], name='idx_profile_activity'),
            # Index for timezone-based notifications
            models.Index(fields=['timezone', 'email_notifications'], name='idx_profile_tz_email'),
        ]

    def __str__(self) -> str:
        return f"Profile for {self.user.email}"

    @transaction.atomic
    def increment_login_count(self) -> None:
        """Increment login counter efficiently."""
        # Use F() expression for atomic update
        self.login_count = F('login_count') + 1
        self.save(update_fields=['login_count', 'last_activity'])

        # Refresh from DB to get actual value
        self.refresh_from_db(fields=['login_count'])

    def get_notification_preferences(self) -> dict:
        """
        Get notification preferences as dict.

        Returns:
            Dictionary of notification settings
        """
        return {
            'email': self.email_notifications,
            'push': self.push_notifications,
            'sms': self.sms_notifications,
            'whatsapp': self.whatsapp_notifications,
        }


class UserSession(models.Model):
    """
    User session tracking with optimized queries and auto-cleanup.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        db_index=True  # Ensure index on FK
    )

    # Session identification
    session_key = models.CharField(
        max_length=SessionConstants.SESSION_KEY_MAX_LENGTH,
        unique=True,
        db_index=True,
        help_text="Django session key"
    )

    # Device/Network info
    ip_address = models.GenericIPAddressField(
        db_index=True,  # Index for security queries
        help_text="Client IP address"
    )
    user_agent = models.TextField(
        help_text="Browser user agent"
    )

    # Parsed device info
    device_type = models.CharField(
        max_length=SessionConstants.DEVICE_TYPE_MAX_LENGTH,
        choices=SessionConstants.DEVICE_TYPES,
        default=SessionConstants.DEFAULT_DEVICE_TYPE,
        help_text="Type of device"
    )
    browser = models.CharField(
        max_length=SessionConstants.BROWSER_MAX_LENGTH,
        blank=True,
        help_text="Browser name"
    )

    # Geolocation
    country = models.CharField(
        max_length=SessionConstants.COUNTRY_MAX_LENGTH,
        blank=True,
        db_index=True,
        help_text="Country from IP"
    )
    city = models.CharField(
        max_length=SessionConstants.CITY_MAX_LENGTH,
        blank=True,
        help_text="City from IP"
    )

    # Lifecycle
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        db_index=True
    )
    expires_at = models.DateTimeField(
        db_index=True,
        help_text="Session expiration"
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Session validity"
    )

    class Meta:
        db_table = 'user_sessions'
        verbose_name = _('User Session')
        verbose_name_plural = _('User Sessions')
        ordering = ['-last_activity']
        indexes = [
            # Composite index for user's active sessions
            models.Index(
                fields=['user', 'is_active', '-last_activity'],
                name='idx_session_user_active'
            ),
            # Index for cleanup queries
            models.Index(
                fields=['expires_at', 'is_active'],
                name='idx_session_expires'
            ),
            # Index for security monitoring
            models.Index(
                fields=['ip_address', 'created_at'],
                name='idx_session_ip_created'
            ),
        ]

    def __str__(self) -> str:
        return f"Session for {self.user.email} from {self.ip_address}"

    def is_expired(self) -> bool:
        """Check if session expired."""
        return timezone.now() > self.expires_at

    @transaction.atomic
    def deactivate(self) -> None:
        """Deactivate session safely."""
        self.is_active = False
        self.save(update_fields=['is_active'])

        # Invalidate session count cache
        from .cache import SessionCache
        SessionCache.invalidate_session_count(self.user_id)

    @classmethod
    def cleanup_expired(cls) -> int:
        """
        Cleanup expired sessions efficiently.

        Returns:
            Number of sessions deactivated
        """
        now = timezone.now()
        expired = cls.objects.filter(
            Q(expires_at__lt=now) | Q(is_active=False),
            created_at__lt=now - timezone.timedelta(days=30)
        )
        count = expired.count()
        expired.delete()  # Hard delete old inactive sessions
        return count

    @classmethod
    def get_active_for_user(cls, user: User) -> QuerySet['UserSession']:
        """
        Get active sessions for user, optimized.

        Args:
            user: User instance

        Returns:
            QuerySet of active sessions
        """
        return cls.objects.filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).only(
            'id', 'session_key', 'ip_address', 'country',
            'city', 'device_type', 'created_at', 'last_activity'
        )

    @classmethod
    def limit_concurrent_sessions(cls, user: User, max_sessions: int = 5) -> None:
        """
        Limit concurrent sessions per user.

        Args:
            user: User instance
            max_sessions: Maximum allowed sessions
        """
        active_sessions = cls.objects.filter(
            user=user,
            is_active=True
        ).order_by('-created_at')

        if active_sessions.count() > max_sessions:
            # Deactivate oldest sessions
            for session in active_sessions[max_sessions:]:
                session.deactivate()