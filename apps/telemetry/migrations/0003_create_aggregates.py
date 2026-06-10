from django.db import migrations

def create_aggregates(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    
    schema_editor.execute("""
        -- Hourly Average Power
        CREATE MATERIALIZED VIEW hourly_power_stats
        WITH (timescaledb.continuous) AS
        SELECT time_bucket('1 hour', timestamp) AS bucket,
               device_id,
               AVG(value_numeric) as avg_power,
               MAX(value_numeric) as max_power,
               MIN(value_numeric) as min_power
        FROM telemetry_telemetrydata
        WHERE key = 'active_power'
        GROUP BY bucket, device_id
        WITH NO DATA;

        -- Daily Energy Ingestion (kWh calculation)
        CREATE MATERIALIZED VIEW daily_energy_stats
        WITH (timescaledb.continuous) AS
        SELECT time_bucket('1 day', timestamp) AS bucket,
               device_id,
               (AVG(value_numeric) * 24) / 1000 as kwh_total
        FROM telemetry_telemetrydata
        WHERE key = 'active_power'
        GROUP BY bucket, device_id
        WITH NO DATA;

        -- Refresh Policies
        SELECT add_continuous_aggregate_policy('hourly_power_stats',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour');

        SELECT add_continuous_aggregate_policy('daily_energy_stats',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 day');
    """)

def reverse_aggregates(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    schema_editor.execute("""
        DROP MATERIALIZED VIEW IF EXISTS daily_energy_stats CASCADE;
        DROP MATERIALIZED VIEW IF EXISTS hourly_power_stats CASCADE;
    """)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('telemetry', '0002_create_hypertable'),
    ]

    operations = [
        migrations.RunPython(create_aggregates, reverse_aggregates),
    ]
