"""Celery configuration for Kita project.

Configures task routing, queues, and scheduling for async processing.
"""
from __future__ import annotations
from typing import Dict
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kita.settings')

app: Celery = Celery('kita')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

# Task routing configuration
TASK_ROUTES: Dict[str, Dict[str, str]] = {
    'invoicing.tasks.*': {'queue': 'high'},
    'payments.tasks.*': {'queue': 'high'},
    'webhooks.tasks.*': {'queue': 'high'},
    'notifications.tasks.*': {'queue': 'default'},
    'billing.tasks.*': {'queue': 'default'},
    'core.tasks.*': {'queue': 'low'},
    'analytics.tasks.*': {'queue': 'low'},
}

app.conf.task_routes = TASK_ROUTES

@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Debug task for testing Celery configuration."""
    print(f'Request: {self.request!r}')


# Additional configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Mexico_City',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_send_sent_event=True,
    worker_send_task_events=True,
    result_expires=3600,
)