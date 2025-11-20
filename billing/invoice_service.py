"""
Subscription Invoice Service - Generate CFDI invoices for Kita subscriptions using FiscalAPI SDK.
"""
from __future__ import annotations
from typing import Dict, Any
from decimal import Decimal
import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.db import transaction

# Import FiscalAPI SDK
from fiscalapi import FiscalApiClient
from fiscalapi.models.common_models import FiscalApiSettings
from fiscalapi.models.fiscalapi_models import (
    Invoice,
    InvoiceIssuer,
    InvoiceRecipient,
    InvoiceItem,
    ItemTax
)

logger = logging.getLogger(__name__)


class SubscriptionInvoiceService:
    """Generate CFDI invoices for subscription payments using FiscalAPI SDK."""

    def __init__(self):
        """Initialize FiscalAPI client."""
        fiscal_settings = FiscalApiSettings(
            api_url=settings.FISCALAPI_URL,
            api_key=settings.FISCALAPI_API_KEY,
            tenant=settings.FISCALAPI_TENANT_KEY
        )
        self.client = FiscalApiClient(settings=fiscal_settings)

    @transaction.atomic
    def generate_invoice(
        self,
        billing_payment: Any,
        fiscal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate CFDI invoice for subscription payment using SDK.

        Args:
            billing_payment: BillingPayment instance
            fiscal_data: Dict with receptor fiscal data from form

        Returns:
            Dict with success, uuid, xml, pdf, or error
        """
        try:
            tenant = billing_payment.tenant

            # Validate
            if billing_payment.invoice_generated:
                raise ValueError("Este pago ya ha sido facturado")

            if billing_payment.status != 'completed':
                raise ValueError("Solo se pueden facturar pagos completados")

            # Calculate amounts
            total = Decimal(str(billing_payment.amount))
            subtotal = (total / Decimal('1.16')).quantize(Decimal('0.01'))
            iva_amount = (total - subtotal).quantize(Decimal('0.01'))

            logger.info(f"Creating invoice using SDK for payment {billing_payment.id}")

            # Get issuer with CSD from FiscalAPI
            issuer_id = self._get_issuer_with_csd()

            # Get or create recipient
            recipient_id = self._get_or_create_recipient_id(fiscal_data)

            # Build invoice using SDK models (BY REFERENCES)
            invoice = Invoice(
                series='SUBS',
                date=datetime.now(),
                type_code='I',
                currency_code='MXN',
                payment_form_code=fiscal_data.get('forma_pago', '03'),
                payment_method_code='PUE',
                expedition_zip_code=settings.KITA_CODIGO_POSTAL,
                export_code='01',
                # By reference - ONLY ID
                issuer=InvoiceIssuer(
                    id=issuer_id
                ),
                recipient=InvoiceRecipient(
                    id=recipient_id
                ),
                items=[
                    InvoiceItem(
                        item_sku='KITA-SUB-001',
                        item_code='81161700',
                        quantity=Decimal('1.0'),
                        unit_of_measurement_code='E48',
                        description=f"Suscripción Kita Pro - {billing_payment.billing_period_start.strftime('%B %Y')}",
                        unit_price=subtotal,
                        tax_object_code='02',
                        item_taxes=[
                            ItemTax(
                                tax_code='002',
                                tax_type_code='Tasa',
                                tax_rate=Decimal('0.160000'),
                                tax_flag_code='T'
                            )
                        ]
                    )
                ]
            )

            # Log what we're sending
            logger.info(f"SDK Invoice created - Series: {invoice.series}, Type: {invoice.type_code}")
            logger.info(f"Issuer: {invoice.issuer.tin}, Recipient: {invoice.recipient.tin}")

            # Create invoice via SDK
            result = self.client.invoices.create(invoice)

            logger.info(f"SDK response received: {result.succeeded}")

            # Log complete result for debugging
            logger.error(f"SDK RESULT: succeeded={result.succeeded}")
            logger.error(f"SDK RESULT: message={result.message}")
            logger.error(f"SDK RESULT: details={result.details}")
            logger.error(f"SDK RESULT: data={result.data}")

            if not result.succeeded:
                error_msg = f"{result.message}"
                if result.details:
                    error_msg += f" | {result.details}"
                if result.data:
                    error_msg += f" | Validation: {result.data}"

                logger.error(f"SDK error completo: {error_msg}")
                raise ValueError(error_msg)

            invoice_data = result.data

            # Update billing payment
            billing_payment.invoice_generated = True
            billing_payment.invoice_sent = True
            billing_payment.invoice_data = {
                'uuid': invoice_data.uuid,
                'fiscal_folio': getattr(invoice_data, 'consecutive', None),
                'issued_at': timezone.now().isoformat(),
                'series': invoice_data.series,
                'number': invoice_data.number,
                'total': str(invoice_data.total),
                'receptor_rfc': fiscal_data['rfc'],
                'receptor_name': fiscal_data['business_name'],
                'sdk_response': invoice_data.model_dump() if hasattr(invoice_data, 'model_dump') else {}
            }
            billing_payment.save()

            logger.info(f"✅ Invoice generated via SDK - UUID: {invoice_data.uuid}")

            return {
                'success': True,
                'uuid': invoice_data.uuid,
                'message': 'Factura generada exitosamente'
            }

        except Exception as e:
            logger.error(f"Error generating invoice via SDK: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Error generando factura: {str(e)}'
            }

    def _get_issuer_with_csd(self) -> str:
        """Find first issuer with CSD by checking tax-files."""
        from invoicing.fiscalapi_service import fiscalapi_service

        # Use REST API directly to get tax-files (más confiable)
        response = fiscalapi_service._make_request('GET', '/api/v4/tax-files', params={'limit': 100})

        tax_files = response.get('data', {}).get('items', [])
        logger.info(f"Found {len(tax_files)} tax files")

        # Group by personId
        by_person = {}
        for item in tax_files:
            person_id = item.get('personId')
            if person_id not in by_person:
                by_person[person_id] = []
            by_person[person_id].append(item)

        # Find first with 2+ files
        for person_id, files in by_person.items():
            if len(files) >= 2:
                rfc = files[0].get('tin')

                # Validate RFC exists
                if not rfc or rfc == 'None':
                    logger.warning(f"Skipping person {person_id}: no valid RFC in tax files")
                    continue

                logger.info(f"✅ Found issuer with CSD: {rfc} (person_id: {person_id}, files: {len(files)})")

                # Use this person even if GET fails (CSD exists in tax-files)
                return str(person_id)

        raise ValueError("No se encontró ningún emisor con CSD en FiscalAPI")

    def _get_or_create_recipient_id(self, fiscal_data: Dict[str, Any]) -> str:
        """Get or create recipient in FiscalAPI and return ID."""
        from invoicing.fiscalapi_service import fiscalapi_service

        rfc = fiscal_data['rfc']

        # Use existing method from fiscalapi_service
        customer_data = {
            'rfc': rfc,
            'business_name': fiscal_data['business_name'],
            'email': fiscal_data.get('email', ''),
            'postal_code': fiscal_data.get('codigo_postal', ''),
            'fiscal_regime': fiscal_data.get('fiscal_regime', ''),
            'cfdi_use': fiscal_data.get('uso_cfdi', ''),
        }

        recipient_id = fiscalapi_service._get_or_create_recipient(customer_data)
        logger.info(f"Recipient ID: {recipient_id}")
        return str(recipient_id)


# Global service instance
subscription_invoice_service = SubscriptionInvoiceService()
