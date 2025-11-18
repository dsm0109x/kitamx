"""Tests for accounts models."""
from __future__ import annotations
from datetime import timedelta

from django.utils import timezone
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from core.test_utils import KitaTestCase
from accounts.models import User, UserProfile, UserSession


class UserModelTestCase(KitaTestCase):
    """Test cases for User model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.user_data = {
            'email': 'test@example.com',
            'password': 'TestPass123!',
            'first_name': 'Test',
            'last_name': 'User',
        }

    def test_create_user(self) -> None:
        """Test normal user creation."""
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        self.assertTrue(user.check_password('TestPass123!'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.is_email_verified)

    def test_create_superuser(self) -> None:
        """Test superuser creation."""
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            password='AdminPass123!'
        )

        self.assertTrue(superuser.is_active)
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_email_verified)
        self.assertTrue(superuser.onboarding_completed)

    def test_email_normalization(self) -> None:
        """Test email is normalized on creation."""
        user = User.objects.create_user(
            email='TEST@EXAMPLE.COM',
            password='TestPass123!'
        )
        self.assertEqual(user.email, 'TEST@example.com')

    def test_duplicate_email_prevented(self) -> None:
        """Test duplicate emails are prevented."""
        User.objects.create_user(**self.user_data)

        with self.assertRaises(ValueError):
            User.objects.create_user(**self.user_data)

    def test_email_required(self) -> None:
        """Test email is required for user creation."""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(email='', password='TestPass123!')

        self.assertIn('Email address is required', str(context.exception))

    def test_profile_created_automatically(self) -> None:
        """Test UserProfile is created automatically."""
        user = User.objects.create_user(**self.user_data)

        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, UserProfile)
        self.assertEqual(user.profile.user, user)

    def test_get_full_name(self) -> None:
        """Test full name generation."""
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.get_full_name(), 'Test User')

        # Test with empty names
        user.first_name = ''
        user.last_name = ''
        self.assertEqual(user.get_full_name(), 'test@example.com')

    def test_phone_validation(self) -> None:
        """Test phone number validation."""
        user = User.objects.create_user(
            email='phone@example.com',
            password='TestPass123!',
            phone='+525512345678'
        )
        self.assertEqual(user.phone, '+525512345678')

        # Test invalid phone
        user.phone = 'invalid'
        with self.assertRaises(ValidationError):
            user.full_clean()

    def test_onboarding_steps(self) -> None:
        """Test onboarding step progression."""
        user = User.objects.create_user(**self.user_data)

        self.assertEqual(user.onboarding_step, 1)
        self.assertFalse(user.onboarding_completed)

        user.onboarding_step = 4
        user.save()

        # Should auto-complete onboarding at step 4
        user.refresh_from_db()
        self.assertEqual(user.onboarding_step, 4)


class UserProfileModelTestCase(KitaTestCase):
    """Test cases for UserProfile model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='profile@example.com',
            password='TestPass123!'
        )
        self.profile = self.user.profile

    def test_default_values(self) -> None:
        """Test profile has correct defaults."""
        self.assertEqual(self.profile.timezone, 'America/Mexico_City')
        self.assertEqual(self.profile.language, 'es')
        self.assertEqual(self.profile.theme, 'auto')
        self.assertTrue(self.profile.email_notifications)
        self.assertTrue(self.profile.push_notifications)
        self.assertFalse(self.profile.sms_notifications)

    def test_login_count_increment(self) -> None:
        """Test login count incrementation."""
        initial_count = self.profile.login_count

        self.profile.increment_login_count()
        self.assertEqual(self.profile.login_count, initial_count + 1)

        self.profile.increment_login_count()
        self.assertEqual(self.profile.login_count, initial_count + 2)

    def test_last_activity_update(self) -> None:
        """Test last activity auto-updates."""
        old_activity = self.profile.last_activity

        # Wait a moment and update profile
        from time import sleep
        sleep(0.01)

        self.profile.bio = 'Updated bio'
        self.profile.save()

        self.assertGreater(self.profile.last_activity, old_activity)

    def test_profile_str(self) -> None:
        """Test string representation."""
        self.assertEqual(str(self.profile), 'Profile for profile@example.com')


class UserSessionModelTestCase(KitaTestCase):
    """Test cases for UserSession model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            email='session@example.com',
            password='TestPass123!'
        )

    def test_create_session(self) -> None:
        """Test session creation."""
        expires = timezone.now() + timedelta(hours=24)
        session = UserSession.objects.create(
            user=self.user,
            session_key='test_session_123',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            expires_at=expires
        )

        self.assertTrue(session.is_active)
        self.assertEqual(session.user, self.user)
        self.assertEqual(session.ip_address, '192.168.1.1')

    def test_session_expiration(self) -> None:
        """Test session expiration check."""
        # Create expired session
        expired_time = timezone.now() - timedelta(hours=1)
        session = UserSession.objects.create(
            user=self.user,
            session_key='expired_123',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            expires_at=expired_time
        )

        self.assertTrue(session.is_expired())

        # Create valid session
        valid_time = timezone.now() + timedelta(hours=1)
        session.expires_at = valid_time
        session.save()

        self.assertFalse(session.is_expired())

    def test_session_deactivate(self) -> None:
        """Test session deactivation."""
        session = UserSession.objects.create(
            user=self.user,
            session_key='deactivate_123',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            expires_at=timezone.now() + timedelta(hours=1)
        )

        self.assertTrue(session.is_active)

        session.deactivate()
        self.assertFalse(session.is_active)

    def test_unique_session_key(self) -> None:
        """Test session key uniqueness."""
        UserSession.objects.create(
            user=self.user,
            session_key='unique_key',
            ip_address='192.168.1.1',
            user_agent='Mozilla/5.0',
            expires_at=timezone.now() + timedelta(hours=1)
        )

        with self.assertRaises(IntegrityError):
            UserSession.objects.create(
                user=self.user,
                session_key='unique_key',  # Duplicate key
                ip_address='192.168.1.2',
                user_agent='Chrome',
                expires_at=timezone.now() + timedelta(hours=1)
            )


class UserManagerTestCase(KitaTestCase):
    """Test cases for UserManager custom methods."""

    def setUp(self) -> None:
        """Create test users."""
        self.active_user = User.objects.create_user(
            email='active@example.com',
            password='TestPass123!',
            is_active=True
        )

        self.inactive_user = User.objects.create_user(
            email='inactive@example.com',
            password='TestPass123!',
            is_active=False
        )

        self.verified_user = User.objects.create_user(
            email='verified@example.com',
            password='TestPass123!',
            is_email_verified=True
        )

    def test_active_queryset(self) -> None:
        """Test active() queryset method."""
        active_users = User.objects.active()

        self.assertIn(self.active_user, active_users)
        self.assertIn(self.verified_user, active_users)
        self.assertNotIn(self.inactive_user, active_users)

    def test_verified_queryset(self) -> None:
        """Test verified() queryset method."""
        verified_users = User.objects.verified()

        self.assertIn(self.verified_user, verified_users)
        self.assertNotIn(self.active_user, verified_users)
        self.assertNotIn(self.inactive_user, verified_users)

    def test_search_users(self) -> None:
        """Test user search functionality."""
        # Search by email
        results = User.objects.search_users('active@')
        self.assertIn(self.active_user, results)

        # Search by partial email
        results = User.objects.search_users('example.com')
        self.assertEqual(results.count(), 3)

    def test_get_or_create_by_email(self) -> None:
        """Test get_or_create_by_email method."""
        # Get existing user
        user, created = User.objects.get_or_create_by_email('active@example.com')
        self.assertEqual(user, self.active_user)
        self.assertFalse(created)

        # Create new user
        user, created = User.objects.get_or_create_by_email(
            'new@example.com',
            defaults={'first_name': 'New', 'last_name': 'User'}
        )
        self.assertTrue(created)
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(user.first_name, 'New')

    def test_recent_users(self) -> None:
        """Test recent() queryset method."""
        # Create old user
        old_user = User.objects.create_user(
            email='old@example.com',
            password='TestPass123!'
        )
        old_user.date_joined = timezone.now() - timedelta(days=60)
        old_user.save()

        # Get recent users (last 30 days)
        recent = User.objects.recent(days=30)

        self.assertIn(self.active_user, recent)
        self.assertIn(self.verified_user, recent)
        self.assertNotIn(old_user, recent)