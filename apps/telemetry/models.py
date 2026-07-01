from django.db import models


class TelemetryData(models.Model):
    """
    Time-series telemetry data point.
    Optimized for TimescaleDB (converted to hypertable in migrations).
    """

    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="telemetry")
    timestamp = models.DateTimeField(db_index=True)
    cloud_received_at = models.DateTimeField(null=True, blank=True, db_index=True)
    db_flushed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    key = models.CharField(max_length=100)  # e.g., 'active_power', 'voltage', 'temperature'

    # Values as separate fields to avoid JSON overhead in high-frequency writes
    value_numeric = models.FloatField(null=True, blank=True)
    value_string = models.TextField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)

    class Meta:
        # We index (device, key, timestamp) for efficient time-series queries
        indexes = [
            models.Index(fields=["device", "key", "timestamp"]),
        ]
        ordering = ["-timestamp"]
        verbose_name_plural = "Telemetry data"

    def __str__(self):
        val = self.value_numeric or self.value_string or self.value_bool
        return f"{self.device.name} - {self.key}: {val} @ {self.timestamp}"


class GatewayLog(models.Model):
    """Log entries received from edge gateways."""

    gateway = models.ForeignKey("devices.Gateway", on_delete=models.CASCADE, related_name="logs")
    timestamp = models.DateTimeField(db_index=True)
    level = models.CharField(max_length=20)  # INFO, WARNING, ERROR, CRITICAL
    logger_name = models.CharField(max_length=200)
    message = models.TextField()
    module = models.CharField(max_length=100, blank=True)
    line = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["gateway", "timestamp"]),
            models.Index(fields=["gateway", "level"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.gateway.serial_number} @ {self.timestamp}"
