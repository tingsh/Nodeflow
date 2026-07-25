import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0021_governed_policy_models"),
        ("teams", "0008_team_remote_control_epoch_team_remote_control_mode"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ControlCommissioningSession",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("scope", models.JSONField(default=dict)),
                ("evidence", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("completed", "Completed"),
                            ("expired", "Expired"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="open",
                        max_length=16,
                    ),
                ),
                ("expires_at", models.DateTimeField()),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "commissioner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="control_commissioning_sessions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                ("gateway", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="devices.gateway")),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="devices.site")),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ControlReadinessAssessment",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("monitoring_only", "Monitoring only"),
                            ("evidence_collecting", "Evidence collecting"),
                            ("ready_for_commissioning", "Ready for commissioning"),
                            ("commissioning", "Commissioning"),
                            ("ready_for_activation", "Ready for activation"),
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("recommissioning_required", "Recommissioning required"),
                        ],
                        default="monitoring_only",
                        max_length=32,
                    ),
                ),
                ("observation_days", models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ("telemetry_coverage_percent", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("evidence", models.JSONField(default=dict)),
                ("blockers", models.JSONField(blank=True, default=list)),
                ("waiver_reason", models.TextField(blank=True)),
                ("assessed_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "assessed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="control_readiness_assessments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "gateway",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="control_readiness_assessments",
                        to="devices.gateway",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="control_readiness_assessments",
                        to="devices.site",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
                (
                    "waiver_approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="approved_control_readiness_waivers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RemoteCommandApproval",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("requested_by_snapshot", models.JSONField(default=dict)),
                ("approver_snapshot", models.JSONField(blank=True, default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("expired", "Expired"),
                            ("invalidated", "Invalidated"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("binding_checksum", models.CharField(max_length=64)),
                ("expires_at", models.DateTimeField()),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("decision_reason", models.TextField(blank=True)),
                ("mfa_verified", models.BooleanField(default=False)),
                ("recent_auth_at", models.DateTimeField(blank=True, null=True)),
                (
                    "approver",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="remote_command_approvals",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "command",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="approval",
                        to="devices.remotecommand",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ControlActivation",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("command_key", models.CharField(max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("suspended", "Suspended"),
                            ("expired", "Expired"),
                            ("revoked", "Revoked"),
                        ],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("control_epoch", models.PositiveBigIntegerField()),
                ("activated_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField()),
                ("suspended_reason", models.TextField(blank=True)),
                (
                    "activated_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="control_activations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "device",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="control_activations",
                        to="devices.device",
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
                (
                    "commissioning_session",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="devices.controlcommissioningsession"),
                ),
                (
                    "readiness_assessment",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="devices.controlreadinessassessment"),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("device", "command_key", "control_epoch"),
                        name="unique_control_activation_epoch",
                    )
                ]
            },
        ),
        migrations.CreateModel(
            name="SiteMembershipAccess",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "membership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_access",
                        to="teams.membership",
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="membership_access",
                        to="devices.site",
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
                        fields=("membership", "site"),
                        name="unique_membership_site_access",
                    )
                ]
            },
        ),
    ]
