from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import uuid
from datetime import datetime


class SecureCSDStorage(S3Boto3Storage):
    """Secure storage for CSD files with custom paths and encryption"""

    def __init__(self, *args, **kwargs):
        kwargs.update({
            'bucket_name': settings.AWS_STORAGE_BUCKET_NAME,
            'access_key': settings.AWS_ACCESS_KEY_ID,
            'secret_key': settings.AWS_SECRET_ACCESS_KEY,
            'endpoint_url': settings.AWS_S3_ENDPOINT_URL,
            'region_name': settings.AWS_S3_REGION_NAME,
            'default_acl': 'private',
            'file_overwrite': False,
            'object_parameters': {
                'ServerSideEncryption': 'AES256',
                'CacheControl': 'no-cache, no-store, must-revalidate',
                'ContentDisposition': 'attachment',
            }
        })
        super().__init__(*args, **kwargs)

    def get_object_parameters(self, name):
        """Custom object parameters for CSD files"""
        params = super().get_object_parameters(name)

        # Add encryption and security headers for CSD files
        if 'csd/' in name or 'certificates/' in name or 'private_keys/' in name:
            params.update({
                'ServerSideEncryption': 'AES256',
                'CacheControl': 'no-cache, no-store, must-revalidate',
                'ContentDisposition': 'attachment',
                'Metadata': {
                    'file-type': 'csd-sensitive',
                    'uploaded-at': datetime.utcnow().isoformat(),
                }
            })

        return params


class TenantCSDStorage(SecureCSDStorage):
    """Storage for CSD files with tenant-specific paths"""

    def generate_filename(self, name):
        """Generate secure filename with tenant isolation"""
        # Extract file extension
        import os
        _, ext = os.path.splitext(name)

        # Generate unique filename with UUID
        unique_name = f"{uuid.uuid4().hex}{ext}"

        return unique_name

    def get_csd_path(self, tenant_id, file_type, filename):
        """Generate secure path for CSD files"""
        timestamp = datetime.now().strftime('%Y/%m/%d')

        if file_type == 'csd_certificate':
            return f"tenants/{tenant_id}/csd/certificates/{timestamp}/{filename}"
        elif file_type == 'csd_private_key':
            return f"tenants/{tenant_id}/csd/private_keys/{timestamp}/{filename}"
        else:
            return f"tenants/{tenant_id}/uploads/{timestamp}/{filename}"


def get_tenant_csd_storage():
    """Get storage instance for CSD files"""
    return TenantCSDStorage()


def save_csd_file(tenant_id, uploaded_file, file_type):
    """Save CSD file with secure path and encryption"""
    storage = get_tenant_csd_storage()

    # Generate secure filename
    secure_filename = storage.generate_filename(uploaded_file.name)

    # Generate secure path
    secure_path = storage.get_csd_path(tenant_id, file_type, secure_filename)

    # Save file with encryption
    saved_path = storage.save(secure_path, uploaded_file)

    return {
        'path': saved_path,
        'url': storage.url(saved_path),
        'secure_filename': secure_filename
    }