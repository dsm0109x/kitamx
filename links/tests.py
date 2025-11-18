"""Tests for Payment Links management module.

Comprehensive test coverage for link CRUD operations, DataTables integration,
duplicating, canceling, editing, and sending reminders.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
import json
import uuid
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, Mock

from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from core.test_utils import PaymentLinkTestCase
from core.models import AuditLog, Tenant
from payments.models import Payment, PaymentLink

if TYPE_CHECKING:
    from django.contrib.auth.models import User

User = get_user_model()


class LinksViewTestSetup(PaymentLinkTestCase):
    """Base test class with common setup - now inherits from PaymentLinkTestCase."""

    def setUp(self) -> None:
        """Extend setup with specific payment data."""
        super().setUp()

        # Create payment for the paid_link from base class
        self.payment = Payment.objects.create(
            tenant=self.tenant,
            payment_link=self.paid_link,
            payment_id='test_payment_id',
            amount=self.paid_link.amount,
            status='approved',
            payer_email='customer@test.com',
            payer_name='Test Customer'
        )


class LinksIndexViewTests(LinksViewTestSetup):
    """Tests for links index view."""

    def test_links_index_authenticated(self) -> None:
        """Test authenticated access to links index."""
        url = reverse('links:index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Links de Pago')
        self.assertIn('stats', response.context)

    def test_links_index_unauthenticated(self) -> None:
        """Test unauthenticated access redirects to login."""
        self.client.logout()
        url = reverse('links:index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_links_index_no_tenant(self) -> None:
        """Test redirect when user has no tenant."""
        self.tenant_user.delete()
        url = reverse('links:index')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/incorporacion/', response.url)  # 🇪🇸 Migrado (onboarding:start)

    def test_links_index_stats_calculation(self) -> None:
        """Test stats calculation in index view."""
        url = reverse('links:index')
        response = self.client.get(url)

        stats = response.context['stats']
        self.assertEqual(stats['total'], 2)
        self.assertEqual(stats['active'], 1)
        self.assertEqual(stats['paid'], 1)
        self.assertEqual(stats['revenue'], 200.0)

    def test_links_index_caching(self) -> None:
        """Test that stats are cached."""
        url = reverse('links:index')

        # First request - cache miss
        with self.assertNumQueries(6):  # Adjust based on actual queries
            response1 = self.client.get(url)

        # Second request - cache hit (should use fewer queries)
        with self.assertNumQueries(3):  # Fewer queries due to caching
            response2 = self.client.get(url)

        self.assertEqual(response1.context['stats'], response2.context['stats'])


class AjaxDataViewTests(LinksViewTestSetup):
    """Tests for DataTables AJAX endpoint."""

    def test_ajax_data_basic(self) -> None:
        """Test basic DataTables data retrieval."""
        url = reverse('links:ajax_data')
        response = self.client.get(url, {
            'draw': '1',
            'start': '0',
            'length': '10',
            'search[value]': '',
            'order[0][column]': '3',
            'order[0][dir]': 'desc'
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['draw'], 1)
        self.assertEqual(data['recordsTotal'], 2)
        self.assertEqual(len(data['data']), 2)

    def test_ajax_data_search(self) -> None:
        """Test DataTables search functionality."""
        url = reverse('links:ajax_data')
        response = self.client.get(url, {
            'draw': '1',
            'start': '0',
            'length': '10',
            'search[value]': 'Active',
            'order[0][column]': '0',
            'order[0][dir]': 'asc'
        })

        data = response.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['title'], 'Active Link')

    def test_ajax_data_status_filter(self) -> None:
        """Test filtering by status."""
        url = reverse('links:ajax_data')
        response = self.client.get(url, {
            'draw': '1',
            'start': '0',
            'length': '10',
            'status': 'paid'
        })

        data = response.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['status'], 'paid')

    def test_ajax_data_amount_filter(self) -> None:
        """Test filtering by amount range."""
        url = reverse('links:ajax_data')
        response = self.client.get(url, {
            'draw': '1',
            'start': '0',
            'length': '10',
            'amount_min': '150',
            'amount_max': '250'
        })

        data = response.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['amount'], 200.0)

    def test_ajax_data_pagination(self) -> None:
        """Test pagination in DataTables."""
        # Create more links
        for i in range(10):
            PaymentLink.objects.create(
                tenant=self.tenant,
                token=f'test_token_{i+3}',
                title=f'Link {i+3}',
                amount=Decimal('50.00'),
                expires_at=timezone.now() + timedelta(days=1)
            )

        url = reverse('links:ajax_data')
        response = self.client.get(url, {
            'draw': '1',
            'start': '5',
            'length': '5'
        })

        data = response.json()
        self.assertEqual(data['recordsTotal'], 12)
        self.assertEqual(len(data['data']), 5)


class StatsViewTests(LinksViewTestSetup):
    """Tests for stats endpoint."""

    def test_stats_endpoint(self) -> None:
        """Test stats JSON endpoint."""
        url = reverse('links:stats')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['stats']['total'], 2)
        self.assertEqual(data['stats']['active'], 1)
        self.assertEqual(data['stats']['paid'], 1)

    def test_stats_caching(self) -> None:
        """Test that stats endpoint uses caching."""
        url = reverse('links:stats')

        # First request - calculate stats
        response1 = self.client.get(url)
        stats1 = response1.json()['stats']

        # Modify data (should not affect cached result)
        self.active_link.status = 'expired'
        self.active_link.save()

        # Second request - should return cached data
        response2 = self.client.get(url)
        stats2 = response2.json()['stats']

        self.assertEqual(stats1, stats2)  # Should be same due to cache


class DetailViewTests(LinksViewTestSetup):
    """Tests for link detail view."""

    def test_detail_view(self) -> None:
        """Test link detail panel."""
        url = reverse('links:detail', args=[self.active_link.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('link', response.context)
        self.assertEqual(response.context['link'].id, self.active_link.id)

    def test_detail_view_not_found(self) -> None:
        """Test detail view with non-existent link."""
        fake_id = uuid.uuid4()
        url = reverse('links:detail', args=[fake_id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_detail_view_wrong_tenant(self) -> None:
        """Test detail view with link from different tenant."""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            domain="other.example.com"
        )
        other_link = PaymentLink.objects.create(
            tenant=other_tenant,
            token='other_token',
            title='Other Link',
            amount=Decimal('50.00'),
            expires_at=timezone.now() + timedelta(days=1)
        )

        url = reverse('links:detail', args=[other_link.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class DuplicateViewTests(LinksViewTestSetup):
    """Tests for link duplication."""

    def test_duplicate_link_success(self) -> None:
        """Test successful link duplication."""
        url = reverse('links:duplicate')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('link_id', data)
        self.assertIn('token', data)

        # Verify new link was created
        new_link = PaymentLink.objects.get(id=data['link_id'])
        self.assertEqual(new_link.title, 'Active Link (Copia)')
        self.assertEqual(new_link.amount, self.active_link.amount)
        self.assertNotEqual(new_link.token, self.active_link.token)

    def test_duplicate_link_audit_log(self) -> None:
        """Test that duplication creates audit log."""
        url = reverse('links:duplicate')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        data = response.json()
        audit_log = AuditLog.objects.filter(
            action='duplicate',
            entity_type='PaymentLink',
            entity_id=data['link_id']
        ).first()

        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.user_email, self.user.email)

    def test_duplicate_nonexistent_link(self) -> None:
        """Test duplicating non-existent link."""
        url = reverse('links:duplicate')
        fake_id = uuid.uuid4()
        response = self.client.post(
            url,
            json.dumps({'link_id': str(fake_id)}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['success'])


class CancelViewTests(LinksViewTestSetup):
    """Tests for link cancellation."""

    def test_cancel_active_link(self) -> None:
        """Test canceling an active link."""
        url = reverse('links:cancel')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        self.active_link.refresh_from_db()
        self.assertEqual(self.active_link.status, 'cancelled')

    def test_cancel_paid_link_fails(self) -> None:
        """Test that paid links cannot be cancelled."""
        url = reverse('links:cancel')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.paid_link.id)}),
            content_type='application/json'
        )

        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Solo se pueden cancelar links activos', data['error'])

    def test_cancel_creates_audit_log(self) -> None:
        """Test that cancellation creates audit log."""
        url = reverse('links:cancel')
        self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        audit_log = AuditLog.objects.filter(
            action='cancel',
            entity_type='PaymentLink',
            entity_id=self.active_link.id
        ).first()

        self.assertIsNotNone(audit_log)


class EditViewTests(LinksViewTestSetup):
    """Tests for link editing."""

    def test_get_edit_data(self) -> None:
        """Test getting link data for editing."""
        url = reverse('links:edit_data', args=[self.active_link.id])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['link']['title'], 'Active Link')
        self.assertEqual(data['link']['amount'], 100.0)

    def test_edit_link_success(self) -> None:
        """Test successful link editing."""
        url = reverse('links:edit')
        edit_data = {
            'link_id': str(self.active_link.id),
            'title': 'Updated Title',
            'description': 'Updated description',
            'amount': 150.0,
            'customer_name': 'Updated Customer',
            'customer_email': 'updated@example.com',
            'requires_invoice': True,
            'expires_days': 7
        }

        response = self.client.post(
            url,
            json.dumps(edit_data),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        self.active_link.refresh_from_db()
        self.assertEqual(self.active_link.title, 'Updated Title')
        self.assertEqual(self.active_link.amount, 150.0)
        self.assertTrue(self.active_link.requires_invoice)

    def test_edit_paid_link_fails(self) -> None:
        """Test that paid links cannot be edited."""
        url = reverse('links:edit')
        edit_data = {
            'link_id': str(self.paid_link.id),
            'title': 'Should Not Update',
            'amount': 999.0
        }

        response = self.client.post(
            url,
            json.dumps(edit_data),
            content_type='application/json'
        )

        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Solo se pueden editar links activos', data['error'])

    def test_edit_creates_audit_log(self) -> None:
        """Test that editing creates audit log with old and new values."""
        url = reverse('links:edit')
        edit_data = {
            'link_id': str(self.active_link.id),
            'title': 'New Title',
            'amount': 200.0
        }

        self.client.post(
            url,
            json.dumps(edit_data),
            content_type='application/json'
        )

        audit_log = AuditLog.objects.filter(
            action='update',
            entity_type='PaymentLink',
            entity_id=self.active_link.id
        ).first()

        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.old_values['title'], 'Active Link')
        self.assertEqual(audit_log.new_values['title'], 'New Title')


class SendReminderViewTests(LinksViewTestSetup):
    """Tests for sending payment reminders."""

    @patch('core.notifications.notification_service.send_payment_reminder')
    def test_send_reminder_success(self, mock_send: Mock) -> None:
        """Test successful reminder sending."""
        mock_send.return_value = {'success': True}

        url = reverse('links:send_reminder')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        mock_send.assert_called_once_with(self.active_link)

    def test_send_reminder_no_email(self) -> None:
        """Test reminder fails without customer email."""
        self.active_link.customer_email = ''
        self.active_link.save()

        url = reverse('links:send_reminder')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('No hay email del cliente', data['error'])

    def test_send_reminder_inactive_link(self) -> None:
        """Test reminder fails for inactive links."""
        self.active_link.status = 'expired'
        self.active_link.save()

        url = reverse('links:send_reminder')
        response = self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Solo se pueden enviar recordatorios a links activos', data['error'])

    @patch('core.notifications.notification_service.send_payment_reminder')
    def test_send_reminder_creates_audit_log(self, mock_send: Mock) -> None:
        """Test that sending reminder creates audit log."""
        mock_send.return_value = {'success': True}

        url = reverse('links:send_reminder')
        self.client.post(
            url,
            json.dumps({'link_id': str(self.active_link.id)}),
            content_type='application/json'
        )

        audit_log = AuditLog.objects.filter(
            action='send_reminder',
            entity_type='PaymentLink',
            entity_id=self.active_link.id
        ).first()

        self.assertIsNotNone(audit_log)
        self.assertIn('Manual reminder sent', audit_log.notes)


class UtilityFunctionsTests(LinksViewTestSetup):
    """Tests for utility functions."""

    def test_get_client_ip_with_forwarded(self) -> None:
        """Test get_client_ip with X-Forwarded-For header."""
        from links.views import get_client_ip

        request = Mock()
        request.META = {
            'HTTP_X_FORWARDED_FOR': '192.168.1.1, 10.0.0.1',
            'REMOTE_ADDR': '127.0.0.1'
        }

        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

    def test_get_client_ip_without_forwarded(self) -> None:
        """Test get_client_ip without X-Forwarded-For header."""
        from links.views import get_client_ip

        request = Mock()
        request.META = {
            'REMOTE_ADDR': '127.0.0.1'
        }

        ip = get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')

    def test_log_audit_action(self) -> None:
        """Test audit logging function."""
        from links.views import log_audit_action

        log_audit_action(
            tenant=self.tenant,
            user=self.user,
            action='test_action',
            entity_type='TestEntity',
            entity_id='test_id',
            entity_name='Test Name',
            ip_address='127.0.0.1',
            user_agent='Test Agent',
            old_values={'old': 'value'},
            new_values={'new': 'value'},
            notes='Test note'
        )

        audit_log = AuditLog.objects.filter(
            action='test_action',
            entity_type='TestEntity'
        ).first()

        self.assertIsNotNone(audit_log)
        self.assertEqual(audit_log.entity_name, 'Test Name')
        self.assertEqual(audit_log.notes, 'Test note')