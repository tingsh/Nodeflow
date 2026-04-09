from django.db import models
from django.utils.translation import gettext_lazy as _

class TelemetryData(models.Model):
    """
    Time-series telemetry data point.
    Optimized for TimescaleDB (converted to hypertable in migrations).
    """
    device = models.ForeignKey('devices.Device', on_delete=models.CASCADE, related_name='telemetry')
    timestamp = models.DateTimeField(db_index=True)
    key = models.CharField(max_length=100)  # e.g., 'active_power', 'voltage', 'temperature'
    
    # Values as separate fields to avoid JSON overhead in high-frequency writes
    value_numeric = models.FloatField(null=True, blank=True)
    value_string = models.TextField(null=True, blank=True)
    value_bool = models.BooleanField(null=True, blank=True)

    class Meta:
        # We index (device, key, timestamp) for efficient time-series queries
        indexes = [
            models.Index(fields=['device', 'key', 'timestamp']),
        ]
        ordering = ['-timestamp']
        verbose_name_plural = "Telemetry data"

    def __str__(self):
        return f"{self.device.name} - {self.key}: {self.value_numeric or self.value_string or self.value_bool} @ {self.timestamp}"
