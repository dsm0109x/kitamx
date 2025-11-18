"""
FiscalAPI Service - Modern PAC integration using official Python SDK
Replaces SmartWeb as primary PAC provider for CFDI 4.0
"""
from __future__ import annotations

import logging
import base64
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import FiscalAPI SDK only if available
try:
    import requests  # Fallback if SDK not installed yet
    FISCALAPI_SDK_AVAILABLE = False
except ImportError:
    FISCALAPI_SDK_AVAILABLE = False

from .services import CSDEncryptionService


class FiscalAPIServiceException(Exception):
    """Exception for FiscalAPI service errors"""
    pass


class FiscalAPIService:
    """
    FiscalAPI Integration - Official SDK wrapper for Kita

    Provides methods to:
    - Upload CSD certificates
    - Create/stamp CFDI invoices
    - Cancel CFDIs
    - Manage issuers (People)
    """

    def __init__(self):
        """Initialize FiscalAPI client with settings from Django config"""
        if not settings.FISCALAPI_API_KEY or not settings.FISCALAPI_TENANT_KEY:
            raise ValueError("FISCALAPI_API_KEY and FISCALAPI_TENANT_KEY must be configured in settings")

        self.api_url = settings.FISCALAPI_URL
        self.api_key = settings.FISCALAPI_API_KEY
        self.tenant_key = settings.FISCALAPI_TENANT_KEY
        self.timeout = settings.FISCALAPI_TIMEOUT

        logger.info(f"FiscalAPI: Client initialized for tenant {self.tenant_key[:8]}...")

    def _get_headers(self) -> Dict[str, str]:
        """Get standard headers for FiscalAPI requests"""
        return {
            'X-API-KEY': self.api_key,
            'X-TENANT-KEY': self.tenant_key,
            'Content-Type': 'application/json'
        }

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make HTTP request to FiscalAPI"""
        url = f"{self.api_url}{endpoint}"
        headers = self._get_headers()

        try:
            import requests

            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, timeout=self.timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Parse response
            if response.status_code in [200, 201]:
                return response.json()
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                raise FiscalAPIServiceException(
                    f"FiscalAPI error {response.status_code}: {error_data.get('message', response.text)}"
                )

        except requests.exceptions.Timeout:
            raise FiscalAPIServiceException("FiscalAPI timeout - intenta de nuevo")
        except requests.exceptions.ConnectionError:
            raise FiscalAPIServiceException("No se pudo conectar con FiscalAPI")
        except requests.exceptions.RequestException as e:
            raise FiscalAPIServiceException(f"Error de conexión: {str(e)}")

    def _get_or_create_issuer(self, tenant) -> str:
        """
        Get or create FiscalAPI Person (issuer) for Kita tenant.
        Returns FiscalAPI person_id.
        """
        # Check cache first
        cache_key = f"fiscalapi_issuer_{tenant.id}"
        cached_id = cache.get(cache_key)
        if cached_id:
            logger.info(f"FiscalAPI: Using cached issuer ID for {tenant.name}")
            return cached_id

        try:
            # Search for existing issuer by RFC
            logger.info(f"FiscalAPI: Searching for issuer with RFC {tenant.rfc}")
            response = self._make_request('GET', '/api/v4/people', params={'tin': tenant.rfc, 'limit': 1})

            # FiscalAPI response structure: {data: {items: [...], total: N}}
            items = response.get('data', {}).get('items', [])
            logger.info(f"FiscalAPI: Search response: succeeded={response.get('succeeded')}, items count={len(items)}")

            if items and len(items) > 0:
                # Log first person for debugging
                first_person = items[0]
                logger.info(f"FiscalAPI: First person in results: {first_person}")

                person_id = first_person.get('id')
                logger.info(f"FiscalAPI: Extracted person_id: {person_id} (type: {type(person_id)})")

                if not person_id:
                    raise FiscalAPIServiceException("Person ID not found in response")
                logger.info(f"FiscalAPI: Found existing issuer {person_id} for RFC {tenant.rfc}")
            else:
                # Create new issuer
                logger.info(f"FiscalAPI: Creating new issuer for {tenant.name}")
                person_data = {
                    'legalName': tenant.business_name,
                    'tin': tenant.rfc,
                    'email': tenant.email,
                    'satTaxRegimeId': self._map_fiscal_regime(tenant.fiscal_regime),
                    'postalCode': tenant.codigo_postal,
                    'isIssuer': True,
                }

                logger.info(f"FiscalAPI: Issuer data: {person_data}")
                new_person = self._make_request('POST', '/api/v4/people', data=person_data)
                logger.info(f"FiscalAPI: Create response: {new_person}")

                if not new_person.get('succeeded') or not new_person.get('data'):
                    raise FiscalAPIServiceException(f"Failed to create issuer: {new_person.get('message', 'Unknown error')}")

                person_id = new_person['data'].get('id')
                if not person_id:
                    raise FiscalAPIServiceException("Person ID not found in create response")

                logger.info(f"FiscalAPI: Created new issuer {person_id} for {tenant.name}")

            # Validate person_id
            if not person_id or person_id == 0:
                raise FiscalAPIServiceException(f"Invalid person_id: {person_id}")

            # Cache for 1 hour
            cache.set(cache_key, person_id, 3600)
            logger.info(f"FiscalAPI: Cached person_id {person_id}")
            return person_id

        except FiscalAPIServiceException as e:
            logger.error(f"FiscalAPI: Error managing issuer: {str(e)}")
            raise

    def _map_fiscal_regime(self, kita_regime: str) -> int:
        """Map Kita fiscal regime codes to FiscalAPI satTaxRegimeId"""
        # Map string code to integer ID
        try:
            return int(kita_regime)
        except (ValueError, TypeError):
            # Default to 612 if conversion fails
            logger.warning(f"Could not convert fiscal regime '{kita_regime}' to int, using default 612")
            return 612

    def upload_certificate(self, csd_certificate) -> Dict[str, Any]:
        """
        Upload CSD certificate to FiscalAPI.

        Args:
            csd_certificate: CSDCertificate model instance

        Returns:
            Dict with success status and details
        """
        logger.info(f"FiscalAPI: Uploading certificate for tenant {csd_certificate.tenant.name}")

        try:
            # Get or create issuer in FiscalAPI
            person_id = self._get_or_create_issuer(csd_certificate.tenant)
            tenant = csd_certificate.tenant

            logger.info(f"FiscalAPI: Person ID: {person_id}")

            # Decrypt CSD data
            encryption_service = CSDEncryptionService()
            decrypted_data = encryption_service.decrypt_csd_data(csd_certificate)

            logger.info(f"FiscalAPI: Decrypted data keys: {list(decrypted_data.keys())}")

            # Prepare files for upload (FiscalAPI expects base64)
            cert_content = decrypted_data.get('certificate_bytes') or decrypted_data.get('certificate', '').encode()
            key_content = decrypted_data.get('private_key_bytes') or decrypted_data.get('private_key', '').encode()
            password = decrypted_data['password']

            logger.info(f"FiscalAPI: cert_content type: {type(cert_content)}, length: {len(cert_content) if cert_content else 0}")
            logger.info(f"FiscalAPI: key_content type: {type(key_content)}, length: {len(key_content) if key_content else 0}")
            logger.info(f"FiscalAPI: password length: {len(password) if password else 0}")

            # Validate content before encoding
            if not cert_content or len(cert_content) == 0:
                raise FiscalAPIServiceException("Certificate content is empty")
            if not key_content or len(key_content) == 0:
                raise FiscalAPIServiceException("Private key content is empty")
            if not password:
                raise FiscalAPIServiceException("Password is empty")

            cert_b64 = base64.b64encode(cert_content).decode('utf-8')
            key_b64 = base64.b64encode(key_content).decode('utf-8')

            logger.info(f"FiscalAPI: Base64 encoding successful. Cert length: {len(cert_b64)}, Key length: {len(key_b64)}")

            logger.info(f"FiscalAPI: Uploading .cer file for tenant {tenant.name}")

            # STEP 1: Upload .cer file (fileType=0)
            try:
                cert_upload_payload = {
                    'personId': person_id,
                    'tin': tenant.rfc,
                    'base64File': cert_b64,
                    'fileType': 0,  # .cer certificate
                    'password': password
                }

                logger.info(f"FiscalAPI: Sending .cer upload request to /api/v4/tax-files")
                cert_response = self._make_request('POST', '/api/v4/tax-files', data=cert_upload_payload)
                logger.info(f"FiscalAPI: .cer response: {cert_response}")

                if not cert_response.get('succeeded'):
                    error_msg = cert_response.get('message', 'Unknown error')
                    error_details = cert_response.get('details', '')
                    raise FiscalAPIServiceException(f"Failed to upload .cer: {error_msg}. Details: {error_details}")

            except Exception as e:
                logger.error(f"FiscalAPI: Error uploading .cer file: {str(e)}")
                raise FiscalAPIServiceException(f"Error en upload de .cer: {str(e)}")

            logger.info(f"FiscalAPI: .cer uploaded successfully, uploading .key file")

            # STEP 2: Upload .key file (fileType=1)
            try:
                key_upload_payload = {
                    'personId': person_id,
                    'tin': tenant.rfc,
                    'base64File': key_b64,
                    'fileType': 1,  # .key private key
                    'password': password
                }

                logger.info(f"FiscalAPI: Sending .key upload request to /api/v4/tax-files")
                key_response = self._make_request('POST', '/api/v4/tax-files', data=key_upload_payload)
                logger.info(f"FiscalAPI: .key response: {key_response}")

                if not key_response.get('succeeded'):
                    error_msg = key_response.get('message', 'Unknown error')
                    error_details = key_response.get('details', '')
                    raise FiscalAPIServiceException(f"Failed to upload .key: {error_msg}. Details: {error_details}")

            except Exception as e:
                logger.error(f"FiscalAPI: Error uploading .key file: {str(e)}")
                raise FiscalAPIServiceException(f"Error en upload de .key: {str(e)}")

            logger.info(f"FiscalAPI: Both certificate files uploaded successfully")

            # Update certificate record
            csd_certificate.pac_uploaded = True
            csd_certificate.pac_uploaded_at = timezone.now()
            csd_certificate.pac_response = {
                'person_id': person_id,
                'cer_upload': cert_response.get('data', {}),
                'key_upload': key_response.get('data', {})
            }
            csd_certificate.pac_error = ''
            csd_certificate.save()

            logger.info(f"FiscalAPI: Certificate uploaded successfully for {csd_certificate.tenant.name}")

            return {
                'success': True,
                'message': 'Certificado subido exitosamente a FiscalAPI',
                'person_id': person_id,
                'data': {
                    'cer_upload': cert_response.get('data'),
                    'key_upload': key_response.get('data')
                }
            }

        except FiscalAPIServiceException as e:
            error_msg = str(e)
            logger.error(f"FiscalAPI: Certificate upload failed: {error_msg}")

            # Update certificate with error
            csd_certificate.pac_uploaded = False
            csd_certificate.pac_error = error_msg
            csd_certificate.save()

            return {
                'success': False,
                'message': f'Error subiendo certificado: {error_msg}',
                'error': error_msg
            }
        except Exception as e:
            error_msg = str(e)
            logger.error(f"FiscalAPI: Unexpected error: {error_msg}")

            csd_certificate.pac_uploaded = False
            csd_certificate.pac_error = error_msg
            csd_certificate.save()

            return {
                'success': False,
                'message': f'Error inesperado: {error_msg}',
                'error': error_msg
            }

    def _get_or_create_recipient(self, customer_data: Dict[str, Any]) -> str:
        """
        Get or create FiscalAPI recipient (customer who receives invoice).

        Args:
            customer_data: Dict with customer fiscal data:
                - rfc: Customer RFC
                - business_name: Legal name
                - email: Contact email
                - postal_code: Fiscal address CP
                - fiscal_regime: Tax regime (optional)
                - cfdi_use: CFDI usage (optional)

        Returns:
            FiscalAPI person_id for the recipient
        """
        rfc = customer_data.get('rfc')
        email = customer_data.get('email')

        # Check cache first
        cache_key = f"fiscalapi_recipient_{rfc}"
        cached_id = cache.get(cache_key)
        if cached_id:
            logger.info(f"FiscalAPI: Using cached recipient ID for RFC {rfc}")
            return cached_id

        try:
            # Search for existing recipient by RFC
            logger.info(f"FiscalAPI: Searching for recipient with RFC {rfc}")
            response = self._make_request('GET', '/api/v4/people', params={'tin': rfc, 'limit': 1})

            items = response.get('data', {}).get('items', [])
            logger.info(f"FiscalAPI: Recipient search response: items count={len(items)}")

            if items and len(items) > 0:
                person_id = items[0].get('id')
                if person_id:
                    logger.info(f"FiscalAPI: Found existing recipient {person_id} for RFC {rfc}")
                    cache.set(cache_key, person_id, 3600)
                    return person_id

            # Create new recipient
            logger.info(f"FiscalAPI: Creating new recipient for RFC {rfc}")
            recipient_data = {
                'legalName': customer_data.get('business_name'),
                'tin': rfc,
                'email': email,
                'password': 'TempPass123!',  # Required but not used by recipient
                'isIssuer': False,  # Receptor, no emisor
            }

            # Add optional fields if provided
            if customer_data.get('postal_code'):
                recipient_data['postalCode'] = customer_data['postal_code']

            if customer_data.get('fiscal_regime'):
                recipient_data['satTaxRegimeId'] = self._map_fiscal_regime(customer_data['fiscal_regime'])

            if customer_data.get('cfdi_use'):
                recipient_data['satCfdiUseId'] = customer_data['cfdi_use']

            logger.info(f"FiscalAPI: Recipient data: {recipient_data}")
            new_person = self._make_request('POST', '/api/v4/people', data=recipient_data)

            if not new_person.get('succeeded') or not new_person.get('data'):
                raise FiscalAPIServiceException(f"Failed to create recipient: {new_person.get('message', 'Unknown error')}")

            person_id = new_person['data'].get('id')
            if not person_id:
                raise FiscalAPIServiceException("Person ID not found in create response")

            logger.info(f"FiscalAPI: Created new recipient {person_id} for RFC {rfc}")

            # Cache for 1 hour
            cache.set(cache_key, person_id, 3600)
            return person_id

        except FiscalAPIServiceException as e:
            logger.error(f"FiscalAPI: Error managing recipient: {str(e)}")
            raise

    def create_invoice(self, invoice_data: Dict[str, Any], tenant) -> Dict[str, Any]:
        """
        Create and stamp invoice using FiscalAPI by references.

        This is the recommended method for FiscalAPI.

        Args:
            invoice_data: Invoice data with:
                - payment: Payment amount
                - customer: Customer fiscal data (rfc, name, email, etc.)
                - items: List of invoice items/concepts
            tenant: Kita Tenant instance

        Returns:
            Dict with success, uuid, xml, pdf
        """
        try:
            # Get or create issuer (tenant)
            issuer_id = self._get_or_create_issuer(tenant)

            # Get or create recipient (customer)
            recipient_id = self._get_or_create_recipient(invoice_data['customer'])

            logger.info(f"FiscalAPI: Creating invoice - Issuer: {issuer_id}, Recipient: {recipient_id}")

            # Prepare invoice payload for FiscalAPI
            fiscal_invoice = {
                'issuerId': issuer_id,
                'recipientId': recipient_id,
                'paymentMethod': invoice_data.get('payment_method', 'PUE'),
                'paymentForm': invoice_data.get('payment_form', '01'),  # Efectivo
                'items': invoice_data.get('items', []),
                'currency': invoice_data.get('currency', 'MXN'),
            }

            logger.info(f"FiscalAPI: Invoice payload prepared")

            # Create invoice via FiscalAPI
            response = self._make_request('POST', '/api/v4/invoices', data=fiscal_invoice)

            if not response.get('succeeded'):
                raise FiscalAPIServiceException(f"Failed to create invoice: {response.get('message', 'Unknown error')}")

            invoice_response = response.get('data', {})

            logger.info(f"FiscalAPI: Invoice created successfully")

            return {
                'success': True,
                'uuid': invoice_response.get('uuid'),
                'xml': invoice_response.get('xml'),
                'pdf': invoice_response.get('pdf'),
                'data': invoice_response,
                'message': 'Factura creada y timbrada exitosamente'
            }

        except FiscalAPIServiceException as e:
            logger.error(f"FiscalAPI: Invoice creation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Error creando factura: {str(e)}'
            }

    def stamp_cfdi(self, cfdi_data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Stamp CFDI using FiscalAPI by references.

        This method now uses create_invoice() which is the recommended FiscalAPI approach.

        Args:
            cfdi_data: CFDI data structure (will be converted to FiscalAPI format)
            tenant_id: Tenant ID

        Returns:
            Dict with success, uuid, xml, pdf
        """
        try:
            # Get tenant
            from core.models import Tenant
            tenant = Tenant.objects.get(id=tenant_id)

            # Convert cfdi_data to FiscalAPI format
            # cfdi_data ya viene con la estructura necesaria de InvoiceGenerationService

            invoice_data = {
                'customer': {
                    'rfc': cfdi_data.get('Receptor', {}).get('Rfc'),
                    'business_name': cfdi_data.get('Receptor', {}).get('Nombre'),
                    'email': cfdi_data.get('customer_email'),  # Added by our system
                    'postal_code': cfdi_data.get('Receptor', {}).get('DomicilioFiscalReceptor'),
                    'fiscal_regime': cfdi_data.get('Receptor', {}).get('RegimenFiscalReceptor'),
                    'cfdi_use': cfdi_data.get('Receptor', {}).get('UsoCFDI'),
                },
                'items': cfdi_data.get('Conceptos', []),
                'payment_method': cfdi_data.get('FormaPago', 'PUE'),
                'payment_form': cfdi_data.get('MetodoPago', '01'),
                'currency': cfdi_data.get('Moneda', 'MXN'),
            }

            return self.create_invoice(invoice_data, tenant)

        except Exception as e:
            logger.error(f"FiscalAPI: Error in stamp_cfdi: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Error al timbrar CFDI: {str(e)}'
            }

    def cancel_cfdi(self, uuid: str, rfc: str, tenant_id: str) -> Dict[str, Any]:
        """
        Cancel CFDI invoice using FiscalAPI
        """
        try:
            # Find invoice by UUID
            # FiscalAPI endpoint: DELETE /api/v4/invoices/{id}
            # Or specific cancel endpoint if exists

            cancel_data = {
                'uuid': uuid,
                'reason': '02'  # Comprobante emitido con errores
            }

            # Placeholder - adjust based on actual FiscalAPI cancel endpoint
            response = self._make_request('DELETE', f'/api/v4/invoices/{uuid}', data=cancel_data)

            return {
                'success': True,
                'uuid': uuid,
                'status': 'cancelled',
                'data': response,
                'message': 'Factura cancelada exitosamente'
            }

        except FiscalAPIServiceException as e:
            logger.error(f"FiscalAPI: Cancellation failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Error cancelando factura: {str(e)}'
            }

    def test_connection(self) -> Dict[str, Any]:
        """Test FiscalAPI connection and authentication"""
        try:
            # Test by listing people (should work if authenticated)
            response = self._make_request('GET', '/api/v4/people', params={'limit': 1})

            logger.info("FiscalAPI: Connection test successful")
            return {
                'success': True,
                'message': 'Conexión con FiscalAPI exitosa',
                'tenant': self.tenant_key[:8] + '...',
                'data': response
            }

        except FiscalAPIServiceException as e:
            logger.error(f"FiscalAPI: Connection test failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Error conectando con FiscalAPI: {str(e)}'
            }
        except Exception as e:
            logger.error(f"FiscalAPI: Unexpected connection error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Error inesperado: {str(e)}'
            }


# Singleton instance
fiscalapi_service = FiscalAPIService()
