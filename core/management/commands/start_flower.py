from django.core.management.base import BaseCommand
from django.conf import settings
import subprocess


class Command(BaseCommand):
    help = 'Start Flower for Celery monitoring'

    def add_arguments(self, parser):
        parser.add_argument(
            '--port',
            type=int,
            default=5555,
            help='Port to run Flower on (default: 5555)',
        )
        parser.add_argument(
            '--address',
            type=str,
            default='0.0.0.0',
            help='Address to bind to (default: 0.0.0.0)',
        )

    def handle(self, *args, **options):
        port = options['port']
        address = options['address']

        broker_url = settings.CELERY_BROKER_URL

        cmd = [
            'celery',
            '--broker', broker_url,
            'flower',
            f'--port={port}',
            f'--address={address}',
            '--basic_auth=admin:kitaflower2025',
        ]

        self.stdout.write(self.style.SUCCESS(
            f'Starting Flower on {address}:{port}'
        ))
        self.stdout.write(self.style.WARNING(
            'Login with: admin / kitaflower2025'
        ))

        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('Flower stopped'))