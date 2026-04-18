from django import forms


class DateRangeForm(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))


from .models import SharedDashboard


class SharedDashboardForm(forms.ModelForm):
    raw_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Leave blank for no password. If set, users will need this password to view the dashboard.",
    )

    class Meta:
        model = SharedDashboard
        fields = ["name", "is_active", "expires_at"]
        widgets = {
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_pw = self.cleaned_data.get("raw_password")
        if raw_pw:
            instance.set_password(raw_pw)
        elif "raw_password" in self.changed_data:
            # If they cleared the field, remove password
            instance.set_password(None)

        if commit:
            instance.save()
        return instance
