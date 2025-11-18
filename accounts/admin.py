"""Django admin configuration for accounts app."""
from __future__ import annotations
from typing import Optional

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from core.admin_mixins import TimestampAdminMixin
from .models import User, UserProfile, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model."""
    list_display = ['email', 'first_name', 'last_name', 'is_email_verified', 'onboarding_completed', 'is_active', 'date_joined']
    list_filter = ['is_email_verified', 'onboarding_completed', 'is_active', 'is_staff', 'accepts_marketing', 'date_joined']
    search_fields = ['email', 'first_name', 'last_name', 'phone']
    ordering = ['-date_joined']
    readonly_fields = ['id', 'date_joined', 'last_login', 'email_verified_at']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        (_('Email verification'), {
            'fields': ('is_email_verified', 'email_verified_at'),
            'classes': ('collapse',)
        }),
        (_('Onboarding'), {
            'fields': ('onboarding_completed', 'onboarding_step'),
            'classes': ('collapse',)
        }),
        (_('Terms & Privacy'), {
            'fields': ('terms_accepted_at', 'privacy_accepted_at', 'accepts_marketing'),
            'classes': ('collapse',)
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        (_('Important dates'), {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


class UserProfileInline(admin.StackedInline):
    """Inline admin for UserProfile."""
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


@admin.register(UserProfile)
class UserProfileAdmin(TimestampAdminMixin, admin.ModelAdmin):
    """Admin interface for UserProfile model."""
    list_display = ['user', 'timezone', 'language', 'theme', 'email_notifications', 'last_activity']
    list_filter = ['timezone', 'language', 'theme', 'email_notifications', 'push_notifications']  # created_at added by TimestampAdminMixin
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'location']
    readonly_fields = ['last_activity', 'login_count']  # id, created_at, updated_at added by TimestampAdminMixin

    fieldsets = (
        ('Basic Info', {
            'fields': ('user', 'bio', 'location', 'website')
        }),
        ('Preferences', {
            'fields': ('timezone', 'language', 'theme')
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'push_notifications', 'sms_notifications'),
            'classes': ('collapse',)
        }),
        ('Activity', {
            'fields': ('last_activity', 'login_count'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserSession)
class UserSessionAdmin(TimestampAdminMixin, admin.ModelAdmin):
    """Admin interface for UserSession model."""
    list_display = ['user', 'ip_address', 'country', 'city', 'created_at', 'last_activity', 'is_active']
    list_filter = ['is_active', 'country', 'last_activity']  # created_at added by TimestampAdminMixin
    search_fields = ['user__email', 'ip_address', 'country', 'city']
    readonly_fields = ['session_key', 'last_activity']  # id, created_at, updated_at added by TimestampAdminMixin

    fieldsets = (
        ('Session Info', {
            'fields': ('user', 'session_key', 'is_active')
        }),
        ('Location & Device', {
            'fields': ('ip_address', 'user_agent', 'country', 'city')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_activity', 'expires_at'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Sessions cannot be created manually."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Optional[UserSession] = None) -> bool:
        """Sessions cannot be edited manually."""
        return False

    def get_queryset(self, request: HttpRequest) -> QuerySet[UserSession]:
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related('user')
