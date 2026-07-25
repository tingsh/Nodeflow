import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0020_remote_command_core"),
        ("teams", "0008_team_remote_control_epoch_team_remote_control_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gateway",
            name="remote_control_clock_ready",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gateway",
            name="remote_control_epoch",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="gateway",
            name="remote_control_journal_ready",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="gateway",
            name="remote_control_policy_revision",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="commissioning_revision",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="policy_checksum",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="policy_revision",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="schema_version",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="signature",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="signing_key_id",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="template_revision",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="RemoteControlScope",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("command_key", models.CharField(blank=True, max_length=100)),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("disabled", "Disabled"),
                            ("commissioning", "Commissioning"),
                            ("enabled", "Enabled"),
                            ("suspended", "Suspended"),
                        ],
                        default="disabled",
                        max_length=20,
                    ),
                ),
                ("control_epoch", models.PositiveBigIntegerField(default=1)),
                ("reason", models.TextField(blank=True)),
                (
                    "device",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="devices.device"),
                ),
                (
                    "gateway",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="devices.gateway"),
                ),
                (
                    "site",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="devices.site"),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CommandPolicy",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("command_key", models.CharField(max_length=100)),
                ("allowed_roles", models.JSONField(default=list)),
                ("customer_limits", models.JSONField(default=dict)),
                ("prerequisites", models.JSONField(blank=True, default=list)),
                ("approval_required", models.BooleanField(default=False)),
                (
                    "risk",
                    models.CharField(
                        choices=[
                            ("diagnostic", "Diagnostic"),
                            ("low", "Low"),
                            ("high", "High"),
                            ("critical", "Critical"),
                        ],
                        default="high",
                        max_length=16,
                    ),
                ),
                ("revision", models.PositiveIntegerField(default=1)),
                ("checksum", models.CharField(max_length=64)),
                ("is_enabled", models.BooleanField(default=False)),
                (
                    "device",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="devices.device"),
                ),
                (
                    "gateway",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="devices.gateway"),
                ),
                (
                    "site",
                    models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="devices.site"),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("device", "command_key", "revision"),
                        name="unique_command_policy_revision",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="CommandTransportAttempt",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("attempt_number", models.PositiveIntegerField()),
                ("request_id", models.UUIDField(blank=True, null=True)),
                ("state", models.CharField(default="started", max_length=32)),
                ("broker_message_id", models.PositiveIntegerField(blank=True, null=True)),
                ("error", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "command",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="publish_attempts", to="devices.remotecommand"),
                ),
                (
                    "outbox",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transport_attempts", to="devices.commandoutbox"),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("command", "attempt_number"),
                        name="unique_command_transport_attempt",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="CommissionedControlEnvelope",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("command_key", models.CharField(max_length=100)),
                ("operating_limits", models.JSONField(default=dict)),
                ("prerequisites", models.JSONField(blank=True, default=list)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("checksum", models.CharField(max_length=64)),
                ("commissioned_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=False)),
                (
                    "commissioned_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commissioned_control_envelopes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="commissioned_control_envelopes",
                        to="devices.device",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("device", "command_key", "revision"),
                        name="unique_commissioned_control_revision",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="GatewayControlPolicyBundle",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revision", models.PositiveIntegerField()),
                ("control_epoch", models.PositiveBigIntegerField()),
                ("payload", models.JSONField(default=dict)),
                ("checksum", models.CharField(max_length=64)),
                ("signing_key_id", models.CharField(max_length=64)),
                ("signature", models.TextField()),
                ("published_at", models.DateTimeField(blank=True, null=True)),
                ("acknowledged_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=False)),
                (
                    "gateway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="control_policy_bundles",
                        to="devices.gateway",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("gateway", "revision"),
                        name="unique_gateway_policy_bundle_revision",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="TemplateControlDefinition",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("command_key", models.CharField(max_length=100)),
                ("operation", models.CharField(default="write_device", max_length=64)),
                ("data_type", models.CharField(max_length=32)),
                ("unit", models.CharField(blank=True, max_length=32)),
                ("connector_mapping", models.JSONField(default=dict)),
                ("technical_limits", models.JSONField(default=dict)),
                ("prerequisites", models.JSONField(blank=True, default=list)),
                ("revision", models.PositiveIntegerField(default=1)),
                ("checksum", models.CharField(max_length=64)),
                ("is_verified", models.BooleanField(default=False)),
                ("is_enabled", models.BooleanField(default=False)),
                (
                    "template",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="control_definitions",
                        to="devices.devicetemplate",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("template", "command_key", "revision"),
                        name="unique_template_control_revision",
                    )
                ]
            },
        ),
    ]
