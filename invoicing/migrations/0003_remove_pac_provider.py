# Remove pac_provider field - FiscalAPI is sole provider
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0002_rename_sw_to_pac'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='csdcertificate',
            name='pac_provider',
        ),
    ]
