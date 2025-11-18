"""Admin configuration for payments models."""
from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from core.admin_mixins import (
    FullKitaAdminMixin,
    TenantModelAdminMixin,
    TenantScopedAdminMixin,
    ExternalReferenceAdminMixin
)
from .models import (
    MercadoPagoIntegration,
    PaymentLink,
    Payment,
    PaymentLinkView,
    PaymentLinkClick,
    PaymentLinkReminder
)


@admin.register(MercadoPagoIntegration)
class MercadoPagoIntegrationAdmin(TenantModelAdminMixin, ExternalReferenceAdminMixin, admin.ModelAdmin):
    """Admin interface for MercadoPagoIntegration model."""

    list_display = ['tenant', 'user_id', 'is_active', 'last_token_refresh', 'created_at']
    list_filter = ['token_type']  # tenant, is_active, created_at added by mixins
    search_fields = ['user_id', 'scope']  # tenant fields added by TenantModelAdminMixin
    readonly_fields = ['last_token_refresh', 'webhook_id', 'webhook_secret']  # external fields and base fields added by mixins

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'user_id', 'is_active')
        }),
        ('OAuth Credentials', {
            'fields': ('access_token', 'refresh_token', 'expires_in', 'scope', 'token_type'),
            'classes': ('collapse',)
        }),
        ('Webhook', {
            'fields': ('webhook_id', 'webhook_secret'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('last_token_refresh', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PaymentLink)
class PaymentLinkAdmin(FullKitaAdminMixin, admin.ModelAdmin):
    """Admin interface for PaymentLink model."""

    list_display = ['title', 'tenant', 'amount', 'currency', 'status_display', 'expires_at', 'uses_count', 'max_uses', 'created_at']
    list_filter = ['currency', 'requires_invoice']  # tenant, status, created_at added by mixins
    search_fields = ['title', 'description', 'customer_name', 'customer_email']  # tenant fields added by mixins
    readonly_fields = ['token', 'uses_count']  # external fields and base fields added by mixins

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'title', 'description', 'token')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'status')
        }),
        ('Link Configuration', {
            'fields': ('expires_at', 'max_uses', 'uses_count')
        }),
        ('Customer Info', {
            'fields': ('requires_invoice', 'customer_name', 'customer_email', 'customer_rfc'),
            'classes': ('collapse',)
        }),
        ('MercadoPago', {
            'fields': ('mp_preference_id',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make token readonly for existing objects."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:  # editing existing object
            readonly.append('token')
        return readonly


@admin.register(Payment)
class PaymentAdmin(FullKitaAdminMixin, admin.ModelAdmin):
    """Admin interface for Payment model."""

    list_display = ['mp_payment_id', 'tenant', 'payment_link', 'amount', 'currency', 'status_display', 'payer_email', 'processed_at', 'created_at']
    list_filter = ['currency', 'billing_data_provided']  # tenant, status, created_at added by mixins
    search_fields = ['mp_payment_id', 'payer_email', 'payer_name', 'billing_rfc']  # tenant fields added by mixins
    readonly_fields = ['processed_at', 'mp_created_at', 'mp_updated_at', 'webhook_data']  # external fields and base fields added by mixins
    date_hierarchy = 'processed_at'

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'payment_link', 'status')
        }),
        ('Payment Details', {
            'fields': ('amount', 'currency', 'processed_at')
        }),
        ('Payer Info', {
            'fields': ('payer_email', 'payer_name', 'payer_phone')
        }),
        ('Billing Data', {
            'fields': (
                'billing_data_provided', 'billing_rfc', 'billing_name',
                'billing_address', 'billing_postal_code', 'billing_cfdi_use'
            ),
            'classes': ('collapse',)
        }),
        ('MercadoPago', {
            'fields': ('mp_payment_id', 'mp_preference_id', 'mp_collection_id', 'mp_created_at', 'mp_updated_at'),
            'classes': ('collapse',)
        }),
        ('Invoice', {
            'fields': ('invoice',),
            'classes': ('collapse',)
        }),
        ('Webhook Data', {
            'fields': ('webhook_data',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def successful_display(self, obj: Payment) -> str:
        """Display success status with color."""
        if obj.is_successful:
            return format_html('<span style="color: green;">✓ Success</span>')
        return format_html('<span style="color: red;">✗ Failed</span>')
    successful_display.short_description = 'Success'


@admin.register(PaymentLinkView)
class PaymentLinkViewAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    """Admin interface for PaymentLinkView model."""

    list_display = ['payment_link', 'tenant', 'ip_address', 'country', 'city', 'created_at']
    list_filter = ['country', 'city']  # tenant, created_at added by mixins
    search_fields = ['ip_address', 'user_agent', 'referrer']  # tenant fields added by mixins
    list_per_page = 100

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'payment_link', 'ip_address')
        }),
        ('Location', {
            'fields': ('country', 'city')
        }),
        ('Details', {
            'fields': ('user_agent', 'referrer'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Views are tracked automatically."""
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """Views cannot be edited."""
        return False


@admin.register(PaymentLinkClick)
class PaymentLinkClickAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    """Admin interface for PaymentLinkClick model."""

    list_display = ['payment_link', 'tenant', 'click_type', 'ip_address', 'created_at']
    list_filter = ['click_type']  # tenant, created_at added by mixins
    search_fields = ['ip_address', 'user_agent']  # tenant fields added by mixins
    list_per_page = 100

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'payment_link', 'click_type', 'ip_address')
        }),
        ('Details', {
            'fields': ('user_agent',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Clicks are tracked automatically."""
        return False

    def has_change_permission(self, request: HttpRequest, obj=None) -> bool:
        """Clicks cannot be edited."""
        return False


@admin.register(PaymentLinkReminder)
class PaymentLinkReminderAdmin(TenantScopedAdminMixin, admin.ModelAdmin):
    """Admin interface for PaymentLinkReminder model."""

    list_display = ['payment_link', 'tenant', 'reminder_type', 'notification', 'created_at']
    list_filter = ['reminder_type']  # tenant, created_at added by mixins
    search_fields = []  # tenant fields added by mixins

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'payment_link', 'reminder_type')
        }),
        ('Notification', {
            'fields': ('notification',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )