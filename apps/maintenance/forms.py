from django import forms
from .models import MaintenanceTicket, TicketComment, TicketTemplate, PreventiveSchedule

class MaintenanceTicketForm(forms.ModelForm):
    class Meta:
        model = MaintenanceTicket
        fields = ['device', 'title', 'description', 'priority', 'status', 'assigned_to', 'due_date']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        team = kwargs.pop('team', None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields['device'].queryset = self.fields['device'].queryset.filter(team=team)
            # Filter assigned_to to only team members
            from apps.users.models import CustomUser
            team_users = CustomUser.objects.filter(membership__team=team)
            self.fields['assigned_to'].queryset = team_users

class TicketCommentForm(forms.ModelForm):
    class Meta:
        model = TicketComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Add a comment or update...'}),
        }
        
class TicketTemplateForm(forms.ModelForm):
    class Meta:
        model = TicketTemplate
        fields = ['name', 'description', 'estimated_duration_minutes']

class PreventiveScheduleForm(forms.ModelForm):
    class Meta:
        model = PreventiveSchedule
        fields = ['device', 'template', 'title', 'interval', 'next_due_at', 'is_active']
        widgets = {
            'next_due_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        team = kwargs.pop('team', None)
        super().__init__(*args, **kwargs)
        if team:
            self.fields['device'].queryset = self.fields['device'].queryset.filter(team=team)
            self.fields['template'].queryset = self.fields['template'].queryset.filter(team=team)
