"""
Optimized User manager for accounts app.

Provides efficient query methods and user creation with proper validation.
"""
from __future__ import annotations
from typing import Optional, Any
from django.contrib.auth.models import BaseUserManager
from django.db import transaction
from django.db.models import QuerySet, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)


class UserQuerySet(QuerySet):
    """
    Custom QuerySet for User model with optimized methods.
    """

    def active(self) -> QuerySet:
        """Get only active users."""
        return self.filter(is_active=True)

    def verified(self) -> QuerySet:
        """Get only email-verified users."""
        return self.filter(is_email_verified=True)

    def active_verified(self) -> QuerySet:
        """Get active AND verified users (common query)."""
        return self.filter(
            is_active=True,
            is_email_verified=True
        )

    def onboarded(self) -> QuerySet:
        """Get users who completed onboarding."""
        return self.filter(onboarding_completed=True)

    def not_onboarded(self) -> QuerySet:
        """Get users who haven't completed onboarding."""
        return self.filter(onboarding_completed=False)

    def marketing_enabled(self) -> QuerySet:
        """Get users who accept marketing (for campaigns)."""
        return self.filter(
            accepts_marketing=True,
            is_active=True,
            is_email_verified=True
        )

    def search(self, query: str) -> QuerySet:
        """
        Search users by email, name, or phone.

        Args:
            query: Search string

        Returns:
            Filtered QuerySet
        """
        if not query:
            return self.none()

        # Clean the query
        query = query.strip()

        # Build search conditions
        conditions = Q(email__icontains=query)
        conditions |= Q(first_name__icontains=query)
        conditions |= Q(last_name__icontains=query)

        # Check if it might be a phone number
        if query.replace('+', '').replace('-', '').replace(' ', '').isdigit():
            conditions |= Q(phone__icontains=query)

        return self.filter(conditions).distinct()

    def with_profile(self) -> QuerySet:
        """Prefetch user profile for efficiency."""
        return self.select_related('profile')

    def with_tenants(self) -> QuerySet:
        """Prefetch user's tenants."""
        return self.prefetch_related(
            'tenantuser_set__tenant'
        )

    def by_tenant(self, tenant_id: Any) -> QuerySet:
        """
        Get users belonging to a specific tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Users in that tenant
        """
        from core.models import TenantUser
        tenant_emails = TenantUser.objects.filter(
            tenant_id=tenant_id
        ).values_list('email', flat=True)

        return self.filter(email__in=tenant_emails)

    def recent(self, days: int = 30) -> QuerySet:
        """
        Get recently created users.

        Args:
            days: Number of days to look back

        Returns:
            Recent users
        """
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(date_joined__gte=cutoff)


class UserManager(BaseUserManager):
    """
    Optimized user manager with efficient user creation and queries.
    """

    def get_queryset(self) -> UserQuerySet:
        """Return custom QuerySet."""
        return UserQuerySet(self.model, using=self._db)

    def active(self) -> QuerySet:
        """Shortcut for active users."""
        return self.get_queryset().active()

    def verified(self) -> QuerySet:
        """Shortcut for verified users."""
        return self.get_queryset().verified()

    @transaction.atomic
    def create_user(
        self,
        email: str,
        password: Optional[str] = None,
        **extra_fields: Any
    ) -> Any:
        """
        Create and save a regular User with optimized profile creation.

        Args:
            email: User's email address
            password: User's password
            **extra_fields: Additional user fields

        Returns:
            Created user instance

        Raises:
            ValueError: If email is not provided
        """
        if not email:
            raise ValueError(_('Email address is required'))

        # Normalize email
        email = self.normalize_email(email)

        # Check for duplicate in a case-insensitive way
        if self.model.objects.filter(email__iexact=email).exists():
            raise ValueError(_('A user with this email already exists'))

        # Set defaults
        extra_fields.setdefault('first_name', '')
        extra_fields.setdefault('last_name', '')
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        # Don't set username - let it be null
        extra_fields['username'] = None

        # Create user
        user = self.model(email=email, **extra_fields)

        # Set password
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        # Save user
        user.save(using=self._db)

        # Create profile automatically
        from .models import UserProfile
        UserProfile.objects.create(user=user)

        # Log creation
        logger.info(f"Created new user: {email}")

        # Warm cache for new user
        from .cache import warm_cache_for_user
        warm_cache_for_user(user.id, user.email)

        return user

    @transaction.atomic
    def create_superuser(
        self,
        email: str,
        password: str,
        **extra_fields: Any
    ) -> Any:
        """
        Create and save a SuperUser with all permissions.

        Args:
            email: Superuser's email
            password: Superuser's password
            **extra_fields: Additional fields

        Returns:
            Created superuser instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Set superuser flags
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_email_verified', True)
        extra_fields.setdefault('onboarding_completed', True)

        # Validate flags
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True'))

        # Password is required for superuser
        if not password:
            raise ValueError(_('Superuser must have a password'))

        # Create the superuser
        user = self.create_user(email, password, **extra_fields)

        # Mark email as verified
        user.email_verified_at = timezone.now()
        user.save(update_fields=['email_verified_at'])

        logger.info(f"Created new superuser: {email}")

        return user

    def get_by_natural_key(self, email: str) -> Any:
        """
        Get user by email (natural key).

        Args:
            email: User's email

        Returns:
            User instance

        Note:
            Used by Django's authentication system
        """
        # Case-insensitive lookup with optimization
        return self.get_queryset().select_related('profile').get(
            email__iexact=email
        )

    def active_in_tenant(self, tenant_id: Any) -> QuerySet:
        """
        Get active users in a specific tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            QuerySet of active users in tenant
        """
        return self.get_queryset().by_tenant(tenant_id).active()

    def search_users(
        self,
        query: str,
        tenant_id: Optional[Any] = None,
        active_only: bool = True
    ) -> QuerySet:
        """
        Advanced user search with filters.

        Args:
            query: Search string
            tenant_id: Optional tenant filter
            active_only: Only return active users

        Returns:
            Filtered QuerySet
        """
        qs = self.get_queryset().search(query)

        if active_only:
            qs = qs.active()

        if tenant_id:
            qs = qs.by_tenant(tenant_id)

        # Optimize with select_related
        return qs.select_related('profile')

    def bulk_create_users(
        self,
        user_data_list: list[dict],
        tenant_id: Optional[Any] = None
    ) -> list:
        """
        Efficiently create multiple users.

        Args:
            user_data_list: List of user data dictionaries
            tenant_id: Optional tenant to add users to

        Returns:
            List of created users
        """
        created_users = []

        with transaction.atomic():
            for user_data in user_data_list:
                try:
                    email = user_data.pop('email')
                    password = user_data.pop('password', None)

                    user = self.create_user(email, password, **user_data)
                    created_users.append(user)

                    # Add to tenant if specified
                    if tenant_id:
                        from core.models import TenantUser
                        TenantUser.objects.create(
                            tenant_id=tenant_id,
                            email=user.email,
                            first_name=user.first_name,
                            last_name=user.last_name,
                            role='user'
                        )

                except Exception as e:
                    logger.error(f"Failed to create user {email}: {e}")
                    continue

        return created_users

    def get_or_create_by_email(
        self,
        email: str,
        defaults: Optional[dict] = None
    ) -> tuple:
        """
        Get or create user by email with proper defaults.

        Args:
            email: User's email
            defaults: Default values if creating

        Returns:
            Tuple of (user, created)
        """
        email = self.normalize_email(email)
        defaults = defaults or {}

        try:
            user = self.get_queryset().get(email__iexact=email)
            return user, False
        except self.model.DoesNotExist:
            return self.create_user(email, **defaults), True

    def update_last_login(self, user: Any) -> None:
        """
        Update user's last login time efficiently.

        Args:
            user: User instance
        """
        # Update only the last_login field
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])

        # Update profile login count if exists
        if hasattr(user, 'profile'):
            user.profile.increment_login_count()


# Export for convenience
__all__ = ['UserManager', 'UserQuerySet']