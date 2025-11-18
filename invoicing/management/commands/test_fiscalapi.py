"""
Django management command para probar FiscalAPI
Uso: python manage.py test_fiscalapi
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from invoicing.fiscalapi_service import fiscalapi_service
from core.models import Tenant
from invoicing.models import CSDCertificate


class Command(BaseCommand):
    help = 'Test FiscalAPI connection and certificate upload'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("🧪 FISCALAPI DIAGNOSTIC TEST"))
        self.stdout.write("="*70 + "\n")

        # Test 1: Connection
        self.stdout.write("\n1️⃣  Testing connection...")
        result = fiscalapi_service.test_connection()
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"   ✅ {result.get('message')}"))
        else:
            self.stdout.write(self.style.ERROR(f"   ❌ {result.get('error')}"))
            return

        # Test 2: Find tenant
        self.stdout.write("\n2️⃣  Finding tenant...")
        tenant = Tenant.objects.first()
        if not tenant:
            self.stdout.write(self.style.ERROR("   ❌ No tenants found"))
            return

        self.stdout.write(self.style.SUCCESS(f"   ✅ Found: {tenant.name}"))
        self.stdout.write(f"      RFC: {tenant.rfc}")
        self.stdout.write(f"      Email: {tenant.email}")
        self.stdout.write(f"      Fiscal Regime: {tenant.fiscal_regime}")

        # Test 3: Find CSD
        self.stdout.write("\n3️⃣  Finding CSD certificate...")
        csd = CSDCertificate.objects.filter(tenant=tenant).first()
        if not csd:
            self.stdout.write(self.style.ERROR("   ❌ No CSD certificates found"))
            return

        self.stdout.write(self.style.SUCCESS(f"   ✅ Found: {csd.serial_number}"))
        self.stdout.write(f"      Valid until: {csd.valid_to}")
        self.stdout.write(f"      PAC uploaded: {csd.pac_uploaded}")
        self.stdout.write(f"      Is active: {csd.is_active}")

        # Test 4: Get/Create Issuer
        self.stdout.write("\n4️⃣  Testing Get/Create Issuer...")
        try:
            person_id = fiscalapi_service._get_or_create_issuer(tenant)
            self.stdout.write(self.style.SUCCESS(f"   ✅ Person ID: {person_id}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Error: {str(e)}"))
            return

        # Test 5: Upload Certificate
        self.stdout.write("\n5️⃣  Testing Certificate Upload...")
        self.stdout.write("   (Check logs above for detailed output)")
        self.stdout.write("\n" + "-"*70)

        result = fiscalapi_service.upload_certificate(csd)

        self.stdout.write("-"*70 + "\n")

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"   ✅ SUCCESS: {result.get('message')}"))
            self.stdout.write(f"      Person ID: {result.get('person_id')}")

            # Refresh from DB
            csd.refresh_from_db()
            self.stdout.write(f"      pac_uploaded: {csd.pac_uploaded}")
            self.stdout.write(f"      pac_uploaded_at: {csd.pac_uploaded_at}")
        else:
            self.stdout.write(self.style.ERROR(f"   ❌ FAILED: {result.get('message')}"))
            self.stdout.write(f"      Error: {result.get('error')}")

        self.stdout.write("\n" + "="*70 + "\n")
