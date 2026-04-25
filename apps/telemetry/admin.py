from django.contrib import admin

from .models import GatewayLog, TelemetryData


@admin.register(TelemetryData)
class TelemetryDataAdmin(admin.ModelAdmin):
    list_display = ("device", "key", "timestamp", "value_numeric", "value_string", "value_bool")
    list_filter = ("key", "device__site__team")
    search_fields = ("key", "device__name")
    date_hierarchy = "timestamp"


@admin.register(GatewayLog)
class GatewayLogAdmin(admin.ModelAdmin):
    list_display = ("gateway", "level", "logger_name", "timestamp", "message")
    list_filter = ("level", "gateway__serial_number")
    search_fields = ("message", "logger_name", "gateway__serial_number")
    date_hierarchy = "timestamp"
