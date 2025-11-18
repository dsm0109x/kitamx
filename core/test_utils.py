"""
Utilidades comunes para tests de la aplicación Kita.

Este módulo proporciona clases base y helpers para reducir duplicación
en tests y asegurar consistencia en el setup de datos de prueba.
"""
from __future__ import annotations
from typing import Optional, Dict, Any

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta

from core.models import Tenant, TenantUser

User = get_user_model()


class KitaTestCase(TestCase):
    """
    Clase base para tests de Kita con setup común de tenant y usuario.

    Proporciona:
    - Tenant de prueba configurado
    - Usuario owner autenticado
    - Cliente HTTP listo para requests
    - Cache limpio para cada test

    Usage:
        class MyAppTestCase(KitaTestCase):
            def test_something(self):
                # self.tenant, self.user, self.tenant_user ya disponibles
                response = self.client.get('/my-view/')
                self.assertEqual(response.status_code, 200)
    """

    @classmethod
    def setUpClass(cls) -> None:
        """Setup a nivel de clase para optimizar performance."""
        super().setUpClass()

    def setUp(self) -> None:
        """Setup común para todos los tests."""
        # Limpiar cache antes de cada test
        cache.clear()

        # Setup básico de datos
        self.setup_tenant()
        self.setup_user()
        self.setup_authentication()

        # Cliente HTTP
        self.client = Client()

    def setup_tenant(self) -> None:
        """Crear tenant de prueba con configuración estándar."""
        self.tenant = Tenant.objects.create(
            name='Test Company',
            slug='test-company',
            rfc='ABC010101ABC',
            email='info@test.com',
            domain='test.example.com'
        )

    def setup_user(self) -> None:
        """Crear usuario owner de prueba."""
        self.user = User.objects.create_user(
            email='owner@test.com',
            password='TestPass123!',
            first_name='Test',
            last_name='Owner',
            username='testowner',
            onboarding_completed=True
        )

        # Crear relación tenant-user
        self.tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            email=self.user.email,
            name=self.user.get_full_name(),
            is_owner=True,
            role='owner'
        )

    def setup_authentication(self) -> None:
        """Autenticar usuario para requests."""
        self.client = Client()
        login_success = self.client.login(
            username='testowner',
            password='TestPass123!'
        )
        self.assertTrue(login_success, "Failed to login test user")

    def create_additional_user(self,
                              email: str = 'user2@test.com',
                              is_owner: bool = False,
                              **kwargs) -> tuple[User, TenantUser]:
        """
        Crear usuario adicional para tests que requieren múltiples usuarios.

        Args:
            email: Email del usuario
            is_owner: Si el usuario es owner del tenant
            **kwargs: Parámetros adicionales para User.objects.create_user()

        Returns:
            Tuple con (User, TenantUser) creados
        """
        defaults = {
            'first_name': 'Additional',
            'last_name': 'User',
            'username': email.split('@')[0],
            'password': 'TestPass123!'
        }
        defaults.update(kwargs)

        user = User.objects.create_user(email=email, **defaults)
        tenant_user = TenantUser.objects.create(
            tenant=self.tenant,
            email=user.email,
            name=user.get_full_name(),
            is_owner=is_owner
        )

        return user, tenant_user

    def authenticate_as(self, user: User) -> bool:
        """
        Cambiar autenticación a otro usuario.

        Args:
            user: Usuario para autenticar

        Returns:
            True si la autenticación fue exitosa
        """
        self.client.logout()
        return self.client.login(
            username=user.username,
            password='TestPass123!'
        )

    def assert_tenant_context(self, response, tenant: Optional[Tenant] = None) -> None:
        """
        Verificar que el response tiene el contexto de tenant correcto.

        Args:
            response: Django HTTP response
            tenant: Tenant esperado (usa self.tenant por defecto)
        """
        expected_tenant = tenant or self.tenant
        self.assertIn('tenant', response.context)
        self.assertEqual(response.context['tenant'], expected_tenant)

    def assert_requires_authentication(self, url: str, method: str = 'GET') -> None:
        """
        Verificar que una URL requiere autenticación.

        Args:
            url: URL a verificar
            method: Método HTTP ('GET', 'POST', etc.)
        """
        self.client.logout()

        if method.upper() == 'GET':
            response = self.client.get(url)
        elif method.upper() == 'POST':
            response = self.client.post(url)
        else:
            response = self.client.generic(method, url)

        self.assertIn(response.status_code, [302, 401, 403],
                     f"URL {url} should require authentication")

    def assert_requires_owner(self, url: str, method: str = 'GET') -> None:
        """
        Verificar que una URL requiere permisos de owner.

        Args:
            url: URL a verificar
            method: Método HTTP
        """
        # Crear usuario no-owner
        non_owner, _ = self.create_additional_user(
            email='nonowner@test.com',
            is_owner=False
        )

        # Autenticar como no-owner
        self.authenticate_as(non_owner)

        if method.upper() == 'GET':
            response = self.client.get(url)
        elif method.upper() == 'POST':
            response = self.client.post(url)
        else:
            response = self.client.generic(method, url)

        self.assertIn(response.status_code, [403, 404],
                     f"URL {url} should require owner permissions")


class PaymentLinkTestMixin:
    """
    Mixin para tests que requieren PaymentLinks de prueba.

    Debe usarse junto con KitaTestCase.
    """

    def setUp(self) -> None:
        """Extender setup base con PaymentLinks."""
        super().setUp()
        self.setup_payment_links()

    def setup_payment_links(self) -> None:
        """Crear PaymentLinks de prueba con diferentes estados."""
        from payments.models import PaymentLink

        # Link activo
        self.active_link = PaymentLink.objects.create(
            tenant=self.tenant,
            token='test_token_active',
            title='Active Test Link',
            amount='100.00',
            status='active',
            expires_at=timezone.now() + timedelta(days=7)
        )

        # Link pagado
        self.paid_link = PaymentLink.objects.create(
            tenant=self.tenant,
            token='test_token_paid',
            title='Paid Test Link',
            amount='250.00',
            status='paid',
            expires_at=timezone.now() + timedelta(days=7)
        )

        # Link expirado
        self.expired_link = PaymentLink.objects.create(
            tenant=self.tenant,
            token='test_token_expired',
            title='Expired Test Link',
            amount='75.00',
            status='expired',
            expires_at=timezone.now() - timedelta(days=1)
        )


class InvoiceTestMixin:
    """
    Mixin para tests que requieren facturas de prueba.

    Debe usarse junto con KitaTestCase.
    """

    def setUp(self) -> None:
        """Extender setup base con facturas."""
        super().setUp()
        self.setup_invoices()

    def setup_invoices(self) -> None:
        """Crear facturas de prueba con diferentes estados."""
        from invoicing.models import Invoice

        # Factura timbrada
        self.stamped_invoice = Invoice.objects.create(
            tenant=self.tenant,
            folio='001',
            serie='A',
            customer_name='Test Customer',
            customer_rfc='XYZ010101XYZ',
            customer_email='customer@test.com',
            subtotal='100.00',
            tax_amount='16.00',
            total='116.00',
            status='stamped'
        )

        # Factura borrador
        self.draft_invoice = Invoice.objects.create(
            tenant=self.tenant,
            folio='002',
            serie='A',
            customer_name='Test Customer 2',
            customer_rfc='ABC010101ABC',
            customer_email='customer2@test.com',
            subtotal='200.00',
            tax_amount='32.00',
            total='232.00',
            status='draft'
        )


# Convenience classes que combinan mixins comunes
class PaymentLinkTestCase(PaymentLinkTestMixin, KitaTestCase):
    """TestCase con setup de tenant + PaymentLinks."""
    pass


class InvoiceTestCase(InvoiceTestMixin, KitaTestCase):
    """TestCase con setup de tenant + Invoices."""
    pass


class FullKitaTestCase(InvoiceTestMixin, PaymentLinkTestMixin, KitaTestCase):
    """TestCase con setup completo: tenant + PaymentLinks + Invoices."""
    pass


# Helpers para datos de prueba
def create_test_payment_data() -> Dict[str, Any]:
    """Crear datos de pago de prueba para requests."""
    return {
        'title': 'Test Payment Link',
        'amount': '150.00',
        'description': 'Test payment description',
        'customer_name': 'John Doe',
        'customer_email': 'john@example.com',
        'expires_days': 7,
        'requires_invoice': False
    }


def create_test_invoice_data() -> Dict[str, Any]:
    """Crear datos de factura de prueba para requests."""
    return {
        'customer_name': 'Test Customer',
        'customer_rfc': 'XYZ010101XYZ',
        'customer_email': 'customer@test.com',
        'customer_address': 'Test Address 123',
        'cfdi_use': '01',  # Adquisición de mercancías
        'payment_method': 'PUE',  # Pago en una sola exhibición
        'payment_form': '01',  # Efectivo
        'subtotal': '100.00',
        'tax_amount': '16.00',
        'total': '116.00'
    }


__all__ = [
    'KitaTestCase',
    'PaymentLinkTestMixin',
    'InvoiceTestMixin',
    'PaymentLinkTestCase',
    'InvoiceTestCase',
    'FullKitaTestCase',
    'create_test_payment_data',
    'create_test_invoice_data',
]