from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.teams.models import BaseTeamModel


class Site(BaseTeamModel):
    """A physical location (factory, cold room, building, solar farm) belonging to a team."""

    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    timezone = models.CharField(max_length=50, default="Asia/Singapore")

    def __str__(self):
        return self.name


class Gateway(BaseTeamModel):
    """An edge gateway device (RPi running our forked TB Gateway)."""

    STATUS_CHOICES = (
        ("online", _("Online")),
        ("offline", _("Offline")),
        ("maintenance", _("Maintenance")),
    )
    TLS_MODE_CHOICES = (
        ("none", _("None")),
        ("one-way", _("One-Way TLS")),
        ("mutual", _("Mutual TLS")),
    )

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="gateways")
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=100, unique=True)
    access_token = models.CharField(max_length=64, unique=True, help_text=_("MQTT authentication token"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="offline")
    last_seen = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    config = models.JSONField(default=dict, blank=True)
    capacity = models.PositiveIntegerField(default=8, help_text=_("Maximum number of devices this gateway can support"))
    discovery_data = models.JSONField(
        default=dict, blank=True, help_text=_("Most recent discovery report from the edge")
    )

    # MQTT credentials (per-gateway authentication)
    mqtt_username = models.CharField(max_length=100, unique=True, null=True, blank=True)
    mqtt_password = models.CharField(max_length=255, blank=True, help_text=_("Bcrypt hash of the MQTT password"))
    tls_mode = models.CharField(max_length=10, choices=TLS_MODE_CHOICES, default="one-way")
    client_cert_pem = models.TextField(blank=True, help_text=_("Client certificate PEM for mTLS"))
    client_key_pem = models.TextField(blank=True, help_text=_("Client private key PEM for mTLS"))

    # Heartbeat / attribute sync fields (populated by edge gateway)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    uptime_seconds = models.IntegerField(null=True, blank=True)
    python_version = models.CharField(max_length=20, blank=True)
    platform_info = models.CharField(max_length=200, blank=True)
    active_connectors = models.JSONField(default=list, blank=True)
    connected_devices = models.JSONField(default=list, blank=True)

    # Network Watchdog fields
    active_interface = models.CharField(max_length=20, blank=True, default="eth0")
    failover_count = models.IntegerField(default=0)
    ethernet_status = models.CharField(max_length=20, blank=True, default="unknown")
    wifi_status = models.CharField(max_length=20, blank=True, default="unknown")
    fourg_status = models.CharField(max_length=20, blank=True, default="unknown")
    signal_strength = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"


class DeviceTemplate(models.Model):
    """Pre-configured register maps for known equipment."""

    DEVICE_TYPE_CHOICES = (
        ("power_meter", _("Power Meter")),
        ("solar_inverter", _("Solar Inverter")),
        ("vfd", _("Variable Frequency Drive")),
        ("plc", _("PLC")),
        ("temp_sensor", _("Temperature Sensor")),
        ("chiller", _("Chiller")),
        ("other", _("Other")),
    )
    PROTOCOL_CHOICES = (
        ("modbus_tcp", _("Modbus TCP")),
        ("modbus_rtu", _("Modbus RTU")),
        ("opcua", _("OPC-UA")),
        ("mqtt", _("MQTT")),
        ("bacnet", _("BACnet")),
    )
    VERTICAL_CHOICES = (
        ("energy", _("Energy Monitoring")),
        ("cold_chain", _("Cold Chain")),
        ("factory", _("Smart Factory")),
    )

    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=200, blank=True)
    model_number = models.CharField(max_length=200, blank=True)
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPE_CHOICES)
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES)
    register_map = models.JSONField(help_text=_("Definition of registers. Keys can have 'writable': true."))
    default_polling_interval = models.IntegerField(default=5)
    category = models.CharField(max_length=20, choices=VERTICAL_CHOICES, default="energy")
    alert_presets = models.JSONField(default=list, blank=True)
    is_verified = models.BooleanField(default=False)

    SOURCE_CHOICES = (
        ("curated", _("Curated (Nodeflow)")),
        ("ai_generated", _("AI Generated")),
        ("user_created", _("User Created")),
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="curated")
    source_url = models.URLField(blank=True, max_length=500, help_text=_("URL where the register map was found"))
    ai_confidence = models.FloatField(null=True, blank=True, help_text=_("AI confidence score 0.0-1.0"))
    created_by_team = models.ForeignKey(
        "teams.Team", null=True, blank=True, on_delete=models.SET_NULL,
        help_text=_("Team that originally created this template")
    )
    usage_count = models.PositiveIntegerField(default=0, help_text=_("Number of devices using this template"))
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.name


class Device(BaseTeamModel):
    """A monitored device (sensor, PLC, VFD, etc.)."""

    STATUS_CHOICES = (
        ("online", _("Online")),
        ("offline", _("Offline")),
        ("alarm", _("Alarm")),
    )
    ENERGY_CATEGORY_CHOICES = (
        ("generation", _("Generation (Solar, Wind, etc.)")),
        ("utility", _("Utility (Main Grid)")),
        ("consumption", _("Consumption (Equipment, Building)")),
        ("none", _("None / Not Applicable")),
    )

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name="devices", null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="devices")
    template = models.ForeignKey(DeviceTemplate, null=True, blank=True, on_delete=models.SET_NULL)

    name = models.CharField(max_length=200)
    device_type = models.CharField(max_length=30, choices=DeviceTemplate.DEVICE_TYPE_CHOICES)
    protocol = models.CharField(max_length=20, choices=DeviceTemplate.PROTOCOL_CHOICES)
    port = models.CharField(max_length=100, null=True, blank=True, help_text="Interface name or address (e.g., /dev/ttyUSB0, 192.168.1.100:502)")
    energy_category = models.CharField(max_length=20, choices=ENERGY_CATEGORY_CHOICES, default="none")

    connection_config = models.JSONField(default=dict)
    discovery_meta = models.JSONField(default=dict, blank=True, help_text="Raw discovery data from Edge (interface, slave_id, baud_rate, etc.)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="offline")
    last_telemetry_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site.name})"


class GatewayConfig(BaseTeamModel):
    """Tracks config versions pushed to gateways."""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("success", _("Success")),
        ("failed", _("Failed")),
    )

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name="config_history")
    config_json = models.JSONField()
    pushed_at = models.DateTimeField(auto_now_add=True)
    request_id = models.UUIDField(unique=True)
    action = models.CharField(max_length=30, default="full_update")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-pushed_at"]

    def __str__(self):
        return f"Config push {self.request_id} → {self.gateway.serial_number} ({self.status})"


class RpcCommand(BaseTeamModel):
    """Tracks RPC commands sent to gateways."""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("success", _("Success")),
        ("error", _("Error")),
        ("timeout", _("Timeout")),
    )

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name="rpc_commands")
    request_id = models.UUIDField(unique=True)
    method = models.CharField(max_length=50)
    params = models.JSONField(default=dict)
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"RPC {self.method} → {self.gateway.serial_number} ({self.status})"


class DeviceCommand(BaseTeamModel):
    """A control command sent to a device (write-back)."""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("sent", _("Sent to Gateway")),
        ("executed", _("Executed Successfully")),
        ("failed", _("Failed")),
        ("timed_out", _("Timed Out")),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="commands")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    command_key = models.CharField(max_length=100)  # e.g., 'motor_speed'
    value = models.JSONField()  # The value to write

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    payload = models.JSONField(default=dict, blank=True, help_text=_("The exact payload sent to the gateway"))
    response_payload = models.JSONField(default=dict, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"CMD: {self.command_key}={self.value} on {self.device.name} ({self.status})"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Device)
def auto_generate_dashboard_on_template_match(sender, instance, **kwargs):
    if instance.template:
        try:
            from apps.dashboard.services import generate_default_dashboard
            generate_default_dashboard(instance)
        except Exception as e:
            logger = logging.getLogger("iot_platform")
            logger.error("Failed to auto-generate dashboard for device %s: %s", instance.name, e)

