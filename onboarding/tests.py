"""
Tests for onboarding flow and tenant creation.

Tests user onboarding steps, tenant creation, and MercadoPago integration.
"""
from __future__ import annotations
from unittest.mock import patch, MagicMock
import json

from django.urls import reverse
from django.contrib.auth import get_user_model

from core.test_utils import KitaTestCase
from core.models import Tenant
from .forms import TenantIdentityForm
from .utils import generate_unique_slug

User = get_user_model()


class OnboardingFlowTestCase(KitaTestCase):
    """Test cases for onboarding flow."""

    def test_onboarding_start_redirects_properly(self) -> None:
        """Test onboarding start redirects to appropriate step."""
        # User with no onboarding progress
        self.user.onboarding_step = 1
        self.user.onboarding_completed = False
        self.user.save()

        url = reverse('onboarding:start')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('step1', response.url)

    def test_onboarding_step1_loads(self) -> None:
        """Test onboarding step 1 loads correctly."""
        self.user.onboarding_step = 1
        self.user.onboarding_completed = False
        self.user.save()

        url = reverse('onboarding:step1')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Identidad de tu Empresa')

    def test_tenant_creation_step1(self) -> None:
        """Test tenant creation in step 1."""
        self.user.onboarding_step = 1
        self.user.onboarding_completed = False
        self.user.save()

        # Delete the existing tenant to test creation
        self.tenant.delete()

        url = reverse('onboarding:step1')
        form_data = {
            'name': 'New Test Company',
            'business_name': 'New Test Company SA de CV',
            'rfc': 'NTC010101NTC',
            'email': 'newtest@company.com',
            'phone': '+5215551234567',
            'address': 'Test Address 123',
            'fiscal_regime': '601',
            'postal_code': '12345'
        }

        response = self.client.post(url, form_data)

        # Should redirect to step 2 after successful tenant creation
        self.assertEqual(response.status_code, 302)
        self.assertIn('step2', response.url)

        # Verify tenant was created
        self.assertTrue(Tenant.objects.filter(rfc='NTC010101NTC').exists())

    def test_step2_requires_tenant(self) -> None:
        """Test step 2 requires existing tenant."""
        url = reverse('onboarding:step2')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mercado Pago')

    @patch('onboarding.views.MercadoPagoService')
    def test_mp_oauth_integration(self, mock_mp_service: MagicMock) -> None:
        """Test MercadoPago OAuth integration."""
        mock_service = MagicMock()
        mock_mp_service.return_value = mock_service
        mock_service.integration = None
        mock_service.get_oauth_url.return_value = 'https://auth.mercadopago.com.mx/test'

        url = reverse('onboarding:step2')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'mercadopago')

    def test_trial_activation(self) -> None:
        """Test trial activation endpoint."""
        url = reverse('onboarding:start_trial')

        response = self.client.post(url, content_type='application/json')

        # Should create subscription trial
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))


class OnboardingFormsTestCase(KitaTestCase):
    """Test cases for onboarding forms."""

    def test_tenant_identity_form_validation(self) -> None:
        """Test tenant identity form validation."""
        valid_data = {
            'name': 'Test Company',
            'business_name': 'Test Company SA de CV',
            'rfc': 'TCO010101TCO',
            'email': 'test@company.com',
            'fiscal_regime': '601'
        }

        form = TenantIdentityForm(data=valid_data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_rfc_validation_ajax(self) -> None:
        """Test RFC validation AJAX endpoint."""
        url = reverse('onboarding:validate_rfc')
        data = {'rfc': 'VALID123456789'}

        response = self.client.post(url, json.dumps(data), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertIn('valid', result)

    def test_business_name_validation_ajax(self) -> None:
        """Test business name validation AJAX endpoint."""
        url = reverse('onboarding:validate_business_name')
        data = {'business_name': 'Valid Business Name SA de CV'}

        response = self.client.post(url, json.dumps(data), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertIn('valid', result)


class OnboardingUtilsTestCase(KitaTestCase):
    """Test cases for onboarding utilities."""

    def test_generate_unique_slug(self) -> None:
        """Test unique slug generation."""
        slug1 = generate_unique_slug('Test Company')
        slug2 = generate_unique_slug('Test Company')

        self.assertIsInstance(slug1, str)
        self.assertNotEqual(slug1, slug2)  # Should be unique
        self.assertIn('test-company', slug1.lower())