import hashlib
import json

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_confirmed_revisions(apps, schema_editor):
    DeviceDatapointMap = apps.get_model("devices", "DeviceDatapointMap")
    DeviceDatapointMapRevision = apps.get_model("devices", "DeviceDatapointMapRevision")
    for mapping in DeviceDatapointMap.objects.filter(status="confirmed").iterator():
        canonical = json.dumps(
            mapping.datapoints or [],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        datapoints_checksum = hashlib.sha256(canonical).hexdigest()
        DeviceDatapointMapRevision.objects.create(
            team_id=mapping.team_id,
            mapping_id=mapping.pk,
            revision_number=1,
            datapoints=mapping.datapoints,
            datapoints_checksum=datapoints_checksum,
            confirmed_checksum=mapping.confirmed_checksum,
            validation_result=mapping.last_validation,
            validated_at=mapping.last_tested_at,
            confirmed_by_id=mapping.confirmed_by_id,
            confirmed_at=mapping.confirmed_at,
        )
        mapping.validated_at = mapping.last_tested_at
        mapping.save(update_fields=["validated_at"])


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0029_plc_datapoint_maps"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="devicedatapointmap",
            name="datapoint_health",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="devicedatapointmap",
            name="validated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="devicedatapointmap",
            name="validated_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="validated_device_datapoint_maps",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.CreateModel(
            name="DeviceDatapointMapRevision",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revision_number", models.PositiveIntegerField()),
                ("datapoints", models.JSONField(default=list)),
                ("datapoints_checksum", models.CharField(max_length=64)),
                ("confirmed_checksum", models.CharField(blank=True, max_length=64)),
                ("validation_result", models.JSONField(blank=True, default=dict)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "confirmed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "mapping",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="revisions",
                        to="devices.devicedatapointmap",
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
                (
                    "validated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["-revision_number"]},
        ),
        migrations.AddConstraint(
            model_name="devicedatapointmaprevision",
            constraint=models.UniqueConstraint(
                fields=("mapping", "revision_number"),
                name="unique_device_datapoint_map_revision",
            ),
        ),
        migrations.AddIndex(
            model_name="devicedatapointmaprevision",
            index=models.Index(fields=["team", "mapping"], name="devices_dpr_team_map_idx"),
        ),
        migrations.RunPython(backfill_confirmed_revisions, migrations.RunPython.noop),
    ]
