from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0027_managed_gateway_hardening"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
