import pytest
from django.test import Client


@pytest.mark.django_db
class TestHealthEndpoints:

    def test_health_check_returns_200(self):
        client = Client()
        response = client.get('/health/')

        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'ok'
        assert data['service'] == 'kita'

    def test_health_detailed_returns_checks(self):
        client = Client()
        response = client.get('/health/detailed/')

        assert response.status_code in [200, 503]
        data = response.json()
        assert 'status' in data
        assert 'checks' in data
        assert 'database' in data['checks']
        assert 'cache' in data['checks']
        assert 'celery' in data['checks']
        assert 'disk' in data['checks']
        assert 'memory' in data['checks']

    def test_health_readiness_checks_critical_components(self):
        client = Client()
        response = client.get('/health/readiness/')

        assert response.status_code in [200, 503]
        data = response.json()
        assert 'status' in data
        assert 'database' in data
        assert 'cache' in data

    def test_health_liveness_returns_200_or_503(self):
        client = Client()
        response = client.get('/health/liveness/')

        assert response.status_code in [200, 503]
        data = response.json()
        assert 'status' in data