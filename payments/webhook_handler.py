"""Centralized MercadoPago webhook handler.

Consolidates all webhook processing logic for MercadoPago events,
including user payments, subscription billing, and merchant orders.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any
import json
import hmac
import hashlib
import logging
import uuid
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.http import HttpResponse, HttpRequest
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from core.models import Tenant
from billing.models import Subscription, BillingPayment
from .models import Payment, PaymentLink, MercadoPagoIntegration
from .services import MercadoPagoService

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class MercadoPagoWebhookHandler:
    """Centralized handler for all MercadoPago webhook events.

    Handles:
    - User payment notifications (payment links)
    - Subscription billing payments
    - Merchant order notifications
    - Refund notifications
    """

    def __init__(self):
        """Initialize webhook handler."""
        self.logger = logger
        self.webhook_secret = settings.MERCADOPAGO_WEBHOOK_SECRET
        self.kita_mp_token = getattr(settings, 'KITA_MP_ACCESS_TOKEN', None)

    def handle_webhook(self, request: HttpRequest, webhook_type: str = 'general') -> HttpResponse:
        """Main entry point for webhook processing.

        Args:
            request: Django HTTP request
            webhook_type: Type of webhook ('general', 'billing', or specific type)

        Returns:
            HTTP response indicating webhook processing result
        """
        try:
            # Step 1: Parse webhook data first (needed to check live_mode)
            try:
                webhook_data = json.loads(request.body.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON in webhook body: {e}")
                return HttpResponse(status=400)

            # Step 2: Verify webhook signature (skip for test webhooks)
            is_test_webhook = webhook_data.get('live_mode', True) == False

            if not is_test_webhook:
                # Production webhooks MUST have valid signature
                if not self._verify_signature(request):
                    self.logger.warning(f"Invalid webhook signature for {webhook_type}")
                    return HttpResponse(status=401)
            else:
                # Test webhooks: log warning but allow
                self.logger.info(f"Test webhook received (live_mode=false), skipping signature verification")

            # Step 3: Log webhook receipt
            event_type = webhook_data.get('type', 'unknown')
            event_action = webhook_data.get('action', '')
            data_id = webhook_data.get('data', {}).get('id', '')

            self.logger.info(
                f"MP Webhook received - Type: {webhook_type}, "
                f"Event: {event_type}.{event_action}, ID: {data_id}"
            )

            # Step 4: Check idempotency
            if self._is_duplicate(webhook_data):
                self.logger.info(f"Duplicate webhook ignored: {data_id}")
                return HttpResponse(status=200)

            # Step 5: Route to appropriate handler
            result = self._route_webhook(webhook_data, webhook_type)

            # Step 6: Mark as processed
            self._mark_processed(webhook_data)

            if result.get('success', False):
                return HttpResponse(status=200)
            else:
                error = result.get('error', 'Unknown error')
                self.logger.error(f"Webhook processing failed: {error}")
                return HttpResponse(status=500)

        except Exception as e:
            self.logger.error(f"Unexpected webhook error: {e}", exc_info=True)
            return HttpResponse(status=500)

    def _verify_signature(self, request: HttpRequest) -> bool:
        """Verify webhook signature using HMAC-SHA256.

        Args:
            request: HTTP request containing signature header

        Returns:
            True if signature is valid
        """
        signature_header = request.headers.get('X-Signature', '')

        if not signature_header:
            self.logger.warning("Webhook missing X-Signature header")
            return False

        if not self.webhook_secret:
            self.logger.error("MERCADOPAGO_WEBHOOK_SECRET not configured")
            return False

        try:
            # Extract signature from header format: "v1=signature,v2=..."
            parts = signature_header.split(',')
            sig_part = next((p for p in parts if p.startswith('v1=')), None)

            if not sig_part:
                return False

            received_signature = sig_part.split('=')[1]

            # Calculate expected signature
            expected_signature = hmac.new(
                self.webhook_secret.encode('utf-8'),
                request.body,
                hashlib.sha256
            ).hexdigest()

            # Constant-time comparison
            return hmac.compare_digest(received_signature, expected_signature)

        except Exception as e:
            self.logger.error(f"Signature verification error: {e}")
            return False

    def _is_duplicate(self, webhook_data: Dict[str, Any]) -> bool:
        """Check if webhook has already been processed.

        Uses cache-based idempotency to prevent duplicate processing.

        Args:
            webhook_data: Parsed webhook data

        Returns:
            True if webhook is duplicate
        """
        event_type = webhook_data.get('type', '')
        data_id = webhook_data.get('data', {}).get('id', '')

        if not data_id:
            return False

        from core.cache import KitaRedisCache
        cache_key = KitaRedisCache.generate_global_key('webhook', 'processed', f"{event_type}:{data_id}")

        # Check if already processed
        if cache.get(cache_key):
            return True

        return False

    def _mark_processed(self, webhook_data: Dict[str, Any]) -> None:
        """Mark webhook as processed in cache.

        Args:
            webhook_data: Parsed webhook data
        """
        event_type = webhook_data.get('type', '')
        data_id = webhook_data.get('data', {}).get('id', '')

        if data_id:
            from core.cache import KitaRedisCache
            cache_key = KitaRedisCache.generate_global_key('webhook', 'processed', f"{event_type}:{data_id}")
            cache.set(cache_key, True, timeout=86400)  # 24 hours

    def _route_webhook(
        self,
        webhook_data: Dict[str, Any],
        webhook_type: str
    ) -> Dict[str, Any]:
        """Route webhook to appropriate handler based on type.

        Args:
            webhook_data: Parsed webhook data
            webhook_type: Type of webhook endpoint hit

        Returns:
            Processing result dictionary
        """
        event_type = webhook_data.get('type', '')

        # Route based on event type
        if event_type == 'payment':
            return self._handle_payment_event(webhook_data, webhook_type)
        elif event_type == 'merchant_order':
            return self._handle_merchant_order_event(webhook_data)
        elif event_type == 'refund':
            return self._handle_refund_event(webhook_data)
        else:
            self.logger.info(f"Ignoring webhook event type: {event_type}")
            return {'success': True, 'ignored': True}

    @transaction.atomic
    def _handle_payment_event(
        self,
        webhook_data: Dict[str, Any],
        webhook_type: str
    ) -> Dict[str, Any]:
        """Handle payment-related webhook events.

        Determines if payment is for user payment link or subscription billing.

        Args:
            webhook_data: Parsed webhook data
            webhook_type: Type of webhook endpoint

        Returns:
            Processing result
        """
        payment_id = webhook_data.get('data', {}).get('id', '')

        if not payment_id:
            return {'success': False, 'error': 'No payment ID in webhook'}

        # Determine payment type based on webhook endpoint or payment data
        if webhook_type == 'billing':
            # Explicitly billing webhook
            return self._process_subscription_payment(payment_id, webhook_data)
        else:
            # Need to determine type by fetching payment data
            return self._process_payment_auto_detect(payment_id, webhook_data)

    def _process_payment_auto_detect(
        self,
        payment_id: str,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Auto-detect payment type and process accordingly.

        Args:
            payment_id: MercadoPago payment ID
            webhook_data: Original webhook data

        Returns:
            Processing result
        """
        # First, check if payment exists in our database
        existing_payment = Payment.objects.filter(mp_payment_id=payment_id).first()

        if existing_payment:
            # Update existing payment
            return self._update_existing_payment(existing_payment, webhook_data)

        # Try to fetch payment data to determine type
        # Check all tenants' integrations to find the payment (optimized)
        for integration in MercadoPagoIntegration.objects.filter(is_active=True).select_related('tenant'):
            try:
                payment_data = MercadoPagoService.get_payment_from_mp_api(
                    payment_id,
                    integration.access_token
                )

                if payment_data:
                    external_ref = payment_data.get('external_reference', '')

                    # Check if it's a payment link reference (UUID)
                    if self._is_payment_link_reference(external_ref):
                        return self._process_user_payment(
                            payment_id,
                            payment_data,
                            integration.tenant,
                            webhook_data
                        )

            except Exception as e:
                self.logger.debug(f"Payment not found in tenant {integration.tenant_id}: {e}")
                continue

        # Try Kita's own MercadoPago account for subscription payments
        if self.kita_mp_token:
            try:
                payment_data = MercadoPagoService.get_payment_from_mp_api(
                    payment_id,
                    self.kita_mp_token
                )

                if payment_data:
                    return self._process_subscription_payment_data(
                        payment_id,
                        payment_data,
                        webhook_data
                    )

            except Exception as e:
                self.logger.error(f"Failed to fetch payment from Kita MP: {e}")

        self.logger.warning(f"Payment {payment_id} could not be matched to any tenant or subscription")
        return {'success': True, 'ignored': True}

    def _is_payment_link_reference(self, reference: str) -> bool:
        """Check if external reference is a payment link UUID.

        Args:
            reference: External reference string

        Returns:
            True if reference appears to be a payment link UUID
        """
        try:
            uuid.UUID(reference)
            # Check if it matches a payment link
            return PaymentLink.objects.filter(id=reference).exists()
        except (ValueError, TypeError):
            return False

    def _process_user_payment(
        self,
        payment_id: str,
        payment_data: Dict[str, Any],
        tenant: Tenant,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process payment for user payment link.

        Args:
            payment_id: MercadoPago payment ID
            payment_data: Payment data from MP API
            tenant: Tenant that owns the payment link
            webhook_data: Original webhook data

        Returns:
            Processing result
        """
        try:
            external_ref = payment_data.get('external_reference', '')
            payment_link = PaymentLink.objects.get(id=external_ref, tenant=tenant)

            # Map MP status to our status
            status_map = {
                'approved': 'approved',
                'authorized': 'approved',
                'pending': 'pending',
                'in_process': 'processing',
                'in_mediation': 'processing',
                'rejected': 'rejected',
                'cancelled': 'cancelled',
                'refunded': 'refunded',
                'charged_back': 'charged_back'
            }

            payment_status = status_map.get(payment_data.get('status'), 'pending')

            # Create or update payment record
            payment, created = Payment.objects.update_or_create(
                mp_payment_id=payment_id,
                defaults={
                    'tenant': tenant,
                    'payment_link': payment_link,
                    'mp_preference_id': payment_data.get('preference_id', ''),
                    'mp_collection_id': payment_data.get('collection_id', ''),
                    'amount': Decimal(str(payment_data.get('transaction_amount', 0))),
                    'currency': payment_data.get('currency_id', 'MXN'),
                    'status': payment_status,
                    'payment_method': payment_data.get('payment_method_id', ''),
                    'payment_type': payment_data.get('payment_type_id', ''),
                    'payer_email': payment_data.get('payer', {}).get('email', ''),
                    'payer_name': f"{payment_data.get('payer', {}).get('first_name', '')} "
                                  f"{payment_data.get('payer', {}).get('last_name', '')}".strip(),
                    'processed_at': timezone.now() if payment_status == 'approved' else None,
                    'webhook_data': webhook_data,
                    'mp_updated_at': timezone.now()
                }
            )

            # Update payment link if payment successful
            if payment_status == 'approved' and created:
                # CRITICAL: Validate link is still active before marking as paid
                if payment_link.status == 'cancelled':
                    self.logger.warning(
                        f"Payment {payment_id} received for CANCELLED link {payment_link.id}. "
                        f"Cancelled at: {payment_link.cancelled_at}, "
                        f"Reason: {payment_link.cancellation_reason}. "
                        f"Payment registered but link NOT marked as paid."
                    )

                    # Alert tenant and admin about this race condition
                    self._alert_cancelled_link_payment(payment_link, payment, payment_data)

                elif payment_link.status == 'active':
                    # Normal flow: mark as paid
                    payment_link.status = 'paid'
                    payment_link.uses_count += 1
                    payment_link.save()
                else:
                    # Link is expired or already paid
                    self.logger.warning(
                        f"Payment {payment_id} received for link {payment_link.id} "
                        f"with status '{payment_link.status}'. Payment registered."
                    )

                # Send notifications
                self._send_payment_notifications(payment)

            # Trigger invoice generation if needed
            if payment_status == 'approved' and payment_link.requires_invoice:
                self._trigger_invoice_generation(payment)

            self.logger.info(
                f"User payment {payment_id} processed - "
                f"Status: {payment_status}, Created: {created}"
            )

            return {'success': True, 'payment_id': payment.id}

        except PaymentLink.DoesNotExist:
            self.logger.error(f"Payment link not found: {external_ref}")
            return {'success': False, 'error': 'Payment link not found'}
        except Exception as e:
            self.logger.error(f"Error processing user payment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _process_subscription_payment(
        self,
        payment_id: str,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process subscription billing payment.

        Args:
            payment_id: MercadoPago payment ID
            webhook_data: Original webhook data

        Returns:
            Processing result
        """
        if not self.kita_mp_token:
            return {'success': False, 'error': 'Kita MP token not configured'}

        try:
            # Get payment data from Kita's MP account
            payment_data = MercadoPagoService.get_payment_from_mp_api(
                payment_id,
                self.kita_mp_token
            )

            if not payment_data:
                return {'success': False, 'error': 'Payment data not found'}

            return self._process_subscription_payment_data(
                payment_id,
                payment_data,
                webhook_data
            )

        except Exception as e:
            self.logger.error(f"Error processing subscription payment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _process_subscription_payment_data(
        self,
        payment_id: str,
        payment_data: Dict[str, Any],
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process subscription payment data.

        Args:
            payment_id: MercadoPago payment ID
            payment_data: Payment data from MP API
            webhook_data: Original webhook data

        Returns:
            Processing result
        """
        external_ref = payment_data.get('external_reference', '')

        # Check if it's new billing system (UUID reference)
        try:
            uuid.UUID(external_ref)

            # Process subscription payment directly
            result = self._process_subscription_payment_direct(payment_data)

            if result['success']:
                self.logger.info(f"Billing payment processed: {payment_id}")
            else:
                self.logger.error(f"Billing payment failed: {result.get('error')}")

            return result

        except (ValueError, TypeError):
            # Legacy system - check for old format
            if external_ref.startswith('kita_subscription_'):
                return self._process_legacy_subscription(
                    payment_id,
                    payment_data,
                    external_ref
                )
            else:
                self.logger.warning(f"Unknown subscription reference: {external_ref}")
                return {'success': True, 'ignored': True}

    def _process_legacy_subscription(
        self,
        payment_id: str,
        payment_data: Dict[str, Any],
        external_ref: str
    ) -> Dict[str, Any]:
        """Process legacy subscription payment.

        Args:
            payment_id: MercadoPago payment ID
            payment_data: Payment data from MP API
            external_ref: External reference (legacy format)

        Returns:
            Processing result
        """
        try:
            # Extract tenant ID from reference
            tenant_id = external_ref.replace('kita_subscription_', '')
            tenant = Tenant.objects.get(id=tenant_id)

            payment_status = payment_data.get('status')
            amount = Decimal(str(payment_data.get('transaction_amount', 299.00)))

            if payment_status == 'approved':
                # Migrate to new billing system
                subscription, created = Subscription.objects.get_or_create(
                    tenant=tenant,
                    defaults={
                        'trial_ends_at': timezone.now() + timedelta(days=30)
                    }
                )

                # Create billing payment record
                billing_payment = BillingPayment.objects.create(
                    tenant=tenant,
                    subscription=subscription,
                    amount=amount,
                    currency='MXN',
                    status='completed',
                    payment_method='mercadopago',
                    external_payment_id=payment_id,
                    external_payment_data=payment_data,
                    billing_period_start=timezone.now(),
                    billing_period_end=timezone.now() + timedelta(days=30),
                    processed_at=timezone.now()
                )

                # Activate subscription
                subscription.mark_payment_successful(amount)

                self.logger.info(f"Legacy subscription payment processed for tenant {tenant.name}")

                return {'success': True, 'subscription_id': subscription.id}
            else:
                self.logger.info(f"Legacy subscription payment {payment_status} for tenant {tenant.name}")
                return {'success': True, 'status': payment_status}

        except Tenant.DoesNotExist:
            self.logger.error(f"Tenant not found for legacy subscription: {tenant_id}")
            return {'success': False, 'error': 'Tenant not found'}
        except Exception as e:
            self.logger.error(f"Error processing legacy subscription: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _update_existing_payment(
        self,
        payment: Payment,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update existing payment with webhook data.

        Args:
            payment: Existing payment record
            webhook_data: Webhook data

        Returns:
            Processing result
        """
        try:
            # Get latest payment data from MP
            mp_service = MercadoPagoService(payment.tenant)

            if not mp_service.integration:
                return {'success': False, 'error': 'MP integration not found'}

            payment_data = mp_service.get_payment_info(payment.mp_payment_id)

            if not payment_data:
                return {'success': False, 'error': 'Payment data not found'}

            # Update payment status
            old_status = payment.status
            payment.status = payment_data.get('status', payment.status)
            payment.webhook_data = webhook_data
            payment.mp_updated_at = timezone.now()
            payment.save()

            self.logger.info(
                f"Payment {payment.mp_payment_id} updated: "
                f"{old_status} → {payment.status}"
            )

            return {'success': True, 'updated': True}

        except Exception as e:
            self.logger.error(f"Error updating payment: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}

    def _handle_merchant_order_event(
        self,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle merchant order webhook events.

        Args:
            webhook_data: Webhook data

        Returns:
            Processing result
        """
        order_id = webhook_data.get('data', {}).get('id', '')

        self.logger.info(f"Merchant order webhook received: {order_id}")

        # Currently we don't process merchant orders directly
        # They're handled through payment webhooks

        return {'success': True, 'ignored': True}

    def _handle_refund_event(
        self,
        webhook_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle refund webhook events.

        Args:
            webhook_data: Webhook data

        Returns:
            Processing result
        """
        refund_id = webhook_data.get('data', {}).get('id', '')

        self.logger.info(f"Refund webhook received: {refund_id}")

        # TODO: Implement refund processing

        return {'success': True, 'ignored': True}

    def _send_payment_notifications(self, payment: Payment) -> None:
        """Send payment notifications.

        Args:
            payment: Payment record
        """
        try:
            from core.notifications import notification_service
            notification_service.send_payment_received(payment)
        except Exception as e:
            self.logger.error(f"Failed to send payment notification: {e}")

    def _trigger_invoice_generation(self, payment: Payment) -> None:
        """Trigger invoice generation for payment.

        Args:
            payment: Payment requiring invoice
        """
        try:
            # TODO: Trigger CFDI generation task
            self.logger.info(f"Payment {payment.id} requires invoice generation")
        except Exception as e:
            self.logger.error(f"Failed to trigger invoice generation: {e}")

    def _alert_cancelled_link_payment(
        self,
        payment_link: PaymentLink,
        payment: Payment,
        payment_data: Dict[str, Any]
    ) -> None:
        """Alert tenant and admin when payment is received for cancelled link.

        This handles the race condition where a user completes payment
        while someone cancels the link.

        Args:
            payment_link: Cancelled PaymentLink that received payment
            payment: Payment record that was created
            payment_data: Payment data from MercadoPago
        """
        try:
            from django.core.mail import send_mail
            from core.notifications import notification_service

            # Extract payment details
            payer_email = payment_data.get('payer', {}).get('email', '')
            payer_name = f"{payment_data.get('payer', {}).get('first_name', '')} " \
                        f"{payment_data.get('payer', {}).get('last_name', '')}".strip()
            amount = payment_data.get('transaction_amount', 0)
            mp_payment_id = payment_data.get('id', '')

            # 1. Alert TENANT via email
            tenant = payment_link.tenant
            tenant_owners = tenant.tenantuser_set.filter(is_owner=True)

            for tenant_user in tenant_owners:
                try:
                    context = {
                        'payment_link_title': payment_link.title,
                        'payment_link_id': str(payment_link.id),
                        'amount': f"${amount:,.2f} MXN",
                        'payer_name': payer_name or 'Cliente',
                        'payer_email': payer_email,
                        'mp_payment_id': mp_payment_id,
                        'cancelled_at': payment_link.cancelled_at,
                        'cancellation_reason': payment_link.get_cancellation_reason_display() if payment_link.cancellation_reason else 'No especificada',
                        'cancelled_by': payment_link.cancelled_by.get_full_name() if payment_link.cancelled_by else 'Desconocido'
                    }

                    notification_service.send_notification(
                        tenant=tenant,
                        notification_type='payment_on_cancelled_link',
                        recipient_email=tenant_user.email,
                        recipient_name=tenant_user.first_name,
                        context=context
                    )

                    self.logger.info(f"Sent cancelled link payment alert to tenant owner: {tenant_user.email}")

                except Exception as e:
                    self.logger.error(f"Failed to send tenant alert: {e}")

            # 2. Alert ADMIN (Diego) via direct email
            admin_email = getattr(settings, 'ADMIN_ALERT_EMAIL', 'dsm0109@gmail.com')

            try:
                subject = f"⚠️ ALERTA: Pago recibido en link cancelado - {tenant.name}"
                message = f"""
ALERTA DE RACE CONDITION EN PAGOS
==================================

Tenant: {tenant.name} (ID: {tenant.id})
Link: {payment_link.title} (ID: {payment_link.id})
Monto: ${amount:,.2f} MXN

DETALLES DEL PAGO:
- Pago ID (MP): {mp_payment_id}
- Pagador: {payer_name} ({payer_email})
- Estado del pago: {payment.status}

DETALLES DE LA CANCELACIÓN:
- Cancelado el: {payment_link.cancelled_at}
- Cancelado por: {payment_link.cancelled_by.get_full_name() if payment_link.cancelled_by else 'Desconocido'}
- Razón: {payment_link.get_cancellation_reason_display() if payment_link.cancellation_reason else 'No especificada'}

ACCIÓN TOMADA:
✅ Pago registrado en la base de datos (ID: {payment.id})
❌ Link NO marcado como pagado (permanece cancelado)
📧 Tenant notificado

ACCIONES SUGERIDAS:
1. Contactar al tenant para confirmar si deben procesar o refund
2. Verificar si el cliente requiere factura
3. Procesar refund desde panel de MercadoPago si es necesario

Dashboard: {settings.APP_BASE_URL}/admin/payments/payment/{payment.id}/
MercadoPago: https://www.mercadopago.com.mx/activities/{mp_payment_id}
                """

                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[admin_email],
                    fail_silently=False
                )

                self.logger.info(f"Sent cancelled link payment alert to admin: {admin_email}")

            except Exception as e:
                self.logger.error(f"Failed to send admin alert: {e}", exc_info=True)

        except Exception as e:
            self.logger.error(f"Error in _alert_cancelled_link_payment: {e}", exc_info=True)

    def _process_subscription_payment_direct(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process subscription payment directly.

        Args:
            payment_data: Payment data from MercadoPago

        Returns:
            Dict with success status and optional error message
        """
        try:
            external_ref = payment_data.get('external_reference', '')
            payment_id = payment_data.get('id')
            status = payment_data.get('status')
            amount = Decimal(str(payment_data.get('transaction_amount', 0)))

            # Find subscription by external reference
            subscription = Subscription.objects.filter(mp_subscription_id=external_ref).first()
            if not subscription:
                self.logger.warning(f"Subscription not found for reference: {external_ref}")
                return {'success': False, 'error': 'Subscription not found'}

            # Create or update billing payment
            billing_payment, created = BillingPayment.objects.update_or_create(
                subscription=subscription,
                mp_payment_id=payment_id,
                defaults={
                    'amount': amount,
                    'status': status,
                    'payment_method': payment_data.get('payment_method_id', ''),
                    'processed_at': timezone.now() if status == 'approved' else None,
                    'webhook_data': payment_data
                }
            )

            # Update subscription if payment is approved
            if status == 'approved':
                subscription.status = 'active'
                subscription.last_payment_date = timezone.now()
                subscription.next_payment_date = timezone.now() + timedelta(days=30)
                subscription.save()

                self.logger.info(f"Subscription {subscription.id} activated with payment {payment_id}")

            return {'success': True, 'payment': billing_payment}

        except Exception as e:
            self.logger.error(f"Error processing subscription payment: {e}")
            return {'success': False, 'error': str(e)}


# Singleton instance
webhook_handler = MercadoPagoWebhookHandler()