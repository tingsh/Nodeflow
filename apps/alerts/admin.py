from django.contrib import admin
from .models import AlertRule, Alert

@admin.register(AlertRule)
class AlertRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'device', 'site', 'telemetry_key', 'condition', 'threshold', 'severity', 'is_active')
    list_filter = ('severity', 'is_active', 'team')
    search_fields = ('name', 'telemetry_key')

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('rule', 'device', 'triggered_at', 'status', 'trigger_value')
    list_filter = ('status', 'rule__severity', 'device__site__team')
    search_fields = ('rule__name', 'device__name')
    date_hierarchy = 'triggered_at'
