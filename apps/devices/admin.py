from django.contrib import admin

from .models import (
    DeploymentSetupEvent,
    DeploymentSetupItem,
    DeploymentSetupRun,
    Device,
    DeviceTemplate,
    EquipmentTemplateRequest,
    FirmwareRelease,
    Gateway,
    GatewayActivation,
    GatewayConfig,
    GatewayConfigOutbox,
    GatewayInventory,
    RpcCommand,
    Site,
)


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "timezone")
    list_filter = ("team",)
    search_fields = ("name",)


@admin.register(Gateway)
class GatewayAdmin(admin.ModelAdmin):
    list_display = ("name", "serial_number", "site", "status", "lifecycle_status", "last_seen", "tls_mode")
    list_filter = ("status", "lifecycle_status", "tls_mode", "site__team")
    search_fields = ("name", "serial_number", "mqtt_username")
    readonly_fields = ("access_token", "mqtt_username", "mqtt_password")
    actions = ["recover_claim_codes"]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "team",
                    "site",
                    "name",
                    "serial_number",
                    "status",
                    "lifecycle_status",
                    "firmware_version",
                    "capacity",
                )
            },
        ),
        ("MQTT Credentials", {"fields": ("access_token", "mqtt_username", "mqtt_password", "tls_mode")}),
        (
            "Heartbeat Attributes",
            {
                "fields": (
                    "last_seen",
                    "ip_address",
                    "uptime_seconds",
                    "python_version",
                    "platform_info",
                    "active_connectors",
                    "connected_devices",
                )
            },
        ),
        (
            "Advanced",
            {
                "fields": ("config", "discovery_data", "client_cert_pem", "client_key_pem"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.action(description="Recover claim codes for selected gateways")
    def recover_claim_codes(self, request, queryset):
        from django.contrib import messages

        from .services import compute_claim_code

        for gw in queryset:
            code = compute_claim_code(gw.serial_number)
            messages.info(request, f"Gateway {gw.serial_number} → Claim Code: {code}")


@admin.register(GatewayInventory)
class GatewayInventoryAdmin(admin.ModelAdmin):
    list_display = ("serial_number", "status", "batch", "claimed_by_team", "gateway", "claimed_at")
    list_filter = ("status", "batch")
    search_fields = ("serial_number", "batch", "claimed_by_team__name")
    readonly_fields = ("manufactured_at", "claimed_at", "gateway", "claimed_by_team")

    actions = ["recover_claim_codes"]

    @admin.action(description="Recover claim codes for selected inventory records")
    def recover_claim_codes(self, request, queryset):
        from django.contrib import messages

        from .services import compute_claim_code

        for item in queryset:
            code = compute_claim_code(item.serial_number)
            messages.info(request, f"Gateway {item.serial_number} -> Claim Code: {code}")


@admin.register(DeviceTemplate)
class DeviceTemplateAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "manufacturer",
        "device_type",
        "protocol",
        "category",
        "is_verified",
        "source",
        "ai_confidence",
        "usage_count",
        "created_at",
    )
    list_filter = ("device_type", "protocol", "category", "is_verified", "source")
    search_fields = ("name", "manufacturer", "model_number")
    readonly_fields = ("usage_count", "created_at")


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "device_type", "energy_category", "site", "status", "last_telemetry_at")
    list_filter = ("device_type", "energy_category", "status", "site__team")
    search_fields = ("name",)


@admin.register(GatewayConfig)
class GatewayConfigAdmin(admin.ModelAdmin):
    list_display = ("gateway", "action", "status", "pushed_at", "acknowledged_at")
    list_filter = ("status", "action")
    search_fields = ("gateway__serial_number", "request_id")
    readonly_fields = ("request_id", "pushed_at")


@admin.register(GatewayConfigOutbox)
class GatewayConfigOutboxAdmin(admin.ModelAdmin):
    list_display = ("config", "status", "attempt_count", "next_attempt_at", "delivered_at")
    list_filter = ("status",)
    readonly_fields = ("config", "attempt_count", "claimed_at", "delivered_at", "dead_lettered_at")


@admin.register(DeploymentSetupRun)
class DeploymentSetupRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "team", "site", "gateway", "state", "current_step", "created_at")
    list_filter = ("state", "team")
    readonly_fields = ("run_id", "created_at", "updated_at")


@admin.register(DeploymentSetupItem)
class DeploymentSetupItemAdmin(admin.ModelAdmin):
    list_display = ("run", "device", "selected_template", "confidence_score", "trust_level", "state")
    list_filter = ("state", "trust_level")


@admin.register(DeploymentSetupEvent)
class DeploymentSetupEventAdmin(admin.ModelAdmin):
    list_display = ("run", "sequence_number", "event_type", "message", "created_at")
    readonly_fields = ("run", "item", "sequence_number", "event_type", "message", "evidence", "actor", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EquipmentTemplateRequest)
class EquipmentTemplateRequestAdmin(admin.ModelAdmin):
    list_display = ("support_reference", "team", "manufacturer", "model_number", "protocol", "status")
    list_filter = ("status", "protocol")
    search_fields = ("support_reference", "manufacturer", "model_number", "team__name")


@admin.register(GatewayActivation)
class GatewayActivationAdmin(admin.ModelAdmin):
    list_display = ("gateway", "status", "attempt_count", "expires_at", "delivered_at", "acknowledged_at")
    list_filter = ("status", "gateway__team")
    search_fields = ("gateway__serial_number", "request_id")
    readonly_fields = (
        "request_id",
        "status",
        "attempt_count",
        "last_attempt_at",
        "delivered_at",
        "acknowledged_at",
        "expires_at",
        "encrypted_mqtt_password",
        "last_error",
    )


@admin.register(RpcCommand)
class RpcCommandAdmin(admin.ModelAdmin):
    list_display = ("gateway", "method", "status", "sent_at", "responded_at")
    list_filter = ("status", "method")
    search_fields = ("gateway__serial_number", "request_id")
    readonly_fields = ("request_id", "sent_at")


@admin.register(FirmwareRelease)
class FirmwareReleaseAdmin(admin.ModelAdmin):
    list_display = ("version", "channel", "signing_status", "key_id", "is_active", "released_at")
    list_filter = ("is_active", "channel", "signing_status")
    search_fields = ("version", "release_notes")
    readonly_fields = (
        "sha256",
        "size_bytes",
        "manifest",
        "signature",
        "key_id",
        "signing_status",
        "signed_at",
        "expires_at",
        "released_at",
    )
