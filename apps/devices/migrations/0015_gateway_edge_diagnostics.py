from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("devices", "0014_devicecommand_unified_rpc_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="gateway",
            name="broker_host",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="gateway",
            name="broker_port",
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="broker_tcp_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="broker_tcp_ok",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="connectivity_checked_ts",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="default_route_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="default_route_ok",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="device_health",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="gateway",
            name="dns_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="dns_ok",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="internet_reachable",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="mqtt_connected",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="mqtt_last_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="ota_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="ota_rollback_performed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gateway",
            name="ota_status",
            field=models.CharField(blank=True, max_length=30),
        ),
        migrations.AddField(
            model_name="gateway",
            name="ota_version",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="gateway",
            name="tls_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gateway",
            name="tls_ok",
            field=models.BooleanField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="connector_results",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="rollback_performed",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="gatewayconfig",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                    ("rolled_back", "Rolled Back"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
