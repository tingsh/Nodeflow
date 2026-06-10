from django import forms

from .models import MaintenanceTicket, PreventiveSchedule, TicketComment, TicketTemplate


class MaintenanceTicketForm(forms.ModelForm):
    template = forms.ModelChoiceField(
        queryset=TicketTemplate.objects.none(),
        required=False,
        label="Checklist Template",
        help_text="Optionally load standard checklist tasks."
    )

    class Meta:
        model = MaintenanceTicket
        fields = ["device", "template", "title", "description", "priority", "status", "assigned_to", "due_date"]
        widgets = {
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields["device"].queryset = self.fields["device"].queryset.filter(team=team)
            self.fields["template"].queryset = TicketTemplate.objects.filter(team=team)
            # Filter assigned_to to only team members
            from apps.users.models import CustomUser

            team_users = CustomUser.objects.filter(membership__team=team)
            self.fields["assigned_to"].queryset = team_users

    def save(self, commit=True):
        instance = super().save(commit=False)
        template = self.cleaned_data.get("template")
        if template and not instance.checklist_state:
            checklist_state = []
            for item in template.checklist:
                checklist_state.append({
                    "task": item.get("task", ""),
                    "required": item.get("required", False),
                    "done": False
                })
            instance.checklist_state = checklist_state
        if commit:
            instance.save()
        return instance


class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 2, "placeholder": "Add a comment or update..."}),
        }


class TicketTemplateForm(forms.ModelForm):
    class Meta:
        model = TicketTemplate
        fields = ["name", "description", "estimated_duration_minutes"]


class PreventiveScheduleForm(forms.ModelForm):
    class Meta:
        model = PreventiveSchedule
        fields = [
            "device", "template", "title", "interval", "next_due_at", 
            "is_active", "is_usage_based", "usage_telemetry_key", "usage_threshold"
        ]
        widgets = {
            "next_due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields["device"].queryset = self.fields["device"].queryset.filter(team=team)
            self.fields["template"].queryset = self.fields["template"].queryset.filter(team=team)
