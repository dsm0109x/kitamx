"""
Django management command para probar el sistema de monitoreo de facturapi.io
Uso: python manage.py test_monitoring [--simulate-down]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Test facturapi.io monitoring system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--simulate-down',
            action='store_true',
            help='Simulate facturapi.io being down',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Clear monitoring cache before testing',
        )

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("🔍 FACTURAPI.IO MONITORING SYSTEM TEST"))
        self.stdout.write("="*80 + "\n")

        # Clear cache if requested
        if options['clear_cache']:
            self.stdout.write("🗑️  Clearing monitoring cache...")
            cache.delete('facturapi_last_known_status')
            cache.delete('facturapi_downtime_start')
            cache.delete('facturapi_health_history')
            cache.delete('facturapi_health_check')
            self.stdout.write(self.style.SUCCESS("   ✅ Cache cleared\n"))

        # Test 1: Health Check Method
        self.stdout.write("1️⃣  Testing facturapi.io health check method...")
        from invoicing.pac_factory import pac_service

        if options['simulate_down']:
            # Temporarily break the connection to simulate downtime
            self.stdout.write(self.style.WARNING("   ⚠️  Simulating service down (invalid credentials)"))
            original_key = pac_service.user_key
            pac_service.user_key = 'sk_user_INVALID_FOR_TESTING'

        health = pac_service.health_check()

        if options['simulate_down']:
            # Restore credentials
            pac_service.user_key = original_key

        if health.get('ok'):
            self.stdout.write(self.style.SUCCESS(f"   ✅ facturapi.io is HEALTHY"))
            self.stdout.write(f"      Response time: {health.get('response_time_ms')}ms")
            self.stdout.write(f"      Timestamp: {health.get('timestamp')}")
        else:
            self.stdout.write(self.style.ERROR(f"   ❌ facturapi.io is DOWN"))
            self.stdout.write(f"      Error: {health.get('error')}")

        # Test 2: Celery Task
        self.stdout.write("\n2️⃣  Testing Celery monitoring task...")
        from invoicing.tasks import monitor_facturapi_health

        if options['simulate_down']:
            self.stdout.write(self.style.WARNING("   ⚠️  Simulating service down for task"))
            from invoicing import facturapi_service
            original_key = facturapi_service.facturapi_service.user_key
            facturapi_service.facturapi_service.user_key = 'sk_user_INVALID_FOR_TESTING'

        result = monitor_facturapi_health()

        if options['simulate_down']:
            # Restore
            facturapi_service.facturapi_service.user_key = original_key

        self.stdout.write(self.style.SUCCESS(f"   ✅ Task executed: {result}"))

        # Test 3: healthchecks.io Integration
        self.stdout.write("\n3️⃣  Testing healthchecks.io integration...")
        from django.conf import settings

        if hasattr(settings, 'HEALTHCHECKS_IO_URL') and settings.HEALTHCHECKS_IO_URL:
            self.stdout.write(self.style.SUCCESS(f"   ✅ healthchecks.io URL configured"))
            self.stdout.write(f"      URL: {settings.HEALTHCHECKS_IO_URL[:50]}...")

            # Verify ping was sent (check logs)
            self.stdout.write("      Check logs above for ping confirmation")
        else:
            self.stdout.write(self.style.ERROR("   ❌ HEALTHCHECKS_IO_URL not configured"))

        # Test 4: Cache Status
        self.stdout.write("\n4️⃣  Checking cached monitoring data...")
        cached_status = cache.get('facturapi_last_known_status')
        downtime_start = cache.get('facturapi_downtime_start')
        history = cache.get('facturapi_health_history', [])

        self.stdout.write(f"   Current status: {cached_status}")
        self.stdout.write(f"   Downtime start: {downtime_start or 'None (service up)'}")
        self.stdout.write(f"   History entries: {len(history)}")

        if len(history) > 0:
            last_check = history[-1]
            self.stdout.write(f"   Last check: {last_check['timestamp']}")
            self.stdout.write(f"   Last healthy: {last_check['healthy']}")

        # Test 5: Celery Beat Schedule
        self.stdout.write("\n5️⃣  Verifying Celery Beat schedule...")
        if 'monitor-facturapi-health' in settings.CELERY_BEAT_SCHEDULE:
            schedule_config = settings.CELERY_BEAT_SCHEDULE['monitor-facturapi-health']
            self.stdout.write(self.style.SUCCESS("   ✅ Task scheduled in Celery Beat"))
            self.stdout.write(f"      Task: {schedule_config['task']}")
            self.stdout.write(f"      Schedule: {schedule_config['schedule']}s ({schedule_config['schedule']/60} minutes)")
            self.stdout.write(f"      Queue: {schedule_config['options']['queue']}")
        else:
            self.stdout.write(self.style.ERROR("   ❌ Task NOT scheduled in Celery Beat"))

        # Summary
        self.stdout.write("\n" + "="*80)
        self.stdout.write(self.style.SUCCESS("✅ MONITORING SYSTEM TEST COMPLETED"))
        self.stdout.write("="*80)

        if not health.get('ok'):
            self.stdout.write("\n" + self.style.WARNING("⚠️  NEXT STEPS:"))
            self.stdout.write("   1. Verify FACTURAPI_USER_KEY is valid")
            self.stdout.write("   2. Check facturapi.io dashboard for API status")
            self.stdout.write("   3. Review logs for detailed error messages")
            self.stdout.write("   4. Service will auto-recover when facturapi.io is back\n")
