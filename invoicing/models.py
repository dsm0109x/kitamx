"""Models for CFDI 4.0 invoicing and certificate management.

This module handles CSD certificates, file uploads, and invoice management
for Mexican CFDI 4.0 electronic invoicing requirements.
"""
from __future__ import annotations
from typing import Optional
import uuid

from django.db import models
from django.core.files.storage import default_storage
from django.db.models import QuerySet, Manager
from django.utils import timezone

from core.models import TenantModel
from core.storage import get_tenant_csd_storage
from core.mixins import MetadataMixin
from core.managers import InvoiceQuerySet as CoreInvoiceQuerySet


class CSDCertificateQuerySet(models.QuerySet):
    """Custom QuerySet for CSD certificates."""

    def active(self) -> QuerySet[CSDCertificate]:
        """Get active certificates."""
        return self.filter(is_active=True)

    def valid(self) -> QuerySet[CSDCertificate]:
        """Get valid, non-expired certificates."""
        now = timezone.now()
        return self.filter(
            is_active=True,
            is_validated=True,
            valid_to__gt=now
        )

    def expiring_soon(self, days: int = 30) -> QuerySet[CSDCertificate]:
        """Get certificates expiring within specified days."""
        from datetime import timedelta
        cutoff = timezone.now() + timedelta(days=days)
        return self.filter(
            is_active=True,
            valid_to__lte=cutoff,
            valid_to__gt=timezone.now()
        )

    def with_pac_status(self) -> QuerySet[CSDCertificate]:
        """Include PAC upload status."""
        return self.filter(pac_uploaded=True)


class CSDCertificateManager(Manager):
    """Custom manager for CSD certificates."""

    def get_queryset(self) -> CSDCertificateQuerySet:
        return CSDCertificateQuerySet(self.model, using=self._db)

    def active(self) -> QuerySet[CSDCertificate]:
        return self.get_queryset().active()

    def valid(self) -> QuerySet[CSDCertificate]:
        return self.get_queryset().valid()


class CSDCertificate(TenantModel):
    """Store encrypted CSD certificates for tenants"""

    # File information - use secure storage
    certificate_file = models.FileField(
        upload_to='csd/certificates/',
        storage=get_tenant_csd_storage,
        max_length=500,
        null=True,
        blank=True
    )
    private_key_file = models.FileField(
        upload_to='csd/private_keys/',
        storage=get_tenant_csd_storage,
        max_length=500,
        null=True,
        blank=True
    )

    # Certificate metadata
    serial_number = models.CharField(max_length=100, unique=True)
    subject_name = models.CharField(max_length=255)
    issuer_name = models.CharField(max_length=255)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()

    # Encrypted certificate data (envelope encryption)
    encrypted_certificate = models.TextField()
    encrypted_private_key = models.TextField()
    encrypted_password = models.TextField()

    # Encryption metadata
    encryption_key_id = models.CharField(max_length=255)
    encryption_algorithm = models.CharField(max_length=50, default='AES-256-GCM')

    # Status
    is_active = models.BooleanField(default=True)
    is_validated = models.BooleanField(default=False)
    validation_error = models.TextField(blank=True)

    # Usage tracking
    last_used = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)

    # PAC integration tracking (FiscalAPI)
    pac_uploaded = models.BooleanField(default=False)
    pac_uploaded_at = models.DateTimeField(null=True, blank=True)
    pac_response = models.JSONField(default=dict, blank=True)
    pac_error = models.TextField(blank=True)

    objects = CSDCertificateManager()

    class Meta:
        db_table = 'csd_certificates'
        verbose_name = 'CSD Certificate'
        verbose_name_plural = 'CSD Certificates'
        indexes = [
            models.Index(fields=['tenant', 'is_active', 'valid_to']),
            models.Index(fields=['serial_number']),
            models.Index(fields=['tenant', 'pac_uploaded']),
            models.Index(fields=['valid_to']),
        ]

    def __str__(self) -> str:
        return f"CSD {self.serial_number} - {self.tenant.name}"

    @property
    def is_valid(self) -> bool:
        """Check if certificate is valid and not expired."""
        return (self.is_active and
                self.is_validated and
                self.valid_to > timezone.now())

    def mark_used(self) -> None:
        """Mark certificate as used (for tracking)."""
        self.last_used = timezone.now()
        self.usage_count += 1
        self.save(update_fields=['last_used', 'usage_count'])


class FileUploadQuerySet(models.QuerySet):
    """Custom QuerySet for file uploads."""

    def active(self) -> QuerySet[FileUpload]:
        """Get non-deleted uploads."""
        return self.exclude(status='deleted')

    def by_type(self, file_type: str) -> QuerySet[FileUpload]:
        """Filter by file type."""
        return self.filter(file_type=file_type)

    def by_session(self, session: str) -> QuerySet[FileUpload]:
        """Filter by upload session."""
        return self.filter(upload_session=session)

    def pending_processing(self) -> QuerySet[FileUpload]:
        """Get uploads pending processing."""
        return self.filter(status='uploaded')


class FileUploadManager(Manager):
    """Custom manager for file uploads."""

    def get_queryset(self) -> FileUploadQuerySet:
        return FileUploadQuerySet(self.model, using=self._db)

    def active(self) -> QuerySet[FileUpload]:
        return self.get_queryset().active()


class FileUpload(TenantModel):
    """Track file uploads with Dropzone"""

    # File information - use secure storage with tenant-specific paths
    file = models.FileField(
        upload_to='uploads/%Y/%m/%d/',
        storage=get_tenant_csd_storage,
        max_length=500
    )
    original_filename = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    content_type = models.CharField(max_length=255)

    # Upload metadata
    upload_token = models.UUIDField(default=uuid.uuid4, unique=True)
    upload_session = models.CharField(max_length=255, blank=True)

    # Processing status
    STATUS_CHOICES = [
        ('uploaded', 'Uploaded'),
        ('processing', 'Processing'),
        ('processed', 'Processed'),
        ('failed', 'Failed'),
        ('deleted', 'Deleted'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')

    # File type classification
    FILE_TYPE_CHOICES = [
        ('csd_certificate', 'CSD Certificate'),
        ('csd_private_key', 'CSD Private Key'),
        ('invoice_xml', 'Invoice XML'),
        ('invoice_pdf', 'Invoice PDF'),
        ('document', 'Document'),
        ('image', 'Image'),
        ('other', 'Other'),
    ]
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')

    # Processing metadata
    processing_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    objects = FileUploadManager()

    class Meta:
        db_table = 'file_uploads'
        verbose_name = 'File Upload'
        verbose_name_plural = 'File Uploads'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['upload_token']),
            models.Index(fields=['tenant', 'file_type', 'status']),
            models.Index(fields=['upload_session', 'status']),
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} ({self.get_file_type_display()})"

    @property
    def file_url(self) -> Optional[str]:
        """Get file URL for download."""
        if self.file:
            return self.file.url
        return None

    @property
    def is_image(self) -> bool:
        """Check if file is an image."""
        image_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        return self.content_type in image_types

    @property
    def is_pdf(self) -> bool:
        """Check if file is a PDF."""
        return self.content_type == 'application/pdf'

    @property
    def file_extension(self) -> str:
        """Get file extension."""
        import os
        return os.path.splitext(self.original_filename)[1].lower()

    def delete_file(self) -> None:
        """Delete the actual file and mark as deleted."""
        if self.file:
            try:
                default_storage.delete(self.file.name)
            except Exception:
                pass  # File might not exist
        self.status = 'deleted'
        self.save(update_fields=['status'])


class InvoiceQuerySet(models.QuerySet):
    """Custom QuerySet for invoices."""

    def stamped(self) -> QuerySet[Invoice]:
        """Get stamped invoices."""
        return self.filter(status='stamped')

    def draft(self) -> QuerySet[Invoice]:
        """Get draft invoices."""
        return self.filter(status='draft')

    def cancelled(self) -> QuerySet[Invoice]:
        """Get cancelled invoices."""
        return self.filter(status='cancelled')

    def by_customer(self, rfc: str) -> QuerySet[Invoice]:
        """Filter by customer RFC."""
        return self.filter(customer_rfc=rfc)

    def current_month(self) -> QuerySet[Invoice]:
        """Get invoices from current month."""
        from datetime import date
        today = date.today()
        return self.filter(
            created_at__year=today.year,
            created_at__month=today.month
        )

    def with_files(self) -> QuerySet[Invoice]:
        """Prefetch related files."""
        return self.select_related('tenant')



class Invoice(TenantModel, MetadataMixin):
    """CFDI 4.0 Invoices"""

    objects = CoreInvoiceQuerySet.as_manager()

    # Invoice identification
    folio = models.CharField(max_length=20)
    serie = models.CharField(max_length=10, blank=True)
    uuid = models.UUIDField(unique=True, null=True, blank=True)

    # Customer information
    customer_name = models.CharField(max_length=255)
    customer_rfc = models.CharField(max_length=13)
    customer_email = models.EmailField()
    customer_address = models.TextField(blank=True)

    # Invoice details
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='MXN')

    # CFDI specific
    payment_method = models.CharField(max_length=10, default='PUE')  # Pago en una sola exhibición
    payment_form = models.CharField(max_length=10, default='03')  # Transferencia electrónica
    cfdi_use = models.CharField(max_length=10, default='G03')  # Gastos en general

    # Status
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('stamped', 'Stamped'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
        ('error', 'Error'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    # Files
    xml_file = models.FileField(upload_to='invoices/xml/', null=True, blank=True)
    pdf_file = models.FileField(upload_to='invoices/pdf/', null=True, blank=True)

    # SAT timbrado
    stamped_at = models.DateTimeField(null=True, blank=True)
    pac_response = models.JSONField(default=dict, blank=True)

    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=255, blank=True)


    class Meta:
        db_table = 'invoices'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'
        ordering = ['-created_at']
        unique_together = ['tenant', 'serie', 'folio']
        indexes = [
            models.Index(fields=['tenant', 'status']),
            models.Index(fields=['customer_rfc']),
            models.Index(fields=['uuid']),
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['stamped_at']),
            models.Index(fields=['tenant', 'serie', 'folio']),
        ]

    def __str__(self) -> str:
        serie_folio = f"{self.serie}-{self.folio}" if self.serie else self.folio
        return f"Factura {serie_folio} - {self.customer_name}"

    @property
    def is_valid_for_cancellation(self) -> bool:
        """Check if invoice can be cancelled (within calendar month)."""
        if self.status != 'stamped' or not self.stamped_at:
            return False

        now = timezone.now()
        stamped_month = self.stamped_at.month
        stamped_year = self.stamped_at.year

        return (now.month == stamped_month and now.year == stamped_year)

    @property
    def serie_folio(self) -> str:
        """Get formatted serie-folio."""
        return f"{self.serie}-{self.folio}" if self.serie else self.folio

    def mark_stamped(self, uuid: str, pac_response: dict) -> None:
        """Mark invoice as stamped."""
        self.uuid = uuid
        self.status = 'stamped'
        self.stamped_at = timezone.now()
        self.pac_response = pac_response
        self.save(update_fields=['uuid', 'status', 'stamped_at', 'pac_response'])

    def mark_cancelled(self, reason: str = '') -> None:
        """Mark invoice as cancelled."""
        self.status = 'cancelled'
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])
