import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


def backfill_hardening_state(apps, schema_editor):
    Gateway = apps.get_model("devices", "Gateway")
    GatewayActivation = apps.get_model("devices", "GatewayActivation")
    GatewayConfig = apps.get_model("devices", "GatewayConfig")
    GatewayConfigOutbox = apps.get_model("devices", "GatewayConfigOutbox")
    GatewayInventory = apps.get_model("devices", "GatewayInventory")
    GatewayReleaseRequest = apps.get_model("devices", "GatewayReleaseRequest")
    RemoteCommand = apps.get_model("devices", "RemoteCommand")

    # MQTT ingress is resolved through factory inventory after this migration.
    # Backfill inventory for older claimed rows so deploying the consumer does
    # not strand an otherwise valid existing Gateway.
    for gateway in Gateway.objects.exclude(lifecycle_status="released").iterator():
        inventory = GatewayInventory.objects.filter(serial_number=gateway.serial_number).first()
        if inventory is None:
            GatewayInventory.objects.create(
                serial_number=gateway.serial_number,
                status="claimed",
                gateway_id=gateway.pk,
                claimed_by_team_id=gateway.team_id,
                claimed_at=gateway.claimed_at,
            )
        elif inventory.gateway_id in {None, gateway.pk}:
            GatewayInventory.objects.filter(pk=inventory.pk).update(
                status="claimed",
                gateway_id=gateway.pk,
                claimed_by_team_id=gateway.team_id,
                claimed_at=inventory.claimed_at or gateway.claimed_at,
            )

    for gateway_id in GatewayActivation.objects.values_list("gateway_id", flat=True).distinct():
        activation_ids = list(
            GatewayActivation.objects.filter(gateway_id=gateway_id)
            .order_by("created_at", "pk")
            .values_list("pk", flat=True)
        )
        for generation, activation_id in enumerate(activation_ids, start=1):
            GatewayActivation.objects.filter(pk=activation_id).update(generation=generation)

    GatewayConfig.objects.filter(status="delivered").update(status="published", published_at=models.F("delivered_at"))
    GatewayConfigOutbox.objects.filter(status="delivered").update(status="awaiting_ack")

    for command in RemoteCommand.objects.select_related("gateway", "device").iterator():
        snapshot = {
            "gateway_serial": command.gateway.serial_number,
            "gateway_name": command.gateway.name,
        }
        if command.device_id:
            snapshot.update({"device_id": command.device_id, "device_name": command.device.name})
        RemoteCommand.objects.filter(pk=command.pk).update(target_snapshot=snapshot)

    # Older code could mark inventory released even when Mosquitto revocation
    # failed. Quarantine those rows and require the new verified workflow to
    # finish; never assume the external credential state is safe.
    for gateway in Gateway.objects.filter(lifecycle_status="release_pending").iterator():
        GatewayReleaseRequest.objects.get_or_create(
            team_id=gateway.team_id,
            gateway_id=gateway.pk,
            defaults={
                "status": "needs_attention",
                "last_error": "Credential revocation must be verified before this Gateway can be released.",
            },
        )
        GatewayInventory.objects.filter(gateway_id=gateway.pk).update(
            status="claimed",
            claimed_by_team_id=gateway.team_id,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0026_alter_devicetemplate_datapoint_schema_version"),
        ("teams", "0008_team_remote_control_epoch_team_remote_control_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GatewayPlanReconciliation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("source_key", models.CharField(max_length=255)),
                ("previous_interval_seconds", models.FloatField()),
                ("new_interval_seconds", models.FloatField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("needs_attention", "Needs attention"),
                        ],
                        default="queued",
                        max_length=24,
                    ),
                ),
                ("queued_gateway_count", models.PositiveIntegerField(default=0)),
                ("skipped_gateway_count", models.PositiveIntegerField(default=0)),
                ("unsupported_gateway_count", models.PositiveIntegerField(default=0)),
                ("last_error", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "team",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="teams.team",
                        verbose_name="Team",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="GatewayReleaseRequest",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("request_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("revoking", "Revoking credentials"),
                            ("retry", "Retry scheduled"),
                            ("needs_attention", "Needs attention"),
                            ("completed", "Completed"),
                        ],
                        default="queued",
                        max_length=24,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "gateway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="release_requests",
                        to="devices.gateway",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="gateway_release_requests",
                        to=settings.AUTH_USER_MODEL,
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
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddField(
            model_name="gatewayactivation",
            name="generation",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="accepted_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="acknowledgement_deadline_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="last_ack_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="target_snapshot",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="gateway",
            name="lifecycle_status",
            field=models.CharField(
                choices=[
                    ("claimed", "Claimed"),
                    ("bootstrap_seen", "Bootstrap Seen"),
                    ("activating", "Activating"),
                    ("online", "Online"),
                    ("commissioning", "Commissioning"),
                    ("active", "Active"),
                    ("release_pending", "Release Pending"),
                    ("released", "Released"),
                ],
                default="claimed",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="gateway",
            name="serial_number",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="gatewayactivation",
            name="status",
            field=models.CharField(
                choices=[
                    ("provisioning", "Provisioning"),
                    ("pending", "Pending"),
                    ("delivered", "Delivered"),
                    ("acknowledged", "Acknowledged"),
                    ("expired", "Expired"),
                    ("retried", "Retried"),
                    ("retry", "Retry Scheduled"),
                    ("failed", "Failed"),
                    ("superseded", "Superseded"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="gatewayconfig",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("waiting_for_gateway", "Waiting for Gateway"),
                    ("published", "Published"),
                    ("accepted", "Accepted"),
                    ("active", "Active"),
                    ("failed", "Failed"),
                    ("rolled_back", "Rolled Back"),
                    ("timed_out", "Timed Out"),
                    ("superseded", "Superseded"),
                ],
                default="queued",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="gatewayconfigoutbox",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("claimed", "Claimed"),
                    ("waiting_gateway", "Waiting for Gateway"),
                    ("awaiting_ack", "Awaiting acknowledgement"),
                    ("completed", "Completed"),
                    ("retry", "Retry"),
                    ("dead_letter", "Dead letter"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="remotecommand",
            name="device",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="remote_commands",
                to="devices.device",
            ),
        ),
        migrations.AddConstraint(
            model_name="gateway",
            constraint=models.UniqueConstraint(
                condition=~models.Q(lifecycle_status="released"),
                fields=("serial_number",),
                name="unique_active_gateway_serial",
            ),
        ),
        migrations.AddConstraint(
            model_name="gatewayplanreconciliation",
            constraint=models.UniqueConstraint(
                fields=("team", "source_key"),
                name="unique_team_plan_reconcile_source",
            ),
        ),
        migrations.AddIndex(
            model_name="gatewayreleaserequest",
            index=models.Index(fields=["status", "next_attempt_at"], name="devices_gat_status_227533_idx"),
        ),
        migrations.AddConstraint(
            model_name="gatewayreleaserequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=["queued", "revoking", "retry", "needs_attention"]),
                fields=("gateway",),
                name="unique_active_gateway_release",
            ),
        ),
        migrations.RunPython(backfill_hardening_state, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="gatewayactivation",
            constraint=models.UniqueConstraint(
                fields=("gateway", "generation"),
                name="unique_gateway_activation_generation",
            ),
        ),
    ]
