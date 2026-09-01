from django.db import migrations

def update_aggregates_and_retention(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    
    schema_editor.execute("""
        -- Drop old materialized views and their policies (CASCADE handles policy deletion)
        DROP MATERIALIZED VIEW IF EXISTS daily_energy_stats CASCADE;
        DROP MATERIALIZED VIEW IF EXISTS hourly_power_stats CASCADE;

        -- Create the generalized hourly telemetry stats continuous aggregate
        CREATE MATERIALIZED VIEW hourly_telemetry_stats
        WITH (timescaledb.continuous) AS
        SELECT time_bucket('1 hour', timestamp) AS bucket,
               device_id,
               key,
               AVG(value_numeric) as avg_value,
               MAX(value_numeric) as max_value,
               MIN(value_numeric) as min_value,
               AVG(CASE WHEN value_bool IS TRUE THEN 1.0 WHEN value_bool IS FALSE THEN 0.0 ELSE NULL END) as true_percentage
        FROM telemetry_telemetrydata
        GROUP BY bucket, device_id, key
        WITH NO DATA;

        -- Add refresh policy for hourly telemetry stats
        SELECT add_continuous_aggregate_policy('hourly_telemetry_stats',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);

        -- Add the global 90-day physical retention policy to the raw telemetry
        -- hypertable. Subscription plans intentionally control customer-visible
        -- query/export history, not immediate row deletion; retained rows can
        -- become visible after an upgrade while still shrinking access
        -- immediately after a downgrade.
        SELECT add_retention_policy('telemetry_telemetrydata', 
            drop_after => INTERVAL '90 days', 
            if_not_exists => TRUE);

        -- Add matching global physical retention to the continuous aggregate
        SELECT add_retention_policy('hourly_telemetry_stats', 
            drop_after => INTERVAL '90 days', 
            if_not_exists => TRUE);
    """)

def reverse_aggregates_and_retention(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    
    schema_editor.execute("""
        -- Drop new view and policies
        DROP MATERIALIZED VIEW IF EXISTS hourly_telemetry_stats CASCADE;

        -- Re-create daily_energy_stats and hourly_power_stats as they were in 0003
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

        CREATE MATERIALIZED VIEW daily_energy_stats
        WITH (timescaledb.continuous) AS
        SELECT time_bucket('1 day', timestamp) AS bucket,
               device_id,
               (AVG(value_numeric) * 24) / 1000 as kwh_total
        FROM telemetry_telemetrydata
        WHERE key = 'active_power'
        GROUP BY bucket, device_id
        WITH NO DATA;

        SELECT add_continuous_aggregate_policy('hourly_power_stats',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour');

        SELECT add_continuous_aggregate_policy('daily_energy_stats',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 day');
    """)


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('telemetry', '0004_gatewaylog'),
    ]

    operations = [
        migrations.RunPython(update_aggregates_and_retention, reverse_aggregates_and_retention),
    ]
