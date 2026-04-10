from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.teams.models import BaseTeamModel

class Site(BaseTeamModel):
    """A physical location (factory, cold room, building, solar farm) belonging to a team."""
    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Singapore')

    def __str__(self):
        return self.name

class Gateway(BaseTeamModel):
    """An edge gateway device (RPi running our forked TB Gateway)."""
    STATUS_CHOICES = (
        ('online', _('Online')),
        ('offline', _('Offline')),
        ('maintenance', _('Maintenance')),
    )
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='gateways')
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=100, unique=True)
    access_token = models.CharField(max_length=64, unique=True, help_text=_("MQTT authentication token"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_seen = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    config = models.JSONField(default=dict, blank=True)
    capacity = models.PositiveIntegerField(default=8, help_text=_("Maximum number of devices this gateway can support"))
    discovery_data = models.JSONField(default=dict, blank=True, help_text=_("Most recent discovery report from the edge"))

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

class DeviceTemplate(models.Model):
    """Pre-configured register maps for known equipment (e.g., 'Eastron SDM630')."""
    DEVICE_TYPE_CHOICES = (
        ('power_meter', _('Power Meter')),
        ('solar_inverter', _('Solar Inverter')),
        ('vfd', _('Variable Frequency Drive')),
        ('plc', _('PLC')),
        ('temp_sensor', _('Temperature Sensor')),
        ('chiller', _('Chiller')),
        ('other', _('Other')),
    )
    PROTOCOL_CHOICES = (
        ('modbus_tcp', _('Modbus TCP')),
        ('modbus_rtu', _('Modbus RTU')),
        ('opcua', _('OPC-UA')),
        ('mqtt', _('MQTT')),
        ('bacnet', _('BACnet')),
    )
    VERTICAL_CHOICES = (
        ('energy', _('Energy Monitoring')),
        ('cold_chain', _('Cold Chain')),
        ('factory', _('Smart Factory')),
    )

    name = models.CharField(max_length=200)
    manufacturer = models.CharField(max_length=200, blank=True)
    model_number = models.CharField(max_length=200, blank=True)
    device_type = models.CharField(max_length=30, choices=DEVICE_TYPE_CHOICES)
    protocol = models.CharField(max_length=20, choices=PROTOCOL_CHOICES)
    register_map = models.JSONField(help_text=_("Definition of Modbus registers or OPC-UA nodes"))
    default_polling_interval = models.IntegerField(default=5, help_text=_("Seconds between data reads"))
    category = models.CharField(max_length=20, choices=VERTICAL_CHOICES, default='energy')
    alert_presets = models.JSONField(default=list, blank=True, help_text=_("List of default alert rules for this template"))
    is_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.name

class Device(BaseTeamModel):
    """A monitored device (sensor, PLC, VFD, power meter, inverter etc.)."""
    STATUS_CHOICES = (
        ('online', _('Online')),
        ('offline', _('Offline')),
        ('alarm', _('Alarm')),
    )
    # Categories for Energy Monitoring vertical (Generation vs Consumption)
    ENERGY_CATEGORY_CHOICES = (
        ('generation', _('Generation (Solar, Wind, etc.)')),
        ('utility', _('Utility (Main Grid)')),
        ('consumption', _('Consumption (Equipment, Building)')),
        ('none', _('None / Not Applicable')),
    )

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name='devices', null=True, blank=True)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='devices')
    template = models.ForeignKey(DeviceTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    
    name = models.CharField(max_length=200)
    device_type = models.CharField(max_length=30, choices=DeviceTemplate.DEVICE_TYPE_CHOICES)
    protocol = models.CharField(max_length=20, choices=DeviceTemplate.PROTOCOL_CHOICES)
    port = models.PositiveIntegerField(null=True, blank=True, help_text=_("Physical port or address on the gateway"))
    energy_category = models.CharField(max_length=20, choices=ENERGY_CATEGORY_CHOICES, default='none')
    
    connection_config = models.JSONField(default=dict, help_text=_("Modbus slave ID, IP address, port, etc."))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    last_telemetry_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site.name})"
