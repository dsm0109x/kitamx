"""
Subscription Invoice Service - Generate CFDI invoices for Kita subscriptions using facturapi.io.

Kita (RFC: SAHM661127B26) factura sus suscripciones a los tenants.
Migrado de FiscalAPI a facturapi.io.
"""
from __future__ import annotations
from typing import Dict, Any
from decimal import Decimal
import logging

from django.conf import settings
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)


class SubscriptionInvoiceService:
    """Generate CFDI invoices for subscription payments using facturapi.io."""

    def __init__(self):
        """Initialize - uses pac_factory."""
        pass

    @transaction.atomic
    def generate_invoice(
        self,
        billing_payment: Any,
        fiscal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate CFDI invoice for subscription payment.

        Emisor: Kita (SAHM661127B26)
        Receptor: Tenant (quien paga la suscripción)

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

            logger.info(f"Creating invoice via facturapi.io for payment {billing_payment.id}")

            # Build CFDI data in Kita format
            cfdi_data = {
                "Version": "4.0",
                "FormaPago": fiscal_data.get('forma_pago', '03'),
                "Serie": "SUBS",
                "Fecha": timezone.now().isoformat(),
                "MetodoPago": "PUE",
                "SubTotal": str(subtotal),
                "Moneda": "MXN",
                "Total": str(total),
                "TipoDeComprobante": "I",
                "Exportacion": "01",
                "LugarExpedicion": settings.KITA_CODIGO_POSTAL,

                "Emisor": {
                    "Rfc": settings.KITA_RFC,
                    "Nombre": settings.KITA_RAZON_SOCIAL,
                    "RegimenFiscal": settings.KITA_REGIMEN_FISCAL
                },

                "Receptor": {
                    "Rfc": fiscal_data['rfc'],
                    "Nombre": fiscal_data['business_name'],
                    "DomicilioFiscalReceptor": fiscal_data.get('codigo_postal', '00000'),
                    "RegimenFiscalReceptor": fiscal_data.get('fiscal_regime', '601'),
                    "UsoCFDI": fiscal_data.get('uso_cfdi', 'G03')
                },

                "customer_email": fiscal_data.get('email'),

                "Conceptos": [
                    {
                        "ClaveProdServ": "81161700",
                        "Cantidad": "1.0",
                        "ClaveUnidad": "E48",
                        "Unidad": "Servicio",
                        "Descripcion": f"Suscripción Kita Pro - {billing_payment.billing_period_start.strftime('%B %Y')}",
                        "ValorUnitario": str(subtotal),
                        "Importe": str(subtotal),
                        "Descuento": "0.00",
                        "ObjetoImp": "02",
                        "Impuestos": {
                            "Traslados": [
                                {
                                    "Base": str(subtotal),
                                    "Importe": str(iva_amount),
                                    "Impuesto": "002",
                                    "TasaOCuota": "0.160000",
                                    "TipoFactor": "Tasa"
                                }
                            ]
                        }
                    }
                ],

                "Impuestos": {
                    "TotalImpuestosTrasladados": str(iva_amount),
                    "Traslados": [
                        {
                            "Base": str(subtotal),
                            "Importe": str(iva_amount),
                            "Impuesto": "002",
                            "TasaOCuota": "0.160000",
                            "TipoFactor": "Tasa"
                        }
                    ]
                }
            }

            # Use pac_factory (points to facturapi_service)
            # stamp_cfdi() will use Kita's organization automatically
            from invoicing.pac_factory import pac_service

            # Note: We pass tenant.id but facturapi uses Kita's Live Key (global)
            pac_result = pac_service.stamp_cfdi(cfdi_data, str(tenant.id))

            if not pac_result['success']:
                raise ValueError(pac_result.get('error', 'Error desconocido'))

            # Create Invoice model
            from invoicing.models import Invoice
            from django.core.files.base import ContentFile
            import base64

            invoice_record = Invoice.objects.create(
                tenant=tenant,
                uuid=pac_result['uuid'],
                serie='SUBS',
                folio='000001',  # Auto-increment handled by facturapi

                # Customer data (tenant is receptor)
                customer_rfc=fiscal_data['rfc'],
                customer_name=fiscal_data['business_name'],
                customer_email=fiscal_data.get('email') or tenant.email,
                customer_address=fiscal_data.get('codigo_postal', ''),
                cfdi_use=fiscal_data.get('uso_cfdi', 'G03'),

                # Amounts
                currency='MXN',
                subtotal=subtotal,
                tax_amount=iva_amount,
                total=total,
                payment_method='PUE',
                payment_form=fiscal_data.get('forma_pago', '03'),

                # Status
                status='stamped',
                stamped_at=timezone.now(),

                # PAC data
                pac_response=pac_result.get('data', {})
            )

            # Save XML
            xml_decoded = base64.b64decode(pac_result['xml'])
            invoice_record.xml_file.save(
                f"factura_SUBS_{invoice_record.uuid}.xml",
                ContentFile(xml_decoded),
                save=False
            )

            # Save PDF
            pdf_decoded = base64.b64decode(pac_result['pdf'])
            invoice_record.pdf_file.save(
                f"factura_SUBS_{invoice_record.uuid}.pdf",
                ContentFile(pdf_decoded),
                save=False
            )

            invoice_record.save()

            logger.info(f"Invoice model created: {invoice_record.uuid}")

            # Send email via facturapi.io
            try:
                invoice_facturapi_id = pac_result.get('data', {}).get('id')
                if invoice_facturapi_id:
                    email_result = pac_service.send_invoice_email(
                        invoice_id=invoice_facturapi_id,
                        recipient_email=fiscal_data.get('email') or tenant.email
                    )
                    logger.info(f"Email sent via facturapi.io: {email_result['success']}")
            except Exception as email_error:
                logger.error(f"Failed to send email: {email_error}")

            # Update billing payment
            billing_payment.invoice_generated = True
            billing_payment.invoice_sent = True
            billing_payment.invoice_data = {
                'uuid': pac_result['uuid'],
                'invoice_id': str(invoice_record.id),
                'issued_at': timezone.now().isoformat(),
                'total': str(total),
                'receptor_rfc': fiscal_data['rfc'],
                'receptor_name': fiscal_data['business_name'],
                'provider': 'facturapi'
            }
            billing_payment.save()

            logger.info(f"✅ Invoice generated - UUID: {pac_result['uuid']}")

            return {
                'success': True,
                'uuid': pac_result['uuid'],
                'invoice_id': str(invoice_record.id),
                'message': 'Factura generada y enviada exitosamente'
            }

        except Exception as e:
            logger.error(f"Error generating invoice: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': f'Error generando factura: {str(e)}'
            }


# Global service instance
subscription_invoice_service = SubscriptionInvoiceService()
