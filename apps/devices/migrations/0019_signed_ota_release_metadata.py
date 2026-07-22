from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0018_rename_devices_gat_gateway_74a7a9_idx_devices_gat_gateway_235b19_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="firmwarerelease",
            name="channel",
            field=models.CharField(
                choices=[("stable", "Stable"), ("pilot", "Pilot"), ("canary", "Canary")],
                default="stable",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="key_id",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="manifest",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="maximum_gateway_version",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="minimum_gateway_version",
            field=models.CharField(blank=True, default="0.1.0", max_length=50),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="signature",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="signed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="firmwarerelease",
            name="signing_status",
            field=models.CharField(
                choices=[("unsigned", "Unsigned"), ("signed", "Signed"), ("failed", "Failed")],
                default="unsigned",
                max_length=20,
            ),
        ),
    ]
