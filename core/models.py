from __future__ import annotations
from typing import Any, Optional
from decimal import Decimal
import uuid

from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.cache import cache
from django.utils import timezone

from .constants import FISCAL_REGIMES_PERSONAS_FISICAS


class TenantQuerySet(models.QuerySet):
    """Custom QuerySet for Tenant model."""

    def active(self) -> TenantQuerySet:
        """Filter active tenants."""
        return self.filter(is_active=True)

    def with_subscription(self) -> TenantQuerySet:
        """Prefetch subscription data."""
        return self.prefetch_related('subscription_set')

    def by_domain(self, domain: str) -> Optional[Tenant]:
        """Get tenant by domain."""
        return self.filter(domain=domain).first()

    def by_slug(self, slug: str) -> Optional[Tenant]:
        """Get tenant by slug."""
        return self.filter(slug=slug).first()


class TenantModelQuerySet(models.QuerySet):
    """Custom QuerySet for TenantModel abstract base."""

    def for_tenant(self, tenant: Tenant) -> TenantModelQuerySet:
        """Filter by tenant."""
        if tenant is None:
            raise ValidationError("Tenant is required")
        return self.filter(tenant=tenant)


class TenantManager(models.Manager):
    """Custom manager for Tenant model."""

    def get_queryset(self) -> TenantQuerySet:
        return TenantQuerySet(self.model, using=self._db)

    def active(self) -> TenantQuerySet:
        return self.get_queryset().active()

    def by_domain(self, domain: str) -> Optional[Tenant]:
        return self.get_queryset().by_domain(domain)

    def by_slug(self, slug: str) -> Optional[Tenant]:
        return self.get_queryset().by_slug(slug)


class TenantModelManager(models.Manager):
    """Custom manager for TenantModel abstract base."""

    def get_queryset(self) -> TenantModelQuerySet:
        return TenantModelQuerySet(self.model, using=self._db)

    def for_tenant(self, tenant: Tenant) -> TenantModelQuerySet:
        return self.get_queryset().for_tenant(tenant)


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantModel(BaseModel):
    """Abstract base model for tenant-scoped models."""

    tenant = models.ForeignKey(
        'core.Tenant',
        on_delete=models.CASCADE,
        related_name='%(class)s_set'
    )

    objects = TenantModelManager()

    class Meta:
        abstract = True

    def get_cache_key(self, suffix: str = '') -> str:
        """Generate cache key for this model instance."""
        key = f"{self.__class__.__name__.lower()}:{self.tenant_id}:{self.id}"
        if suffix:
            key = f"{key}:{suffix}"
        return key


class Tenant(BaseModel):
    """Tenant model representing a company/organization."""

    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, db_index=True)
    domain = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)

    # Business info
    business_name = models.CharField(max_length=255)
    rfc = models.CharField(max_length=13, unique=True, db_index=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)

    # Domicilio fiscal estructurado (CFDI 4.0 compliance)
    calle = models.CharField(max_length=255, blank=False, verbose_name='Calle')
    numero_exterior = models.CharField(max_length=20, blank=False, verbose_name='Número Exterior')
    numero_interior = models.CharField(max_length=50, blank=True, verbose_name='Número Interior')
    colonia = models.CharField(max_length=255, blank=False, verbose_name='Colonia')
    codigo_postal = models.CharField(max_length=5, blank=False, verbose_name='Código Postal', db_index=True)
    municipio = models.CharField(max_length=255, blank=False, verbose_name='Municipio')
    estado = models.CharField(max_length=255, blank=False, verbose_name='Estado')
    pais = models.CharField(max_length=100, default='México', verbose_name='País')
    localidad = models.CharField(max_length=255, blank=True, verbose_name='Localidad')

    # Tenant status
    is_active = models.BooleanField(default=True, db_index=True)

    # Integration settings
    mercadopago_user_id = models.CharField(max_length=255, blank=True)
    mercadopago_access_token = models.TextField(blank=True)
    mercadopago_refresh_token = models.TextField(blank=True)

    # Fiscal settings
    fiscal_regime = models.CharField(
        max_length=10,
        blank=False,
        choices=FISCAL_REGIMES_PERSONAS_FISICAS,
        help_text='Régimen fiscal del SAT para personas físicas'
    )

    # CSD (encrypted)
    csd_certificate = models.TextField(blank=True)
    csd_private_key = models.TextField(blank=True)
    csd_password = models.TextField(blank=True)
    csd_serial_number = models.CharField(max_length=100, blank=True)
    csd_valid_from = models.DateTimeField(null=True, blank=True)
    csd_valid_to = models.DateTimeField(null=True, blank=True)

    objects = TenantManager()

    class Meta:
        db_table = 'tenants'
        verbose_name = 'Tenant'
        verbose_name_plural = 'Tenants'
        indexes = [
            models.Index(fields=['is_active', 'created_at'], name='idx_tenant_active_created'),
            models.Index(fields=['rfc'], name='idx_tenant_rfc'),
        ]

    def __str__(self):
        return self.name

    @property
    def address(self) -> str:
        """
        Generate formatted address from structured fields.

        Auto-generated property - no DB field.
        Returns complete address in SAT-compliant format.

        Returns:
            str: Multi-line formatted address
        """
        parts = []

        # Línea 1: Calle y números
        street_line = []
        if self.calle:
            street_line.append(self.calle)
        if self.numero_exterior:
            street_line.append(self.numero_exterior)
        if self.numero_interior:
            street_line.append(f"Int. {self.numero_interior}")

        if street_line:
            parts.append(' '.join(street_line))

        # Línea 2: Colonia
        if self.colonia:
            parts.append(f"Col. {self.colonia}")

        # Línea 3: Municipio, Estado, CP
        location_line = []
        if self.municipio:
            location_line.append(self.municipio)
        if self.estado:
            location_line.append(self.estado)
        if self.codigo_postal:
            location_line.append(self.codigo_postal)

        if location_line:
            parts.append(', '.join(location_line))

        # Línea 4: País
        if self.pais and self.pais != 'México':
            parts.append(self.pais)

        return '\n'.join(parts) if parts else ''

    @property
    def postal_code(self) -> str:
        """Legacy property for backwards compatibility."""
        return self.codigo_postal

    def get_address_for_cfdi(self) -> dict:
        """
        Get address in CFDI XML format.

        Returns structured address for SAT CFDI 4.0 XML generation.

        Returns:
            dict: Address fields in SAT format
        """
        return {
            'Calle': self.calle or '',
            'NumeroExterior': self.numero_exterior or 'S/N',
            'NumeroInterior': self.numero_interior or '',
            'Colonia': self.colonia or '',
            'CodigoPostal': self.codigo_postal or '',
            'Municipio': self.municipio or '',
            'Estado': self.estado or '',
            'Pais': self.pais or 'México',
            'Localidad': self.localidad or '',
        }

    @property
    def subscription(self) -> Optional[Any]:
        """Get subscription from billing system with caching."""
        cache_key = f"tenant:{self.id}:subscription"
        subscription = cache.get(cache_key)

        if subscription is None:
            from billing.models import Subscription
            subscription = Subscription.objects.filter(tenant=self).first()
            cache.set(cache_key, subscription, 300)  # Cache for 5 minutes

        return subscription

    @property
    def subscription_status(self) -> str:
        """Get subscription status from billing system."""
        subscription = self.subscription
        return subscription.status if subscription else 'trial'

    @property
    def trial_ends_at(self) -> Optional[timezone.datetime]:
        """Get trial end date from billing system."""
        subscription = self.subscription
        return subscription.trial_ends_at if subscription else None

    @property
    def is_trial(self) -> bool:
        """Check if tenant is in trial from billing system."""
        subscription = self.subscription
        return subscription.is_trial if subscription else True

    @property
    def trial_progress_percent(self) -> int:
        """Calculate trial progress percentage (0-100)."""
        if not self.is_trial or not self.trial_ends_at:
            return 0

        subscription = self.subscription
        if not subscription or not subscription.trial_started_at:
            return 0

        # Calculate progress
        from django.utils import timezone
        now = timezone.now()
        trial_start = subscription.trial_started_at
        trial_end = self.trial_ends_at

        total_duration = (trial_end - trial_start).total_seconds()
        elapsed = (now - trial_start).total_seconds()

        if total_duration <= 0:
            return 100

        percent = int((elapsed / total_duration) * 100)
        return min(max(percent, 0), 100)  # Clamp between 0-100

    @property
    def is_subscribed(self) -> bool:
        """Check if tenant has active subscription from billing system."""
        subscription = self.subscription
        return subscription.is_active if subscription else False

    def invalidate_cache(self) -> None:
        """Invalidate tenant-related cache."""
        cache_keys = [
            f"tenant:{self.id}:subscription",
            f"tenant:{self.id}:stats",
            f"tenant:{self.id}:users",
        ]
        cache.delete_many(cache_keys)


class TenantUserQuerySet(models.QuerySet):
    """Custom QuerySet for TenantUser."""

    def active(self) -> TenantUserQuerySet:
        """Filter active users."""
        return self.filter(is_active=True)

    def owners(self) -> TenantUserQuerySet:
        """Filter owner users."""
        return self.filter(is_owner=True)

    def by_role(self, role: str) -> TenantUserQuerySet:
        """Filter by role."""
        return self.filter(role=role)

    def with_tenant(self) -> TenantUserQuerySet:
        """Optimize with select_related."""
        return self.select_related('tenant')


class TenantUserManager(models.Manager):
    """Custom manager for TenantUser."""

    def get_queryset(self) -> TenantUserQuerySet:
        return TenantUserQuerySet(self.model, using=self._db)

    def active(self) -> TenantUserQuerySet:
        return self.get_queryset().active()

    def owners(self) -> TenantUserQuerySet:
        return self.get_queryset().owners()


class TenantUser(BaseModel):
    """User model for tenant-specific users."""
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
    email = models.EmailField()
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    is_active = models.BooleanField(default=True)
    is_owner = models.BooleanField(default=False)
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Owner'),
            ('admin', 'Admin'),
            ('user', 'User'),
        ],
        default='user'
    )

    # Authentication fields
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(null=True, blank=True)

    # Permissions
    can_create_links = models.BooleanField(default=True)
    can_manage_settings = models.BooleanField(default=False)
    can_view_analytics = models.BooleanField(default=True)

    objects = TenantUserManager()

    class Meta:
        db_table = 'tenant_users'
        unique_together = ['tenant', 'email']
        verbose_name = 'Tenant User'
        verbose_name_plural = 'Tenant Users'
        indexes = [
            models.Index(fields=['tenant', 'is_active'], name='idx_tu_tenant_active'),
            models.Index(fields=['tenant', 'role'], name='idx_tu_tenant_role'),
            models.Index(fields=['email'], name='idx_tu_email'),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.tenant.name})"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission."""
        if self.is_owner:
            return True
        return getattr(self, f'can_{permission}', False)


class AnalyticsQuerySet(TenantModelQuerySet):
    """Custom QuerySet for Analytics."""

    def for_period(self, start_date: timezone.datetime, end_date: timezone.datetime) -> AnalyticsQuerySet:
        """Filter by date range."""
        return self.filter(date__gte=start_date, date__lte=end_date)

    def daily(self) -> AnalyticsQuerySet:
        """Filter daily analytics."""
        return self.filter(period_type='daily')

    def monthly(self) -> AnalyticsQuerySet:
        """Filter monthly analytics."""
        return self.filter(period_type='monthly')


class AnalyticsManager(TenantModelManager):
    """Custom manager for Analytics."""

    def get_queryset(self) -> AnalyticsQuerySet:
        return AnalyticsQuerySet(self.model, using=self._db)

    def for_period(self, tenant: Tenant, start_date: timezone.datetime, end_date: timezone.datetime) -> AnalyticsQuerySet:
        return self.get_queryset().for_tenant(tenant).for_period(start_date, end_date)


class Analytics(TenantModel):
    """Store analytics and metrics for tenants."""

    # Date range
    date = models.DateField(db_index=True)
    period_type = models.CharField(
        max_length=10,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily',
        db_index=True
    )

    # Payment links metrics
    links_created = models.IntegerField(default=0)
    links_active = models.IntegerField(default=0)
    links_paid = models.IntegerField(default=0)
    links_expired = models.IntegerField(default=0)
    links_views = models.IntegerField(default=0)
    links_clicks = models.IntegerField(default=0)

    # Payment metrics
    payments_attempted = models.IntegerField(default=0)
    payments_successful = models.IntegerField(default=0)
    payments_failed = models.IntegerField(default=0)
    payments_refunded = models.IntegerField(default=0)

    # Revenue metrics (in centavos to avoid decimal issues)
    revenue_gross = models.BigIntegerField(default=0)  # Total charged
    revenue_fees = models.BigIntegerField(default=0)   # MP fees
    revenue_net = models.BigIntegerField(default=0)    # Net received

    # Invoice metrics
    invoices_generated = models.IntegerField(default=0)
    invoices_sent = models.IntegerField(default=0)
    invoices_cancelled = models.IntegerField(default=0)
    invoices_failed = models.IntegerField(default=0)

    # Notification metrics
    notifications_sent = models.IntegerField(default=0)
    notifications_whatsapp = models.IntegerField(default=0)
    notifications_email = models.IntegerField(default=0)
    notifications_failed = models.IntegerField(default=0)

    objects = AnalyticsManager()

    class Meta:
        db_table = 'analytics'
        unique_together = ['tenant', 'date', 'period_type']
        indexes = [
            models.Index(fields=['tenant', 'date'], name='idx_analytics_tenant_date'),
            models.Index(fields=['tenant', 'period_type', 'date'], name='idx_analytics_tenant_period'),
            models.Index(fields=['date', 'period_type'], name='idx_analytics_date_period'),
        ]
        verbose_name = 'Analytics'
        verbose_name_plural = 'Analytics'

    def __str__(self):
        return f"Analytics {self.tenant.name} - {self.date} ({self.period_type})"

    @property
    def revenue_gross_pesos(self) -> Decimal:
        """Convert centavos to pesos."""
        return Decimal(self.revenue_gross) / 100

    @property
    def revenue_net_pesos(self) -> Decimal:
        """Convert centavos to pesos."""
        return Decimal(self.revenue_net) / 100

    @property
    def revenue_fees_pesos(self) -> Decimal:
        """Convert centavos to pesos."""
        return Decimal(self.revenue_fees) / 100

    @transaction.atomic
    def increment_metric(self, metric: str, value: int = 1) -> None:
        """Atomically increment a metric."""
        field = getattr(self.__class__, metric)
        if field:
            self.__class__.objects.filter(id=self.id).update(**{metric: models.F(metric) + value})
            # Refresh from DB
            self.refresh_from_db(fields=[metric])


class AuditLogQuerySet(TenantModelQuerySet):
    """Custom QuerySet for AuditLog."""

    def by_action(self, action: str) -> AuditLogQuerySet:
        """Filter by action."""
        return self.filter(action=action)

    def by_entity_type(self, entity_type: str) -> AuditLogQuerySet:
        """Filter by entity type."""
        return self.filter(entity_type=entity_type)

    def by_user(self, email: str) -> AuditLogQuerySet:
        """Filter by user email."""
        return self.filter(user_email=email)

    def recent(self, days: int = 7) -> AuditLogQuerySet:
        """Get recent logs."""
        cutoff = timezone.now() - timezone.timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class AuditLogManager(TenantModelManager):
    """Custom manager for AuditLog."""

    def get_queryset(self) -> AuditLogQuerySet:
        return AuditLogQuerySet(self.model, using=self._db)

    def log_action(
        self,
        tenant: Tenant,
        user_email: str,
        user_name: str,
        action: str,
        entity_type: str,
        ip_address: str,
        user_agent: str,
        **kwargs
    ) -> AuditLog:
        """Create an audit log entry."""
        return self.create(
            tenant=tenant,
            user_email=user_email,
            user_name=user_name,
            action=action,
            entity_type=entity_type,
            ip_address=ip_address,
            user_agent=user_agent,
            **kwargs
        )


class AuditLog(TenantModel):
    """Audit log for tracking user actions."""

    # Actor information
    user_email = models.EmailField()
    user_name = models.CharField(max_length=255)

    # Action details
    action = models.CharField(max_length=100, db_index=True)
    entity_type = models.CharField(max_length=50, db_index=True)
    entity_id = models.UUIDField(null=True, blank=True, db_index=True)
    entity_name = models.CharField(max_length=255, blank=True)

    # Request details
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()

    # Changes (for updates)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)

    # Additional context
    notes = models.TextField(blank=True)

    objects = AuditLogManager()

    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['tenant', '-created_at'], name='idx_audit_tenant_created'),
            models.Index(fields=['tenant', 'action'], name='idx_audit_tenant_action'),
            models.Index(fields=['tenant', 'entity_type'], name='idx_audit_tenant_entity'),
            models.Index(fields=['tenant', 'user_email'], name='idx_audit_tenant_user'),
            models.Index(fields=['entity_id'], name='idx_audit_entity_id'),
        ]
        ordering = ['-created_at']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'

    def save(self, *args, **kwargs):
        """Prevent modification of existing audit logs (immutable)."""
        # Use _state.adding to detect if this is a new object
        # (self.pk is not reliable with UUIDField since UUID is assigned before save)
        if not self._state.adding:
            raise ValueError("Audit logs are immutable and cannot be modified")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deletion of audit logs (immutable)."""
        raise ValueError("Audit logs are immutable and cannot be deleted")

    def __str__(self):
        return f"{self.user_name} {self.action} {self.entity_type} at {self.created_at}"


class NotificationQuerySet(TenantModelQuerySet):
    """Custom QuerySet for Notification."""

    def pending(self) -> NotificationQuerySet:
        """Filter pending notifications."""
        return self.filter(status='pending')

    def sent(self) -> NotificationQuerySet:
        """Filter sent notifications."""
        return self.filter(status='sent')

    def failed(self) -> NotificationQuerySet:
        """Filter failed notifications."""
        return self.filter(status='failed')

    def retryable(self) -> NotificationQuerySet:
        """Filter notifications that can be retried."""
        return self.filter(status='failed', retry_count__lt=models.F('max_retries'))

    def by_channel(self, channel: str) -> NotificationQuerySet:
        """Filter by channel."""
        return self.filter(channel=channel)

    def by_type(self, notification_type: str) -> NotificationQuerySet:
        """Filter by notification type."""
        return self.filter(notification_type=notification_type)


class NotificationManager(TenantModelManager):
    """Custom manager for Notification."""

    def get_queryset(self) -> NotificationQuerySet:
        return NotificationQuerySet(self.model, using=self._db)

    def pending(self) -> NotificationQuerySet:
        return self.get_queryset().pending()

    def retryable(self) -> NotificationQuerySet:
        return self.get_queryset().retryable()


class Notification(TenantModel):
    """Notification tracking."""

    # Recipient
    recipient_email = models.EmailField()
    recipient_phone = models.CharField(max_length=20, blank=True)
    recipient_name = models.CharField(max_length=255, blank=True)

    # Notification details
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('link_created', 'Link Created'),
            ('payment_received', 'Payment Received'),
            ('invoice_generated', 'Invoice Generated'),
            ('payment_reminder', 'Payment Reminder'),
            ('link_expired', 'Link Expired'),
            ('subscription_due', 'Subscription Due'),
            ('subscription_failed', 'Subscription Failed'),
        ],
        db_index=True
    )

    channel = models.CharField(
        max_length=20,
        choices=[
            ('whatsapp', 'WhatsApp'),
            ('email', 'Email'),
            ('sms', 'SMS'),
        ],
        db_index=True
    )

    # Content
    subject = models.CharField(max_length=255)
    message = models.TextField()

    # ✅ Metadata para templates HTML (variables dinámicas)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Context variables for HTML email templates"
    )

    # Related entities
    payment_link_id = models.UUIDField(null=True, blank=True)
    payment_id = models.UUIDField(null=True, blank=True)
    invoice_id = models.UUIDField(null=True, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('sent', 'Sent'),
            ('delivered', 'Delivered'),
            ('failed', 'Failed'),
            ('retrying', 'Retrying'),
        ],
        default='pending',
        db_index=True
    )

    # Delivery details
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)

    # External IDs
    external_id = models.CharField(max_length=255, blank=True)  # WhatsApp/Email provider ID

    # Postmark tracking
    postmark_message_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="MessageID de Postmark para tracking de email"
    )

    objects = NotificationManager()

    class Meta:
        db_table = 'notifications'
        indexes = [
            models.Index(fields=['tenant', '-created_at'], name='idx_notif_tenant_created'),
            models.Index(fields=['tenant', 'status'], name='idx_notif_tenant_status'),
            models.Index(fields=['tenant', 'notification_type'], name='idx_notif_tenant_type'),
            models.Index(fields=['tenant', 'channel'], name='idx_notif_tenant_channel'),
            models.Index(fields=['recipient_email'], name='idx_notif_recipient'),
            models.Index(fields=['status', 'retry_count'], name='idx_notif_retry'),
        ]
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self) -> str:
        return f"{self.notification_type} to {self.recipient_email} via {self.channel}"

    def can_retry(self) -> bool:
        """Check if notification can be retried."""
        return self.status == 'failed' and self.retry_count < self.max_retries

    @transaction.atomic
    def mark_sent(self) -> None:
        """Mark notification as sent."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at', 'updated_at'])

    @transaction.atomic
    def mark_failed(self, error_message: str) -> None:
        """Mark notification as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['status', 'error_message', 'retry_count', 'updated_at'])

    def get_email_event(self):
        """Get associated email event if exists."""
        if self.postmark_message_id and self.channel == 'email':
            try:
                return self.email_events.first()
            except:
                return None
        return None

    @property
    def email_delivered(self):
        """Check if email was delivered."""
        event = self.get_email_event()
        return event.delivered if event else False

    @property
    def email_opened(self):
        """Check if email was opened."""
        event = self.get_email_event()
        return event.opened if event else False

    @property
    def email_bounced(self):
        """Check if email bounced."""
        event = self.get_email_event()
        return event.bounced if event else False

    @property
    def open_count(self):
        """Number of times email was opened."""
        event = self.get_email_event()
        return event.open_count if event else 0


# ========================================
# SEPOMEX - Códigos Postales de México
# ========================================

class CodigoPostalQuerySet(models.QuerySet):
    """Optimized queries for postal codes."""

    def by_cp(self, codigo_postal: str):
        return self.filter(codigo_postal=codigo_postal)

    def unique_colonias(self, codigo_postal: str):
        return self.filter(
            codigo_postal=codigo_postal
        ).values_list('asentamiento', flat=True).distinct().order_by('asentamiento')


class CodigoPostalManager(models.Manager):
    """Manager with enterprise methods."""

    def get_queryset(self):
        return CodigoPostalQuerySet(self.model, using=self._db)

    def lookup(self, codigo_postal: str) -> Optional[dict]:
        if not codigo_postal or len(codigo_postal) != 5:
            return None

        records = self.filter(codigo_postal=codigo_postal).values(
            'asentamiento', 'municipio', 'estado', 'ciudad'
        )

        if not records.exists():
            return None

        colonias = list(set(r['asentamiento'] for r in records))
        colonias.sort()

        first = records.first()

        return {
            'success': True,
            'colonias': colonias,
            'municipio': first['municipio'],
            'estado': first['estado'],
            'ciudad': first['ciudad'] or first['municipio'],
            'pais': 'México'
        }

    def validate_colonia(self, codigo_postal: str, colonia: str) -> bool:
        return self.filter(
            codigo_postal=codigo_postal,
            asentamiento__iexact=colonia
        ).exists()


class CodigoPostal(models.Model):
    """Mexican Postal Code - Official SEPOMEX catalog."""

    codigo_postal = models.CharField(max_length=5, db_index=True)
    asentamiento = models.CharField(max_length=255)
    tipo_asentamiento = models.CharField(max_length=100)
    municipio = models.CharField(max_length=255, db_index=True)
    estado = models.CharField(max_length=255, db_index=True)
    ciudad = models.CharField(max_length=255, blank=True)
    zona = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CodigoPostalManager()

    class Meta:
        db_table = 'codigos_postales'
        verbose_name = 'Código Postal'
        verbose_name_plural = 'Códigos Postales'
        indexes = [
            models.Index(fields=['codigo_postal', 'asentamiento'], name='idx_cp_colonia'),
            models.Index(fields=['municipio'], name='idx_municipio'),
            models.Index(fields=['estado'], name='idx_estado'),
        ]
        unique_together = [['codigo_postal', 'asentamiento']]

    def __str__(self):
        return f"{self.codigo_postal} - {self.asentamiento}"


class EmailEvent(TenantModel):
    """
    Email event tracking from Postmark webhooks.
    Tracks delivery, opens, clicks, bounces, and spam complaints.
    """

    # Identificación del email
    message_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="MessageID de Postmark (UUID)"
    )
    message_stream = models.CharField(
        max_length=50,
        default='outbound',
        help_text="Stream de Postmark"
    )

    # Relacionado con qué notificación
    notification = models.ForeignKey(
        'Notification',
        on_delete=models.CASCADE,
        related_name='email_events',
        null=True,
        blank=True,
        help_text="Notificación asociada"
    )

    # Información del email
    recipient = models.EmailField()
    subject = models.CharField(max_length=255, blank=True)
    tag = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Tag de Postmark (ej: 'link_created')"
    )

    # Metadata personalizada
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Metadata enviada en el email"
    )

    # ====================================
    # EVENTOS TRACKED
    # ====================================

    # Sent
    sent_at = models.DateTimeField(auto_now_add=True)

    # Delivery
    delivered = models.BooleanField(default=False)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Opens
    opened = models.BooleanField(default=False, db_index=True)
    first_opened_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.IntegerField(default=0)

    # Clicks
    clicked = models.BooleanField(default=False)
    first_clicked_at = models.DateTimeField(null=True, blank=True)
    click_count = models.IntegerField(default=0)

    # Bounces
    bounced = models.BooleanField(default=False, db_index=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    bounce_type = models.CharField(max_length=50, blank=True)
    bounce_description = models.TextField(blank=True)

    # Spam complaints
    spam_complaint = models.BooleanField(default=False)
    spam_complaint_at = models.DateTimeField(null=True, blank=True)

    # Client info (del que abrió el email)
    client_name = models.CharField(max_length=100, blank=True)
    client_os = models.CharField(max_length=100, blank=True)
    client_platform = models.CharField(max_length=50, blank=True)

    # Geo location
    geo_country = models.CharField(max_length=100, blank=True)
    geo_city = models.CharField(max_length=100, blank=True)
    geo_ip = models.GenericIPAddressField(null=True, blank=True)

    # Postmark IDs
    postmark_bounce_id = models.BigIntegerField(null=True, blank=True)
    server_id = models.IntegerField(null=True, blank=True)

    # Status general
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('opened', 'Opened'),
        ('clicked', 'Clicked'),
        ('bounced', 'Bounced'),
        ('spam', 'Spam Complaint'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='sent',
        db_index=True
    )

    class Meta:
        db_table = 'email_events'
        verbose_name = 'Email Event'
        verbose_name_plural = 'Email Events'
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['message_id'], name='idx_email_message_id'),
            models.Index(fields=['notification', 'status'], name='idx_email_notif_status'),
            models.Index(fields=['tag', '-sent_at'], name='idx_email_tag_date'),
            models.Index(fields=['recipient', '-sent_at'], name='idx_email_recipient'),
        ]

    def __str__(self):
        return f"Email to {self.recipient} - {self.status}"

    @property
    def time_to_open(self):
        """Tiempo entre envío y primera apertura en segundos."""
        if self.first_opened_at and self.sent_at:
            delta = self.first_opened_at - self.sent_at
            return delta.total_seconds()
        return None

    @property
    def time_to_open_display(self):
        """Tiempo hasta apertura en formato legible."""
        seconds = self.time_to_open
        if not seconds:
            return None

        if seconds < 60:
            return f"{int(seconds)} segundos"
        elif seconds < 3600:
            return f"{int(seconds / 60)} minutos"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m" if minutes > 0 else f"{hours} horas"
        else:
            return f"{int(seconds / 86400)} días"

    def update_from_webhook(self, event_type: str, webhook_data: dict):
        """Actualizar desde webhook de Postmark."""
        if event_type == 'Delivery':
            self.delivered = True
            self.delivered_at = timezone.now()
            if self.status == 'sent':
                self.status = 'delivered'

        elif event_type == 'Open':
            if not self.opened:
                # Primera apertura
                self.opened = True
                self.first_opened_at = timezone.now()
                self.status = 'opened'

            self.last_opened_at = timezone.now()
            self.open_count += 1

            # Extraer info del cliente
            client = webhook_data.get('Client', {})
            self.client_name = client.get('Name', '')

            os_info = webhook_data.get('OS', {})
            self.client_os = os_info.get('Name', '')

            self.client_platform = webhook_data.get('Platform', '')

            # Geo
            geo = webhook_data.get('Geo', {})
            self.geo_country = geo.get('CountryISOCode', '')
            self.geo_city = geo.get('City', '')
            self.geo_ip = geo.get('IP', '')

        elif event_type == 'Click':
            if not self.clicked:
                self.clicked = True
                self.first_clicked_at = timezone.now()
                if self.status in ['opened', 'delivered']:
                    self.status = 'clicked'

            self.click_count += 1

        elif event_type == 'Bounce':
            self.bounced = True
            self.bounced_at = timezone.now()
            self.bounce_type = webhook_data.get('Type', 'Unknown')
            self.bounce_description = webhook_data.get('Description', '')
            self.postmark_bounce_id = webhook_data.get('ID')
            self.status = 'bounced'

        elif event_type == 'SpamComplaint':
            self.spam_complaint = True
            self.spam_complaint_at = timezone.now()
            self.status = 'spam'

        self.save()
