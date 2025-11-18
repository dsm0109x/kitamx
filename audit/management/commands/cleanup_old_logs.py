"""
Django management command to cleanup old audit logs.

Deletes audit logs older than AUDIT_LOG_RETENTION_DAYS (90 days by default).
This helps maintain database performance and comply with data retention policies.

Usage:
    python manage.py cleanup_old_logs
    python manage.py cleanup_old_logs --dry-run
    python manage.py cleanup_old_logs --days 180
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from typing import Any

from core.models import AuditLog
from accounts.constants import AuditConstants


class Command(BaseCommand):
    help = 'Delete audit logs older than retention period'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=AuditConstants.AUDIT_LOG_RETENTION_DAYS,
            help=f'Number of days to retain logs (default: {AuditConstants.AUDIT_LOG_RETENTION_DAYS})'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Execute the command."""
        retention_days = options['days']
        dry_run = options['dry_run']

        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # Get logs to delete
        old_logs = AuditLog.objects.filter(created_at__lt=cutoff_date)
        count = old_logs.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'No audit logs older than {retention_days} days found.'
                )
            )
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: Would delete {count} audit logs older than {retention_days} days '
                    f'(before {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")})'
                )
            )

            # Show sample of logs that would be deleted
            sample = old_logs.order_by('-created_at')[:5]
            self.stdout.write('\nSample of logs to be deleted:')
            for log in sample:
                self.stdout.write(
                    f'  - {log.created_at.strftime("%Y-%m-%d")} | '
                    f'{log.user_email} | {log.action} | {log.entity_type}'
                )
            return

        # Perform deletion
        try:
            deleted_count, _ = old_logs.delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully deleted {deleted_count} audit logs older than '
                    f'{retention_days} days (before {cutoff_date.strftime("%Y-%m-%d %H:%M:%S")})'
                )
            )

        except Exception as e:
            raise CommandError(f'Failed to delete old logs: {e}')
