"""
Billing models for subscription and payment management.

Handles Kita Pro subscriptions, trials, payments, and billing cycles.
"""
from __future__ import annotations
from typing import Any
from decimal import Decimal
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from django.core.exceptions import ValidationError
from dateutil.relativedelta import relativedelta

from core.models import TenantModel
from core.mixins import MetadataMixin, ExternalReferenceMixin
from core.managers import SubscriptionQuerySet as CoreSubscriptionQuerySet


class SubscriptionQuerySet(models.QuerySet):
    """Custom QuerySet for Subscription model with optimized methods."""

    def active(self) -> models.QuerySet:
        """Get active subscriptions."""
        return self.filter(status='active')

    def trial(self) -> models.QuerySet:
        """Get trial subscriptions."""
        return self.filter(status='trial')

    def past_due(self) -> models.QuerySet:
        """Get past due subscriptions."""
        return self.filter(status='past_due')

    def expiring_trials(self, days: int = 7) -> models.QuerySet:
        """Get trials expiring in the next N days."""
        cutoff = timezone.now() + timedelta(days=days)
        return self.filter(
            status='trial',
            trial_ends_at__lte=cutoff,
            trial_ends_at__gt=timezone.now()
        )

    def with_tenant(self) -> models.QuerySet:
        """Prefetch tenant for efficiency."""
        return self.select_related('tenant')

    def with_payments(self) -> models.QuerySet:
        """Prefetch payments for efficiency."""
        return self.prefetch_related('payments')


class SubscriptionManager(models.Manager):
    """Custom manager for Subscription model."""

    def get_queryset(self) -> SubscriptionQuerySet:
        """Return custom QuerySet."""
        return SubscriptionQuerySet(self.model, using=self._db)

    def active(self) -> models.QuerySet:
        """Shortcut for active subscriptions."""
        return self.get_queryset().active()

    def trial(self) -> models.QuerySet:
        """Shortcut for trial subscriptions."""
        return self.get_queryset().trial()

    def get_or_create_for_tenant(self, tenant: Any) -> tuple[Subscription, bool]:
        """
        Get or create subscription for a tenant with proper defaults.

        Args:
            tenant: Tenant instance

        Returns:
            Tuple of (subscription, created)
        """
        return self.get_or_create(
            tenant=tenant,
            defaults={
                'trial_ends_at': timezone.now() + timedelta(days=30),
                'plan_name': 'Kita Pro',
                'monthly_price': Decimal('299.00'),
                'currency': 'MXN'
            }
        )


class Subscription(TenantModel, MetadataMixin):
    """
    Tenant subscription management.

    Handles trial periods, billing cycles, and payment status.
    """

    objects = SubscriptionManager()

    # Plan information
    plan_name = models.CharField(
        max_length=100,
        default='Kita Pro',
        help_text='Name of the subscription plan'
    )
    monthly_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('299.00'),
        help_text='Monthly price in currency'
    )
    currency = models.CharField(
        max_length=3,
        default='MXN',
        help_text='Currency code (ISO 4217)'
    )

    # Subscription status
    STATUS_CHOICES = [
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('cancelled', 'Cancelled'),
        ('suspended', 'Suspended'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='trial',
        db_index=True,
        help_text='Current subscription status'
    )

    # Trial information
    trial_started_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When trial period started'
    )
    trial_ends_at = models.DateTimeField(
        db_index=True,
        help_text='When trial period ends'
    )

    # Billing cycle
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Start of current billing period'
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='End of current billing period'
    )
    next_billing_date = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Next scheduled billing date'
    )

    # Payment information
    last_payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date of last successful payment'
    )
    last_payment_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Amount of last payment'
    )
    failed_payment_attempts = models.IntegerField(
        default=0,
        help_text='Number of consecutive failed payment attempts'
    )
    last_failed_payment_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date of last failed payment attempt'
    )

    # Cancellation
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When subscription was cancelled'
    )
    cancellation_reason = models.TextField(
        blank=True,
        help_text='Reason for cancellation'
    )
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text='Cancel at end of current period instead of immediately'
    )

    # MercadoPago subscription ID (if using MP subscriptions)
    mp_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text='MercadoPago subscription identifier'
    )


    class Meta:
        db_table = 'subscriptions'
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        indexes = [
            models.Index(fields=['tenant', 'status'], name='idx_sub_tenant_status'),
            models.Index(fields=['status', 'next_billing_date'], name='idx_sub_status_billing'),
            models.Index(fields=['trial_ends_at', 'status'], name='idx_sub_trial_status'),
            models.Index(fields=['status', '-created_at'], name='idx_sub_status_created'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'],
                name='unique_tenant_subscription'
            )
        ]

    def __str__(self) -> str:
        """String representation."""
        return f"{self.tenant.name} - {self.plan_name} ({self.status})"

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial period."""
        return self.status == 'trial'

    @property
    def is_active(self) -> bool:
        """Check if subscription is active."""
        return self.status == 'active'

    @property
    def is_past_due(self) -> bool:
        """Check if subscription is past due."""
        return self.status == 'past_due'

    @property
    def is_cancelled(self) -> bool:
        """Check if subscription is cancelled."""
        return self.status == 'cancelled'

    @property
    def days_until_trial_end(self) -> int:
        """Calculate days remaining in trial period."""
        if not self.is_trial or not self.trial_ends_at:
            return 0

        delta = self.trial_ends_at - timezone.now()
        return max(0, delta.days)

    @property
    def is_trial_expired(self) -> bool:
        """Check if trial period has expired."""
        if not self.is_trial:
            return False
        return timezone.now() > self.trial_ends_at

    @property
    def can_use_features(self) -> bool:
        """Check if tenant can use platform features."""
        return self.status in ['trial', 'active']

    def get_cache_key(self, suffix: str = '') -> str:
        """Generate cache key for subscription data."""
        base_key = f"subscription:{self.tenant_id}"
        return f"{base_key}:{suffix}" if suffix else base_key

    def invalidate_cache(self) -> None:
        """Invalidate subscription cache."""
        cache.delete(self.get_cache_key())
        cache.delete(self.get_cache_key('stats'))

    @transaction.atomic
    def activate_subscription(self) -> None:
        """
        Activate subscription after trial or reactivation.

        Sets up billing cycle and clears failed payment attempts.
        """
        now = timezone.now()
        self.status = 'active'
        self.current_period_start = now
        self.current_period_end = now + relativedelta(months=1)
        self.next_billing_date = self.current_period_end
        self.failed_payment_attempts = 0
        self.cancelled_at = None
        self.cancel_at_period_end = False
        self.save()
        self.invalidate_cache()

    @transaction.atomic
    def cancel_subscription(self, reason: str = '', immediate: bool = False) -> None:
        """
        Cancel subscription.

        Args:
            reason: Cancellation reason
            immediate: Cancel immediately vs at period end
        """
        if immediate:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
        else:
            self.cancel_at_period_end = True

        self.cancellation_reason = reason
        self.save()
        self.invalidate_cache()

    def mark_payment_failed(self) -> None:
        """
        Mark payment as failed and handle retry logic.

        Suspends subscription after 3 failed attempts.
        """
        self.failed_payment_attempts += 1
        self.last_failed_payment_date = timezone.now()

        if self.failed_payment_attempts >= 3:
            self.status = 'past_due'
        if self.failed_payment_attempts >= 5:
            self.status = 'suspended'

        self.save()
        self.invalidate_cache()

    @transaction.atomic
    def mark_payment_successful(self, amount: Decimal) -> None:
        """
        Mark payment as successful and update billing cycle.

        Args:
            amount: Payment amount
        """
        now = timezone.now()
        self.last_payment_date = now
        self.last_payment_amount = amount
        self.failed_payment_attempts = 0
        self.status = 'active'

        # Update billing cycle
        if self.current_period_end:
            self.current_period_start = self.current_period_end
            self.current_period_end = self.current_period_end + relativedelta(months=1)
        else:
            self.current_period_start = now
            self.current_period_end = now + relativedelta(months=1)

        self.next_billing_date = self.current_period_end
        self.save()
        self.invalidate_cache()

    def clean(self) -> None:
        """Validate model fields."""
        super().clean()

        if self.monthly_price < 0:
            raise ValidationError('Monthly price cannot be negative')

        if self.trial_ends_at and self.trial_started_at:
            if self.trial_ends_at < self.trial_started_at:
                raise ValidationError('Trial end date must be after start date')


class BillingPaymentQuerySet(models.QuerySet):
    """Custom QuerySet for BillingPayment model."""

    def successful(self) -> models.QuerySet:
        """Get successful payments."""
        return self.filter(status='completed')

    def failed(self) -> models.QuerySet:
        """Get failed payments."""
        return self.filter(status='failed')

    def pending(self) -> models.QuerySet:
        """Get pending payments."""
        return self.filter(status='pending')

    def retryable(self) -> models.QuerySet:
        """Get payments that can be retried."""
        return self.filter(
            status='failed',
            retry_count__lt=models.F('max_retries')
        )

    def with_subscription(self) -> models.QuerySet:
        """Prefetch subscription and tenant."""
        return self.select_related('subscription', 'subscription__tenant', 'tenant')


class BillingPaymentManager(models.Manager):
    """Custom manager for BillingPayment model."""

    def get_queryset(self) -> BillingPaymentQuerySet:
        """Return custom QuerySet."""
        return BillingPaymentQuerySet(self.model, using=self._db)

    def successful(self) -> models.QuerySet:
        """Shortcut for successful payments."""
        return self.get_queryset().successful()

    def failed(self) -> models.QuerySet:
        """Shortcut for failed payments."""
        return self.get_queryset().failed()


class BillingPayment(TenantModel, ExternalReferenceMixin, MetadataMixin):
    """
    Subscription payments to Kita.

    Tracks payment attempts, status, and billing periods.
    """

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name='payments',
        help_text='Associated subscription'
    )

    # Payment details
    amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text='Payment amount'
    )
    currency = models.CharField(
        max_length=3,
        default='MXN',
        help_text='Currency code (ISO 4217)'
    )

    # Payment method
    PAYMENT_METHOD_CHOICES = [
        ('mercadopago', 'MercadoPago'),
        ('stripe', 'Stripe'),
        ('transfer', 'Transfer'),
        ('cash', 'Cash'),
    ]
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES,
        default='mercadopago',
        db_index=True,
        help_text='Payment method used'
    )

    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text='Payment status'
    )

    # External payment reference
    external_payment_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text='External payment system ID'
    )
    external_payment_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Raw data from payment provider'
    )

    # Billing period
    billing_period_start = models.DateTimeField(
        help_text='Start of billing period'
    )
    billing_period_end = models.DateTimeField(
        help_text='End of billing period'
    )

    # Processing details
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text='When payment was processed'
    )
    failure_reason = models.TextField(
        blank=True,
        help_text='Reason for payment failure'
    )
    retry_count = models.IntegerField(
        default=0,
        help_text='Number of retry attempts'
    )
    max_retries = models.IntegerField(
        default=3,
        help_text='Maximum retry attempts allowed'
    )

    # Invoice information
    invoice_generated = models.BooleanField(
        default=False,
        help_text='Whether invoice was generated'
    )
    invoice_sent = models.BooleanField(
        default=False,
        help_text='Whether invoice was sent'
    )
    invoice_data = models.JSONField(
        default=dict,
        blank=True,
        help_text='Invoice generation data'
    )

    # Custom manager
    objects = BillingPaymentManager()

    class Meta:
        db_table = 'billing_payments'
        ordering = ['-created_at']
        verbose_name = 'Billing Payment'
        verbose_name_plural = 'Billing Payments'
        indexes = [
            models.Index(fields=['tenant', '-created_at'], name='idx_pay_tenant_created'),
            models.Index(fields=['subscription', '-created_at'], name='idx_pay_sub_created'),
            models.Index(fields=['status', 'processed_at'], name='idx_pay_status_processed'),
            models.Index(fields=['external_payment_id'], name='idx_pay_external_id'),
            models.Index(fields=['status', 'retry_count'], name='idx_pay_status_retry'),
        ]

    def __str__(self) -> str:
        """String representation."""
        return f"Payment ${self.amount} {self.currency} - {self.tenant.name} ({self.status})"

    @property
    def is_successful(self) -> bool:
        """Check if payment was successful."""
        return self.status == 'completed'

    @property
    def is_failed(self) -> bool:
        """Check if payment failed."""
        return self.status == 'failed'

    @property
    def can_retry(self) -> bool:
        """Check if payment can be retried."""
        return self.status == 'failed' and self.retry_count < self.max_retries

    @transaction.atomic
    def mark_completed(self) -> None:
        """
        Mark payment as completed.

        Updates subscription status and billing cycle.
        """
        self.status = 'completed'
        self.processed_at = timezone.now()
        self.save()

        # Update subscription
        self.subscription.mark_payment_successful(self.amount)

    @transaction.atomic
    def mark_failed(self, reason: str = '') -> None:
        """
        Mark payment as failed.

        Args:
            reason: Failure reason
        """
        self.status = 'failed'
        self.failure_reason = reason
        self.processed_at = timezone.now()
        self.save()

        # Update subscription
        self.subscription.mark_payment_failed()

    def clean(self) -> None:
        """Validate model fields."""
        super().clean()

        if self.amount <= 0:
            raise ValidationError('Payment amount must be positive')

        if self.billing_period_end <= self.billing_period_start:
            raise ValidationError('Billing period end must be after start')

        if self.retry_count > self.max_retries:
            raise ValidationError('Retry count cannot exceed max retries')