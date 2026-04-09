from django.contrib import admin
from .models import TelemetryData

@admin.register(TelemetryData)
class TelemetryDataAdmin(admin.ModelAdmin):
    list_display = ('device', 'key', 'timestamp', 'value_numeric', 'value_string', 'value_bool')
    list_filter = ('key', 'device__site__team')
    search_fields = ('key', 'device__name')
    date_hierarchy = 'timestamp'
