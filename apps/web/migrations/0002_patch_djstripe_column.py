from django.db import migrations

def patch_djstripe(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("ALTER TABLE djstripe_paymentintent ALTER COLUMN capture_method TYPE varchar(255);")

def reverse_patch(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ("web", "0001_initial"),
        ("djstripe", "0012_2_8"),
    ]

    operations = [
        migrations.RunPython(patch_djstripe, reverse_patch),
    ]
