"""
Notification system for WhatsApp Cloud API and Email
"""
from __future__ import annotations

import logging
import requests
from typing import Dict, Any
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Notification, Tenant
import re

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending notifications via WhatsApp and Email"""

    def __init__(self):
        self.wa_token = getattr(settings, 'WA_TOKEN', '')
        self.wa_phone_id = getattr(settings, 'WA_PHONE_ID', '')
        self.wa_business_id = getattr(settings, 'WA_BUSINESS_ID', '')

    def send_notification(self,
                         tenant: Tenant,
                         notification_type: str,
                         recipient_email: str,
                         recipient_phone: str = '',
                         recipient_name: str = '',
                         context: Dict[str, Any] = None,
                         payment_link_id: str = None,
                         payment_id: str = None,
                         invoice_id: str = None) -> Dict[str, Any]:
        """Send notification via preferred channel"""

        context = context or {}
        context.update({
            'tenant': tenant,
            'recipient_name': recipient_name,
            'app_base_url': settings.APP_BASE_URL
        })

        # Determine preferred channel
        preferred_channel = 'whatsapp' if recipient_phone else 'email'

        # ✅ Prepare metadata (serialize context for JSON storage)
        from django.utils import timezone as django_timezone
        import pytz

        metadata_to_save = {}
        mexico_tz = pytz.timezone('America/Mexico_City')

        for key, value in context.items():
            # Skip non-serializable objects
            if key in ['tenant']:
                continue
            # Convert datetime objects to string (con timezone de México)
            if hasattr(value, 'strftime'):
                # Si es timezone-aware, convertir a México primero
                if django_timezone.is_aware(value):
                    value = value.astimezone(mexico_tz)
                metadata_to_save[key] = value.strftime('%d/%m/%Y %H:%M')
            else:
                metadata_to_save[key] = value

        # Create notification record
        notification = Notification.objects.create(
            tenant=tenant,
            recipient_email=recipient_email,
            recipient_phone=recipient_phone,
            recipient_name=recipient_name,
            notification_type=notification_type,
            channel=preferred_channel,
            subject=self._get_subject(notification_type, context),
            message=self._get_message(notification_type, context, preferred_channel),
            metadata=metadata_to_save,  # ✅ Guardar metadata para templates HTML
            payment_link_id=payment_link_id,
            payment_id=payment_id,
            invoice_id=invoice_id
        )

        # Send via preferred channel first
        result = self._send_via_channel(notification, preferred_channel)

        # If WhatsApp fails and we have email, try email as fallback
        if not result['success'] and preferred_channel == 'whatsapp' and recipient_email:
            logger.info(f"WhatsApp failed for {recipient_phone}, trying email fallback")
            fallback_notification = Notification.objects.create(
                tenant=tenant,
                recipient_email=recipient_email,
                recipient_phone='',
                recipient_name=recipient_name,
                notification_type=notification_type,
                channel='email',
                subject=self._get_subject(notification_type, context),
                message=self._get_message(notification_type, context, 'email'),
                metadata=metadata_to_save,  # ✅ También para fallback
                payment_link_id=payment_link_id,
                payment_id=payment_id,
                invoice_id=invoice_id
            )
            fallback_result = self._send_via_channel(fallback_notification, 'email')
            if fallback_result['success']:
                result = fallback_result

        return result

    def _send_via_channel(self, notification: Notification, channel: str) -> Dict[str, Any]:
        """Send notification via specific channel"""
        try:
            if channel == 'whatsapp':
                return self._send_whatsapp(notification)
            elif channel == 'email':
                return self._send_email(notification)
            else:
                raise ValueError(f"Unsupported channel: {channel}")

        except Exception as e:
            logger.error(f"Error sending {channel} notification {notification.id}: {e}")
            notification.status = 'failed'
            notification.error_message = str(e)
            notification.save()

            return {
                'success': False,
                'error': str(e),
                'notification_id': notification.id
            }

    def _send_whatsapp(self, notification: Notification) -> Dict[str, Any]:
        """Send WhatsApp message via Cloud API"""
        if not self.wa_token or not self.wa_phone_id:
            logger.warning("WhatsApp credentials not configured")
            notification.status = 'failed'
            notification.error_message = 'WhatsApp not configured'
            notification.save()
            return {
                'success': False,
                'error': 'WhatsApp not configured'
            }

        # Clean phone number to E.164 format
        phone = self._clean_phone_number(notification.recipient_phone)
        if not phone:
            notification.status = 'failed'
            notification.error_message = 'Invalid phone number'
            notification.save()
            return {
                'success': False,
                'error': 'Invalid phone number'
            }

        url = f"https://graph.facebook.com/v18.0/{self.wa_phone_id}/messages"
        headers = {
            'Authorization': f'Bearer {self.wa_token}',
            'Content-Type': 'application/json'
        }

        payload = {
            'messaging_product': 'whatsapp',
            'to': phone,
            'type': 'text',
            'text': {
                'body': notification.message
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                notification.status = 'sent'
                notification.sent_at = timezone.now()
                notification.external_id = data.get('messages', [{}])[0].get('id', '')
                notification.save()

                logger.info(f"WhatsApp sent successfully: {notification.id}")
                return {
                    'success': True,
                    'notification_id': notification.id,
                    'external_id': notification.external_id
                }
            else:
                error_msg = f"WhatsApp API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                notification.status = 'failed'
                notification.error_message = error_msg
                notification.save()

                return {
                    'success': False,
                    'error': error_msg,
                    'notification_id': notification.id
                }

        except Exception as e:
            error_msg = f"WhatsApp request failed: {str(e)}"
            logger.error(error_msg)
            notification.status = 'failed'
            notification.error_message = error_msg
            notification.save()

            return {
                'success': False,
                'error': error_msg,
                'notification_id': notification.id
            }

    def _send_email(self, notification: Notification) -> Dict[str, Any]:
        """Send email via Django mail backend with Postmark tracking."""
        try:
            from django.core.mail import EmailMultiAlternatives

            # Construir metadata para Postmark
            metadata = {
                'notification_id': str(notification.id),
                'notification_type': notification.notification_type,
                'tenant_id': str(notification.tenant.id),
            }

            if notification.payment_link_id:
                metadata['payment_link_id'] = str(notification.payment_link_id)
            if notification.payment_id:
                metadata['payment_id'] = str(notification.payment_id)
            if notification.invoice_id:
                metadata['invoice_id'] = str(notification.invoice_id)

            # Crear email
            email = EmailMultiAlternatives(
                subject=notification.subject,
                body=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[notification.recipient_email],
            )

            # ✅ Agregar HTML template (ahora con método implementado)
            html_message = None
            template_name = self._get_html_template(notification.notification_type)
            if template_name:
                try:
                    context = self._build_template_context(notification)
                    html_message = render_to_string(template_name, context)
                    email.attach_alternative(html_message, "text/html")
                    logger.info(f"HTML template attached: {template_name}")
                except Exception as e:
                    logger.error(f"Failed to render HTML template {template_name}: {e}")
                    # Continue with plain text only

            # Headers personalizados de Postmark para tracking
            email.extra_headers = {
                'X-PM-Tag': notification.notification_type,
                'X-PM-TrackOpens': 'true',
                'X-PM-TrackLinks': 'HtmlOnly',
            }

            # Agregar metadata como headers
            for key, value in metadata.items():
                email.extra_headers[f'X-PM-Metadata-{key}'] = str(value)

            # Enviar
            email.send(fail_silently=False)

            # Intentar obtener MessageID si Postmark/Anymail está configurado
            message_id = None
            if hasattr(email, 'anymail_status'):
                anymail_status = email.anymail_status
                if hasattr(anymail_status, 'message_id'):
                    message_id = anymail_status.message_id
                elif hasattr(anymail_status, 'recipients'):
                    # Anymail retorna dict con recipient: message_id
                    recipients = anymail_status.recipients
                    if notification.recipient_email in recipients:
                        message_id = recipients[notification.recipient_email].message_id

            # Actualizar notification
            notification.status = 'sent'
            notification.sent_at = timezone.now()
            if message_id:
                notification.postmark_message_id = message_id
            notification.save()

            logger.info(f"Email sent successfully: {notification.id}" + (f" (MessageID: {message_id})" if message_id else ""))

            # Crear EmailEvent inicial si tenemos MessageID
            if message_id:
                from core.models import EmailEvent
                try:
                    EmailEvent.objects.create(
                        tenant=notification.tenant,
                        notification=notification,
                        message_id=message_id,
                        message_stream='outbound',
                        recipient=notification.recipient_email,
                        subject=notification.subject,
                        tag=notification.notification_type,
                        metadata=metadata,
                        status='sent'
                    )
                    logger.info(f"EmailEvent created for message {message_id}")
                except Exception as e:
                    logger.error(f"Failed to create EmailEvent: {e}")

            return {
                'success': True,
                'notification_id': notification.id,
                'message_id': message_id
            }

        except Exception as e:
            error_msg = f"Email send failed: {str(e)}"
            logger.error(error_msg)
            notification.status = 'failed'
            notification.error_message = error_msg
            notification.save()

            return {
                'success': False,
                'error': error_msg,
                'notification_id': notification.id
            }

    def _clean_phone_number(self, phone: str) -> str:
        """Clean and validate phone number to E.164 format"""
        if not phone:
            return ''

        # Remove all non-digit characters
        digits = re.sub(r'[^\d]', '', phone)

        # Mexican numbers
        if len(digits) == 10:  # Local Mexican number
            return f'+52{digits}'
        elif len(digits) == 12 and digits.startswith('52'):  # Already with country code
            return f'+{digits}'
        elif len(digits) == 13 and digits.startswith('521'):  # Mobile with extra 1
            return f'+{digits}'
        elif digits.startswith('+'):
            return digits

        # Return as-is if it looks like international format
        if len(digits) >= 10:
            return f'+{digits}'

        return ''

    def _get_subject(self, notification_type: str, context: Dict[str, Any]) -> str:
        """Get email subject based on notification type"""
        subjects = {
            'link_created': 'Tu link de pago está listo - {tenant_name}',
            'payment_received': '¡Pago recibido! - {tenant_name}',
            'invoice_generated': 'Tu factura ha sido generada - {tenant_name}',
            'payment_reminder': 'Recordatorio: Link de pago pendiente - {tenant_name}',
            'link_expired': 'Tu link de pago ha expirado - {tenant_name}',
            'billing_form_available': 'Tu factura está disponible - {tenant_name}',
            'invoice_ready': 'Tu factura CFDI ha sido generada - {tenant_name}',
            'subscription_due': 'Renovación de suscripción - Kita',
            'subscription_failed': 'Problema con tu suscripción - Kita',
            'payment_on_cancelled_link': '⚠️ Atención: Pago recibido en link cancelado - {tenant_name}',
        }

        template = subjects.get(notification_type, 'Notificación - {tenant_name}')
        return template.format(tenant_name=context.get('tenant', {}).name)

    def _get_message(self, notification_type: str, context: Dict[str, Any], channel: str) -> str:
        """Get message content based on type and channel"""
        messages = {
            'link_created': {
                'whatsapp': """🔗 ¡Tu link de pago está listo!

Hola {recipient_name},

Tu link de pago por ${amount} MXN está disponible:
{link_url}

⏰ Expira: {expires_at}
💰 Monto: ${amount} MXN

¡Gracias por elegirnos!

{tenant_name}""",
                'email': """Hola {recipient_name},

Tu link de pago por ${amount} MXN ha sido creado y está disponible en:
{link_url}

Detalles:
- Monto: ${amount} MXN
- Expira: {expires_at}
- Concepto: {concept}

Puedes realizar el pago de forma segura a través de MercadoPago.

Saludos,
{tenant_name}"""
            },
            'payment_received': {
                'whatsapp': """✅ ¡Pago recibido exitosamente!

Hola {recipient_name},

Confirmamos que hemos recibido tu pago de ${amount} MXN.

📧 Te enviaremos tu comprobante por email.
{invoice_text}

¡Gracias por tu preferencia!

{tenant_name}""",
                'email': """Hola {recipient_name},

¡Excelente! Hemos recibido tu pago de ${amount} MXN.

Detalles del pago:
- Monto: ${amount} MXN
- Fecha: {payment_date}
- Referencia: {payment_reference}

{invoice_text}

Gracias por tu confianza.

Saludos,
{tenant_name}"""
            },
            'payment_reminder': {
                'whatsapp': """⏰ Recordatorio: Link de pago pendiente

Hola {recipient_name},

Te recordamos que tienes un link de pago pendiente:

💰 Monto: ${amount} MXN
🔗 Link: {link_url}
⏰ Expira: {expires_at}

¡No lo dejes pasar!

{tenant_name}""",
                'email': """Hola {recipient_name},

Te recordamos que tienes un link de pago pendiente por ${amount} MXN.

Puedes realizar el pago en: {link_url}

Fecha de expiración: {expires_at}

Si ya realizaste el pago, puedes ignorar este mensaje.

Saludos,
{tenant_name}"""
            },
            'billing_form_available': {
                'whatsapp': """📄 ¡Tu pago fue exitoso! Ahora puedes facturar

Hola {recipient_name},

Tu pago de ${amount} MXN fue procesado exitosamente.

Para generar tu factura CFDI, ingresa aquí:
{billing_url}

📋 Necesitarás:
- RFC
- Razón social
- Código postal
- Uso de CFDI

{tenant_name}""",
                'email': """Hola {recipient_name},

¡Excelente! Tu pago de ${amount} MXN fue procesado exitosamente.

Para generar tu factura CFDI, por favor ingresa tus datos fiscales en:
{billing_url}

Información requerida:
- RFC (12 o 13 caracteres)
- Razón social
- Dirección fiscal
- Código postal
- Uso del CFDI

La factura será enviada a tu email una vez generada.

Saludos,
{tenant_name}"""
            },
            'invoice_ready': {
                'whatsapp': """✅ ¡Tu factura CFDI está lista!

Hola {recipient_name},

Tu factura CFDI ha sido generada exitosamente:

🧾 Folio: {invoice_folio}
💰 Total: ${invoice_total} MXN
📧 Enviada a tu email

Puedes descargarla en:
{download_url}

{tenant_name}""",
                'email': """Hola {recipient_name},

Tu factura CFDI ha sido generada exitosamente.

Detalles de la factura:
- Folio: {invoice_folio}
- Total: ${invoice_total} MXN
- UUID: {invoice_uuid}

Puedes descargar tu factura en cualquier momento desde:
{download_url}

Gracias por tu confianza.

Saludos,
{tenant_name}"""
            },
            'link_expired': {
                'whatsapp': """⏰ Link de pago expirado

Hola {recipient_name},

Tu link de pago por ${amount} MXN ha expirado:

📋 Concepto: {concept}
⏰ Expiró: {expired_at}

Si aún necesitas realizar el pago, contacta con nosotros para generar un nuevo link.

{tenant_name}""",
                'email': """Hola {recipient_name},

Te informamos que el link de pago por ${amount} MXN ha expirado.

Detalles:
- Concepto: {concept}
- Expiró el: {expired_at}

Si todavía necesitas realizar este pago, por favor contacta con nosotros y con gusto te generaremos un nuevo link.

Saludos,
{tenant_name}"""
            },
            'payment_on_cancelled_link': {
                'whatsapp': """⚠️ ALERTA: Pago recibido en link cancelado

Hola {recipient_name},

Hemos recibido un pago de {amount} para un link que fue cancelado previamente.

📋 Link: {payment_link_title}
💰 Monto: {amount}
👤 Pagador: {payer_name} ({payer_email})

DETALLES DE LA CANCELACIÓN:
🗓️ Cancelado: {cancelled_at}
👤 Por: {cancelled_by}
📝 Razón: {cancellation_reason}

⚠️ IMPORTANTE:
El pago fue registrado pero el link NO fue marcado como pagado porque ya estaba cancelado.

ACCIÓN REQUERIDA:
1. Revisar si el pago debe ser procesado o reembolsado
2. Contactar al cliente si es necesario
3. Generar factura si aplica

ID del Pago (MercadoPago): {mp_payment_id}

Por favor revisa tu panel de Kita para más detalles.

{tenant_name}""",
                'email': """Hola {recipient_name},

Hemos detectado una situación importante que requiere tu atención.

⚠️ PAGO RECIBIDO EN LINK CANCELADO

Se recibió un pago para un link que había sido cancelado previamente. Esto puede ocurrir cuando un cliente completa el pago mientras el link está siendo cancelado.

DETALLES DEL PAGO:
- Link: {payment_link_title}
- ID del Link: {payment_link_id}
- Monto: {amount}
- Pagador: {payer_name}
- Email del pagador: {payer_email}
- ID del Pago (MercadoPago): {mp_payment_id}

DETALLES DE LA CANCELACIÓN:
- Cancelado el: {cancelled_at}
- Cancelado por: {cancelled_by}
- Razón: {cancellation_reason}

ACCIÓN TOMADA POR EL SISTEMA:
✅ El pago fue registrado en la base de datos
❌ El link NO fue marcado como pagado (permanece cancelado)

ACCIÓN REQUERIDA DE TU PARTE:
1. Revisar la situación con el cliente
2. Decidir si procesar el pago o hacer un reembolso
3. Si procedes con el pago, generar la factura manualmente si es necesario
4. Actualizar el estado del link si corresponde

Puedes revisar los detalles completos en tu panel de administración de Kita o contactarnos si necesitas ayuda.

Saludos,
{tenant_name}"""
            }
        }

        template_dict = messages.get(notification_type, {})
        template = template_dict.get(channel, 'Notificación de {tenant_name}')

        # Format template with context
        try:
            return template.format(**context)
        except KeyError as e:
            logger.warning(f"Missing context key {e} for notification type {notification_type}")
            return template

    def send_payment_link_created(self, payment_link, recipient_phone: str = '', recipient_email: str = '') -> Dict[str, Any]:
        """Send notification when payment link is created"""
        context = {
            'recipient_name': payment_link.customer_name or 'Cliente',
            'amount': float(payment_link.amount),  # ✅ Float para template filter
            'link_url': f"{settings.APP_BASE_URL}/hola/{payment_link.token}/",
            'expires_at': payment_link.expires_at,  # ✅ Datetime object (se serializa después)
            'title': payment_link.title,  # ✅ Nombre correcto para template
            'description': payment_link.description or '',  # ✅ Agregar description
            'requires_invoice': payment_link.requires_invoice,  # ✅ Para mostrar info de factura
            'concept': payment_link.title,  # Mantener para backward compatibility con texto plano
            'tenant_name': payment_link.tenant.name  # ✅ Nombre registrado en Kita
        }

        return self.send_notification(
            tenant=payment_link.tenant,
            notification_type='link_created',
            recipient_email=recipient_email or payment_link.customer_email,
            recipient_phone=recipient_phone,
            recipient_name=payment_link.customer_name,
            context=context,
            payment_link_id=str(payment_link.id)
        )

    def send_payment_received(self, payment) -> Dict[str, Any]:
        """Send notification when payment is received"""
        invoice_text = ""
        billing_form_url = ""
        if payment.payment_link.requires_invoice:
            invoice_text = "📄 Podrás generar tu factura CFDI en el link que te enviaremos."
            billing_form_url = f"{settings.APP_BASE_URL}/facturar/{payment.payment_link.token}/"

        context = {
            'recipient_name': payment.payer_name or 'Cliente',
            'amount': float(payment.amount),
            'title': payment.payment_link.title,  # ✅ Para template
            'paid_at': payment.processed_at or payment.created_at,  # ✅ Datetime object
            'payment_id': payment.mp_payment_id or str(payment.id),  # ✅ ID visible
            'requires_invoice': payment.payment_link.requires_invoice,  # ✅ Para template
            'billing_form_url': billing_form_url,  # ✅ Para template
            'payment_date': payment.processed_at.strftime('%d/%m/%Y %H:%M') if payment.processed_at else '',  # Backward compatibility
            'payment_reference': payment.mp_payment_id,  # Backward compatibility
            'invoice_text': invoice_text,  # Backward compatibility
            'tenant_name': payment.tenant.name  # ✅ Nombre registrado en Kita
        }

        return self.send_notification(
            tenant=payment.tenant,
            notification_type='payment_received',
            recipient_email=payment.payer_email,
            recipient_phone=payment.payer_phone,
            recipient_name=payment.payer_name,
            context=context,
            payment_id=str(payment.id)
        )

    def send_payment_reminder(self, payment_link) -> Dict[str, Any]:
        """Send payment reminder for active links"""
        context = {
            'recipient_name': payment_link.customer_name or 'Cliente',
            'amount': float(payment_link.amount),
            'link_url': f"{settings.APP_BASE_URL}/hola/{payment_link.token}/",
            'expires_at': payment_link.expires_at,  # ✅ Datetime object
            'title': payment_link.title,  # ✅ Para template
            'description': payment_link.description or '',  # ✅ Para template
            'tenant_name': payment_link.tenant.name  # ✅ Nombre registrado en Kita
        }

        result = self.send_notification(
            tenant=payment_link.tenant,
            notification_type='payment_reminder',
            recipient_email=payment_link.customer_email,
            recipient_phone='',  # Only send reminders via email
            recipient_name=payment_link.customer_name,
            context=context,
            payment_link_id=str(payment_link.id)
        )

        # Track reminder if successful
        if result['success']:
            from payments.models import PaymentLinkReminder
            from core.models import Notification

            try:
                notification = Notification.objects.get(id=result['notification_id'])
                PaymentLinkReminder.objects.create(
                    tenant=payment_link.tenant,
                    payment_link=payment_link,
                    notification=notification,
                    reminder_type='manual'
                )
            except Exception as e:
                logger.error(f"Failed to track reminder: {e}")

        return result

    def send_billing_form_link(self, payment) -> Dict[str, Any]:
        """Send billing form link after successful payment"""
        context = {
            'recipient_name': payment.payer_name or 'Cliente',
            'amount': float(payment.amount),
            'billing_form_url': f"{settings.APP_BASE_URL}/facturar/{payment.payment_link.token}/",  # ✅ Nombre correcto
            'billing_url': f"{settings.APP_BASE_URL}/facturar/{payment.payment_link.token}/",  # Backward compatibility
            'title': payment.payment_link.title,  # ✅ Para template
            'paid_at': payment.processed_at or payment.created_at,  # ✅ Cuándo se pagó
            'payment_id': payment.mp_payment_id or str(payment.id),  # ✅ ID visible
            'tenant_name': payment.tenant.name  # ✅ Nombre registrado en Kita
        }

        return self.send_notification(
            tenant=payment.tenant,
            notification_type='billing_form_available',
            recipient_email=payment.payer_email,
            recipient_phone=payment.payer_phone,
            recipient_name=payment.payer_name,
            context=context,
            payment_id=str(payment.id)
        )

    def send_invoice_to_customer(self, invoice, customer_email) -> Dict[str, Any]:
        """Send invoice ready notification to customer"""
        context = {
            'recipient_name': invoice.customer_name,
            'invoice_uuid': str(invoice.uuid),
            'invoice_serie': invoice.serie or 'A',  # ✅ Serie separada
            'invoice_folio': invoice.folio,  # ✅ Folio separado
            'amount': float(invoice.total),  # ✅ Total de la factura
            'customer_rfc': invoice.customer_rfc,  # ✅ RFC del cliente
            'customer_name': invoice.customer_name,  # ✅ Nombre del cliente
            'stamped_at': invoice.stamped_at,  # ✅ Fecha de timbrado
            'download_url': f"{settings.APP_BASE_URL}/descargar/factura/{invoice.uuid}/",  # ✅ URL correcta
            'invoice_total': invoice.total,  # Backward compatibility
            'tenant_name': invoice.tenant.name  # ✅ Nombre registrado en Kita
        }

        return self.send_notification(
            tenant=invoice.tenant,
            notification_type='invoice_ready',
            recipient_email=customer_email,
            recipient_phone='',
            recipient_name=invoice.customer_name,
            context=context,
            invoice_id=str(invoice.id)
        )

    def send_link_expired(self, payment_link) -> Dict[str, Any]:
        """Send notification when payment link expires without payment."""
        context = {
            'recipient_name': payment_link.customer_name or 'Cliente',
            'amount': float(payment_link.amount),
            'title': payment_link.title,  # ✅ Para template
            'concept': payment_link.title,  # Backward compatibility
            'expired_at': payment_link.expires_at,  # ✅ Datetime object
            'tenant_name': payment_link.tenant.name  # ✅ Nombre registrado en Kita
        }

        return self.send_notification(
            tenant=payment_link.tenant,
            notification_type='link_expired',
            recipient_email=payment_link.customer_email,
            recipient_phone='',  # Solo email para expirados
            recipient_name=payment_link.customer_name,
            context=context,
            payment_link_id=str(payment_link.id)
        )

    def send_link_cancelled(self, payment_link, cancellation_reason: str = 'not_specified') -> Dict[str, Any]:
        """Send notification when payment link is cancelled by merchant."""
        # Map reason to customer-friendly message
        reason_messages = {
            'paid_other_method': 'el pago ya fue recibido por otro medio',
            'wrong_amount': 'se detectó un error en los datos del link',
            'customer_request': 'así lo solicitaste',
            'duplicate': 'se generó un link actualizado',
            'expired_intent': 'el periodo de pago finalizó',
            'other': 'razones administrativas',
            'not_specified': 'razones administrativas'
        }
        reason_text = reason_messages.get(cancellation_reason, 'razones administrativas')

        context = {
            'recipient_name': payment_link.customer_name or 'Cliente',
            'amount': float(payment_link.amount),
            'title': payment_link.title,
            'description': payment_link.description or '',
            'cancelled_at': timezone.now(),  # ✅ Cuándo se canceló
            'cancellation_reason_text': reason_text,  # ✅ Texto amigable
            'tenant_name': payment_link.tenant.name
        }

        return self.send_notification(
            tenant=payment_link.tenant,
            notification_type='link_cancelled',
            recipient_email=payment_link.customer_email,
            recipient_phone='',  # Solo email
            recipient_name=payment_link.customer_name,
            context=context,
            payment_link_id=str(payment_link.id)
        )

    def _get_html_template(self, notification_type: str) -> str:
        """
        Get HTML template path for notification type.

        Returns:
            Template path or empty string if no HTML template exists
        """
        templates = {
            # Payment links
            'link_created': 'emails/payments/link_created.html',
            'payment_received': 'emails/payments/payment_received.html',
            'billing_form_available': 'emails/payments/billing_form_available.html',  # ✅ Template propio
            'payment_reminder': 'emails/payments/payment_reminder.html',  # ✅ Template propio
            'link_expired': 'emails/payments/link_expired.html',  # ✅ Template propio
            'link_cancelled': 'emails/payments/link_cancelled.html',  # ✅ Nuevo

            # Invoicing
            'invoice_ready': 'emails/invoicing/invoice_ready.html',
        }
        return templates.get(notification_type, '')

    def _build_template_context(self, notification: 'Notification') -> dict:
        """
        Build context dictionary for email templates.

        Args:
            notification: Notification instance with metadata

        Returns:
            Context dict with all variables needed for templates
        """
        from django.conf import settings
        from django.utils.dateparse import parse_datetime

        # Base context (siempre disponible)
        context = {
            'tenant': notification.tenant,
            'recipient_name': notification.recipient_name or 'Cliente',
            'app_base_url': getattr(settings, 'APP_BASE_URL', 'https://kita.mx'),
        }

        # Add metadata fields to context (ya es dict, no necesita parsear JSON)
        if notification.metadata:
            # notification.metadata es un dict (JSONField)
            metadata = notification.metadata.copy()

            # Convertir strings de fecha de vuelta a datetime para template filters
            import pytz
            mexico_tz = pytz.timezone('America/Mexico_City')

            for key in ['expires_at', 'paid_at', 'stamped_at', 'expired_at']:
                if key in metadata and isinstance(metadata[key], str):
                    try:
                        # Parsear fecha en formato dd/mm/yyyy HH:MM
                        from datetime import datetime
                        naive_dt = datetime.strptime(metadata[key], '%d/%m/%Y %H:%M')
                        # ✅ Hacer timezone-aware en México
                        metadata[key] = mexico_tz.localize(naive_dt)
                    except (ValueError, TypeError):
                        # Si falla, dejar como string
                        pass

            context.update(metadata)

        # Notification type specific context
        if notification.notification_type == 'link_created':
            # Ya tiene: link_url, amount, title, description, expires_at, requires_invoice
            pass

        elif notification.notification_type == 'payment_received':
            # Ya tiene: amount, title, paid_at, payment_id, requires_invoice, billing_form_url
            pass

        elif notification.notification_type == 'invoice_ready':
            # Ya tiene: invoice_uuid, invoice_serie, invoice_folio, amount, customer_rfc, customer_name, stamped_at, download_url
            pass

        return context


# Singleton instance
notification_service = NotificationService()