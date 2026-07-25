import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def backfill_event_sequences(apps, schema_editor):
    CommandEvent = apps.get_model("devices", "CommandEvent")
    command_ids = CommandEvent.objects.order_by().values_list("command_id", flat=True).distinct()
    for command_id in command_ids.iterator():
        event_ids = list(
            CommandEvent.objects.filter(command_id=command_id)
            .order_by("happened_at", "id")
            .values_list("id", flat=True)
        )
        for sequence_number, event_id in enumerate(event_ids, start=1):
            CommandEvent.objects.filter(pk=event_id).update(sequence_number=sequence_number)


def install_append_only_trigger(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            """
            CREATE OR REPLACE FUNCTION devices_commandevent_append_only()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'devices_commandevent is append-only';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER devices_commandevent_append_only_trigger
            BEFORE UPDATE OR DELETE ON devices_commandevent
            FOR EACH ROW EXECUTE FUNCTION devices_commandevent_append_only();
            """
        )
    elif vendor == "sqlite":
        schema_editor.execute(
            """
            CREATE TRIGGER devices_commandevent_no_update
            BEFORE UPDATE ON devices_commandevent
            BEGIN
                SELECT RAISE(ABORT, 'devices_commandevent is append-only');
            END;
            """
        )
        schema_editor.execute(
            """
            CREATE TRIGGER devices_commandevent_no_delete
            BEFORE DELETE ON devices_commandevent
            BEGIN
                SELECT RAISE(ABORT, 'devices_commandevent is append-only');
            END;
            """
        )


def remove_append_only_trigger(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    if vendor == "postgresql":
        schema_editor.execute(
            "DROP TRIGGER IF EXISTS devices_commandevent_append_only_trigger ON devices_commandevent;"
        )
        schema_editor.execute("DROP FUNCTION IF EXISTS devices_commandevent_append_only();")
    elif vendor == "sqlite":
        schema_editor.execute("DROP TRIGGER IF EXISTS devices_commandevent_no_update;")
        schema_editor.execute("DROP TRIGGER IF EXISTS devices_commandevent_no_delete;")


class Migration(migrations.Migration):
    dependencies = [
        ("devices", "0023_remote_control_hardening"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="gateway",
            name="remote_control_capabilities",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="rpccommand",
            name="response_stage",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="execution_status",
            field=models.CharField(default="not_started", max_length=32),
        ),
        migrations.AddField(
            model_name="remotecommand",
            name="transport_status",
            field=models.CharField(default="request_accepted", max_length=32),
        ),
        migrations.AddField(
            model_name="commandoutbox",
            name="dead_lettered_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="commandoutbox",
            name="lease_expires_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="commandoutbox",
            name="next_attempt_at",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="commandevent",
            name="sequence_number",
            field=models.PositiveBigIntegerField(null=True),
        ),
        migrations.RunPython(backfill_event_sequences, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="commandevent",
            name="sequence_number",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="commandevent",
            name="command",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="events",
                to="devices.remotecommand",
            ),
        ),
        migrations.AlterField(
            model_name="commandevent",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RemoveIndex(
            model_name="commandevent",
            name="devices_com_command_5c592b_idx",
        ),
        migrations.AddIndex(
            model_name="commandevent",
            index=models.Index(
                fields=["command", "sequence_number"],
                name="devices_com_command_5dc736_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="commandevent",
            constraint=models.UniqueConstraint(
                fields=("command", "sequence_number"),
                name="unique_command_event_sequence",
            ),
        ),
        migrations.AlterModelOptions(
            name="commandevent",
            options={"ordering": ["sequence_number"]},
        ),
        migrations.AlterField(
            model_name="commandoutbox",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("claimed", "Claimed"),
                    ("published", "Published"),
                    ("retry", "Retry scheduled"),
                    ("failed", "Failed"),
                    ("dead_letter", "Dead letter"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name="devicecommand",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("sent", "Sent to Gateway"),
                    ("accepted", "Accepted by Field Protocol"),
                    ("executed", "Executed Successfully"),
                    ("failed", "Failed"),
                    ("timed_out", "Timed Out"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="remotecommand",
            name="status",
            field=models.CharField(
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
                    ("action_initiated", "Action initiated"),
                    ("action_completed", "Action completed"),
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
        migrations.RemoveIndex(
            model_name="commandoutbox",
            name="devices_com_status_a722dc_idx",
        ),
        migrations.AddIndex(
            model_name="commandoutbox",
            index=models.Index(
                fields=["status", "next_attempt_at"],
                name="devices_com_status_797fed_idx",
            ),
        ),
        migrations.RunPython(install_append_only_trigger, remove_append_only_trigger),
    ]
