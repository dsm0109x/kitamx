"""
Test RFC validation from CSD certificate
Uso: python manage.py test_rfc_validation
"""
from django.core.management.base import BaseCommand

from core.models import Tenant
from invoicing.models import CSDCertificate
from invoicing.services import CSDEncryptionService
from invoicing.validators import CertificateHandler


class Command(BaseCommand):
    help = 'Test RFC extraction and validation from CSD certificate'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("🔍 RFC VALIDATION TEST"))
        self.stdout.write("="*70 + "\n")

        # Find tenant
        tenant = Tenant.objects.first()
        if not tenant:
            self.stdout.write(self.style.ERROR("❌ No tenants found"))
            return

        self.stdout.write(f"Tenant: {tenant.name}")
        self.stdout.write(f"Tenant RFC: {tenant.rfc}\n")

        # Find CSD
        csd = CSDCertificate.objects.filter(tenant=tenant).first()
        if not csd:
            self.stdout.write(self.style.ERROR("❌ No CSD certificates found"))
            return

        self.stdout.write(f"Certificate Serial: {csd.serial_number}")
        self.stdout.write(f"Certificate Subject: {csd.subject_name}\n")

        # Decrypt and load certificate
        self.stdout.write("🔓 Decrypting certificate...")
        encryption_service = CSDEncryptionService()
        decrypted_data = encryption_service.decrypt_csd_data(csd)

        cert_content = decrypted_data.get('certificate_bytes') or decrypted_data.get('certificate', '').encode()

        self.stdout.write("📜 Loading X.509 certificate...")
        certificate = CertificateHandler.load_certificate(cert_content)

        self.stdout.write("📋 Extracting certificate info...")
        cert_info = CertificateHandler.extract_certificate_info(certificate)

        self.stdout.write("\n" + "-"*70)
        self.stdout.write("CERTIFICATE INFORMATION:")
        self.stdout.write("-"*70)
        self.stdout.write(f"Serial Number: {cert_info['serial_number']}")
        self.stdout.write(f"Subject Name (CN): {cert_info['subject_name']}")
        self.stdout.write(f"Issuer Name (CN): {cert_info['issuer_name']}")
        self.stdout.write(f"Valid From: {cert_info['valid_from']}")
        self.stdout.write(f"Valid To: {cert_info['valid_to']}")

        # Show all subject attributes
        self.stdout.write("\nSUBJECT ATTRIBUTES:")
        for attr in cert_info['subject']:
            self.stdout.write(f"  {attr.oid.dotted_string} ({attr.oid._name}): {attr.value}")

        # RFC from certificate
        rfc_from_cert = cert_info.get('rfc')
        self.stdout.write(f"\n" + "-"*70)
        if rfc_from_cert:
            self.stdout.write(self.style.SUCCESS(f"✅ RFC EXTRACTED: {rfc_from_cert}"))
        else:
            self.stdout.write(self.style.WARNING("⚠️  RFC NOT FOUND in certificate"))

        # Validation
        self.stdout.write("\n" + "-"*70)
        self.stdout.write("VALIDATION:")
        self.stdout.write("-"*70)

        if rfc_from_cert:
            cert_rfc_clean = rfc_from_cert.strip().upper()
            tenant_rfc_clean = tenant.rfc.strip().upper()

            self.stdout.write(f"Tenant RFC:      {tenant_rfc_clean}")
            self.stdout.write(f"Certificate RFC: {cert_rfc_clean}")

            if cert_rfc_clean == tenant_rfc_clean:
                self.stdout.write(self.style.SUCCESS("\n✅ RFC MATCH - Certificate belongs to tenant!"))
            else:
                self.stdout.write(self.style.ERROR(f"\n❌ RFC MISMATCH!"))
                self.stdout.write(f"   Expected: {tenant_rfc_clean}")
                self.stdout.write(f"   Got:      {cert_rfc_clean}")
                self.stdout.write(f"\n⚠️  This certificate does NOT belong to {tenant.name}")
        else:
            self.stdout.write(self.style.WARNING("⚠️  Cannot validate - RFC not found in certificate"))
            self.stdout.write("   Check if RFC is in a different OID")

        self.stdout.write("\n" + "="*70 + "\n")
