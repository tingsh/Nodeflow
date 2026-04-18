from django.contrib import admin

from .models import Device, DeviceTemplate, Gateway, Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "timezone")
    list_filter = ("team",)
    search_fields = ("name",)


@admin.register(Gateway)
class GatewayAdmin(admin.ModelAdmin):
    list_display = ("name", "serial_number", "site", "status", "last_seen")
    list_filter = ("status", "site__team")
    search_fields = ("name", "serial_number")
    readonly_fields = ("access_token",)


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
