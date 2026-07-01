from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('telemetry', '0005_update_aggregates_retention'),
    ]

    operations = [
        migrations.AddField(
            model_name='telemetrydata',
            name='cloud_received_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='telemetrydata',
            name='db_flushed_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
