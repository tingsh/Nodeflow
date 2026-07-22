from django.contrib import admin

from .models import ActivityLog, EmailDelivery


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("category", "team", "message", "timestamp")
    list_filter = ("category", "team")
    search_fields = ("message",)
    date_hierarchy = "timestamp"


@admin.register(EmailDelivery)
class EmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "recipient", "team", "status", "attempt_count", "created_at", "delivered_at")
    list_filter = ("notification_type", "status", "team")
    search_fields = ("recipient", "provider_message_id", "last_error")
    readonly_fields = (
        "created_at",
        "updated_at",
        "provider_message_id",
        "attempt_count",
        "last_error",
        "last_event_id",
        "metadata",
        "delivered_at",
    )
    date_hierarchy = "created_at"
