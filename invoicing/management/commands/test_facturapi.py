"""
Management command to test facturapi.io integration

Usage:
    python manage.py test_facturapi
    python manage.py test_facturapi --test-upload
"""
from django.core.management.base import BaseCommand
from invoicing.facturapi_service import facturapi_service
from core.models import Tenant
from invoicing.models import CSDCertificate


class Command(BaseCommand):
    help = 'Test facturapi.io integration'

    def add_arguments(self, parser):
        parser.add_argument('--test-connection', action='store_true')
        parser.add_argument('--test-organization', action='store_true')
        parser.add_argument('--test-upload', action='store_true')
        parser.add_argument('--tenant-id', type=str, help='Tenant ID')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n=== facturapi.io Integration Test ===\n'))

        tenant_id = options.get('tenant_id')
        if tenant_id:
            tenant = Tenant.objects.get(id=tenant_id)
        else:
            tenant = Tenant.objects.first()

        self.stdout.write(f'Using tenant: {tenant.name} (RFC: {tenant.rfc})\n')

        if not any([options['test_connection'], options['test_organization'], options['test_upload']]):
            options['test_connection'] = True
            options['test_organization'] = True

        if options['test_connection']:
            self.test_connection()

        if options['test_organization']:
            self.test_organization(tenant)

        if options['test_upload']:
            self.test_upload(tenant)

        self.stdout.write(self.style.SUCCESS('\n=== Tests completed ===\n'))

    def test_connection(self):
        self.stdout.write('\n--- Test 1: Connection ---')
        result = facturapi_service.test_connection()

        if result['success']:
            self.stdout.write(self.style.SUCCESS('✓ Connection successful'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ Connection failed: {result.get("error")}'))

    def test_organization(self, tenant):
        self.stdout.write('\n--- Test 2: Organization ---')
        org_id = facturapi_service._get_or_create_organization(tenant)

        if org_id:
            self.stdout.write(self.style.SUCCESS(f'✓ Organization: {org_id}'))
        else:
            self.stdout.write(self.style.ERROR('✗ Failed to get/create organization'))

    def test_upload(self, tenant):
        self.stdout.write('\n--- Test 3: Upload CSD ---')
        csd = CSDCertificate.objects.filter(tenant=tenant, is_active=True).first()

        if not csd:
            self.stdout.write(self.style.WARNING('⚠ No active CSD found'))
            return

        result = facturapi_service.upload_certificate(csd)

        if result['success']:
            self.stdout.write(self.style.SUCCESS(f'✓ Certificate uploaded: {result.get("organization_id")}'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ Upload failed: {result.get("error")}'))
