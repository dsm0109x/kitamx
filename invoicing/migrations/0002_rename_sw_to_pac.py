# Generated migration for renaming SmartWeb fields to PAC-agnostic names
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0001_initial'),
    ]

    operations = [
        # Renombrar campos sw_* a pac_* en CSDCertificate
        migrations.RenameField(
            model_name='csdcertificate',
            old_name='sw_uploaded',
            new_name='pac_uploaded',
        ),
        migrations.RenameField(
            model_name='csdcertificate',
            old_name='sw_uploaded_at',
            new_name='pac_uploaded_at',
        ),
        migrations.RenameField(
            model_name='csdcertificate',
            old_name='sw_response',
            new_name='pac_response',
        ),
        migrations.RenameField(
            model_name='csdcertificate',
            old_name='sw_error',
            new_name='pac_error',
        ),

        # Agregar campo pac_provider para tracking
        migrations.AddField(
            model_name='csdcertificate',
            name='pac_provider',
            field=models.CharField(
                max_length=50,
                default='smartweb',
                choices=[
                    ('smartweb', 'SmartWeb'),
                    ('fiscalapi', 'FiscalAPI'),
                ],
                help_text='PAC provider usado para este certificado'
            ),
        ),

        # Actualizar índice (si existe with_sw_status)
        # migrations.RemoveIndex(...) si existe
        # migrations.AddIndex(...) con nuevo nombre
    ]
