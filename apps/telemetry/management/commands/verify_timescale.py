from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Verify the TimescaleDB hypertable state for telemetry data."

    def handle(self, *args, **options):
        self.stdout.write("Verifying TimescaleDB Hypertable...")

        with connection.cursor() as cursor:
            # Check if telemetry_telemetrydata is a hypertable
            cursor.execute(
                "SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_name = 'telemetry_telemetrydata';"
            )
            row = cursor.fetchone()

            if row:
                self.stdout.write(self.style.SUCCESS(f"OK: '{row[0]}' is a verified TimescaleDB Hypertable."))

                # Get chunk info
                cursor.execute(
                    "SELECT count(*) FROM timescaledb_information.chunks WHERE hypertable_name = 'telemetry_telemetrydata';"
                )
                chunk_count = cursor.fetchone()[0]
                self.stdout.write(f"Active Chunks: {chunk_count}")

                # Check dimensions
                cursor.execute(
                    "SELECT column_name, time_interval FROM timescaledb_information.dimensions WHERE hypertable_name = 'telemetry_telemetrydata';"
                )
                dimensions = cursor.fetchall()
                for dim in dimensions:
                    self.stdout.write(f"Dimension: {dim[0]} (Interval: {dim[1]})")
            else:
                self.stdout.write(self.style.ERROR("ERROR: 'telemetry_telemetrydata' is NOT a hypertable!"))
                self.stdout.write(
                    self.style.WARNING(
                        "Fix: Consider running SELECT create_hypertable('telemetry_telemetrydata', 'timestamp'); manually if migrations failed."
                    )
                )

        self.stdout.write("Verification complete.")
