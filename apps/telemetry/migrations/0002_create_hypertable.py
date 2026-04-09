from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('telemetry', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            -- Create the extension
            CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
            
            -- Django automatically creates a unique primary key on 'id'.
            -- TimescaleDB requires that any unique index on a hypertable includes the partitioning column.
            -- So we drop the existing PK and create a composite one.
            ALTER TABLE telemetry_telemetrydata DROP CONSTRAINT telemetry_telemetrydata_pkey;
            ALTER TABLE telemetry_telemetrydata ADD PRIMARY KEY (id, timestamp);

            -- Convert to hypertable
            SELECT create_hypertable('telemetry_telemetrydata', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);
            
            -- Set up compression
            ALTER TABLE telemetry_telemetrydata SET (
                timescaledb.compress,
                timescaledb.compress_segmentby = 'device_id'
            );
            SELECT add_compression_policy('telemetry_telemetrydata', INTERVAL '7 days', if_not_exists => TRUE);
            """,
            reverse_sql=""
        ),
    ]
