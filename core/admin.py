from __future__ import annotations
from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone

from .admin_mixins import (
    TimestampAdminMixin,
    TenantScopedAdminMixin,
    StatusAdminMixin
)
from .models import Tenant, TenantUser, Analytics, AuditLog, Notification


@admin.register(Tenant)
class TenantAdmin(TimestampAdminMixin, StatusAdminMixin, admin.ModelAdmin):
    """Admin interface for Tenant model."""

    list_display = ['name', 'slug', 'rfc', 'email', 'subscription_status', 'is_active', 'created_at']
    list_filter = ['is_active']  # created_at added by TimestampAdminMixin
    search_fields = ['name', 'slug', 'rfc', 'email', 'business_name']
    readonly_fields = ['subscription_status', 'trial_ends_at', 'is_trial', 'is_subscribed']  # id, created_at, updated_at added by TimestampAdminMixin

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset with prefetch."""
        qs = super().get_queryset(request)
        return qs.select_related()

    def subscription_status(self, obj: Tenant) -> str:
        """Show subscription status from billing system."""
        return obj.subscription_status
    subscription_status.short_description = 'Subscription Status'
    subscription_status.admin_order_field = 'subscription__status'

    def trial_ends_at(self, obj: Tenant) -> Any:
        """Show trial end date from billing system."""
        return obj.trial_ends_at
    trial_ends_at.short_description = 'Trial Ends At'

    def is_trial(self, obj: Tenant) -> bool:
        """Show if tenant is in trial."""
        return obj.is_trial
    is_trial.boolean = True
    is_trial.short_description = 'Is Trial'

    def is_subscribed(self, obj: Tenant) -> bool:
        """Show if tenant is subscribed."""
        return obj.is_subscribed
    is_subscribed.boolean = True
    is_subscribed.short_description = 'Is Subscribed'

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'domain', 'business_name', 'rfc')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'address')
        }),
        ('Status', {
            'fields': ('is_active', 'subscription_status', 'trial_ends_at', 'is_trial', 'is_subscribed')
        }),
        ('Fiscal Settings', {
            'fields': ('fiscal_regime', 'postal_code'),
            'classes': ('collapse',)
        }),
        ('Mercado Pago Integration', {
            'fields': ('mercadopago_user_id',),
            'classes': ('collapse',)
        }),
        ('CSD Info', {
            'fields': ('csd_serial_number', 'csd_valid_from', 'csd_valid_to'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TenantUser)
class TenantUserAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    """Admin interface for TenantUser model."""

    list_display = ['email', 'full_name', 'tenant', 'role', 'is_active', 'is_owner', 'created_at']
    list_filter = ['role', 'is_active', 'is_owner']  # tenant, created_at added by TenantScopedAdminMixin
    search_fields = ['email', 'first_name', 'last_name']  # tenant fields added by TenantScopedAdminMixin
    autocomplete_fields = ['tenant']

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'email', 'first_name', 'last_name')
        }),
        ('Role & Status', {
            'fields': ('role', 'is_owner', 'is_active')
        }),
        ('Permissions', {
            'fields': ('can_create_links', 'can_manage_settings', 'can_view_analytics'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    # get_queryset is handled by TenantScopedAdminMixin


@admin.register(Analytics)
class AnalyticsAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    """Admin interface for Analytics model."""

    list_display = ['tenant', 'date', 'period_type', 'links_created', 'payments_successful', 'revenue_gross_pesos', 'created_at']
    list_filter = ['period_type', 'date']  # tenant, created_at added by TenantScopedAdminMixin
    search_fields = []  # tenant fields added by TenantScopedAdminMixin
    readonly_fields = ['revenue_gross_pesos', 'revenue_net_pesos', 'revenue_fees_pesos']  # id, created_at, updated_at added by TenantScopedAdminMixin
    date_hierarchy = 'date'
    list_per_page = 100
    ordering = ['-date']

    # get_queryset is handled by TenantScopedAdminMixin


@admin.register(AuditLog)
class AuditLogAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    """Admin interface for AuditLog model.

    Audit logs are immutable - they can only be viewed, not modified or deleted.
    This ensures data integrity and compliance with security best practices.
    """

    list_display = ['user_email', 'action', 'entity_type', 'tenant', 'ip_address', 'created_at']
    list_filter = ['action', 'entity_type']  # tenant, created_at added by TenantScopedAdminMixin
    search_fields = ['user_email', 'user_name', 'action', 'entity_type']  # tenant fields added by TenantScopedAdminMixin
    list_per_page = 100

    # get_queryset is handled by TenantScopedAdminMixin

    def has_add_permission(self, request):
        """Prevent manual creation of audit logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit logs (immutable)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of audit logs (immutable)."""
        return False


@admin.register(Notification)
class NotificationAdmin(TenantScopedAdminMixin, StatusAdminMixin, admin.ModelAdmin):
    """Admin interface for Notification model."""

    list_display = ['recipient_email', 'notification_type', 'channel', 'status_display', 'tenant', 'created_at']
    list_filter = ['channel', 'notification_type']  # status, tenant, created_at added by mixins
    search_fields = ['recipient_email', 'recipient_name', 'subject']  # tenant fields added by TenantScopedAdminMixin
    readonly_fields = ['sent_at', 'delivered_at']  # id, created_at, updated_at added by TenantScopedAdminMixin
    list_per_page = 100

    # get_queryset is handled by TenantScopedAdminMixin

    actions = ['mark_as_sent', 'mark_as_failed']

    def mark_as_sent(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Mark selected notifications as sent."""
        updated = queryset.update(status='sent', sent_at=timezone.now())
        self.message_user(request, f'{updated} notifications marked as sent.')
    mark_as_sent.short_description = 'Mark selected as sent'

    def mark_as_failed(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Mark selected notifications as failed."""
        updated = queryset.update(status='failed')
        self.message_user(request, f'{updated} notifications marked as failed.')
    mark_as_failed.short_description = 'Mark selected as failed'
