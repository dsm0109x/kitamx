"""
Sepomex (Servicio Postal Mexicano) models.

Local database of Mexican postal codes for fast, reliable lookups.
Data is imported from official SEPOMEX catalog.
"""
from django.db import models
from django.db.models import Q


class CodigoPostalManager(models.Manager):
    """Manager for CodigoPostal with optimized queries."""

    def lookup(self, codigo_postal: str):
        """
        Lookup postal code data.

        Args:
            codigo_postal: 5-digit postal code

        Returns:
            dict with colonias, municipio, estado or None
        """
        if not codigo_postal or len(codigo_postal) != 5:
            return None

        # Get all records for this CP (multiple colonias)
        records = self.filter(
            codigo_postal=codigo_postal
        ).values(
            'asentamiento',
            'tipo_asentamiento',
            'municipio',
            'estado',
            'ciudad'
        )

        if not records:
            return None

        # Group by unique colonias
        colonias = list(set(r['asentamiento'] for r in records))
        colonias.sort()

        # Get first record for municipio/estado (all should be same for a CP)
        first = records[0]

        return {
            'success': True,
            'colonias': colonias,
            'municipio': first['municipio'],
            'estado': first['estado'],
            'ciudad': first['ciudad'] or first['municipio'],
            'pais': 'México'
        }

    def validate_colonia(self, codigo_postal: str, colonia: str) -> bool:
        """
        Validate that colonia exists for postal code.

        Args:
            codigo_postal: 5-digit postal code
            colonia: Colonia name

        Returns:
            bool: True if valid combination
        """
        return self.filter(
            codigo_postal=codigo_postal,
            asentamiento__iexact=colonia
        ).exists()


class CodigoPostal(models.Model):
    """
    Código Postal (Mexican postal code) with location data.

    Imported from official SEPOMEX catalog.
    One record per CP + Colonia combination.
    """

    # Datos del catálogo SEPOMEX
    codigo_postal = models.CharField(max_length=5, db_index=True, verbose_name='Código Postal')
    asentamiento = models.CharField(max_length=255, verbose_name='Asentamiento/Colonia')
    tipo_asentamiento = models.CharField(max_length=100, verbose_name='Tipo de Asentamiento')
    municipio = models.CharField(max_length=255, db_index=True, verbose_name='Municipio')
    estado = models.CharField(max_length=255, db_index=True, verbose_name='Estado')
    ciudad = models.CharField(max_length=255, blank=True, verbose_name='Ciudad')
    zona = models.CharField(max_length=50, blank=True, verbose_name='Zona')

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CodigoPostalManager()

    class Meta:
        db_table = 'codigos_postales'
        verbose_name = 'Código Postal'
        verbose_name_plural = 'Códigos Postales'
        indexes = [
            models.Index(fields=['codigo_postal', 'asentamiento'], name='idx_cp_asentamiento'),
            models.Index(fields=['municipio'], name='idx_municipio'),
            models.Index(fields=['estado'], name='idx_estado'),
        ]
        # Unique constraint: cada combinación CP + Colonia es única
        unique_together = [['codigo_postal', 'asentamiento']]

    def __str__(self):
        return f"{self.codigo_postal} - {self.asentamiento}, {self.municipio}"
