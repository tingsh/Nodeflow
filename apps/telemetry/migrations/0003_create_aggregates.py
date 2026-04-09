from django.db import migrations

class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('telemetry', '0002_create_hypertable'),
    ]

    operations = [
        # Hourly Active Power Average Continuous Aggregate
        migrations.RunSQL(
            sql="""
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
            """,
            reverse_sql="""
            DROP MATERIALIZED VIEW IF EXISTS daily_energy_stats;
            DROP MATERIALIZED VIEW IF EXISTS hourly_power_stats;
            """
        ),
    ]
