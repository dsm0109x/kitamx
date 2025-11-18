"""Admin configuration for billing models."""
from __future__ import annotations

from django.contrib import admin
from django.utils.html import format_html

from core.admin_mixins import TenantModelAdminMixin, ExternalReferenceAdminMixin
from .models import Subscription, BillingPayment


@admin.register(Subscription)
class SubscriptionAdmin(TenantModelAdminMixin, ExternalReferenceAdminMixin, admin.ModelAdmin):
    """Admin interface for Subscription model using centralized mixins."""

    list_display = [
        'tenant', 'plan_name', 'status_display', 'monthly_price',
        'trial_ends_at', 'next_billing_date', 'is_active_display', 'created_at'
    ]
    list_filter = ['plan_name', 'currency']  # tenant, status, created_at added by mixins
    search_fields = ['mp_subscription_id']  # tenant fields added by mixin
    readonly_fields = ['trial_started_at', 'last_payment_date', 'cancelled_at']  # base fields added by mixin

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'plan_name', 'monthly_price', 'currency', 'status')
        }),
        ('Trial Period', {
            'fields': ('trial_started_at', 'trial_ends_at'),
            'classes': ('collapse',)
        }),
        ('Billing Period', {
            'fields': (
                'current_period_start', 'current_period_end',
                'next_billing_date', 'last_payment_date', 'last_payment_amount'
            ),
            'classes': ('collapse',)
        }),
        ('Payment Issues', {
            'fields': ('failed_payment_attempts', 'last_failed_payment_date'),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('cancel_at_period_end', 'cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('MercadoPago', {
            'fields': ('mp_subscription_id',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('tenant')

    def is_active_display(self, obj: Subscription) -> str:
        """Display active status with color."""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_display.short_description = 'Active'

    actions = ['activate_subscriptions', 'cancel_subscriptions']

    def activate_subscriptions(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Activate selected subscriptions."""
        count = 0
        for subscription in queryset:
            subscription.activate_subscription()
            count += 1
        self.message_user(request, f'{count} subscriptions activated.')
    activate_subscriptions.short_description = 'Activate selected subscriptions'

    def cancel_subscriptions(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Cancel selected subscriptions."""
        count = 0
        for subscription in queryset:
            subscription.cancel_subscription(
                reason='Admin cancellation',
                immediate=True
            )
            count += 1
        self.message_user(request, f'{count} subscriptions cancelled.')
    cancel_subscriptions.short_description = 'Cancel selected subscriptions'


@admin.register(BillingPayment)
class BillingPaymentAdmin(admin.ModelAdmin):
    """Admin interface for BillingPayment model."""

    list_display = [
        'tenant', 'subscription', 'amount', 'currency', 'status',
        'payment_method', 'processed_at', 'retry_count', 'created_at'
    ]
    list_filter = ['status', 'payment_method', 'currency', 'created_at']
    search_fields = [
        'tenant__name', 'tenant__email',
        'external_payment_id', 'subscription__plan_name'
    ]
    readonly_fields = [
        'id', 'created_at', 'updated_at', 'processed_at',
        'external_payment_id', 'external_payment_data'
    ]
    date_hierarchy = 'created_at'
    list_per_page = 100
    ordering = ['-created_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('tenant', 'subscription', 'amount', 'currency')
        }),
        ('Payment Details', {
            'fields': (
                'payment_method', 'status', 'processed_at',
                'billing_period_start', 'billing_period_end'
            )
        }),
        ('External Payment', {
            'fields': ('external_payment_id', 'external_payment_data'),
            'classes': ('collapse',)
        }),
        ('Failure Info', {
            'fields': ('failure_reason', 'retry_count', 'max_retries'),
            'classes': ('collapse',)
        }),
        ('Invoice', {
            'fields': ('invoice_generated', 'invoice_sent', 'invoice_data'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Optimize queryset with select_related."""
        qs = super().get_queryset(request)
        return qs.select_related('tenant', 'subscription')

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Prevent manual payment creation."""
        return False  # Payments should only be created via webhooks/API

    actions = ['mark_as_completed', 'mark_as_failed', 'reset_for_retry']

    def mark_as_completed(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Mark selected payments as completed."""
        count = 0
        for payment in queryset.filter(status__in=['pending', 'processing']):
            payment.mark_completed()
            count += 1
        self.message_user(request, f'{count} payments marked as completed.')
    mark_as_completed.short_description = 'Mark as completed'

    def mark_as_failed(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Mark selected payments as failed."""
        count = 0
        for payment in queryset.filter(status__in=['pending', 'processing']):
            payment.mark_failed('Admin marked as failed')
            count += 1
        self.message_user(request, f'{count} payments marked as failed.')
    mark_as_failed.short_description = 'Mark as failed'

    def reset_for_retry(self, request: HttpRequest, queryset: QuerySet) -> None:
        """Reset failed payments for retry."""
        count = queryset.filter(status='failed').update(
            status='pending',
            retry_count=0,
            failure_reason='',
            updated_at=timezone.now()
        )
        self.message_user(request, f'{count} payments reset for retry.')
    reset_for_retry.short_description = 'Reset for retry'
