"""
Django management command to import SEPOMEX postal codes.

Usage:
    python manage.py import_sepomex --file=/path/to/sepomex.txt
    python manage.py import_sepomex --sample  # Import sample data for testing
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from core.models import CodigoPostal


class Command(BaseCommand):
    help = 'Import SEPOMEX postal codes data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            help='Path to SEPOMEX TXT file'
        )
        parser.add_argument(
            '--sample',
            action='store_true',
            help='Import sample data for testing (CDMX + major cities)'
        )

    def handle(self, *args, **options):
        if options['sample']:
            self.import_sample_data()
        elif options['file']:
            self.import_from_file(options['file'])
        else:
            self.stdout.write(self.style.ERROR(
                'Debes especificar --file o --sample'
            ))

    def import_sample_data(self):
        """Import sample data for development/testing."""
        self.stdout.write('📦 Importing sample data...')

        sample_data = [
            # CDMX - Tlalpan (CP 14240 - COMPLETO con todas las colonias)
            ('14240', 'Lomas de Padierna', 'Colonia', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'Pedregal de San Nicolás', 'Colonia', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'Ampliación Tepepan', 'Colonia', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'San Nicolás Totolapan', 'Pueblo', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'Parres El Guarda', 'Pueblo', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'Miguel Hidalgo', 'Colonia', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'San Miguel Topilejo', 'Pueblo', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'San Miguel Xicalco', 'Pueblo', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'Lomas de Cuilotepec', 'Colonia', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('14240', 'Magdalena Petlacalco', 'Pueblo', 'Tlalpan', 'Ciudad de México', 'Ciudad de México', 'Urbano'),

            # CDMX - Cuauhtémoc
            ('06600', 'Juárez', 'Colonia', 'Cuauhtémoc', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('06600', 'Doctores', 'Colonia', 'Cuauhtémoc', 'Ciudad de México', 'Ciudad de México', 'Urbano'),

            # CDMX - Benito Juárez
            ('03100', 'Del Valle Centro', 'Colonia', 'Benito Juárez', 'Ciudad de México', 'Ciudad de México', 'Urbano'),
            ('03100', 'Del Valle Norte', 'Colonia', 'Benito Juárez', 'Ciudad de México', 'Ciudad de México', 'Urbano'),

            # CDMX - Miguel Hidalgo
            ('11000', 'Polanco', 'Colonia', 'Miguel Hidalgo', 'Ciudad de México', 'Ciudad de México', 'Urbano'),

            # CDMX - Álvaro Obregón
            ('01000', 'San Ángel', 'Colonia', 'Álvaro Obregón', 'Ciudad de México', 'Ciudad de México', 'Urbano'),

            # Monterrey
            ('64000', 'Monterrey Centro', 'Colonia', 'Monterrey', 'Nuevo León', 'Monterrey', 'Urbano'),

            # Guadalajara
            ('44100', 'Guadalajara Centro', 'Colonia', 'Guadalajara', 'Jalisco', 'Guadalajara', 'Urbano'),
        ]

        with transaction.atomic():
            CodigoPostal.objects.all().delete()

            objects = [
                CodigoPostal(
                    codigo_postal=cp,
                    asentamiento=col,
                    tipo_asentamiento=tipo,
                    municipio=mun,
                    estado=edo,
                    ciudad=city,
                    zona=zona
                )
                for cp, col, tipo, mun, edo, city, zona in sample_data
            ]

            CodigoPostal.objects.bulk_create(objects)

        count = CodigoPostal.objects.count()
        self.stdout.write(self.style.SUCCESS(f'✅ {count} sample records imported'))

        # Test
        test = CodigoPostal.objects.lookup('14240')
        if test:
            self.stdout.write(self.style.SUCCESS(
                f"✅ Test CP 14240: {test['municipio']}, {test['estado']}"
            ))
            self.stdout.write(f"   Colonias: {', '.join(test['colonias'])}")

    @transaction.atomic
    def import_from_file(self, file_path: str):
        """Import from official SEPOMEX file (CSV or TXT)."""
        self.stdout.write(f'📁 Importing from: {file_path}')

        # Detect file format
        import csv
        delimiter = '|'
        if file_path.endswith('.csv'):
            delimiter = ','
            self.stdout.write('   Format: CSV detected')
        else:
            self.stdout.write('   Format: Pipe-separated TXT')

        CodigoPostal.objects.all().delete()

        batch = []
        batch_size = 5000
        total = 0
        errors = 0

        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                reader = csv.reader(f, delimiter=delimiter)

                # Skip header
                next(reader, None)

                for line_num, parts in enumerate(reader, 1):
                    try:
                        if len(parts) < 5:
                            continue

                        # CSV format: idEstado,estado,idMunicipio,municipio,ciudad,zona,cp,asentamiento,tipo
                        if delimiter == ',':
                            cp = CodigoPostal(
                                codigo_postal=parts[6].strip(),  # cp
                                asentamiento=parts[7].strip().replace('"', ''),  # asentamiento
                                tipo_asentamiento=parts[8].strip() if len(parts) > 8 else '',  # tipo
                                municipio=parts[3].strip(),  # municipio
                                estado=parts[1].strip(),  # estado
                                ciudad=parts[4].strip() if len(parts) > 4 else '',  # ciudad
                                zona=parts[5].strip() if len(parts) > 5 else ''  # zona
                            )
                        else:
                            # Pipe format: cp|asentamiento|tipo|municipio|estado|ciudad|...|zona
                            cp = CodigoPostal(
                                codigo_postal=parts[0].strip(),
                                asentamiento=parts[1].strip(),
                                tipo_asentamiento=parts[2].strip() if len(parts) > 2 else '',
                                municipio=parts[3].strip() if len(parts) > 3 else '',
                                estado=parts[4].strip() if len(parts) > 4 else '',
                                ciudad=parts[5].strip() if len(parts) > 5 else '',
                                zona=parts[13].strip() if len(parts) > 13 else ''
                            )

                        batch.append(cp)

                        if len(batch) >= batch_size:
                            CodigoPostal.objects.bulk_create(batch, ignore_conflicts=True)
                            total += len(batch)
                            self.stdout.write(f'  ✅ {total:,} imported...')
                            batch = []

                    except Exception as e:
                        errors += 1

                # Import remaining
                if batch:
                    CodigoPostal.objects.bulk_create(batch, ignore_conflicts=True)
                    total += len(batch)

            self.stdout.write(self.style.SUCCESS(
                f'🎉 Import complete: {total:,} records, {errors} errors'
            ))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'❌ File not found: {file_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Import failed: {e}'))
