from datetime import time
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.teams.models import Membership

from .models import ImpactDataSource, ImpactOpportunity, SiteImpactProfile
from .services import create_assumption_revision, ensure_business_profile

WEEKDAY_CHOICES = (
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
)


class ImpactSettingsForm(forms.Form):
    currency = forms.CharField(max_length=3, initial="SGD")
    operating_days = forms.MultipleChoiceField(
        choices=WEEKDAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    operating_start = forms.TimeField(initial=time(8, 0), widget=forms.TimeInput(attrs={"type": "time"}))
    operating_end = forms.TimeField(initial=time(18, 0), widget=forms.TimeInput(attrs={"type": "time"}))
    one_time_investment = forms.DecimalField(min_value=0, decimal_places=2, required=False)
    amortization_months = forms.IntegerField(min_value=1, max_value=120, initial=24)
    recurring_monthly_cost = forms.DecimalField(min_value=0, decimal_places=2, required=False)
    use_subscription_cost = forms.BooleanField(required=False, initial=True)
    tariff_per_kwh = forms.DecimalField(min_value=0, decimal_places=5, required=False)
    expected_after_hours_base_kw = forms.DecimalField(min_value=0, decimal_places=4, required=False)
    abnormal_tolerance_pct = forms.DecimalField(min_value=0, max_value=100, decimal_places=2, initial=15)
    downtime_cost_per_hour = forms.DecimalField(min_value=0, decimal_places=2, required=False)
    labor_cost_per_hour = forms.DecimalField(min_value=0, decimal_places=2, required=False)
    cold_min_temperature = forms.DecimalField(decimal_places=3, required=False)
    cold_max_temperature = forms.DecimalField(decimal_places=3, required=False)
    excursion_delay_minutes = forms.IntegerField(min_value=0, max_value=1440, initial=5)
    cold_loss_per_critical_excursion = forms.DecimalField(min_value=0, decimal_places=2, required=False)
    cold_critical_duration_minutes = forms.IntegerField(min_value=1, max_value=10080, required=False)
    baseline_strategy = forms.ChoiceField(choices=SiteImpactProfile.BaselineStrategy.choices)
    supplied_monthly_energy_kwh = forms.DecimalField(min_value=0, decimal_places=3, required=False)
    supplied_monthly_downtime_minutes = forms.IntegerField(min_value=0, required=False)
    supplied_monthly_labor_minutes = forms.IntegerField(min_value=0, required=False)
    email_reports = forms.BooleanField(required=False)
    report_recipients = forms.CharField(
        required=False,
        help_text="Comma-separated email addresses. Monthly email remains off until enabled.",
    )

    def __init__(
        self,
        *args,
        site_profile,
        user=None,
        can_manage_reports=False,
        **kwargs,
    ):
        self.site_profile = site_profile
        self.user = user
        self.can_manage_reports = can_manage_reports
        business = ensure_business_profile(site_profile.team)
        latest = site_profile.assumption_revisions.order_by("-revision").first()
        schedule = site_profile.operating_schedule or {}
        operating_days = [day for day, windows in schedule.items() if windows]
        first_window = next((windows[0] for windows in schedule.values() if windows), ["08:00", "18:00"])
        supplied = site_profile.supplied_baseline or {}
        initial = {
            "currency": business.currency,
            "operating_days": operating_days,
            "operating_start": first_window[0],
            "operating_end": first_window[1],
            "one_time_investment": business.one_time_investment,
            "amortization_months": business.amortization_months,
            "recurring_monthly_cost": business.recurring_monthly_cost,
            "use_subscription_cost": business.use_subscription_cost,
            "baseline_strategy": site_profile.baseline_strategy,
            "supplied_monthly_energy_kwh": supplied.get("monthly_energy_kwh"),
            "supplied_monthly_downtime_minutes": supplied.get("monthly_downtime_minutes"),
            "supplied_monthly_labor_minutes": supplied.get("monthly_labor_minutes"),
            "email_reports": business.email_reports,
            "report_recipients": ", ".join(business.report_recipients),
        }
        if latest:
            for field_name in (
                "tariff_per_kwh",
                "expected_after_hours_base_kw",
                "abnormal_tolerance_pct",
                "downtime_cost_per_hour",
                "labor_cost_per_hour",
                "cold_min_temperature",
                "cold_max_temperature",
                "excursion_delay_minutes",
                "cold_loss_per_critical_excursion",
                "cold_critical_duration_minutes",
            ):
                initial[field_name] = getattr(latest, field_name)
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)
        if not can_manage_reports:
            self.fields["email_reports"].disabled = True
            self.fields["report_recipients"].disabled = True

    def clean_currency(self):
        currency = self.cleaned_data["currency"].strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValidationError("Enter a three-letter ISO currency code.")
        return currency

    def clean_report_recipients(self):
        raw = self.cleaned_data.get("report_recipients", "")
        emails = [email.strip().lower() for email in raw.split(",") if email.strip()]
        for email in emails:
            validate_email(email)
        return ", ".join(dict.fromkeys(emails))

    def clean(self):
        cleaned = super().clean()
        minimum = cleaned.get("cold_min_temperature")
        maximum = cleaned.get("cold_max_temperature")
        if minimum is not None and maximum is not None and minimum >= maximum:
            self.add_error("cold_max_temperature", "Maximum temperature must be above the minimum.")
        strategy = cleaned.get("baseline_strategy")
        supplied_values = [
            cleaned.get("supplied_monthly_energy_kwh"),
            cleaned.get("supplied_monthly_downtime_minutes"),
            cleaned.get("supplied_monthly_labor_minutes"),
        ]
        if strategy == SiteImpactProfile.BaselineStrategy.SUPPLIED and not any(
            value is not None for value in supplied_values
        ):
            self.add_error("baseline_strategy", "Enter at least one supplied monthly baseline.")
        return cleaned

    def save(self):
        values = self.cleaned_data
        business = ensure_business_profile(self.site_profile.team)
        business.currency = values["currency"]
        business.one_time_investment = values.get("one_time_investment") or Decimal("0")
        business.amortization_months = values["amortization_months"]
        business.recurring_monthly_cost = values.get("recurring_monthly_cost") or Decimal("0")
        business.use_subscription_cost = values.get("use_subscription_cost", False)
        if self.can_manage_reports:
            business.email_reports = values.get("email_reports", False)
            business.report_recipients = [
                email.strip().lower() for email in values.get("report_recipients", "").split(",") if email.strip()
            ]
        business.full_clean()
        business.save()

        start = values["operating_start"].strftime("%H:%M")
        end = values["operating_end"].strftime("%H:%M")
        selected_days = set(values.get("operating_days") or [])
        self.site_profile.operating_schedule = {
            day: [[start, end]] if day in selected_days else [] for day, _label in WEEKDAY_CHOICES
        }
        self.site_profile.baseline_strategy = values["baseline_strategy"]
        self.site_profile.supplied_baseline = {
            key: value
            for key, value in {
                "monthly_energy_kwh": values.get("supplied_monthly_energy_kwh"),
                "monthly_downtime_minutes": values.get("supplied_monthly_downtime_minutes"),
                "monthly_labor_minutes": values.get("supplied_monthly_labor_minutes"),
            }.items()
            if value is not None
        }
        self.site_profile.save(
            update_fields=["operating_schedule", "baseline_strategy", "supplied_baseline", "updated_at"]
        )
        assumption_fields = {
            key: values.get(key)
            for key in (
                "tariff_per_kwh",
                "expected_after_hours_base_kw",
                "abnormal_tolerance_pct",
                "downtime_cost_per_hour",
                "labor_cost_per_hour",
                "cold_min_temperature",
                "cold_max_temperature",
                "excursion_delay_minutes",
                "cold_loss_per_critical_excursion",
                "cold_critical_duration_minutes",
            )
        }
        assumption_fields["currency"] = values["currency"]
        return create_assumption_revision(
            self.site_profile,
            assumption_fields,
            user=self.user,
            change_note="Updated from business impact settings",
        )


class ImpactDataSourceForm(forms.ModelForm):
    class Meta:
        model = ImpactDataSource
        fields = [
            "source_role",
            "include_in_totals",
            "calibration_status",
            "calibration_accuracy",
            "calibration_expires_at",
        ]
        widgets = {"calibration_expires_at": forms.DateInput(attrs={"type": "date"})}


class ImpactOpportunityForm(forms.ModelForm):
    class Meta:
        model = ImpactOpportunity
        fields = ["status", "assigned_to", "dismissed_reason"]

    def __init__(self, *args, team, **kwargs):
        super().__init__(*args, **kwargs)
        member_ids = Membership.objects.filter(team=team).values_list("user_id", flat=True)
        self.fields["assigned_to"].queryset = self.fields["assigned_to"].queryset.filter(id__in=member_ids)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == ImpactOpportunity.Status.DISMISSED and not cleaned.get("dismissed_reason"):
            self.add_error("dismissed_reason", "Explain why this opportunity is not actionable.")
        return cleaned
