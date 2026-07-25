import hashlib
import json
import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def backfill_gateway_configs(apps, schema_editor):
    GatewayConfig = apps.get_model("devices", "GatewayConfig")
    gateway_ids = GatewayConfig.objects.values_list("gateway_id", flat=True).distinct()
    for gateway_id in gateway_ids:
        rows = GatewayConfig.objects.filter(gateway_id=gateway_id).order_by("pushed_at", "pk")
        for revision, row in enumerate(rows, start=1):
            canonical = json.dumps(
                row.config_json,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
            status = {"pending": "queued", "success": "active"}.get(row.status, row.status)
            GatewayConfig.objects.filter(pk=row.pk).update(
                revision=revision,
                idempotency_key=uuid.uuid4(),
                checksum=hashlib.sha256(canonical).hexdigest(),
                status=status,
            )


def reverse_gateway_config_statuses(apps, schema_editor):
    GatewayConfig = apps.get_model("devices", "GatewayConfig")
    GatewayConfig.objects.filter(status="active").update(status="success")
    GatewayConfig.objects.filter(status__in=["queued", "delivered", "accepted"]).update(status="pending")


def install_setup_event_append_only_trigger(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            """
            CREATE OR REPLACE FUNCTION devices_deploymentsetupevent_append_only()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'devices_deploymentsetupevent is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER devices_deploymentsetupevent_append_only_trigger
            BEFORE UPDATE OR DELETE ON devices_deploymentsetupevent
            FOR EACH ROW EXECUTE FUNCTION devices_deploymentsetupevent_append_only();
            """
        )
    elif vendor == "sqlite":
        schema_editor.execute(
            """
            CREATE TRIGGER devices_deploymentsetupevent_no_update
            BEFORE UPDATE ON devices_deploymentsetupevent
            BEGIN
                SELECT RAISE(ABORT, 'devices_deploymentsetupevent is append-only');
            END;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER devices_deploymentsetupevent_no_delete
            BEFORE DELETE ON devices_deploymentsetupevent
            BEGIN
                SELECT RAISE(ABORT, 'devices_deploymentsetupevent is append-only');
            END;
            """
        )


def remove_setup_event_append_only_trigger(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS devices_deploymentsetupevent_append_only_trigger "
            "ON devices_deploymentsetupevent;"
        )
        schema_editor.execute(
            "DROP FUNCTION IF EXISTS devices_deploymentsetupevent_append_only();"
        )
    elif vendor == "sqlite":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS devices_deploymentsetupevent_no_update;"
        )
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS devices_deploymentsetupevent_no_delete;"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0024_p1_remote_control_reliability"),
        ("teams", "0008_team_remote_control_epoch_team_remote_control_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="devicetemplate",
            name="datapoint_schema_version",
            field=models.PositiveSmallIntegerField(
                default=1,
                help_text="Version of the normalized datapoint representation stored in register_map.",
            ),
        ),
        migrations.AddField(
            model_name="gateway",
            name="gateway_capabilities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="delivered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="envelope_json",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="error_code",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="technical_error",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="idempotency_key",
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="revision",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="rollback_connector_results",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_gateway_configs, reverse_gateway_config_statuses),
        migrations.AlterField(
            model_name="gatewayconfig",
            name="idempotency_key",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name="gatewayconfig",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("delivered", "Delivered"),
                    ("accepted", "Accepted"),
                    ("active", "Active"),
                    ("failed", "Failed"),
                    ("rolled_back", "Rolled Back"),
                ],
                default="queued",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="DeploymentSetupRun",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("run_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("gateway_check", "Gateway check"),
                            ("discovering", "Discovering"),
                            ("configuring", "Configuring"),
                            ("deploying", "Deploying"),
                            ("verifying", "Verifying"),
                            ("completed", "Completed"),
                            ("completed_attention", "Completed with attention"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="draft",
                        max_length=30,
                    ),
                ),
                ("current_step", models.CharField(default="location", max_length=30)),
                ("readiness", models.JSONField(blank=True, default=dict)),
                ("summary", models.JSONField(blank=True, default=dict)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "gateway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deployment_setup_runs",
                        to="devices.gateway",
                    ),
                ),
                (
                    "initiated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deployment_setup_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deployment_setup_runs",
                        to="devices.site",
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
        migrations.CreateModel(
            name="DeploymentSetupItem",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("discovery_index", models.PositiveIntegerField(blank=True, null=True)),
                ("candidate_data", models.JSONField(blank=True, default=dict)),
                ("confidence_score", models.PositiveSmallIntegerField(default=0)),
                ("confidence_explanation", models.TextField(blank=True)),
                (
                    "trust_level",
                    models.CharField(
                        choices=[
                            ("novena_verified", "Novena verified"),
                            ("customer_validated", "Customer validated"),
                            ("ai_draft", "AI draft"),
                            ("unvalidated", "Unvalidated"),
                        ],
                        default="unvalidated",
                        max_length=30,
                    ),
                ),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("discovered", "Discovered"),
                            ("template_selected", "Template selected"),
                            ("validating", "Validating"),
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
                ("connection", models.JSONField(blank=True, default=dict)),
                ("datapoints", models.JSONField(blank=True, default=list)),
                ("validation_result", models.JSONField(blank=True, default=dict)),
                ("first_telemetry_at", models.DateTimeField(blank=True, null=True)),
                (
                    "device",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deployment_setup_items",
                        to="devices.device",
                    ),
                ),
                (
                    "selected_template",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deployment_setup_items",
                        to="devices.devicetemplate",
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
                    "validation_command",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="deployment_validation_items",
                        to="devices.remotecommand",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="devices.deploymentsetuprun",
                    ),
                ),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.CreateModel(
            name="DeploymentSetupEvent",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence_number", models.PositiveIntegerField()),
                ("event_type", models.CharField(max_length=80)),
                ("message", models.TextField()),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="devices.deploymentsetupitem",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="events",
                        to="devices.deploymentsetuprun",
                    ),
                ),
            ],
            options={"ordering": ["sequence_number"]},
        ),
        migrations.CreateModel(
            name="EquipmentTemplateRequest",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("manufacturer", models.CharField(max_length=200)),
                ("model_number", models.CharField(max_length=200)),
                (
                    "protocol",
                    models.CharField(
                        choices=[
                            ("modbus_tcp", "Modbus TCP"),
                            ("modbus_rtu", "Modbus RTU"),
                            ("opcua", "OPC-UA"),
                            ("mqtt", "MQTT"),
                            ("bacnet", "BACnet"),
                        ],
                        max_length=20,
                    ),
                ),
                ("documentation_url", models.URLField(blank=True, max_length=500)),
                (
                    "documentation_file",
                    models.FileField(blank=True, upload_to="equipment-template-requests/%Y/%m/"),
                ),
                ("discovery_evidence", models.JSONField(blank=True, default=dict)),
                ("support_reference", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("open", "Open"), ("reviewing", "Reviewing"), ("completed", "Completed")],
                        default="open",
                        max_length=20,
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="template_requests",
                        to="devices.deploymentsetuprun",
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
        ),
        migrations.CreateModel(
            name="GatewayConfigOutbox",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("claimed", "Claimed"),
                            ("delivered", "Delivered"),
                            ("retry", "Retry"),
                            ("dead_letter", "Dead letter"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("dead_lettered_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                (
                    "config",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbox",
                        to="devices.gatewayconfig",
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
            options={"ordering": ["next_attempt_at", "created_at"]},
        ),
        migrations.AddField(
            model_name="gatewayconfig",
            name="setup_run",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="configurations",
                to="devices.deploymentsetuprun",
            ),
        ),
        migrations.AddIndex(
            model_name="deploymentsetuprun",
            index=models.Index(
                fields=["team", "gateway", "state"],
                name="devices_dep_team_id_d8db7c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="deploymentsetupitem",
            index=models.Index(fields=["run", "state"], name="devices_dep_run_id_27269b_idx"),
        ),
        migrations.AddConstraint(
            model_name="deploymentsetupevent",
            constraint=models.UniqueConstraint(
                fields=("run", "sequence_number"),
                name="unique_deployment_setup_event_sequence",
            ),
        ),
        migrations.AddIndex(
            model_name="gatewayconfigoutbox",
            index=models.Index(
                fields=["status", "next_attempt_at"],
                name="devices_gat_status_3cb324_idx",
            ),
        ),
        migrations.RunPython(
            install_setup_event_append_only_trigger,
            remove_setup_event_append_only_trigger,
        ),
    ]
