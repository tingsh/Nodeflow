import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0022_control_readiness_and_approval"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gateway",
            name="remote_control_event_spool_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="gateway",
            name="remote_control_storage_healthy",
            field=models.BooleanField(default=False),
        ),
        migrations.CreateModel(
            name="RemoteControlSigningKey",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key_id", models.CharField(max_length=64, unique=True)),
                ("public_key", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("active", "Active"),
                            ("next", "Next"),
                            ("retired", "Retired"),
                            ("revoked", "Revoked"),
                        ],
                        max_length=16,
                    ),
                ),
                (
                    "private_key_reference",
                    models.CharField(
                        blank=True,
                        help_text="Reference to a managed secret; private key material is never stored here.",
                        max_length=255,
                    ),
                ),
                ("activated_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="CommandAuditLegalHold",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reason", models.TextField()),
                ("placed_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("released_at", models.DateTimeField(blank=True, null=True)),
                (
                    "command",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="legal_holds",
                        to="devices.remotecommand",
                    ),
                ),
                (
                    "placed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="command_audit_legal_holds",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "team",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="teams.team", verbose_name="Team"),
                ),
            ],
        ),
    ]
