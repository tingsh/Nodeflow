from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.teams.models import BaseTeamModel

class AlertRule(BaseTeamModel):
    """User-defined alert rule."""
    CONDITION_CHOICES = (
        ('gt', _('Greater Than (> )')),
        ('lt', _('Less Than (< )')),
        ('gte', _('Greater Than or Equal (>= )')),
        ('lte', _('Less Than or Equal (<= )')),
        ('eq', _('Equal (== )')),
        ('neq', _('Not Equal (!= )')),
    )
    SEVERITY_CHOICES = (
        ('info', _('Info')),
        ('warning', _('Warning')),
        ('critical', _('Critical')),
    )

    name = models.CharField(max_length=200)
    device = models.ForeignKey('devices.Device', on_delete=models.CASCADE, related_name='alert_rules', null=True, blank=True)
    site = models.ForeignKey('devices.Site', on_delete=models.CASCADE, related_name='alert_rules', null=True, blank=True)
    
    telemetry_key = models.CharField(max_length=100, help_text=_("The key to monitor (e.g., 'temperature')"))
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    threshold = models.FloatField()
    
    duration_seconds = models.IntegerField(default=0, help_text=_("How long the condition must persist before triggering an alert"))
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')
    
    is_active = models.BooleanField(default=True)
    notify_email = models.BooleanField(default=True)
    notify_webhook = models.URLField(blank=True)
    cooldown_minutes = models.IntegerField(default=15, help_text=_("Minutes to wait before re-triggering notifications for the same alert"))

    def __str__(self):
        return f"{self.name} ({self.device.name if self.device else 'Site: ' + self.site.name})"

class Alert(BaseTeamModel):
    """A triggered alert instance."""
    STATUS_CHOICES = (
        ('active', _('Active')),
        ('acknowledged', _('Acknowledged')),
        ('resolved', _('Resolved')),
    )
    
    rule = models.ForeignKey(AlertRule, on_delete=models.CASCADE, related_name='alerts')
    device = models.ForeignKey('devices.Device', on_delete=models.CASCADE, related_name='alerts')
    
    triggered_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    
    trigger_value = models.FloatField()  # The value that triggered the alert
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.rule.name} on {self.device.name} @ {self.triggered_at}"
