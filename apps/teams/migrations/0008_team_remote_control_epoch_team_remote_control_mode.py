from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("teams", "0007_alter_team_closed_reason_alter_team_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="team",
            name="remote_control_epoch",
            field=models.PositiveBigIntegerField(
                db_default=1,
                default=1,
                help_text="Monotonic epoch used to invalidate previously issued remote commands.",
            ),
        ),
        migrations.AddField(
            model_name="team",
            name="remote_control_mode",
            field=models.CharField(
                choices=[
                    ("monitoring_only", "Monitoring only"),
                    ("controlled", "Controlled"),
                    ("locked_down", "Locked down"),
                ],
                db_default="monitoring_only",
                default="monitoring_only",
                help_text="Remote control is disabled until the team completes governed-control activation.",
                max_length=24,
            ),
        ),
    ]
