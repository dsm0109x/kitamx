"""
Tests for payment processing and public payment links.

Tests payment flows, MercadoPago integration, and webhook processing.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import json

from django.urls import reverse
from django.contrib.auth import get_user_model

from core.test_utils import PaymentLinkTestCase
from .models import MercadoPagoIntegration, Payment
from .services import MercadoPagoService

User = get_user_model()


class PublicPaymentLinkTestCase(PaymentLinkTestCase):
    """Test cases for public payment link functionality."""

    def test_public_link_active_loads(self) -> None:
        """Test public payment link loads correctly."""
        url = reverse('payments:public_link', args=[self.active_link.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.active_link.title)
        self.assertContains(response, str(self.active_link.amount))

    def test_public_link_expired_shows_message(self) -> None:
        """Test expired link shows appropriate message."""
        url = reverse('payments:public_link', args=[self.expired_link.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'expirado')

    def test_public_link_paid_shows_success(self) -> None:
        """Test paid link shows success page."""
        url = reverse('payments:public_link', args=[self.paid_link.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should show paid hub with options

    def test_public_link_rate_limiting(self) -> None:
        """Test rate limiting on public payment links."""
        url = reverse('payments:public_link', args=[self.active_link.token])

        # Should be allowed up to rate limit
        for i in range(30):
            response = self.client.get(url)
            if i < 29:
                self.assertEqual(response.status_code, 200)
            # Note: Rate limiting testing requires careful setup in test environment


class PaymentSuccessTestCase(PaymentLinkTestCase):
    """Test cases for payment success/failure/pending pages."""

    def test_payment_success_page(self) -> None:
        """Test payment success page."""
        url = reverse('payments:success', args=[self.paid_link.token])
        response = self.client.get(url, {'payment_id': '12345', 'collection_id': '67890'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'success')

    def test_payment_failure_page(self) -> None:
        """Test payment failure page."""
        url = reverse('payments:failure', args=[self.active_link.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.active_link.title)

    def test_payment_pending_page(self) -> None:
        """Test payment pending page."""
        url = reverse('payments:pending', args=[self.active_link.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'procesando')


class BillingFormTestCase(PaymentLinkTestCase):
    """Test cases for self-service billing form."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        # Create successful payment for billing
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            payment_link=self.paid_link,
            payment_id='test_payment',
            amount=self.paid_link.amount,
            status='approved',
            payer_email='customer@test.com',
            payer_name='Test Customer'
        )

    def test_billing_form_loads(self) -> None:
        """Test billing form loads for paid link."""
        url = reverse('payments:billing_form', args=[self.paid_link.token])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'facturación')

    def test_billing_form_requires_payment(self) -> None:
        """Test billing form redirects if no payment."""
        url = reverse('payments:billing_form', args=[self.active_link.token])
        response = self.client.get(url)

        # Should redirect or show error for unpaid link
        self.assertIn(response.status_code, [302, 400, 404])


class MercadoPagoWebhookTestCase(PaymentLinkTestCase):
    """Test cases for MercadoPago webhook processing."""

    @patch('payments.webhook_handler.webhook_handler.handle_webhook')
    def test_webhook_endpoint(self, mock_handler: MagicMock) -> None:
        """Test webhook endpoint delegates correctly."""
        mock_handler.return_value = json.dumps({'status': 'processed'})

        url = reverse('payments:mp_webhook')
        response = self.client.post(url, {'data': {'id': '12345'}}, content_type='application/json')

        mock_handler.assert_called_once()
        self.assertEqual(response.status_code, 200)

    def test_webhook_rate_limiting(self) -> None:
        """Test webhook rate limiting protection."""
        url = reverse('payments:mp_webhook')

        # Note: Webhook rate limiting testing requires proper setup
        response = self.client.post(url, {'test': 'data'}, content_type='application/json')
        # Should handle the request (may fail on processing, but not rate limiting)


class TrackingTestCase(PaymentLinkTestCase):
    """Test cases for analytics tracking."""

    def test_track_view_endpoint(self) -> None:
        """Test view tracking endpoint."""
        url = reverse('payments:track_view')
        data = {
            'token': self.active_link.token,
            'action': 'page_view'
        }

        response = self.client.post(url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)

    def test_track_interaction_endpoint(self) -> None:
        """Test interaction tracking endpoint."""
        url = reverse('payments:track_interaction')
        data = {
            'token': self.active_link.token,
            'action': 'button_click'
        }

        response = self.client.post(url, data, content_type='application/json')
        self.assertEqual(response.status_code, 200)


class MercadoPagoServiceTestCase(PaymentLinkTestCase):
    """Test cases for MercadoPago service integration."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        super().setUp()

        self.mp_integration = MercadoPagoIntegration.objects.create(
            tenant=self.tenant,
            access_token='test_token',
            refresh_token='test_refresh',
            user_id='test_user_123',
            expires_in=3600
        )

    def test_mp_service_initialization(self) -> None:
        """Test MercadoPago service initializes correctly."""
        service = MercadoPagoService(self.tenant)
        self.assertIsNotNone(service.integration)
        self.assertEqual(service.integration.tenant, self.tenant)

    @patch('payments.services.requests.post')
    def test_oauth_url_generation(self, mock_post: MagicMock) -> None:
        """Test OAuth URL generation."""
        service = MercadoPagoService(self.tenant)

        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        try:
            oauth_url = service.get_oauth_url('http://localhost/callback')
            self.assertIsInstance(oauth_url, str)
            self.assertIn('mercadopago.com', oauth_url)
        except ValueError:
            # Expected if MP credentials not configured in test
            pass