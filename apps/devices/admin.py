from django.contrib import admin

from .models import Device, DeviceTemplate, Gateway, GatewayConfig, RpcCommand, Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "timezone")
    list_filter = ("team",)
    search_fields = ("name",)


@admin.register(Gateway)
class GatewayAdmin(admin.ModelAdmin):
    list_display = ("name", "serial_number", "site", "status", "last_seen", "tls_mode")
    list_filter = ("status", "tls_mode", "site__team")
    search_fields = ("name", "serial_number", "mqtt_username")
    readonly_fields = ("access_token", "mqtt_username", "mqtt_password")
    actions = ["recover_claim_codes"]
    fieldsets = (
        (None, {"fields": ("team", "site", "name", "serial_number", "status", "firmware_version", "capacity")}),
        ("MQTT Credentials", {"fields": ("access_token", "mqtt_username", "mqtt_password", "tls_mode")}),
        ("Heartbeat Attributes", {"fields": ("last_seen", "ip_address", "uptime_seconds", "python_version", "platform_info", "active_connectors", "connected_devices")}),
        ("Advanced", {"fields": ("config", "discovery_data", "client_cert_pem", "client_key_pem"), "classes": ("collapse",)}),
    )

    @admin.action(description="Recover claim codes for selected gateways")
    def recover_claim_codes(self, request, queryset):
        from django.contrib import messages

        from .services import compute_claim_code

        for gw in queryset:
            code = compute_claim_code(gw.serial_number)
            messages.info(request, f"Gateway {gw.serial_number} → Claim Code: {code}")


@admin.register(DeviceTemplate)
class DeviceTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "manufacturer", "device_type", "protocol", "category", "is_verified")
    list_filter = ("device_type", "protocol", "category", "is_verified")
    search_fields = ("name", "manufacturer", "model_number")


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


@admin.register(RpcCommand)
class RpcCommandAdmin(admin.ModelAdmin):
    list_display = ("gateway", "method", "status", "sent_at", "responded_at")
    list_filter = ("status", "method")
    search_fields = ("gateway__serial_number", "request_id")
    readonly_fields = ("request_id", "sent_at")
