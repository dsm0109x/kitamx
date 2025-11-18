"""
Management command to update django.contrib.sites Site model.

Usage:
    python manage.py update_site
"""
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site


class Command(BaseCommand):
    help = 'Update Site model domain to kita.mx'

    def handle(self, *args, **options):
        """Update the Site model."""
        try:
            site = Site.objects.get(id=1)
            self.stdout.write(
                self.style.SUCCESS(f'✓ Sitio actual: {site.domain} - {site.name}')
            )

            # Actualizar
            old_domain = site.domain
            site.domain = 'kita.mx'
            site.name = 'Kita'
            site.save()

            self.stdout.write(
                self.style.SUCCESS(f'✓ Sitio actualizado: {old_domain} → {site.domain}')
            )
            self.stdout.write(
                self.style.SUCCESS('\n✅ Dominio actualizado correctamente!')
            )

        except Site.DoesNotExist:
            self.stdout.write(
                self.style.WARNING('⚠ No existe Site con id=1, creando...')
            )

            site = Site.objects.create(
                id=1,
                domain='kita.mx',
                name='Kita'
            )
            self.stdout.write(
                self.style.SUCCESS(f'✓ Sitio creado: {site.domain} - {site.name}')
            )
