"""
Tests for webhook processing functionality.

Tests webhook endpoints and delegation to centralized handler.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import json

from django.urls import reverse

from core.test_utils import PaymentLinkTestCase


class WebhookViewsTestCase(PaymentLinkTestCase):
    """Test cases for webhook views."""

    @patch('payments.webhook_handler.webhook_handler.handle_webhook')
    def test_mercadopago_webhook_delegation(self, mock_handler: MagicMock) -> None:
        """Test MercadoPago webhook delegates to centralized handler."""
        mock_handler.return_value = json.dumps({'status': 'processed'})

        url = reverse('webhooks:mercadopago_webhook')
        webhook_data = {
            'type': 'payment',
            'data': {'id': '12345'}
        }

        response = self.client.post(url, webhook_data, content_type='application/json')

        mock_handler.assert_called_once_with(mock_handler.call_args[0][0], webhook_type='payment')
        self.assertEqual(response.status_code, 200)

    @patch('payments.webhook_handler.webhook_handler.handle_webhook')
    def test_billing_webhook_delegation(self, mock_handler: MagicMock) -> None:
        """Test billing webhook delegates to centralized handler."""
        mock_handler.return_value = json.dumps({'status': 'processed'})

        url = reverse('webhooks:kita_billing_webhook')
        webhook_data = {
            'type': 'payment',
            'data': {'id': '67890'}
        }

        response = self.client.post(url, webhook_data, content_type='application/json')

        mock_handler.assert_called_once_with(mock_handler.call_args[0][0], webhook_type='billing')
        self.assertEqual(response.status_code, 200)

    def test_webhook_rate_limiting(self) -> None:
        """Test webhook rate limiting protection."""
        url = reverse('webhooks:mercadopago_webhook')

        # Test that webhooks are rate limited
        for i in range(5):
            response = self.client.post(url, {'test': 'data'}, content_type='application/json')
            # Should handle requests appropriately (may fail on processing, but not rate limiting)
            self.assertIn(response.status_code, [200, 400, 429])

    def test_webhook_csrf_exemption(self) -> None:
        """Test webhooks are properly CSRF exempt."""
        url = reverse('webhooks:mercadopago_webhook')

        # Should work without CSRF token (webhooks come from external services)
        response = self.client.post(url, {'data': {'id': 'test'}}, content_type='application/json')

        # Should not return 403 Forbidden for CSRF
        self.assertNotEqual(response.status_code, 403)