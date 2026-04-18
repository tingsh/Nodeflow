from django import forms
from django.forms import inlineformset_factory

from .models import Automation, AutomationAction, AutomationCondition


class AutomationForm(forms.ModelForm):
    class Meta:
        model = Automation
        fields = ["name", "description", "is_active", "trigger_logic", "cooldown_minutes"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 2}),
        }


class AutomationConditionForm(forms.ModelForm):
    class Meta:
        model = AutomationCondition
        fields = ["device", "telemetry_key", "operator", "threshold", "duration_seconds"]

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields["device"].queryset = self.fields["device"].queryset.filter(team=team)


class AutomationActionForm(forms.ModelForm):
    class Meta:
        model = AutomationAction
        fields = [
            "action_type",
            "target_device",
            "command_key",
            "command_payload",
            "notify_emails",
            "webhook_url",
            "webhook_headers",
        ]

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields["target_device"].queryset = self.fields["target_device"].queryset.filter(team=team)


# Formsets for the builder UI
ConditionFormSet = inlineformset_factory(
    Automation, AutomationCondition, form=AutomationConditionForm, extra=1, can_delete=True
)

ActionFormSet = inlineformset_factory(Automation, AutomationAction, form=AutomationActionForm, extra=1, can_delete=True)
