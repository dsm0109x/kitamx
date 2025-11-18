"""CFDI Generation Service for Kita.

Generates CFDI 4.0 invoices from payment data with SW PAC integration.
"""
from __future__ import annotations
from typing import Dict, Any
import logging
from decimal import Decimal

from django.utils import timezone
from django.db import transaction

from .models import Invoice, CSDCertificate
from .pac_factory import pac_service

logger = logging.getLogger(__name__)


class InvoiceGenerationService:
    """Service to generate CFDI invoices from payment data."""

    def __init__(self, tenant: Any) -> None:
        """Initialize with tenant."""
        self.tenant = tenant

    @transaction.atomic
    def generate_invoice_from_payment(
        self,
        payment: Any,
        fiscal_data: Dict[str, Any]
    ) -> Invoice:
        """Generate CFDI invoice from payment and fiscal data.

        Args:
            payment: Payment object to generate invoice from
            fiscal_data: Dictionary with fiscal information

        Returns:
            Generated Invoice object

        Raises:
            ValueError: If CFDI stamping fails
        """
        try:
            # Build CFDI JSON data according to SW format
            cfdi_data = self._build_cfdi_data(payment, fiscal_data)

            # Issue CFDI via PAC provider
            pac_result = pac_service.stamp_cfdi(cfdi_data, str(self.tenant.id))

            if pac_result['success']:
                # Create invoice record
                invoice = self._create_invoice_record(payment, fiscal_data, pac_result)

                # Send notification
                try:
                    from core.notifications import notification_service
                    notification_service.send_invoice_generated(invoice, fiscal_data['email'])
                except Exception as e:
                    logger.error(f"Failed to send invoice notification: {e}")

                return invoice
            else:
                raise ValueError(f"Error al timbrar CFDI: {pac_result.get('error', 'Error desconocido')}")

        except Exception as e:
            logger.error(f"Error generating invoice for payment {payment.mp_payment_id}: {e}")
            raise

    def _build_cfdi_data(
        self,
        payment: Any,
        fiscal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build CFDI JSON data structure for SW API.

        Args:
            payment: Payment object
            fiscal_data: Fiscal information dictionary

        Returns:
            CFDI data structure for SW API
        """
        # Generate serie and folio with proper locking
        last_invoice = Invoice.objects.filter(
            tenant=self.tenant
        ).select_for_update().order_by('-created_at').first()

        if last_invoice and last_invoice.folio.isdigit():
            folio_num = int(last_invoice.folio) + 1
        else:
            folio_num = 1

        serie = self.tenant.rfc[:3].upper()  # Use first 3 chars of RFC
        folio = str(folio_num).zfill(6)

        # Calculate taxes (remove IVA from total to get subtotal)
        total = Decimal(str(payment.amount))
        subtotal = (total / Decimal('1.16')).quantize(Decimal('0.01'))
        iva_amount = (total - subtotal).quantize(Decimal('0.01'))

        cfdi_data = {
            "Version": "4.0",
            "FormaPago": "01",  # Efectivo
            "Serie": serie,
            "Folio": folio,
            "Fecha": payment.processed_at.isoformat() if payment.processed_at else timezone.now().isoformat(),
            "MetodoPago": "PUE",  # Pago en una sola exhibición
            "SubTotal": str(subtotal),
            "Moneda": "MXN",
            "Total": str(total),
            "TipoDeComprobante": "I",  # Ingreso
            "Exportacion": "01",  # No aplica
            "LugarExpedicion": self.tenant.postal_code,

            "Emisor": {
                "Rfc": self.tenant.rfc,
                "Nombre": self.tenant.business_name,
                "RegimenFiscal": self.tenant.fiscal_regime
            },

            "Receptor": {
                "Rfc": fiscal_data['rfc'],
                "Nombre": fiscal_data['business_name'],
                "DomicilioFiscalReceptor": fiscal_data['postal_code'],
                "RegimenFiscalReceptor": fiscal_data['fiscal_regime'],
                "UsoCFDI": fiscal_data['cfdi_use']
            },

            # Additional data for our system (not part of CFDI XML)
            "customer_email": fiscal_data.get('email'),

            "Conceptos": [
                {
                    "ClaveProdServ": "84111506",  # Servicios de facturación
                    "Cantidad": "1.0",
                    "ClaveUnidad": "ACT",  # Actividad
                    "Unidad": "Actividad",
                    "Descripcion": payment.payment_link.title,
                    "ValorUnitario": str(subtotal),
                    "Importe": str(subtotal),
                    "Descuento": "0.00",
                    "ObjetoImp": "02",  # Sí objeto de impuesto
                    "Impuestos": {
                        "Traslados": [
                            {
                                "Base": str(subtotal),
                                "Importe": str(iva_amount),
                                "Impuesto": "002",  # IVA
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
                        "Impuesto": "002",  # IVA
                        "TasaOCuota": "0.160000",
                        "TipoFactor": "Tasa"
                    }
                ]
            }
        }

        return cfdi_data

    def _create_invoice_record(
        self,
        payment: Any,
        fiscal_data: Dict[str, Any],
        pac_result: Dict[str, Any]
    ) -> Invoice:
        """Create invoice record in database.

        Args:
            payment: Payment object
            fiscal_data: Fiscal information
            pac_result: PAC provider response (FiscalAPI)

        Returns:
            Created Invoice object
        """
        import base64
        from django.core.files.base import ContentFile

        # Decode XML and PDF from base64
        xml_content = base64.b64decode(pac_result['xml']).decode('utf-8')

        # Get serie/folio from CFDI data
        serie = self.tenant.rfc[:3].upper()
        last_invoice = Invoice.objects.filter(
            tenant=self.tenant
        ).order_by('-created_at').first()

        if last_invoice and last_invoice.folio.isdigit():
            folio = str(int(last_invoice.folio) + 1).zfill(6)
        else:
            folio = '000001'

        # Create invoice
        invoice = Invoice.objects.create(
            tenant=self.tenant,
            uuid=pac_result['uuid'],
            serie=serie,
            folio=folio,

            # Customer data
            customer_rfc=fiscal_data['rfc'],
            customer_name=fiscal_data['business_name'],
            customer_email=fiscal_data['email'],
            customer_address=fiscal_data.get('postal_code', ''),
            cfdi_use=fiscal_data['cfdi_use'],

            # Invoice data
            currency='MXN',
            subtotal=(Decimal(str(payment.amount)) / Decimal('1.16')).quantize(Decimal('0.01')),
            tax_amount=((Decimal(str(payment.amount)) / Decimal('1.16')) * Decimal('0.16')).quantize(Decimal('0.01')),
            total=Decimal(str(payment.amount)),
            payment_method='PUE',  # Pago en una sola exhibición
            payment_form='01',  # Efectivo


            # Status
            status='stamped',
            stamped_at=timezone.now(),

            # PAC data
            pac_response=pac_result.get('data', pac_result)
        )

        # Save XML file
        xml_filename = f"factura_{invoice.serie_folio}.xml"
        invoice.xml_file.save(
            xml_filename,
            ContentFile(xml_content.encode('utf-8')),
            save=False
        )

        # Save PDF if provided
        if pac_result.get('pdf'):
            pdf_content = base64.b64decode(pac_result['pdf'])
            pdf_filename = f"factura_{invoice.serie_folio}.pdf"
            invoice.pdf_file.save(
                pdf_filename,
                ContentFile(pdf_content),
                save=False
            )

        invoice.save()

        logger.info(f"Invoice created: {invoice.uuid} for payment {payment.mp_payment_id}")

        # Mark CSD as used
        try:
            csd = CSDCertificate.objects.filter(
                tenant=self.tenant,
                is_active=True,
                is_validated=True
            ).first()
            if csd:
                csd.mark_used()
        except Exception as e:
            logger.warning(f"Could not mark CSD as used: {e}")

        return invoice