from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class KitaBillingService:
    """Service to handle Kita subscription billing using Kita's MP account"""

    def __init__(self):
        self.access_token = settings.KITA_MP_ACCESS_TOKEN
        self.public_key = settings.KITA_MP_PUBLIC_KEY
        self.user_id = settings.KITA_MP_USER_ID

    def create_subscription_preference(self, tenant, plan='monthly'):
        """Create subscription payment preference using Kita's MP account"""
        try:
            # Build preference for Kita subscription - Credit/Debit cards only
            preference_data = {
                "items": [
                    {
                        "title": f"Suscripción Kita - {tenant.business_name}",
                        "description": "Suscripción mensual a Kita - Facturación CFDI 4.0",
                        "quantity": 1,
                        "currency_id": "MXN",
                        "unit_price": float(settings.MONTHLY_SUBSCRIPTION_PRICE)
                    }
                ],
                "payer": {
                    "name": tenant.business_name,
                    "surname": "",
                    "email": tenant.email,
                    "phone": {
                        "area_code": "",
                        "number": tenant.phone or ""
                    },
                    "identification": {
                        "type": "RFC",
                        "number": tenant.rfc
                    },
                    "address": {
                        "street_name": f"{tenant.calle} {tenant.numero_exterior}".strip(),
                        "street_number": tenant.numero_exterior or "",
                        "zip_code": tenant.codigo_postal or ""
                    }
                },
                "payment_methods": {
                    "excluded_payment_types": [
                        {"id": "atm"},          # Exclude ATM
                        {"id": "ticket"},       # Exclude cash/ticket
                        {"id": "bank_transfer"} # Exclude bank transfer
                    ],
                    "installments": 1  # Single payment only (PUE)
                },
                "back_urls": {
                    "success": f"{settings.APP_BASE_URL}/suscripcion/pago/exito/",  # 🇪🇸 Migrado a billing
                    "failure": f"{settings.APP_BASE_URL}/suscripcion/pago/error/",  # 🇪🇸 Migrado a billing
                    "pending": f"{settings.APP_BASE_URL}/suscripcion/pago/pendiente/"  # 🇪🇸 Migrado a billing
                },
                "auto_return": "approved",
                "external_reference": f"kita_subscription_{tenant.id}",
                "notification_url": f"{settings.APP_BASE_URL}/webhooks/kita-billing/",
                "statement_descriptor": "KITA FACTURACION",
                "expires": True,
                "expiration_date_from": timezone.now().isoformat(),
                "expiration_date_to": (timezone.now() + timedelta(hours=2)).isoformat()  # 2 hours to pay
            }

            # Create preference using REST API
            import requests

            preference_url = settings.MERCADOPAGO_PREFERENCES_URL
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            response = requests.post(preference_url, json=preference_data, headers=headers, timeout=10)

            if response.status_code == 201:
                preference_response = response.json()
                preference_id = preference_response["id"]
                init_point = preference_response["init_point"]
                sandbox_init_point = preference_response.get("sandbox_init_point", "")

                logger.info(f"Kita subscription preference created: {preference_id} for tenant {tenant.name}")

                return {
                    'success': True,
                    'preference_id': preference_id,
                    'init_point': init_point,
                    'sandbox_init_point': sandbox_init_point,
                    'public_key': self.public_key
                }
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                logger.error(f"Failed to create Kita subscription preference: {error_msg}")
                raise ValueError(f"Error creando preferencia de pago: {error_msg}")

        except Exception as e:
            logger.error(f"Kita billing service error: {str(e)}")
            raise ValueError(f"Error en servicio de facturación: {str(e)}")

    def get_payment_info(self, payment_id):
        """Get payment information for Kita subscription"""
        try:
            import requests

            payment_url = f"{settings.MERCADOPAGO_PAYMENTS_URL}/{payment_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json"
            }

            response = requests.get(payment_url, headers=headers, timeout=10)

            if response.status_code == 200:
                return response.json()
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get("message", f"HTTP {response.status_code}")
                raise ValueError(f"Error obteniendo información de pago: {error_msg}")

        except Exception as e:
            logger.error(f"Error getting Kita payment info: {str(e)}")
            raise ValueError(f"Error consultando pago: {str(e)}")

    def activate_subscription(self, tenant, payment_id):
        """Activate tenant subscription after successful payment"""
        try:
            # Get payment details
            payment_info = self.get_payment_info(payment_id)

            if payment_info.get('status') == 'approved':
                # Use new billing system
                from billing.models import Subscription, BillingPayment
                from decimal import Decimal
                from datetime import timedelta

                # Get or create subscription
                subscription, created = Subscription.objects.get_or_create(
                    tenant=tenant,
                    defaults={
                        'trial_ends_at': timezone.now() + timedelta(days=30)
                    }
                )

                # Create billing payment record
                amount = Decimal(str(payment_info.get('transaction_amount', 299.00)))
                billing_payment = BillingPayment.objects.create(
                    tenant=tenant,
                    subscription=subscription,
                    amount=amount,
                    currency='MXN',
                    status='completed',
                    payment_method='mercadopago',
                    external_payment_id=payment_id,
                    external_payment_data=payment_info,
                    billing_period_start=timezone.now(),
                    billing_period_end=timezone.now() + timedelta(days=30),
                    processed_at=timezone.now()
                )

                # Activate subscription
                subscription.mark_payment_successful(amount)

                logger.info(f"Subscription activated via new billing system for tenant {tenant.name}")
                return True
            else:
                logger.warning(f"Payment not approved for tenant {tenant.name}: {payment_info.get('status')}")
                return False

        except Exception as e:
            logger.error(f"Error activating subscription: {str(e)}")
            return False

    def is_configured(self):
        """Check if Kita billing is properly configured"""
        return bool(settings.KITA_MP_ACCESS_TOKEN and
                   settings.KITA_MP_PUBLIC_KEY and
                   settings.KITA_MP_USER_ID)