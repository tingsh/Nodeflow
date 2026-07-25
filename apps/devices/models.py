import logging
import uuid

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.teams.models import BaseTeamModel


class Site(BaseTeamModel):
    """A physical location (factory, cold room, building, solar farm) belonging to a team."""

    SOLUTION_PROFILE_CHOICES = (
        ("general_iot", _("General IoT")),
        ("cold_chain", _("Cold Chain Monitoring")),
        ("factory_energy", _("Factory Energy Monitoring")),
        ("facilities_hvac", _("Facilities / HVAC")),
    )

    name = models.CharField(max_length=200)
    address = models.TextField(blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    timezone = models.CharField(max_length=50, default="Asia/Singapore")
    solution_profile = models.CharField(
        max_length=30,
        choices=SOLUTION_PROFILE_CHOICES,
        default="general_iot",
        help_text=_("UX preset for onboarding, dashboards, alerts, and reports."),
    )
    site_type = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Optional profile-specific site type, such as hotel, clinic, or warehouse."),
    )

    def __str__(self):
        return self.name


class Gateway(BaseTeamModel):
    """An edge gateway device (RPi running our forked TB Gateway)."""

    STATUS_CHOICES = (
        ("online", _("Online")),
        ("offline", _("Offline")),
        ("maintenance", _("Maintenance")),
    )
    LIFECYCLE_CHOICES = (
        ("claimed", _("Claimed")),
        ("bootstrap_seen", _("Bootstrap Seen")),
        ("activating", _("Activating")),
        ("online", _("Online")),
        ("commissioning", _("Commissioning")),
        ("active", _("Active")),
        ("release_pending", _("Release Pending")),
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
    lifecycle_status = models.CharField(max_length=20, choices=LIFECYCLE_CHOICES, default="claimed")
    last_seen = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    config = models.JSONField(default=dict, blank=True)
    capacity = models.PositiveIntegerField(default=8, help_text=_("Maximum number of devices this gateway can support"))
    discovery_data = models.JSONField(
        default=dict, blank=True, help_text=_("Most recent discovery report from the edge")
    )

    # MQTT credentials (per-gateway authentication)
    mqtt_username = models.CharField(max_length=100, unique=True, null=True, blank=True)
    mqtt_password = models.CharField(max_length=255, blank=True, help_text=_("Hashed operational MQTT password"))
    tls_mode = models.CharField(max_length=10, choices=TLS_MODE_CHOICES, default="one-way")
    client_cert_pem = models.TextField(blank=True, help_text=_("Client certificate PEM for mTLS"))
    client_key_pem = models.TextField(blank=True, help_text=_("Client private key PEM for mTLS"))
    mqtt_provisioning_status = models.CharField(max_length=20, default="not_started")
    mqtt_provisioning_error = models.TextField(blank=True)
    mqtt_provisioned_at = models.DateTimeField(null=True, blank=True)
    credential_rotation_status = models.CharField(max_length=20, default="not_started")
    last_bootstrap_seen_at = models.DateTimeField(null=True, blank=True)

    # Heartbeat / attribute sync fields (populated by edge gateway)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    uptime_seconds = models.IntegerField(null=True, blank=True)
    python_version = models.CharField(max_length=20, blank=True)
    platform_info = models.CharField(max_length=200, blank=True)
    active_connectors = models.JSONField(default=list, blank=True)
    connected_devices = models.JSONField(default=list, blank=True)
    remote_control_protocol_version = models.PositiveIntegerField(default=0)
    remote_control_local_writeback_enabled = models.BooleanField(default=False)
    remote_control_policy_loaded = models.BooleanField(default=False)

    # Network Watchdog fields
    active_interface = models.CharField(max_length=20, blank=True, default="eth0")
    failover_count = models.IntegerField(default=0)
    ethernet_status = models.CharField(max_length=20, blank=True, default="unknown")
    wifi_status = models.CharField(max_length=20, blank=True, default="unknown")
    fourg_status = models.CharField(max_length=20, blank=True, default="unknown")
    signal_strength = models.IntegerField(null=True, blank=True)
    buffered_event_count = models.IntegerField(null=True, blank=True)
    last_replay_status = models.CharField(max_length=30, blank=True, default="")
    replay_failure_count = models.IntegerField(default=0)

    # Broker / firewall diagnostics emitted by Novena Gateway
    connectivity_checked_ts = models.PositiveBigIntegerField(null=True, blank=True)
    internet_reachable = models.BooleanField(null=True, blank=True)
    default_route_ok = models.BooleanField(null=True, blank=True)
    default_route_error = models.TextField(blank=True)
    dns_ok = models.BooleanField(null=True, blank=True)
    dns_error = models.TextField(blank=True)
    broker_host = models.CharField(max_length=255, blank=True)
    broker_port = models.IntegerField(null=True, blank=True)
    broker_tcp_ok = models.BooleanField(null=True, blank=True)
    broker_tcp_error = models.TextField(blank=True)
    tls_ok = models.BooleanField(null=True, blank=True)
    tls_error = models.TextField(blank=True)
    mqtt_connected = models.BooleanField(null=True, blank=True)
    mqtt_last_error = models.TextField(blank=True)

    # Edge diagnostics for customer support
    device_health = models.JSONField(default=dict, blank=True)
    ota_status = models.CharField(max_length=30, blank=True)
    ota_version = models.CharField(max_length=50, blank=True)
    ota_error = models.TextField(blank=True)
    ota_rollback_performed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

    @property
    def freshness(self):
        from apps.devices.freshness import gateway_freshness_state

        return gateway_freshness_state(self)


class GatewayInventory(models.Model):
    """Factory registry for physical gateways before customer claim."""

    STATUS_CHOICES = (
        ("unclaimed", _("Unclaimed")),
        ("claimed", _("Claimed")),
        ("released", _("Released")),
        ("retired", _("Retired")),
    )

    serial_number = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="unclaimed")
    batch = models.CharField(max_length=100, blank=True)
    gateway = models.OneToOneField(
        Gateway, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_record"
    )
    claimed_by_team = models.ForeignKey(
        "teams.Team", null=True, blank=True, on_delete=models.SET_NULL, related_name="claimed_gateway_inventory"
    )
    manufactured_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["serial_number"]
        verbose_name_plural = "gateway inventory"

    def __str__(self):
        return f"{self.serial_number} ({self.status})"


class GatewayActivation(BaseTeamModel):
    """Durable activation attempt for first-time operational MQTT credentials."""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("delivered", _("Delivered")),
        ("acknowledged", _("Acknowledged")),
        ("expired", _("Expired")),
        ("retried", _("Retried")),
        ("failed", _("Failed")),
    )
    UNRESOLVED_STATUSES = ("pending", "delivered", "retried", "failed")

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name="activations")
    request_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    encrypted_mqtt_password = models.TextField(blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["gateway", "status"]),
            models.Index(fields=["expires_at", "status"]),
        ]

    def __str__(self):
        return f"Activation {self.request_id} -> {self.gateway.serial_number} ({self.status})"


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
    discovery_hints = models.JSONField(default=dict, blank=True)
    default_polling_interval = models.IntegerField(default=5)
    category = models.CharField(max_length=20, choices=VERTICAL_CHOICES, default="energy")
    alert_presets = models.JSONField(default=list, blank=True)
    is_verified = models.BooleanField(default=False)

    SOURCE_CHOICES = (
        ("curated", _("Curated (Novena)")),
        ("ai_generated", _("AI Generated")),
        ("user_created", _("User Created")),
    )
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="curated")
    source_url = models.URLField(blank=True, max_length=500, help_text=_("URL where the register map was found"))
    ai_confidence = models.FloatField(null=True, blank=True, help_text=_("AI confidence score 0.0-1.0"))
    created_by_team = models.ForeignKey(
        "teams.Team",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text=_("Team that originally created this template"),
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
    port = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Interface name or address (e.g., /dev/ttyUSB0, 192.168.1.100:502)",
    )
    energy_category = models.CharField(max_length=20, choices=ENERGY_CATEGORY_CHOICES, default="none")

    connection_config = models.JSONField(default=dict)
    discovery_meta = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw discovery data from Edge (interface, slave_id, baud_rate, etc.)",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="offline")
    last_telemetry_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.name} ({self.site.name})"

    @property
    def freshness(self):
        from apps.devices.freshness import device_freshness_state

        return device_freshness_state(self)

    @property
    def gateway_context_display(self):
        from apps.devices.freshness import device_gateway_context_display

        return device_gateway_context_display(self)


class GatewayConfig(BaseTeamModel):
    """Tracks config versions pushed to gateways."""

    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("success", _("Success")),
        ("failed", _("Failed")),
        ("rolled_back", _("Rolled Back")),
    )

    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name="config_history")
    config_json = models.JSONField()
    pushed_at = models.DateTimeField(auto_now_add=True)
    request_id = models.UUIDField(unique=True)
    action = models.CharField(max_length=30, default="full_update")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    error_message = models.TextField(blank=True)
    rollback_performed = models.BooleanField(default=False)
    connector_results = models.JSONField(default=list, blank=True)
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
    remote_command = models.ForeignKey(
        "RemoteCommand",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transport_attempts",
    )

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"RPC {self.method} → {self.gateway.serial_number} ({self.status})"


class DeviceCommand(BaseTeamModel):
    """A control command sent to a device (write-back)."""

    COMMAND_TYPE_CHOICES = (
        ("read", _("Read")),
        ("write", _("Write")),
    )
    STATUS_CHOICES = (
        ("pending", _("Pending")),
        ("sent", _("Sent to Gateway")),
        ("executed", _("Executed Successfully")),
        ("failed", _("Failed")),
        ("timed_out", _("Timed Out")),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="commands")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    rpc_command = models.OneToOneField(
        RpcCommand,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="device_command",
    )

    command_type = models.CharField(max_length=10, choices=COMMAND_TYPE_CHOICES, default="write")
    command_key = models.CharField(max_length=100)  # e.g., 'motor_speed'
    value = models.JSONField(null=True, blank=True)  # The value to write, if any

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)

    payload = models.JSONField(default=dict, blank=True, help_text=_("The exact payload sent to the gateway"))
    response_payload = models.JSONField(default=dict, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    executed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    remote_command = models.OneToOneField(
        "RemoteCommand",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_device_command",
    )

    def __str__(self):
        return f"CMD: {self.command_key}={self.value} on {self.device.name} ({self.status})"


class RemoteCommand(BaseTeamModel):
    """Canonical governed command intent, separate from MQTT transport attempts."""

    class Source(models.TextChoices):
        USER = "user", _("User")
        AUTOMATION = "automation", _("Automation")
        SYSTEM = "system", _("System")
        SUPPORT = "support", _("Support")

    class Risk(models.TextChoices):
        DIAGNOSTIC = "diagnostic", _("Diagnostic")
        LOW = "low", _("Low")
        HIGH = "high", _("High")
        CRITICAL = "critical", _("Critical")

    class Status(models.TextChoices):
        REQUESTED = "requested", _("Requested")
        POLICY_DENIED = "policy_denied", _("Policy denied")
        AWAITING_APPROVAL = "awaiting_approval", _("Awaiting approval")
        APPROVED = "approved", _("Approved")
        QUEUED = "queued_for_dispatch", _("Queued for dispatch")
        DISPATCHING = "dispatching", _("Dispatching")
        PUBLISH_ACCEPTED = "publish_accepted", _("Publish accepted")
        BROKER_ACKNOWLEDGED = "broker_acknowledged", _("Broker acknowledged")
        GATEWAY_RECEIVED = "gateway_received", _("Gateway received")
        EXECUTING = "executing", _("Executing")
        FIELD_PROTOCOL_ACCEPTED = "field_protocol_accepted", _("Field protocol accepted")
        VERIFICATION_PENDING = "verification_pending", _("Verification pending")
        VERIFIED = "verified", _("Verified")
        REJECTED = "rejected", _("Rejected")
        FAILED = "failed", _("Failed")
        EXPIRED = "expired", _("Expired")
        TIMED_OUT = "timed_out", _("Timed out")
        CANCELLED = "cancelled", _("Cancelled")
        OUTCOME_UNKNOWN = "outcome_unknown", _("Outcome unknown")
        RECONCILED_VERIFIED = "reconciled_verified", _("Reconciled: verified")
        RECONCILED_NOT_APPLIED = "reconciled_not_applied", _("Reconciled: not applied")
        RECONCILED_UNRESOLVED = "reconciled_unresolved", _("Reconciled: unresolved")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.ForeignKey(Gateway, on_delete=models.PROTECT, related_name="remote_commands")
    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="remote_commands",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_remote_commands",
    )
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.USER)
    operation = models.CharField(max_length=64)
    command_key = models.CharField(max_length=100, blank=True)
    requested_value = models.JSONField(null=True, blank=True)
    normalized_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True)
    risk = models.CharField(max_length=16, choices=Risk.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.REQUESTED)
    actor_snapshot = models.JSONField(default=dict, blank=True)
    policy_snapshot = models.JSONField(default=dict, blank=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    control_epoch = models.PositiveBigIntegerField(default=1)
    sequence_number = models.PositiveBigIntegerField(default=0)
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField()
    broker_acknowledged_at = models.DateTimeField(null=True, blank=True)
    gateway_received_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "status", "created_at"]),
            models.Index(fields=["gateway", "status"]),
            models.Index(fields=["device", "status"]),
        ]

    def __str__(self):
        target = self.device.name if self.device_id else self.gateway.serial_number
        return f"{self.operation} -> {target} ({self.status})"


class CommandEvent(models.Model):
    """Append-only evidence for a governed command lifecycle transition."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    command = models.ForeignKey(RemoteCommand, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=80)
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    actor_snapshot = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    checksum = models.CharField(max_length=64, blank=True)
    happened_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["happened_at", "id"]
        indexes = [models.Index(fields=["command", "happened_at"])]


class CommandOutbox(models.Model):
    """Transactional dispatch intent claimed by a dedicated MQTT dispatcher."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        CLAIMED = "claimed", _("Claimed")
        PUBLISHED = "published", _("Published")
        FAILED = "failed", _("Failed")
        CANCELLED = "cancelled", _("Cancelled")

    command = models.OneToOneField(RemoteCommand, on_delete=models.CASCADE, related_name="outbox")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now)
    claimed_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "available_at"])]


class FirmwareRelease(models.Model):
    """Firmware binaries uploaded by administrators for OTA updates."""

    CHANNEL_CHOICES = (
        ("stable", _("Stable")),
        ("pilot", _("Pilot")),
        ("canary", _("Canary")),
    )
    SIGNING_STATUS_CHOICES = (
        ("unsigned", _("Unsigned")),
        ("signed", _("Signed")),
        ("failed", _("Failed")),
    )

    version = models.CharField(max_length=50, unique=True, help_text=_("Version string, e.g. '1.1.0'"))
    release_notes = models.TextField(blank=True)
    file = models.FileField(upload_to="firmware/", help_text=_("The firmware binary tarball (.tar.gz)"))
    sha256 = models.CharField(max_length=64, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default="stable")
    minimum_gateway_version = models.CharField(max_length=50, blank=True, default="0.1.0")
    maximum_gateway_version = models.CharField(max_length=50, blank=True)
    manifest = models.JSONField(default=dict, blank=True)
    signature = models.TextField(blank=True)
    key_id = models.CharField(max_length=80, blank=True)
    signing_status = models.CharField(max_length=20, choices=SIGNING_STATUS_CHOICES, default="unsigned")
    signed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False, help_text=_("Whether this release is available to gateways"))
    released_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-released_at"]

    @property
    def is_signed(self):
        return self.signing_status == "signed" and bool(self.manifest and self.signature and self.key_id)

    def __str__(self):
        return f"Firmware v{self.version} ({'Active' if self.is_active else 'Draft'})"


@receiver(post_save, sender=Device)
def auto_generate_dashboard_on_template_match(sender, instance, **kwargs):
    if instance.template:
        try:
            from apps.dashboard.services import generate_default_dashboard

            generate_default_dashboard(instance)
        except Exception as e:
            logger = logging.getLogger("novena_hub")
            logger.error("Failed to auto-generate dashboard for device %s: %s", instance.name, e)
