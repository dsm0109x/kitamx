"""Tests for CFDI 4.0 invoicing and certificate management.

Tests CSD certificate handling, invoice generation, and SW integration.
"""
from __future__ import annotations
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock, Mock
import json
import uuid
import base64

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from core.test_utils import KitaTestCase
from .models import CSDCertificate, FileUpload, Invoice
from .services import (
    CSDEncryptionService,
    FileUploadService
)

User = get_user_model()


class CSDCertificateTestCase(KitaTestCase):
    """Test cases for CSD certificate management."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Update user to have onboarding completed
        self.user.onboarding_completed = True
        self.user.save()

    def test_csd_certificate_creation(self) -> None:
        """Test CSD certificate model creation."""
        csd = CSDCertificate.objects.create(
            tenant=self.tenant,
            serial_number='12345678901234567890',
            subject_name='Test Company SA de CV',
            issuer_name='SAT',
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=365),
            encrypted_certificate='encrypted_cert_data',
            encrypted_private_key='encrypted_key_data',
            encrypted_password='encrypted_password',
            encryption_key_id='key_id_123',
            is_active=True,
            is_validated=True
        )

        self.assertEqual(csd.serial_number, '12345678901234567890')
        self.assertTrue(csd.is_valid)
        self.assertFalse(csd.pac_uploaded)

    def test_csd_queryset_methods(self) -> None:
        """Test CSD certificate queryset methods."""
        # Create valid certificate
        valid_csd = CSDCertificate.objects.create(
            tenant=self.tenant,
            serial_number='valid123',
            subject_name='Valid Cert',
            issuer_name='SAT',
            valid_from=timezone.now() - timedelta(days=30),
            valid_to=timezone.now() + timedelta(days=335),
            encrypted_certificate='data',
            encrypted_private_key='data',
            encrypted_password='data',
            encryption_key_id='key',
            is_active=True,
            is_validated=True
        )

        # Create expired certificate
        expired_csd = CSDCertificate.objects.create(
            tenant=self.tenant,
            serial_number='expired123',
            subject_name='Expired Cert',
            issuer_name='SAT',
            valid_from=timezone.now() - timedelta(days=400),
            valid_to=timezone.now() - timedelta(days=35),
            encrypted_certificate='data',
            encrypted_private_key='data',
            encrypted_password='data',
            encryption_key_id='key',
            is_active=True,
            is_validated=True
        )

        # Test active queryset
        active_certs = CSDCertificate.objects.active()
        self.assertEqual(active_certs.count(), 2)

        # Test valid queryset
        valid_certs = CSDCertificate.objects.valid()
        self.assertEqual(valid_certs.count(), 1)
        self.assertEqual(valid_certs.first(), valid_csd)

        # Test expiring soon
        expiring = CSDCertificate.objects.expiring_soon(days=365)
        self.assertEqual(expiring.count(), 1)

    def test_csd_mark_used(self) -> None:
        """Test marking CSD as used."""
        csd = CSDCertificate.objects.create(
            tenant=self.tenant,
            serial_number='test123',
            subject_name='Test',
            issuer_name='SAT',
            valid_from=timezone.now(),
            valid_to=timezone.now() + timedelta(days=365),
            encrypted_certificate='data',
            encrypted_private_key='data',
            encrypted_password='data',
            encryption_key_id='key'
        )

        self.assertEqual(csd.usage_count, 0)
        self.assertIsNone(csd.last_used)

        csd.mark_used()

        self.assertEqual(csd.usage_count, 1)
        self.assertIsNotNone(csd.last_used)


class CSDEncryptionServiceTestCase(TestCase):
    """Test cases for CSD encryption service."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.service = CSDEncryptionService()

    @patch('invoicing.services.settings.MASTER_KEY_KEK_CURRENT', 'test_master_key_12345')
    def test_encrypt_decrypt_cycle(self) -> None:
        """Test encryption and decryption of CSD data."""
        cert_content = "-----BEGIN CERTIFICATE-----\ntest_certificate\n-----END CERTIFICATE-----"
        key_content = "-----BEGIN PRIVATE KEY-----\ntest_private_key\n-----END PRIVATE KEY-----"
        password = "test_password"

        # Encrypt data
        encrypted_data = self.service.encrypt_csd_data(
            cert_content, key_content, password
        )

        self.assertIn('encrypted_certificate', encrypted_data)
        self.assertIn('encrypted_private_key', encrypted_data)
        self.assertIn('encrypted_password', encrypted_data)
        self.assertIn('encryption_key_id', encrypted_data)

        # Create mock CSD certificate with encrypted data
        mock_csd = MagicMock()
        mock_csd.encrypted_certificate = encrypted_data['encrypted_certificate']
        mock_csd.encrypted_private_key = encrypted_data['encrypted_private_key']
        mock_csd.encrypted_password = encrypted_data['encrypted_password']
        mock_csd.encryption_key_id = encrypted_data['encryption_key_id']

        # Decrypt data
        decrypted_data = self.service.decrypt_csd_data(mock_csd)

        self.assertEqual(decrypted_data['certificate'], cert_content)
        self.assertEqual(decrypted_data['private_key'], key_content)
        self.assertEqual(decrypted_data['password'], password)

    def test_encrypt_binary_content(self) -> None:
        """Test encryption of binary certificate content."""
        cert_bytes = b'\x00\x01\x02\x03\x04\x05'
        key_bytes = b'\x06\x07\x08\x09\x0a\x0b'
        password = "test_password"

        encrypted_data = self.service.encrypt_csd_data(
            cert_bytes, key_bytes, password
        )

        self.assertIn('encrypted_certificate', encrypted_data)
        self.assertIn('encryption_algorithm', encrypted_data)
        self.assertEqual(encrypted_data['encryption_algorithm'], 'AES-256-GCM')


class FileUploadServiceTestCase(KitaTestCase):
    """Test cases for file upload service."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()
        self.service = FileUploadService(self.tenant)

    @patch('invoicing.services.save_csd_file')
    def test_process_upload(self, mock_save_file: Mock) -> None:
        """Test file upload processing."""
        mock_save_file.return_value = {
            'path': 'csd/test.cer',
            'url': '/media/csd/test.cer'
        }

        # Create mock uploaded file
        mock_file = MagicMock()
        mock_file.name = 'test.cer'
        mock_file.size = 1024
        mock_file.content_type = 'application/x-x509-ca-cert'

        result = self.service.process_upload(
            uploaded_file=mock_file,
            file_type='csd_certificate',
            upload_session='session123'
        )

        self.assertTrue(result['success'])
        self.assertIn('upload_token', result)
        self.assertEqual(result['filename'], 'test.cer')

        # Verify FileUpload was created
        upload = FileUpload.objects.get(upload_token=result['upload_token'])
        self.assertEqual(upload.tenant, self.tenant)
        self.assertEqual(upload.original_filename, 'test.cer')
        self.assertEqual(upload.file_type, 'csd_certificate')

    def test_delete_upload(self) -> None:
        """Test file upload deletion."""
        # Create test upload
        upload = FileUpload.objects.create(
            tenant=self.tenant,
            file='test.pdf',
            original_filename='test.pdf',
            file_size=1024,
            content_type='application/pdf',
            file_type='document'
        )

        result = self.service.delete_upload(str(upload.upload_token))

        self.assertTrue(result['success'])

        # Verify status updated
        upload.refresh_from_db()
        self.assertEqual(upload.status, 'deleted')


class InvoiceModelTestCase(KitaTestCase):
    """Test cases for Invoice model."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

    def test_invoice_creation(self) -> None:
        """Test invoice creation."""
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            serie='A',
            customer_name='Cliente Test',
            customer_rfc='XYZ010101XYZ',
            customer_email='cliente@test.com',
            subtotal=Decimal('100.00'),
            tax_amount=Decimal('16.00'),
            total=Decimal('116.00'),
            payment_method='PUE',
            payment_form='03',
            cfdi_use='G03'
        )

        self.assertEqual(invoice.serie_folio, 'A-001')
        self.assertEqual(invoice.status, 'draft')
        self.assertIsNone(invoice.uuid)

    def test_invoice_cancellation_validation(self) -> None:
        """Test invoice cancellation validation."""
        # Create stamped invoice
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            folio='002',
            customer_name='Test',
            customer_rfc='XYZ010101XYZ',
            customer_email='test@test.com',
            total=Decimal('100.00'),
            status='stamped',
            stamped_at=timezone.now()
        )

        # Should be valid for cancellation (same month)
        self.assertTrue(invoice.is_valid_for_cancellation)

        # Create old invoice
        old_invoice = Invoice.objects.create(
            tenant=self.tenant,
            folio='003',
            customer_name='Old',
            customer_rfc='XYZ010101XYZ',
            customer_email='old@test.com',
            total=Decimal('100.00'),
            status='stamped',
            stamped_at=timezone.now() - timedelta(days=35)
        )

        # Should not be valid (different month)
        self.assertFalse(old_invoice.is_valid_for_cancellation)

    def test_invoice_queryset_methods(self) -> None:
        """Test invoice queryset methods."""
        # Create invoices with different statuses
        draft = Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            customer_name='Draft',
            customer_rfc='RFC1',
            customer_email='draft@test.com',
            total=Decimal('100.00'),
            status='draft'
        )

        stamped = Invoice.objects.create(
            tenant=self.tenant,
            folio='002',
            customer_name='Stamped',
            customer_rfc='RFC2',
            customer_email='stamped@test.com',
            total=Decimal('200.00'),
            status='stamped'
        )

        cancelled = Invoice.objects.create(
            tenant=self.tenant,
            folio='003',
            customer_name='Cancelled',
            customer_rfc='RFC3',
            customer_email='cancelled@test.com',
            total=Decimal('300.00'),
            status='cancelled'
        )

        # Test queryset methods
        self.assertEqual(Invoice.objects.draft().count(), 1)
        self.assertEqual(Invoice.objects.stamped().count(), 1)
        self.assertEqual(Invoice.objects.cancelled().count(), 1)

        # Test by customer
        by_customer = Invoice.objects.by_customer('RFC2')
        self.assertEqual(by_customer.count(), 1)
        self.assertEqual(by_customer.first(), stamped)

    def test_mark_stamped(self) -> None:
        """Test marking invoice as stamped."""
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            customer_name='Test',
            customer_rfc='RFC1',
            customer_email='test@test.com',
            total=Decimal('100.00')
        )

        test_uuid = str(uuid.uuid4())
        pac_response = {'status': 'success', 'message': 'Timbrado exitoso'}

        invoice.mark_stamped(test_uuid, pac_response)

        self.assertEqual(invoice.status, 'stamped')
        self.assertEqual(str(invoice.uuid), test_uuid)
        self.assertIsNotNone(invoice.stamped_at)
        self.assertEqual(invoice.pac_response, pac_response)


class InvoiceViewsTestCase(KitaTestCase):
    """Test cases for invoice views."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Update user to have onboarding completed
        self.user.onboarding_completed = True
        self.user.save()

    def test_facturacion_index_view(self) -> None:
        """Test main invoicing page."""
        response = self.client.get(reverse('invoicing:index'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('stats', response.context)
        self.assertIn('tenant', response.context)

    def test_ajax_invoices_endpoint(self) -> None:
        """Test AJAX invoices DataTable endpoint."""
        # Create test invoices
        for i in range(5):
            Invoice.objects.create(
                tenant=self.tenant,
                folio=str(i+1),
                customer_name=f'Customer {i}',
                customer_rfc=f'RFC{i}',
                customer_email=f'customer{i}@test.com',
                total=Decimal(str((i+1) * 100)),
                status='draft' if i < 3 else 'stamped'
            )

        response = self.client.get(
            reverse('invoicing:ajax_invoices'),
            {
                'draw': 1,
                'start': 0,
                'length': 10,
                'search[value]': ''
            }
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['recordsTotal'], 5)
        self.assertEqual(len(data['data']), 5)

    def test_ajax_invoices_with_filters(self) -> None:
        """Test AJAX invoices with filters."""
        # Create invoices
        Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            customer_name='Test Customer',
            customer_rfc='TEST123',
            customer_email='test@test.com',
            total=Decimal('100.00'),
            status='stamped'
        )

        Invoice.objects.create(
            tenant=self.tenant,
            folio='002',
            customer_name='Another Customer',
            customer_rfc='ANOTHER456',
            customer_email='another@test.com',
            total=Decimal('200.00'),
            status='draft'
        )

        # Test with status filter
        response = self.client.get(
            reverse('invoicing:ajax_invoices'),
            {
                'draw': 1,
                'start': 0,
                'length': 10,
                'status': 'stamped',
                'search[value]': ''
            }
        )

        data = json.loads(response.content)
        self.assertEqual(data['recordsTotal'], 1)

    def test_ajax_invoice_stats(self) -> None:
        """Test invoice statistics endpoint."""
        # Create test invoices
        Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            customer_name='Test',
            customer_rfc='TEST123',
            customer_email='test@test.com',
            total=Decimal('100.00'),
            status='stamped'
        )

        Invoice.objects.create(
            tenant=self.tenant,
            folio='002',
            customer_name='Test2',
            customer_rfc='TEST456',
            customer_email='test2@test.com',
            total=Decimal('200.00'),
            status='cancelled'
        )

        response = self.client.get(reverse('invoicing:ajax_invoice_stats'))

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['stats']['total_invoices'], 2)
        self.assertEqual(data['stats']['total_amount'], 300.0)

    @patch('invoicing.views.FileUploadService')
    def test_file_upload_view(self, mock_service: Mock) -> None:
        """Test file upload endpoint."""
        mock_instance = mock_service.return_value
        mock_instance.process_upload.return_value = {
            'success': True,
            'upload_token': 'test-token',
            'filename': 'test.pdf'
        }

        file_content = b'test file content'
        test_file = SimpleUploadedFile('test.pdf', file_content)

        response = self.client.post(
            reverse('invoicing:upload_file'),
            {'file': test_file, 'file_type': 'document'},
            format='multipart'
        )

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])

    def test_export_invoices_csv(self) -> None:
        """Test invoice export to CSV."""
        # Create test invoice
        Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            serie='A',
            customer_name='Test Customer',
            customer_rfc='TEST123',
            customer_email='test@test.com',
            total=Decimal('116.00'),
            status='stamped',
            uuid=uuid.uuid4()
        )

        response = self.client.get(
            reverse('invoicing:export_invoices'),
            {'format': 'csv'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
