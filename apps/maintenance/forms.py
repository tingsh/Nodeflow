from django import forms
from django.core.validators import FileExtensionValidator

from .models import MaintenanceTicket, PreventiveSchedule, SharedTicketLink, TicketComment, TicketTemplate


class MaintenanceTicketForm(forms.ModelForm):
    template = forms.ModelChoiceField(
        queryset=TicketTemplate.objects.none(),
        required=False,
        label="Checklist Template",
        help_text="Optionally load standard checklist tasks.",
    )

    class Meta:
        model = MaintenanceTicket
        fields = [
            "device",
            "template",
            "title",
            "description",
            "priority",
            "status",
            "assigned_to",
            "due_date",
            "send_email_notification",
            "send_whatsapp_notification",
        ]
        widgets = {
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        send_email = cleaned_data.get("send_email_notification")
        send_whatsapp = cleaned_data.get("send_whatsapp_notification")

        if not send_email and not send_whatsapp:
            raise forms.ValidationError("You must select at least one notification channel (Email or WhatsApp).")
        return cleaned_data

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
                checklist_state.append(
                    {"task": item.get("task", ""), "required": item.get("required", False), "done": False}
                )
            instance.checklist_state = checklist_state
        if commit:
            instance.save()
        return instance


class TicketCommentForm(forms.ModelForm):
    attachment = forms.FileField(
        required=False,
        validators=[FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png", "pdf"])],
        widget=forms.FileInput(
            attrs={
                "accept": ".jpg,.jpeg,.png,.pdf",
                "class": "file-input file-input-bordered file-input-primary w-full",
            }
        ),
        help_text="Optional document or photo (JPG, PNG, PDF up to 10MB)",
    )

    class Meta:
        model = TicketComment
        fields = ["content", "attachment", "guest_name"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Add a comment, upload certificates or signed checksheets...",
                    "class": "textarea textarea-bordered textarea-primary w-full bg-gray-900 text-white",
                }
            ),
            "guest_name": forms.TextInput(
                attrs={
                    "placeholder": "Enter your name (Required for guests)",
                    "class": "input input-bordered input-primary w-full bg-gray-900 text-white",
                }
            ),
        }

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment and attachment.size > 10 * 1024 * 1024:  # 10MB limit
            raise forms.ValidationError("Files must be under 10MB.")
        return attachment


class TicketTemplateForm(forms.ModelForm):
    class Meta:
        model = TicketTemplate
        fields = ["name", "description", "estimated_duration_minutes"]


class PreventiveScheduleForm(forms.ModelForm):
    class Meta:
        model = PreventiveSchedule
        fields = [
            "device",
            "template",
            "title",
            "interval",
            "next_due_at",
            "is_active",
            "is_usage_based",
            "usage_telemetry_key",
            "usage_threshold",
            "assigned_to",
            "send_email_notification",
            "send_whatsapp_notification",
        ]
        widgets = {
            "next_due_at": forms.DateInput(
                attrs={"type": "date", "class": "input input-bordered w-full bg-white dark:bg-gray-900"}
            ),
        }
        labels = {
            "next_due_at": "Next Due Date",
        }

    def __init__(self, *args, **kwargs):
        team = kwargs.pop("team", None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields["device"].queryset = self.fields["device"].queryset.filter(team=team)
            self.fields["template"].queryset = self.fields["template"].queryset.filter(team=team)
            # Filter assigned_to to only team members
            from apps.users.models import CustomUser

            self.fields["assigned_to"].queryset = CustomUser.objects.filter(membership__team=team)

    def clean(self):
        cleaned_data = super().clean()
        assigned_to = cleaned_data.get("assigned_to")
        send_email = cleaned_data.get("send_email_notification")
        send_whatsapp = cleaned_data.get("send_whatsapp_notification")

        if assigned_to and not send_email and not send_whatsapp:
            raise forms.ValidationError(
                "You must select at least one notification channel (Email or WhatsApp) if assigning a user."
            )
        return cleaned_data


class SharedTicketLinkForm(forms.ModelForm):
    class Meta:
        model = SharedTicketLink
        fields = ["expires_at", "auto_revoke_on_resolve"]
        widgets = {
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
