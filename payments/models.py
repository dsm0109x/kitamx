from __future__ import annotations

from django.db import models
from core.models import TenantModel
from core.mixins import ActivatableMixin, MetadataMixin, ExternalReferenceMixin
from core.managers import PaymentLinkQuerySet, PaymentQuerySet


class MercadoPagoIntegration(TenantModel, ActivatableMixin):
    """Store Mercado Pago OAuth credentials for tenant"""

    # OAuth credentials
    access_token = models.TextField()
    refresh_token = models.TextField()
    user_id = models.CharField(max_length=255)

    # Token metadata
    expires_in = models.IntegerField()
    scope = models.CharField(max_length=255, blank=True)
    token_type = models.CharField(max_length=50, default='Bearer')

    # Integration status (is_active, activated_at, deactivated_at from ActivatableMixin)
    last_token_refresh = models.DateTimeField(auto_now=True)

    # Webhook configuration
    webhook_id = models.CharField(max_length=255, blank=True)
    webhook_secret = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'mercadopago_integrations'
        verbose_name = 'Mercado Pago Integration'
        verbose_name_plural = 'Mercado Pago Integrations'

    def __str__(self):
        return f"MP Integration for {self.tenant.name} (User: {self.user_id})"

    @property
    def is_valid(self):
        """Check if token is still valid (basic check)"""
        return self.is_active and self.access_token


class PaymentLink(TenantModel, MetadataMixin):
    """Payment links created by tenants"""

    objects = PaymentLinkQuerySet.as_manager()

    # Link identification
    token = models.CharField(max_length=32, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='MXN')

    # Invoice settings
    requires_invoice = models.BooleanField(default=False)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_rfc = models.CharField(max_length=13, blank=True)

    # Link configuration
    expires_at = models.DateTimeField()
    max_uses = models.IntegerField(default=1)
    uses_count = models.IntegerField(default=0)

    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Mercado Pago preference
    mp_preference_id = models.CharField(max_length=255, blank=True)

    # ====================================
    # NOTIFICATION CONFIGURATION (Email only)
    # ====================================
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name="Enviar notificaciones",
        help_text="Habilitar notificaciones automáticas por email para este link"
    )

    # Notificación al crear
    notify_on_create = models.BooleanField(
        default=True,
        verbose_name="Notificar al crear",
        help_text="Enviar email al cliente cuando se crea el link"
    )

    # Recordatorios
    send_reminders = models.BooleanField(
        default=True,
        verbose_name="Enviar recordatorios",
        help_text="Recordatorio automático por email antes de expirar"
    )
    reminder_hours_before = models.IntegerField(
        default=24,
        choices=[
            (6, '6 horas antes'),
            (12, '12 horas antes'),
            (24, '24 horas antes'),
            (48, '48 horas antes'),
            (72, '72 horas antes'),
        ],
        verbose_name="Anticipación del recordatorio"
    )
    reminder_sent = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Flag para tracking si ya se envió recordatorio"
    )

    # Link expirado
    notify_on_expiry = models.BooleanField(
        default=False,
        verbose_name="Notificar si expira",
        help_text="Enviar email si link expira sin pagar"
    )

    # Tracking
    notification_count = models.IntegerField(
        default=0,
        help_text="Total de notificaciones por email enviadas para este link"
    )

    # ✅ Cancellation metadata (for audit and analytics)
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when link was cancelled"
    )
    cancelled_by = models.ForeignKey(
        'accounts.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='cancelled_payment_links',
        help_text="User who cancelled the link"
    )
    cancellation_reason = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ('paid_other_method', 'Cliente pagó por otro medio'),
            ('wrong_amount', 'Error en monto o descripción'),
            ('customer_request', 'Cliente solicitó cancelación'),
            ('duplicate', 'Link duplicado'),
            ('expired_intent', 'Cliente ya no quiere pagar'),
            ('other', 'Otra razón'),
            ('not_specified', 'No especificada'),
        ],
        help_text="Reason for cancellation"
    )

    class Meta:
        db_table = 'payment_links'
        verbose_name = 'Payment Link'
        verbose_name_plural = 'Payment Links'
        ordering = ['-created_at']
        indexes = [
            # Index for reminder queries
            models.Index(
                fields=['status', 'send_reminders', 'reminder_sent', 'expires_at'],
                name='idx_link_reminders'
            ),
        ]

    def __str__(self):
        return f"{self.title} - ${self.amount} MXN"

    @property
    def public_url(self):
        """Generate public URL for payment link"""
        return f"/hola/{self.token}/"

    @property
    def is_active(self):
        """Check if link is still active"""
        from django.utils import timezone
        return (self.status == 'active' and
                self.expires_at > timezone.now() and
                self.uses_count < self.max_uses)

    def get_views_count(self):
        """Get total views count"""
        return self.views.count()

    def get_clicks_count(self):
        """Get total clicks count"""
        return self.clicks.count()

    def get_reminders_count(self):
        """Get total reminders sent count"""
        return self.reminders.count()

    def track_view(self, ip_address, user_agent, referrer='', action='page_view'):
        """Track a view of this payment link"""
        return PaymentLinkView.objects.create(
            tenant=self.tenant,
            payment_link=self,
            ip_address=ip_address,
            user_agent=user_agent,
            referrer=referrer
        )

    def track_click(self, ip_address, user_agent, click_type='pay_button'):
        """Track a click on this payment link"""
        return PaymentLinkClick.objects.create(
            tenant=self.tenant,
            payment_link=self,
            ip_address=ip_address,
            user_agent=user_agent,
            click_type=click_type
        )

    def track_interaction(self, action, ip_address, user_agent):
        """Track interactions like checkout_ready, payment_attempt, etc."""
        # Use the existing track_click method with different types
        return self.track_click(
            ip_address=ip_address,
            user_agent=user_agent,
            click_type=action
        )


class Payment(TenantModel, ExternalReferenceMixin):
    """Track payments received via Mercado Pago"""

    objects = PaymentQuerySet.as_manager()

    # Link relationship
    payment_link = models.ForeignKey(PaymentLink, on_delete=models.CASCADE, related_name='payments')

    # Mercado Pago data (external_id from mixin replaces mp_payment_id)
    mp_payment_id = models.CharField(max_length=255, unique=True, help_text='Legacy field - use external_id')
    mp_preference_id = models.CharField(max_length=255)
    mp_collection_id = models.CharField(max_length=255, blank=True)

    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='MXN')

    # Customer info
    payer_email = models.EmailField()
    payer_name = models.CharField(max_length=255, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True)

    # Billing data (filled after payment by customer)
    billing_rfc = models.CharField(max_length=13, blank=True)
    billing_name = models.CharField(max_length=255, blank=True)
    billing_address = models.TextField(blank=True)
    billing_postal_code = models.CharField(max_length=10, blank=True)
    billing_cfdi_use = models.CharField(max_length=10, default='G03')
    billing_data_provided = models.BooleanField(default=False)

    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('authorized', 'Authorized'),
        ('in_process', 'In Process'),
        ('in_mediation', 'In Mediation'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('charged_back', 'Charged Back'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Timestamps
    processed_at = models.DateTimeField(null=True, blank=True)
    mp_created_at = models.DateTimeField(null=True, blank=True)
    mp_updated_at = models.DateTimeField(null=True, blank=True)

    # Invoice relationship
    invoice = models.OneToOneField(
        'invoicing.Invoice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment'
    )

    # Webhook data
    webhook_data = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'payments'
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.mp_payment_id} - ${self.amount} MXN"

    @property
    def is_successful(self):
        """Check if payment was successful"""
        return self.status in ['approved', 'authorized']


class PaymentLinkView(TenantModel):
    """Track views of payment links"""
    payment_link = models.ForeignKey(PaymentLink, on_delete=models.CASCADE, related_name='views')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    referrer = models.URLField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'payment_link_views'
        indexes = [
            models.Index(fields=['payment_link', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]
        verbose_name = 'Payment Link View'
        verbose_name_plural = 'Payment Link Views'

    def __str__(self):
        return f"View of {self.payment_link.title} from {self.ip_address}"


class PaymentLinkClick(TenantModel):
    """Track clicks on payment buttons"""
    payment_link = models.ForeignKey(PaymentLink, on_delete=models.CASCADE, related_name='clicks')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    click_type = models.CharField(
        max_length=20,
        choices=[
            ('pay_button', 'Pay Button'),
            ('copy_link', 'Copy Link'),
            ('share', 'Share'),
        ],
        default='pay_button'
    )

    class Meta:
        db_table = 'payment_link_clicks'
        indexes = [
            models.Index(fields=['payment_link', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]
        verbose_name = 'Payment Link Click'
        verbose_name_plural = 'Payment Link Clicks'

    def __str__(self):
        return f"Click on {self.payment_link.title} ({self.click_type})"


class PaymentLinkReminder(TenantModel):
    """Track payment reminders sent"""
    payment_link = models.ForeignKey(PaymentLink, on_delete=models.CASCADE, related_name='reminders')
    notification = models.ForeignKey(
        'core.Notification',
        on_delete=models.CASCADE,
        related_name='link_reminders'
    )
    reminder_type = models.CharField(
        max_length=20,
        choices=[
            ('expiry_24h', '24 hours before expiry'),
            ('expiry_1h', '1 hour before expiry'),
            ('manual', 'Manual reminder'),
        ],
        default='manual'
    )

    class Meta:
        db_table = 'payment_link_reminders'
        indexes = [
            models.Index(fields=['payment_link', 'created_at']),
            models.Index(fields=['tenant', 'created_at']),
        ]
        verbose_name = 'Payment Link Reminder'
        verbose_name_plural = 'Payment Link Reminders'

    def __str__(self):
        return f"Reminder for {self.payment_link.title} ({self.reminder_type})"

    @property
    def needs_invoice(self):
        """Check if payment can generate invoice (successful, billing data provided, not yet invoiced)"""
        return (self.payment_link.requires_invoice and
                self.is_successful and
                self.billing_data_provided and
                not self.invoice)

    @property
    def can_request_billing_data(self):
        """Check if we can request billing data from customer"""
        return (self.payment_link.requires_invoice and
                self.is_successful and
                not self.billing_data_provided)
