#!/usr/bin/env python
"""
Script para actualizar el dominio en django.contrib.sites.

Ejecutar con:
    python scripts/update_site_domain.py
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'kita.settings')
django.setup()

from django.contrib.sites.models import Site

def update_site():
    """Actualizar el Site model con el dominio de producción."""
    try:
        site = Site.objects.get(id=1)
        print(f"✓ Sitio actual: {site.domain} - {site.name}")

        # Actualizar
        site.domain = 'kita.mx'
        site.name = 'Kita'
        site.save()

        print(f"✓ Sitio actualizado: {site.domain} - {site.name}")
        print("\n✅ Dominio actualizado correctamente!")

    except Site.DoesNotExist:
        print("❌ Error: No existe Site con id=1")
        print("Creando nuevo Site...")

        site = Site.objects.create(
            id=1,
            domain='kita.mx',
            name='Kita'
        )
        print(f"✓ Sitio creado: {site.domain} - {site.name}")

if __name__ == '__main__':
    update_site()
