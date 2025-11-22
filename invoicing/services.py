from __future__ import annotations

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from django.conf import settings
from .models import FileUpload
from .validators import validate_csd_files, CertificateHandler, CSDValidationError
import logging

logger = logging.getLogger(__name__)


class CSDEncryptionService:
    """Service for encrypting/decrypting CSD certificates using envelope encryption"""

    def __init__(self):
        self.master_key = settings.MASTER_KEY_KEK_CURRENT.encode()

    def _generate_data_key(self):
        """Generate a data encryption key"""
        return Fernet.generate_key()

    def _encrypt_data_key(self, data_key):
        """Encrypt data key with master key"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'kita_salt_2024',  # Use a fixed salt for KEK
            iterations=100000,
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        fernet = Fernet(fernet_key)
        return fernet.encrypt(data_key)

    def _decrypt_data_key(self, encrypted_data_key):
        """Decrypt data key with master key"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'kita_salt_2024',
            iterations=100000,
        )
        fernet_key = base64.urlsafe_b64encode(kdf.derive(self.master_key))
        fernet = Fernet(fernet_key)
        return fernet.decrypt(encrypted_data_key)

    def encrypt_csd_data(self, certificate_content, private_key_content, password):
        """Encrypt CSD certificate data using envelope encryption"""
        try:
            # Generate data encryption key
            data_key = self._generate_data_key()
            data_fernet = Fernet(data_key)

            # Convert content to bytes if needed
            if isinstance(certificate_content, str):
                cert_bytes = certificate_content.encode()
            else:
                cert_bytes = certificate_content

            if isinstance(private_key_content, str):
                key_bytes = private_key_content.encode()
            else:
                key_bytes = private_key_content

            if isinstance(password, str):
                password_bytes = password.encode()
            else:
                password_bytes = password

            # Encrypt the actual data
            encrypted_certificate = data_fernet.encrypt(cert_bytes)
            encrypted_private_key = data_fernet.encrypt(key_bytes)
            encrypted_password = data_fernet.encrypt(password_bytes)

            # Encrypt the data key with master key
            encrypted_data_key = self._encrypt_data_key(data_key)

            return {
                'encrypted_certificate': base64.b64encode(encrypted_certificate).decode(),
                'encrypted_private_key': base64.b64encode(encrypted_private_key).decode(),
                'encrypted_password': base64.b64encode(encrypted_password).decode(),
                'encryption_key_id': base64.b64encode(encrypted_data_key).decode(),
                'encryption_algorithm': 'AES-256-GCM'
            }

        except Exception as e:
            logger.error(f"Error encrypting CSD data: {str(e)}")
            raise ValueError(f"Error al cifrar datos CSD: {str(e)}")

    def decrypt_csd_data(self, csd_certificate):
        """Decrypt CSD certificate data"""
        try:
            # Decrypt the data key
            encrypted_data_key = base64.b64decode(csd_certificate.encryption_key_id.encode())
            data_key = self._decrypt_data_key(encrypted_data_key)
            data_fernet = Fernet(data_key)

            # Decrypt the actual data
            certificate_data = base64.b64decode(csd_certificate.encrypted_certificate.encode())
            private_key_data = base64.b64decode(csd_certificate.encrypted_private_key.encode())
            password_data = base64.b64decode(csd_certificate.encrypted_password.encode())

            # Decrypt as bytes first
            decrypted_certificate_bytes = data_fernet.decrypt(certificate_data)
            decrypted_private_key_bytes = data_fernet.decrypt(private_key_data)
            decrypted_password = data_fernet.decrypt(password_data).decode()

            # Handle both DER (binary) and PEM (text) formats
            try:
                # Try to decode as UTF-8 (PEM format)
                decrypted_certificate = decrypted_certificate_bytes.decode('utf-8')
                decrypted_private_key = decrypted_private_key_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # Binary DER format - convert to base64 directly
                decrypted_certificate = base64.b64encode(decrypted_certificate_bytes).decode()
                decrypted_private_key = base64.b64encode(decrypted_private_key_bytes).decode()

            return {
                'certificate': decrypted_certificate,
                'private_key': decrypted_private_key,
                'password': decrypted_password,
                'certificate_bytes': decrypted_certificate_bytes,
                'private_key_bytes': decrypted_private_key_bytes
            }

        except Exception as e:
            logger.error(f"Error decrypting CSD data: {str(e)}")
            raise ValueError(f"Error al descifrar datos CSD: {str(e)}")


class CSDValidationService:
    """Service for validating CSD certificates"""

    def validate_certificate_files(self, cert_content, key_content, password,
                                   tenant_rfc=None, tenant_business_name=None):
        """
        Validate CSD certificate and private key files.

        Args:
            cert_content: Certificate file content
            key_content: Private key file content
            password: Private key password
            tenant_rfc: Optional RFC to validate against certificate
        """
        try:
            # Use centralized validation functions
            certificate, private_key = validate_csd_files(cert_content, key_content, password)

            # Extract certificate information using centralized handler
            cert_info = CertificateHandler.extract_certificate_info(certificate)

            # Validate business_name if provided
            if tenant_business_name and cert_info.get('subject_name'):
                self._validate_business_name(tenant_business_name, cert_info['subject_name'])

            # Validate RFC if tenant_rfc provided
            if tenant_rfc and cert_info.get('rfc'):
                cert_rfc = cert_info['rfc'].strip().upper()
                tenant_rfc_clean = tenant_rfc.strip().upper()

                logger.info(f"Validating RFC: Tenant={tenant_rfc_clean}, Certificate={cert_rfc}")

                if cert_rfc != tenant_rfc_clean:
                    raise ValueError(
                        f"El RFC del certificado ({cert_rfc}) no coincide con el RFC de tu empresa ({tenant_rfc_clean}). "
                        f"Verifica que el certificado pertenezca a tu RFC."
                    )

                logger.info(f"✅ RFC validation passed: {cert_rfc}")
            elif tenant_rfc and not cert_info.get('rfc'):
                logger.warning(f"⚠️ Could not extract RFC from certificate for validation")

            # Continue with existing validations...

            # Validate that it's a valid SAT certificate
            sat_issuers = [
                "AC AUTORIDAD CERTIFICADORA DEL SERVICIO DE ADMINISTRACION TRIBUTARIA",
                "AUTORIDAD CERTIFICADORA DEL SERVICIO DE ADMINISTRACION TRIBUTARIA",
                "AC SAT",
                "SAT970701NN3",
                "SERVICIO DE ADMINISTRACION TRIBUTARIA"
            ]

            # Get additional issuer info for SAT validation
            issuer_org = ""
            for attribute in cert_info['issuer']:
                if attribute.oid.dotted_string == "2.5.4.10":  # O (Organization)
                    issuer_org = attribute.value
                    break

            # Combine issuer name and organization for better matching
            full_issuer_info = f"{cert_info['issuer_name']} {issuer_org}".strip()
            is_sat_cert = any(issuer.upper() in full_issuer_info.upper() for issuer in sat_issuers)

            logger.info(f"Certificate issuer CN: {cert_info['issuer_name']}")
            logger.info(f"Certificate issuer O: {issuer_org}")
            logger.info(f"Full issuer info: {full_issuer_info}")
            logger.info(f"Is SAT certificate: {is_sat_cert}")

            if not is_sat_cert:
                raise ValueError(f"El certificado no es válido para facturación. Debe ser emitido por el SAT. Emisor encontrado: {full_issuer_info}")

            # Check expiration (handle timezone-aware comparison)
            from django.utils import timezone as django_timezone
            from datetime import timezone as dt_timezone

            valid_from = cert_info['valid_from']
            valid_to = cert_info['valid_to']

            # Make dates timezone-aware if they aren't
            if valid_from.tzinfo is None:
                valid_from = django_timezone.make_aware(valid_from, dt_timezone.utc)

            if valid_to.tzinfo is None:
                valid_to = django_timezone.make_aware(valid_to, dt_timezone.utc)

            current_time = django_timezone.now()

            if valid_to < current_time:
                raise ValueError(f"El certificado ha expirado el {valid_to.strftime('%d/%m/%Y')}")

            if valid_from > current_time:
                raise ValueError(f"El certificado aún no es válido. Será válido desde el {valid_from.strftime('%d/%m/%Y')}")

            return {
                'valid': True,
                'serial_number': cert_info['serial_number'],
                'subject_name': cert_info['subject_name'],
                'issuer_name': cert_info['issuer_name'],
                'valid_from': valid_from,
                'valid_to': valid_to,
                'certificate_pem': cert_content,
                'private_key_pem': key_content
            }

        except CSDValidationError as e:
            # Re-raise CSDValidationError as ValueError for backward compatibility
            raise ValueError(str(e))
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Error validating CSD: {str(e)}")
            raise ValueError(f"Error validando certificado: {str(e)}")

    def _validate_business_name(self, tenant_business_name: str, cert_subject_name: str):
        """Validate that tenant business name matches certificate subject name."""
        import re
        import unicodedata
        from difflib import SequenceMatcher

        # Extract CN from subject
        match = re.search(r'CN=([^,]+)', cert_subject_name)
        subject_cn = match.group(1).strip() if match else cert_subject_name

        logger.info(f"Validating business name: Certificate='{subject_cn}' vs Tenant='{tenant_business_name}'")

        # Normalize
        def normalize(name):
            name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
            name = name.lower()
            name = re.sub(r'\b(s\.?a\.?|de\s+c\.?v\.?|s\.?c\.?)\b', '', name)
            name = re.sub(r'[^\w\s]', '', name)
            return ' '.join(name.split()).strip()

        similarity = SequenceMatcher(None, normalize(subject_cn), normalize(tenant_business_name)).ratio()

        if similarity < 0.85:
            raise ValueError(
                f"La razón social del certificado ({subject_cn}) no coincide "
                f"con la registrada ({tenant_business_name})."
            )

        logger.info(f"✅ Business name validation passed ({similarity:.0%})")


class FileUploadService:
    """Service for handling file uploads with Dropzone"""

    def __init__(self, tenant):
        self.tenant = tenant

    def process_upload(self, uploaded_file, file_type='other', upload_session=None):
        """Process a file upload from Dropzone using secure storage"""
        try:
            from core.storage import save_csd_file
            import os

            # BUG FIX #22: Validate file type server-side
            ALLOWED_EXTENSIONS = {
                'csd_certificate': ['.cer', '.pem', '.crt', '.der'],
                'csd_private_key': ['.key', '.pem'],
                'invoice_xml': ['.xml'],
                'invoice_pdf': ['.pdf'],
                'document': ['.pdf', '.doc', '.docx', '.txt'],
                'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            }

            # Extract file extension
            filename = uploaded_file.name
            ext = os.path.splitext(filename)[1].lower()

            # Validate extension if file_type is specified
            if file_type in ALLOWED_EXTENSIONS:
                if not ext or ext not in ALLOWED_EXTENSIONS[file_type]:
                    allowed = ', '.join(ALLOWED_EXTENSIONS[file_type])
                    raise ValueError(f"Tipo de archivo no permitido para {file_type}. Permitidos: {allowed}. Recibido: {ext or 'sin extensión'}")

            # BUG FIX #23: Validate file size server-side
            MAX_SIZE = 10 * 1024 * 1024  # 10MB
            file_size = getattr(uploaded_file, 'size', 0)

            if file_size > MAX_SIZE:
                raise ValueError(f"Archivo muy grande: {file_size / (1024*1024):.1f}MB. Máximo permitido: 10MB")

            if file_size == 0:
                raise ValueError("El archivo está vacío")

            # Save file using secure storage
            storage_result = save_csd_file(
                tenant_id=str(self.tenant.id),
                uploaded_file=uploaded_file,
                file_type=file_type
            )

            # Clean content type to ensure it fits in field
            content_type = getattr(uploaded_file, 'content_type', None) or 'application/octet-stream'
            if len(content_type) > 255:
                content_type = content_type[:255]

            # Create FileUpload record with secure path
            file_upload = FileUpload.objects.create(
                tenant=self.tenant,
                file=storage_result['path'],
                original_filename=uploaded_file.name,
                file_size=getattr(uploaded_file, 'size', 0),
                content_type=content_type,
                file_type=file_type,
                upload_session=upload_session or '',
                status='uploaded'
            )

            logger.info(f"File securely uploaded: {uploaded_file.name} to {storage_result['path']} for tenant {self.tenant.name}")

            return {
                'success': True,
                'file_id': str(file_upload.id),
                'upload_token': str(file_upload.upload_token),
                'filename': file_upload.original_filename,
                'size': file_upload.file_size,
                'url': storage_result['url'],
                'secure_path': storage_result['path']
            }

        except Exception as e:
            logger.error(f"Error processing secure upload: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_upload(self, upload_token):
        """Delete a file upload by token"""
        try:
            file_upload = FileUpload.objects.get(
                tenant=self.tenant,
                upload_token=upload_token
            )
            file_upload.delete_file()

            logger.info(f"File deleted: {file_upload.original_filename}")
            return {'success': True}

        except FileUpload.DoesNotExist:
            return {'success': False, 'error': 'Archivo no encontrado'}
        except Exception as e:
            logger.error(f"Error deleting file: {str(e)}")
            return {'success': False, 'error': str(e)}

    def get_uploads_by_session(self, upload_session):
        """Get all uploads for a session"""
        return FileUpload.objects.filter(
            tenant=self.tenant,
            upload_session=upload_session,
            status__in=['uploaded', 'processing', 'processed']
        ).order_by('-created_at')

    def get_uploads_by_type(self, file_type):
        """Get all uploads of a specific type"""
        return FileUpload.objects.filter(
            tenant=self.tenant,
            file_type=file_type,
            status__in=['uploaded', 'processing', 'processed']
        ).order_by('-created_at')

