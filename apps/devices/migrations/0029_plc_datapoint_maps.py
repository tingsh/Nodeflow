import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def mark_programmable_templates(apps, schema_editor):
    DeviceTemplate = apps.get_model("devices", "DeviceTemplate")
    DeviceTemplate.objects.filter(device_type="plc").update(mapping_strategy="site_defined")
    DeviceTemplate.objects.filter(
        device_type="plc",
        manufacturer__in=["Siemens", "Omron"],
    ).update(register_map={})


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0028_site_metadata"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="devicetemplate",
            name="mapping_strategy",
            field=models.CharField(
                choices=[("fixed", "Fixed equipment map"), ("site_defined", "Site-defined signals")],
                default="fixed",
                help_text="Whether the template supplies a deployable map or only a device/protocol starter.",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="deploymentsetupitem",
            name="state",
            field=models.CharField(
                choices=[
                    ("discovered", "Discovered"),
                    ("template_selected", "Template selected"),
                    ("validating", "Validating"),
                    ("awaiting_confirmation", "Awaiting confirmation"),
                    ("validated", "Validated"),
                    ("queued", "Queued"),
                    ("applied", "Applied"),
                    ("telemetry_confirmed", "Telemetry confirmed"),
                    ("needs_attention", "Needs attention"),
                    ("failed", "Failed"),
                    ("rolled_back", "Rolled back"),
                ],
                default="discovered",
                max_length=30,
            ),
        ),
        migrations.CreateModel(
            name="DeviceDatapointMap",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("testing", "Testing"),
                            ("awaiting_confirmation", "Awaiting confirmation"),
                            ("confirmed", "Confirmed"),
                            ("needs_attention", "Needs attention"),
                        ],
                        default="draft",
                        max_length=24,
                    ),
                ),
                ("schema_version", models.PositiveSmallIntegerField(default=1)),
                ("datapoints", models.JSONField(blank=True, default=list)),
                ("last_validation", models.JSONField(blank=True, default=dict)),
                ("tested_checksum", models.CharField(blank=True, max_length=64)),
                ("confirmed_checksum", models.CharField(blank=True, max_length=64)),
                ("last_tested_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "cloned_from",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="clones",
                        to="devices.devicedatapointmap",
                    ),
                ),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="confirmed_device_datapoint_maps",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "device",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="datapoint_map",
                        to="devices.device",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="teams.team",
                        verbose_name="Team",
                    ),
                ),
            ],
            options={"ordering": ["device__name"]},
        ),
        migrations.AddIndex(
            model_name="devicedatapointmap",
            index=models.Index(fields=["team", "status"], name="devices_dev_team_id_23d97f_idx"),
        ),
        migrations.RunPython(mark_programmable_templates, migrations.RunPython.noop),
    ]
