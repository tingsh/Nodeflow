from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.devices.models import Device
from apps.teams.models import BaseTeamModel
from apps.users.models import CustomUser


class TicketTemplate(BaseTeamModel):
    """Pre-built templates with standardized checklists for common procedures."""

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(default=60)
    checklist = models.JSONField(
        default=list, help_text=_("List of checklist items like {'task': 'Check oil', 'required': True}")
    )

    def __str__(self):
        return f"{self.name} ({self.team.name})"


class PreventiveSchedule(BaseTeamModel):
    """Configuration for recurring preventive maintenance."""

    class IntervalChoices(models.TextChoices):
        DAILY = "daily", _("Daily")
        WEEKLY = "weekly", _("Weekly")
        MONTHLY = "monthly", _("Monthly")
        QUARTERLY = "quarterly", _("Quarterly")
        YEARLY = "yearly", _("Yearly")

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="maintenance_schedules")
    template = models.ForeignKey(TicketTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=200)
    interval = models.CharField(max_length=20, choices=IntervalChoices.choices, default=IntervalChoices.MONTHLY, null=True, blank=True)
    next_due_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    # Usage-based PM settings
    is_usage_based = models.BooleanField(default=False)
    usage_telemetry_key = models.CharField(max_length=100, default="run_hours", blank=True)
    usage_threshold = models.FloatField(default=0.0, blank=True, null=True)
    last_trigger_usage_value = models.FloatField(default=0.0, blank=True, null=True)

    def __str__(self):
        return f"PM: {self.title} on {self.device.name}"


class MaintenanceTicket(BaseTeamModel):
    """The core ticket model representing a reactive or scheduled maintenance job."""

    class PriorityChoices(models.TextChoices):
        LOW = "low", _("Low")
        MEDIUM = "medium", _("Medium")
        HIGH = "high", _("High")
        CRITICAL = "critical", _("Critical")

    class StatusChoices(models.TextChoices):
        OPEN = "open", _("Open")
        IN_PROGRESS = "in_progress", _("In Progress")
        WAITING = "waiting", _("Waiting on Parts/Vendor")
        RESOLVED = "resolved", _("Resolved (Pending Verification)")
        CLOSED = "closed", _("Closed")

    class TypeChoices(models.TextChoices):
        REACTIVE = "reactive", _("Reactive (Alert/Breakdown)")
        PREVENTIVE = "preventive", _("Preventive (Scheduled)")

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="tickets")
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    ticket_type = models.CharField(max_length=50, choices=TypeChoices.choices, default=TypeChoices.REACTIVE)
    priority = models.CharField(max_length=20, choices=PriorityChoices.choices, default=PriorityChoices.MEDIUM)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.OPEN)

    assigned_to = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_tickets"
    )
    reported_by = models.ForeignKey(
        CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="reported_tickets"
    )

    # Traceability
    alert_reference = models.CharField(
        max_length=100, blank=True, help_text=_("UUID of the alert that triggered this ticket, if any")
    )
    schedule_reference = models.ForeignKey(PreventiveSchedule, on_delete=models.SET_NULL, null=True, blank=True)

    # Process tracking
    due_date = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    downtime_minutes = models.PositiveIntegerField(default=0)

    # Template instances mapping
    checklist_state = models.JSONField(
        default=list, help_text=_("Instance copy of the template checklist with completion states")
    )

    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"TKT-{self.id}: {self.title}"

    def save(self, *args, **kwargs):
        if self.status in [self.StatusChoices.CLOSED, self.StatusChoices.RESOLVED] and not self.closed_at:
            self.closed_at = timezone.now()
        super().save(*args, **kwargs)


class TicketComment(BaseTeamModel):
    """Threaded notes, updates, and attachments appended to a ticket."""

    ticket = models.ForeignKey(MaintenanceTicket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    is_system_generated = models.BooleanField(default=False)

    def __str__(self):
        return f"Comment by {self.author} on {self.ticket}"
