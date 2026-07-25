import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0019_signed_ota_release_metadata"),
        ("teams", "0008_team_remote_control_epoch_team_remote_control_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gateway",
            name="remote_control_local_writeback_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gateway",
            name="remote_control_policy_loaded",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gateway",
            name="remote_control_protocol_version",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="RemoteCommand",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("user", "User"),
                            ("automation", "Automation"),
                            ("system", "System"),
                            ("support", "Support"),
                        ],
                        default="user",
                        max_length=16,
                    ),
                ),
                ("operation", models.CharField(max_length=64)),
                ("command_key", models.CharField(blank=True, max_length=100)),
                ("requested_value", models.JSONField(blank=True, null=True)),
                ("normalized_value", models.JSONField(blank=True, null=True)),
                ("reason", models.TextField(blank=True)),
                (
                    "risk",
                    models.CharField(
                        choices=[
                            ("diagnostic", "Diagnostic"),
                            ("low", "Low"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("requested", "Requested"),
                            ("policy_denied", "Policy denied"),
                            ("awaiting_approval", "Awaiting approval"),
                            ("approved", "Approved"),
                            ("queued_for_dispatch", "Queued for dispatch"),
                            ("dispatching", "Dispatching"),
                            ("publish_accepted", "Publish accepted"),
                            ("broker_acknowledged", "Broker acknowledged"),
                            ("gateway_received", "Gateway received"),
                            ("executing", "Executing"),
                            ("field_protocol_accepted", "Field protocol accepted"),
                            ("verification_pending", "Verification pending"),
                            ("verified", "Verified"),
                            ("rejected", "Rejected"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                            ("timed_out", "Timed out"),
                            ("cancelled", "Cancelled"),
                            ("outcome_unknown", "Outcome unknown"),
                            ("reconciled_verified", "Reconciled: verified"),
                            ("reconciled_not_applied", "Reconciled: not applied"),
                            ("reconciled_unresolved", "Reconciled: unresolved"),
                        ],
                        default="requested",
                        max_length=32,
                    ),
                ),
                ("actor_snapshot", models.JSONField(blank=True, default=dict)),
                ("policy_snapshot", models.JSONField(blank=True, default=dict)),
                ("request_payload", models.JSONField(blank=True, default=dict)),
                ("response_payload", models.JSONField(blank=True, default=dict)),
                ("control_epoch", models.PositiveBigIntegerField(default=1)),
                ("sequence_number", models.PositiveBigIntegerField(default=0)),
                ("idempotency_key", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("expires_at", models.DateTimeField()),
                ("broker_acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("gateway_received_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("error_code", models.CharField(blank=True, max_length=80)),
                ("error_message", models.TextField(blank=True)),
                (
                    "device",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="remote_commands",
                        to="devices.device",
                    ),
                ),
                (
                    "gateway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="remote_commands",
                        to="devices.gateway",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="requested_remote_commands",
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
        migrations.CreateModel(
            name="CommandOutbox",
            fields=[
                (
                    "id",
                    models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("claimed", "Claimed"),
                            ("published", "Published"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("available_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "command",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="outbox",
                        to="devices.remotecommand",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CommandEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("event_type", models.CharField(max_length=80)),
                ("from_status", models.CharField(blank=True, max_length=32)),
                ("to_status", models.CharField(blank=True, max_length=32)),
                ("actor_snapshot", models.JSONField(blank=True, default=dict)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("checksum", models.CharField(blank=True, max_length=64)),
                ("happened_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "command",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="events",
                        to="devices.remotecommand",
                    ),
                ),
            ],
            options={"ordering": ["happened_at", "id"]},
        ),
        migrations.AddField(
            model_name="devicecommand",
            name="remote_command",
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="legacy_device_command",
                to="devices.remotecommand",
            ),
        ),
        migrations.AddField(
            model_name="rpccommand",
            name="remote_command",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="transport_attempts",
                to="devices.remotecommand",
            ),
        ),
        migrations.AddIndex(
            model_name="remotecommand",
            index=models.Index(
                fields=["team", "status", "created_at"],
                name="devices_rem_team_id_f2f356_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="remotecommand",
            index=models.Index(fields=["gateway", "status"], name="devices_rem_gateway_0a29d0_idx"),
        ),
        migrations.AddIndex(
            model_name="remotecommand",
            index=models.Index(fields=["device", "status"], name="devices_rem_device__35a0f2_idx"),
        ),
        migrations.AddIndex(
            model_name="commandoutbox",
            index=models.Index(fields=["status", "available_at"], name="devices_com_status_a722dc_idx"),
        ),
        migrations.AddIndex(
            model_name="commandevent",
            index=models.Index(fields=["command", "happened_at"], name="devices_com_command_5c592b_idx"),
        ),
    ]
