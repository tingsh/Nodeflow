from django import forms
from django.core.exceptions import ValidationError

from apps.devices.models import Device, Site
from apps.maintenance.models import TicketTemplate
from apps.users.models import CustomUser

from .models import AlertRule


class AlertRuleForm(forms.ModelForm):
    class Meta:
        model = AlertRule
        fields = [
            "name",
            "device",
            "site",
            "telemetry_key",
            "condition",
            "threshold",
            "severity",
            "is_active",
            "notify_email",
            "notify_whatsapp",
            "notify_webhook",
            "cooldown_minutes",
            "duration_seconds",
            "recipients",
            "create_maintenance_ticket",
            "maintenance_template",
        ]

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields["device"].queryset = Device.objects.filter(team=team)
            self.fields["site"].queryset = Site.objects.filter(team=team)
            self.fields["maintenance_template"].queryset = TicketTemplate.objects.filter(team=team)
            self.fields["recipients"].queryset = CustomUser.objects.filter(membership__team=team)

    def clean(self):
        cleaned_data = super().clean()
        notify_email = cleaned_data.get("notify_email")
        notify_whatsapp = cleaned_data.get("notify_whatsapp")
        recipients = cleaned_data.get("recipients")
        if (notify_email or notify_whatsapp) and not recipients:
            raise ValidationError({"recipients": "Select at least one recipient when notifications are enabled."})
        return cleaned_data
