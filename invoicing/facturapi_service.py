"""
facturapi.io Service - Modern PAC integration for CFDI 4.0
Official replacement for FiscalAPI in Kita

Documentation: https://docs.facturapi.io/en/api/
"""
from __future__ import annotations

import logging
import base64
import requests
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class FacturapiServiceException(Exception):
    """Exception for facturapi.io service errors"""
    pass


class FacturapiService:
    """
    facturapi.io Integration for Kita

    Provides methods to:
    - Upload CSD certificates to Organizations
    - Create/stamp CFDI invoices
    - Cancel CFDIs
    - Manage organizations

    API Docs: https://docs.facturapi.io/en/api/
    """

    def __init__(self):
        """Initialize facturapi.io client with settings from Django config"""
        if not settings.FACTURAPI_USER_KEY:
            raise ValueError("FACTURAPI_USER_KEY must be configured in settings")

        self.api_url = settings.FACTURAPI_URL
        self.user_key = settings.FACTURAPI_USER_KEY  # For organization management
        self.api_key = settings.FACTURAPI_API_KEY  # For invoice operations (optional)
        self.timeout = settings.FACTURAPI_TIMEOUT

        logger.info("facturapi.io: Client initialized")

    def _get_headers(self, include_content_type: bool = True, use_user_key: bool = True) -> Dict[str, str]:
        """
        Get standard headers for facturapi.io requests

        Args:
            include_content_type: Whether to include Content-Type header
                                 (False for multipart uploads)
            use_user_key: Whether to use User Key (for org management) or API Key (for invoices)

        Returns:
            Dict of HTTP headers
        """
        # Use User Key for organization management, API Key for invoices
        auth_key = self.user_key if use_user_key else (self.api_key or self.user_key)

        headers = {
            'Authorization': f'Bearer {auth_key}'
        }

        if include_content_type:
            headers['Content-Type'] = 'application/json'

        return headers

    def _make_request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None,
        use_user_key: bool = True
    ) -> Dict[str, Any]:
        """
        Make HTTP request to facturapi.io

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/organizations')
            json: JSON payload for request body
            data: Form data payload
            files: Files for multipart upload
            params: Query parameters

        Returns:
            Parsed response data

        Raises:
            FacturapiServiceException: On request errors
        """
        url = f"{self.api_url}{endpoint}"

        # Headers (no Content-Type if multipart upload)
        headers = self._get_headers(include_content_type=(files is None), use_user_key=use_user_key)

        try:
            if method.upper() == 'GET':
                response = requests.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout
                )
            elif method.upper() == 'POST':
                response = requests.post(
                    url,
                    headers=headers,
                    json=json,
                    data=data,
                    files=files,
                    timeout=self.timeout
                )
            elif method.upper() == 'PUT':
                response = requests.put(
                    url,
                    headers=headers,
                    json=json,
                    data=data,
                    files=files,
                    timeout=self.timeout
                )
            elif method.upper() == 'DELETE':
                response = requests.delete(
                    url,
                    headers=headers,
                    json=json,
                    timeout=self.timeout
                )
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Parse response based on content type
            if response.status_code in [200, 201]:
                content_type = response.headers.get('content-type', '')

                if 'application/json' in content_type:
                    return response.json()
                elif 'application/xml' in content_type or 'text/xml' in content_type:
                    return {'xml': response.text}
                elif 'application/pdf' in content_type:
                    return {'pdf': response.content}
                else:
                    return {'data': response.text}
            else:
                # Parse error response
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {'message': response.text}

                raise FacturapiServiceException(
                    f"facturapi.io error {response.status_code}: {error_data.get('message', 'Unknown error')}"
                )

        except requests.exceptions.Timeout:
            raise FacturapiServiceException("facturapi.io timeout - intenta de nuevo")
        except requests.exceptions.ConnectionError:
            raise FacturapiServiceException("No se pudo conectar con facturapi.io")
        except requests.exceptions.RequestException as e:
            raise FacturapiServiceException(f"Error de conexión: {str(e)}")

    def _make_request_with_key(
        self,
        method: str,
        endpoint: str,
        api_key: str,
        json: Optional[Dict] = None,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request with specific API key (for organization-specific operations).

        This is used when we need to use an organization's Live Key instead of
        the global User Key.

        Args:
            method: HTTP method
            endpoint: API endpoint
            api_key: Specific API key to use (Live Key)
            ... (rest same as _make_request)

        Returns:
            Parsed response data
        """
        url = f"{self.api_url}{endpoint}"

        headers = {
            'Authorization': f'Bearer {api_key}'
        }

        if files is None:
            headers['Content-Type'] = 'application/json'

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=json, data=data, files=files, timeout=self.timeout)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=json, data=data, files=files, timeout=self.timeout)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, json=json, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Parse response
            if response.status_code in [200, 201]:
                content_type = response.headers.get('content-type', '')

                if 'application/json' in content_type:
                    return response.json()
                elif 'application/xml' in content_type or 'text/xml' in content_type:
                    return {'xml': response.text}
                elif 'application/pdf' in content_type:
                    return {'pdf': response.content}
                else:
                    return {'data': response.text}
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {'message': response.text}

                raise FacturapiServiceException(
                    f"facturapi.io error {response.status_code}: {error_data.get('message', 'Unknown error')}"
                )

        except requests.exceptions.Timeout:
            raise FacturapiServiceException("facturapi.io timeout - intenta de nuevo")
        except requests.exceptions.ConnectionError:
            raise FacturapiServiceException("No se pudo conectar con facturapi.io")
        except requests.exceptions.RequestException as e:
            raise FacturapiServiceException(f"Error de conexión: {str(e)}")

    # ===================
    # PUBLIC METHODS
    # ===================

    def test_connection(self) -> Dict[str, Any]:
        """
        Test connection to facturapi.io

        Returns:
            {
                'success': bool,
                'message': str
            }
        """
        try:
            response = self._make_request('GET', '/organizations', params={'limit': 1})

            logger.info("facturapi.io connection test: SUCCESS")

            return {
                'success': True,
                'message': 'Conexión exitosa con facturapi.io',
                'data': response
            }
        except Exception as e:
            logger.error(f"facturapi.io connection test failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Error de conexión con facturapi.io'
            }

    def upload_certificate(self, csd_certificate) -> Dict[str, Any]:
        """
        Upload CSD certificate to facturapi.io Organization

        Flow:
        1. Get or create Organization for tenant
        2. Decrypt CSD certificate data
        3. Upload .cer + .key files in one multipart request
        4. Update CSD record with organization_id

        Args:
            csd_certificate: CSDCertificate model instance

        Returns:
            {
                'success': bool,
                'organization_id': str,
                'serial_number': str,
                'message': str,
                'data': {...}  # Raw facturapi.io response
            }
        """
        try:
            tenant = csd_certificate.tenant

            logger.info(f"Uploading CSD certificate for tenant {tenant.name} to facturapi.io")

            # 1. Get or create Organization
            logger.info(f"Getting or creating organization for tenant {tenant.name} (RFC: {tenant.rfc})")
            org_id = self._get_or_create_organization(tenant)
            logger.info(f"Organization ID obtained: {org_id}")

            if not org_id:
                logger.error("Failed to get organization_id from _get_or_create_organization")
                return {
                    'success': False,
                    'error': 'Failed to create/get organization',
                    'message': 'Error creando organización en facturapi.io'
                }

            # 2. Decrypt certificate data
            from .services import CSDEncryptionService
            encryption_service = CSDEncryptionService()
            decrypted_data = encryption_service.decrypt_csd_data(csd_certificate)

            # 3. Prepare multipart upload
            files = {
                'cer': (
                    'certificate.cer',
                    decrypted_data['certificate_bytes'],
                    'application/octet-stream'
                ),
                'key': (
                    'privatekey.key',
                    decrypted_data['private_key_bytes'],
                    'application/octet-stream'
                ),
            }

            data = {
                'password': decrypted_data['password']
            }

            # 4. Update legal/fiscal data BEFORE uploading certificate
            logger.info(f"Updating legal data for organization {org_id}")

            legal_payload = {
                'name': tenant.business_name or tenant.name,
                'legal_name': tenant.business_name or tenant.name,
                'tax_system': tenant.fiscal_regime or '601',
                'phone': tenant.phone or '',
                'address': {
                    'street': tenant.calle or '',
                    'exterior': tenant.numero_exterior or '',
                    'interior': tenant.numero_interior or '',
                    'neighborhood': tenant.colonia or '',
                    'city': tenant.municipio or '',
                    'municipality': tenant.municipio or '',
                    'zip': tenant.codigo_postal or '00000',
                    'state': tenant.estado or ''
                }
            }

            try:
                logger.info(f"Attempting to update legal data for org_id: {org_id}")
                logger.info(f"Legal payload: {legal_payload}")
                self._make_request('PUT', f'/organizations/{org_id}/legal', json=legal_payload)
                logger.info(f"Legal data updated successfully for organization {org_id}")
            except Exception as legal_error:
                logger.error(f"Legal data update failed: {legal_error}")
                logger.error(f"org_id was: {org_id}")
                # Continue with certificate upload even if legal update fails

            # 5. Upload CSD certificate to facturapi.io
            endpoint = f'/organizations/{org_id}/certificate'
            logger.info(f"Uploading CSD to facturapi.io: PUT {endpoint}")

            cert_response = self._make_request('PUT', endpoint, files=files, data=data)

            # 6. Update CSD record with facturapi.io data
            csd_certificate.pac_response = {
                'provider': 'facturapi',
                'organization_id': org_id,
                'uploaded_at': timezone.now().isoformat(),
                'response': cert_response
            }
            csd_certificate.pac_uploaded = True
            csd_certificate.save(update_fields=['pac_response', 'pac_uploaded'])

            logger.info(f"Certificate uploaded successfully to facturapi.io for tenant {tenant.name}")

            return {
                'success': True,
                'organization_id': org_id,
                'serial_number': csd_certificate.serial_number,
                'data': cert_response,
                'message': 'Certificado subido exitosamente a facturapi.io'
            }

        except Exception as e:
            logger.error(f"facturapi.io certificate upload error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Error subiendo certificado: {str(e)}'
            }

    def stamp_cfdi(self, cfdi_data: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """
        Create and stamp CFDI invoice via facturapi.io

        Flow:
        1. Transform cfdi_data (Kita format) → facturapi.io format
        2. POST /v2/invoices to create and stamp
        3. Download XML and PDF
        4. Return in format compatible with existing code

        Args:
            cfdi_data: CFDI data in Kita format (same as FiscalAPI)
            tenant_id: Tenant UUID string

        Returns:
            {
                'success': bool,
                'uuid': str,            # SAT UUID
                'xml': str,             # Base64 encoded XML
                'pdf': str,             # Base64 encoded PDF
                'data': {...}           # Raw facturapi.io response
            }
        """
        try:
            from core.models import Tenant
            tenant = Tenant.objects.get(id=tenant_id)

            logger.info(f"Stamping CFDI for tenant {tenant.name} via facturapi.io")

            # 1. Get organization_id from tenant
            if not tenant.pac_integration_data or 'facturapi' not in tenant.pac_integration_data:
                raise ValueError("Organization not configured for tenant. Upload CSD first.")

            org_id = tenant.pac_integration_data['facturapi'].get('organization_id')

            if not org_id:
                raise ValueError("Organization ID not found. Upload CSD first.")

            # 2. Get or create Live Key for this organization (TRANSPARENT)
            live_key = self._get_or_create_live_key(org_id, tenant)

            if not live_key:
                raise ValueError("Could not obtain Live API Key for organization")

            logger.info(f"Using Live Key for organization {org_id[:20]}...")

            # 3. Transform cfdi_data (Kita format) → facturapi.io format
            facturapi_payload = self._transform_cfdi_data(cfdi_data, tenant)

            # 4. Create invoice with organization-specific Live Key
            logger.info(f"Creating invoice in facturapi.io: POST /invoices")
            response = self._make_request_with_key('POST', '/invoices', live_key, json=facturapi_payload)

            invoice_id = response['id']
            uuid = response['uuid']

            logger.info(f"Invoice created in facturapi.io: {uuid} (id: {invoice_id})")

            # 5. Download XML (use Live Key)
            xml_response = self._make_request_with_key('GET', f'/invoices/{invoice_id}/xml', live_key)
            xml_content = xml_response['xml']

            # 6. Download PDF (use Live Key)
            pdf_response = self._make_request_with_key('GET', f'/invoices/{invoice_id}/pdf', live_key)
            pdf_content = pdf_response['pdf']

            # 5. Encode to base64 (for compatibility with existing code)
            xml_base64 = base64.b64encode(xml_content.encode('utf-8')).decode('utf-8')
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

            logger.info(f"CFDI stamped successfully: {uuid}")

            return {
                'success': True,
                'uuid': uuid,
                'xml': xml_base64,
                'pdf': pdf_base64,
                'data': response
            }

        except Exception as e:
            logger.error(f"facturapi.io stamp_cfdi error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Error timbrando CFDI: {str(e)}'
            }

    def cancel_cfdi(self, uuid: str, rfc: str, tenant_id: str) -> Dict[str, Any]:
        """
        Cancel CFDI invoice in facturapi.io

        Flow:
        1. Find invoice_id by UUID
        2. DELETE /v2/invoices/{invoice_id} with cancellation motive
        3. Return cancellation receipt

        Args:
            uuid: CFDI UUID to cancel
            rfc: Tenant RFC (not used by facturapi.io but kept for compatibility)
            tenant_id: Tenant UUID (not used but kept for compatibility)

        Returns:
            {
                'success': bool,
                'cancellation_receipt': str,
                'message': str
            }
        """
        try:
            logger.info(f"Cancelling CFDI {uuid} via facturapi.io")

            # 1. Find invoice_id by UUID
            invoice_id = self._get_invoice_id_by_uuid(uuid)

            if not invoice_id:
                return {
                    'success': False,
                    'error': f'Invoice not found: {uuid}',
                    'message': 'Factura no encontrada en facturapi.io'
                }

            # 2. Cancel invoice (use Live Key)
            payload = {
                'motive': '02'  # Comprobante emitido con errores sin relación
            }

            logger.info(f"Cancelling invoice in facturapi.io: DELETE /invoices/{invoice_id}")
            response = self._make_request('DELETE', f'/invoices/{invoice_id}', json=payload, use_user_key=False)

            logger.info(f"Invoice cancelled successfully: {uuid}")

            return {
                'success': True,
                'cancellation_receipt': response.get('cancellation_receipt'),
                'data': response,
                'message': 'CFDI cancelado exitosamente'
            }

        except Exception as e:
            logger.error(f"facturapi.io cancel_cfdi error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Error cancelando CFDI: {str(e)}'
            }

    def create_invoice(self, invoice_data: Dict[str, Any], tenant) -> Dict[str, Any]:
        """
        Wrapper compatibility method - delegates to stamp_cfdi

        This method exists for compatibility with code that might call
        create_invoice directly (used internally by FiscalAPI).

        Args:
            invoice_data: Invoice data
            tenant: Tenant instance

        Returns:
            Same as stamp_cfdi
        """
        return self.stamp_cfdi(invoice_data, str(tenant.id))

    def delete_certificate(self, organization_id: str) -> Dict[str, Any]:
        """
        Delete CSD certificate from facturapi.io organization

        Endpoint: DELETE /v2/organizations/{organization_id}/certificate

        Args:
            organization_id: facturapi.io organization ID

        Returns:
            {
                'success': bool,
                'message': str
            }
        """
        try:
            logger.info(f"Deleting CSD certificate from organization {organization_id}")

            endpoint = f'/organizations/{organization_id}/certificate'
            response = self._make_request('DELETE', endpoint)

            logger.info(f"✅ Certificate deleted from facturapi.io: {organization_id}")

            return {
                'success': True,
                'message': 'Certificado eliminado de facturapi.io',
                'data': response
            }

        except Exception as e:
            logger.error(f"facturapi.io certificate deletion error: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Error eliminando certificado de facturapi.io: {str(e)}'
            }

    # ===================
    # PRIVATE HELPERS
    # ===================

    def _get_or_create_organization(self, tenant) -> Optional[str]:
        """
        Get or create Organization in facturapi.io for tenant

        SECURITY: Never searches by RFC to prevent certificate hijacking.
        Only trusts tenant.pac_integration_data as source of truth.

        Flow:
        1. Check cache (tenant-specific)
        2. Check tenant.pac_integration_data (our record)
        3. Create new organization (never search by RFC)

        Args:
            tenant: Tenant instance

        Returns:
            organization_id (string) or None if error
        """
        # 1. Check cache
        cache_key = f'facturapi_org_{tenant.id}'
        org_id = cache.get(cache_key)

        if org_id:
            logger.debug(f"Organization found in cache: {org_id}")
            return org_id

        # 2. Check tenant.pac_integration_data (ONLY source of truth)
        if hasattr(tenant, 'pac_integration_data') and tenant.pac_integration_data:
            facturapi_data = tenant.pac_integration_data.get('facturapi', {})
            org_id = facturapi_data.get('organization_id')

            if org_id:
                logger.debug(f"Organization found in tenant data: {org_id}")
                cache.set(cache_key, org_id, 3600)
                return org_id

        # SECURITY FIX: NEVER search by RFC in facturapi.io
        # Reasoning:
        # - Attacker could register with victim's RFC
        # - Search would find victim's organization
        # - Attacker would reuse victim's CSD certificates
        # - This is a CRITICAL security vulnerability
        #
        # Solution: ONLY trust tenant.pac_integration_data
        # If not found, always CREATE new organization

        logger.info(f"No organization found for tenant {tenant.name}, creating new")

        # 3. Create new organization (always, never search)
        try:
            logger.info(f"Creating new organization for tenant {tenant.name}")

            # Step 1: Create organization with just name
            create_payload = {
                'name': tenant.business_name or tenant.name  # Commercial name (required)
            }

            response = self._make_request('POST', '/organizations', json=create_payload)
            org_id = response['id']

            logger.info(f"Organization created successfully: {org_id}")

            # NOTE: Fiscal data and certificate upload will be done separately
            # when uploading CSD certificate via upload_certificate() method

            # Save to tenant
            if not hasattr(tenant, 'pac_integration_data') or not tenant.pac_integration_data:
                tenant.pac_integration_data = {}

            tenant.pac_integration_data['facturapi'] = {
                'organization_id': org_id,
                'created_at': timezone.now().isoformat()
            }
            tenant.save(update_fields=['pac_integration_data'])

            cache.set(cache_key, org_id, 3600)

            return org_id

        except Exception as e:
            logger.error(f"Error creating organization: {e}", exc_info=True)
            return None

    def _transform_cfdi_data(self, cfdi_data: Dict[str, Any], tenant) -> Dict[str, Any]:
        """
        Transform CFDI data from Kita format to facturapi.io format

        IMPORTANT: In Kita format, we define Emisor and Receptor.
        In facturapi.io, we only send 'customer' (the receptor).
        facturapi.io automatically uses the organization as emisor.

        Kita format:
        {
            "Emisor": {...},      # Who issues (Kita for subscriptions, tenant for payment links)
            "Receptor": {...},    # Who receives (tenant for subscriptions, end customer for links)
            "Conceptos": [...]
        }

        facturapi.io format:
        {
            "customer": {...},    # Always the receptor
            "items": [...]
        }

        Args:
            cfdi_data: Kita CFDI structure
            tenant: Tenant instance (can be emisor OR receptor depending on invoice type)

        Returns:
            facturapi.io invoice payload
        """
        # Extract data from Kita format
        emisor = cfdi_data.get('Emisor', {})
        receptor = cfdi_data.get('Receptor', {})
        conceptos = cfdi_data.get('Conceptos', [])

        # Determine who is the customer (receptor) for facturapi.io
        # facturapi.io always uses the authenticated organization as emisor
        # So we ALWAYS send receptor as customer, regardless of who it is

        # Build facturapi.io payload
        payload = {
            'customer': {
                'legal_name': receptor.get('Nombre'),
                'tax_id': receptor.get('Rfc'),
                'tax_system': receptor.get('RegimenFiscalReceptor', '601'),
                'email': cfdi_data.get('customer_email') or receptor.get('email'),
                'address': {
                    'zip': receptor.get('DomicilioFiscalReceptor', '00000')
                }
            },
            'items': [],
            'payment_form': cfdi_data.get('FormaPago', '03'),
            'use': receptor.get('UsoCFDI', 'G03')
        }

        # Transform items/conceptos
        for concepto in conceptos:
            item = {
                'quantity': float(concepto.get('Cantidad', 1)),
                'product': {
                    'description': concepto.get('Descripcion', 'Servicio'),
                    'product_key': concepto.get('ClaveProdServ', '84111506'),
                    'price': float(concepto.get('ValorUnitario', 0)),
                    'unit_key': concepto.get('ClaveUnidad', 'E48'),
                    'unit_name': concepto.get('Unidad', 'Servicio'),
                }
            }

            # Add taxes if present
            impuestos = concepto.get('Impuestos', {})
            traslados = impuestos.get('Traslados', [])

            if traslados:
                item['product']['taxes'] = []
                for traslado in traslados:
                    item['product']['taxes'].append({
                        'type': 'IVA',
                        'rate': float(traslado.get('TasaOCuota', 0.16))
                    })

            payload['items'].append(item)

        return payload

    def _get_invoice_id_by_uuid(self, uuid: str) -> Optional[str]:
        """
        Get facturapi.io invoice ID by UUID

        Strategy:
        1. Try from database (Invoice.pac_response)
        2. Try search API (GET /invoices?q=uuid:...)

        Args:
            uuid: CFDI UUID

        Returns:
            invoice_id (string) or None
        """
        # 1. Try from database
        from .models import Invoice

        try:
            invoice = Invoice.objects.get(uuid=uuid)

            if invoice.pac_response:
                # Check if it's facturapi response
                facturapi_data = invoice.pac_response.get('data', {})
                invoice_id = facturapi_data.get('id')

                if invoice_id:
                    logger.debug(f"Invoice ID found in database: {invoice_id}")
                    return invoice_id
        except Invoice.DoesNotExist:
            pass

        # 2. Try search API
        try:
            logger.info(f"Searching invoice by UUID: {uuid}")
            response = self._make_request('GET', '/invoices', params={'q': f'uuid:{uuid}', 'limit': 1})

            if response.get('data') and len(response['data']) > 0:
                invoice_id = response['data'][0]['id']
                logger.info(f"Invoice ID found via search: {invoice_id}")
                return invoice_id
        except Exception as e:
            logger.error(f"Error searching invoice by UUID: {e}")

        logger.warning(f"Invoice ID not found for UUID: {uuid}")
        return None


    def _get_or_create_live_key(self, organization_id: str, tenant) -> Optional[str]:
        """
        Get or create Live API Key for organization (transparent to user).

        This method ensures each tenant's organization has its own Live Key
        for creating invoices. The process is automatic and transparent.

        Flow:
        1. Check tenant.pac_integration_data
        2. Check cache
        3. Generate new Live Key from facturapi.io
        4. Save and cache

        Args:
            organization_id: facturapi.io organization ID
            tenant: Tenant instance

        Returns:
            live_key (string) or None if error
        """
        # 1. Check tenant data
        if hasattr(tenant, 'pac_integration_data') and tenant.pac_integration_data:
            facturapi_data = tenant.pac_integration_data.get('facturapi', {})
            live_key = facturapi_data.get('live_key')

            if live_key and live_key.startswith('sk_live_'):
                logger.debug(f"Live Key found in tenant data for org {organization_id}")
                return live_key

        # 2. Check cache
        cache_key = f'facturapi_live_key_{organization_id}'
        live_key = cache.get(cache_key)

        if live_key:
            logger.debug(f"Live Key found in cache for org {organization_id}")
            return live_key

        # 3. Generate new Live Key
        try:
            logger.info(f"Generating Live Key for organization {organization_id}")

            response = self._make_request(
                'PUT',
                f'/organizations/{organization_id}/apikeys/live',
                use_user_key=True  # User Key to manage org
            )

            # Response is plain string: "sk_live_XXXXX..."
            live_key = response if isinstance(response, str) else response.get('key', response)

            if not live_key or not str(live_key).startswith('sk_live_'):
                raise ValueError(f"Invalid Live Key format received: {live_key}")

            logger.info(f"✅ Live Key generated for organization {organization_id}")

            # 4. Save to tenant
            if not hasattr(tenant, 'pac_integration_data') or not tenant.pac_integration_data:
                tenant.pac_integration_data = {}
            if 'facturapi' not in tenant.pac_integration_data:
                tenant.pac_integration_data['facturapi'] = {}

            tenant.pac_integration_data['facturapi']['live_key'] = live_key
            tenant.pac_integration_data['facturapi']['live_key_generated_at'] = timezone.now().isoformat()
            tenant.save(update_fields=['pac_integration_data'])

            # 5. Cache
            cache.set(cache_key, live_key, 3600)  # 1 hour

            return live_key

        except Exception as e:
            logger.error(f"Error generating Live Key for org {organization_id}: {e}", exc_info=True)
            return None


# Singleton instance (same pattern as fiscalapi_service)
facturapi_service = FacturapiService()
