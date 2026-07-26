from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.teams.models import BaseTeamModel


def default_operating_schedule():
    return {
        "monday": [["08:00", "18:00"]],
        "tuesday": [["08:00", "18:00"]],
        "wednesday": [["08:00", "18:00"]],
        "thursday": [["08:00", "18:00"]],
        "friday": [["08:00", "18:00"]],
        "saturday": [],
        "sunday": [],
    }


class BusinessImpactProfile(BaseTeamModel):
    """Team-level investment and report preferences."""

    currency = models.CharField(max_length=3, default="SGD")
    roi_start_date = models.DateField(null=True, blank=True)
    one_time_investment = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    amortization_months = models.PositiveSmallIntegerField(default=24)
    recurring_monthly_cost = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    use_subscription_cost = models.BooleanField(default=True)
    reports_enabled = models.BooleanField(default=True)
    email_reports = models.BooleanField(default=False)
    report_recipients = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team"], name="impact_one_business_profile_per_team"),
        ]

    def __str__(self):
        return f"Business impact profile for {self.team}"

    def clean(self):
        super().clean()
        self.currency = (self.currency or "SGD").upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError({"currency": "Enter a three-letter ISO currency code."})
        if self.amortization_months < 1:
            raise ValidationError({"amortization_months": "Amortization must be at least one month."})


class SiteImpactProfile(BaseTeamModel):
    """Site-level configuration controlling impact calculations."""

    class BaselineStrategy(models.TextChoices):
        ROLLING = "rolling", "Rolling measured baseline"
        SUPPLIED = "supplied", "Customer-supplied baseline"

    class CalculationStatus(models.TextChoices):
        NEEDS_CONFIGURATION = "needs_configuration", "Needs configuration"
        COLLECTING_BASELINE = "collecting_baseline", "Collecting baseline"
        READY = "ready", "Ready"
        LOW_COVERAGE = "low_coverage", "Low data coverage"
        ERROR = "error", "Calculation error"

    site = models.OneToOneField("devices.Site", on_delete=models.CASCADE, related_name="impact_profile")
    vertical_profile = models.CharField(max_length=30)
    operating_schedule = models.JSONField(default=default_operating_schedule)
    schedule_overrides = models.JSONField(default=dict, blank=True)
    baseline_strategy = models.CharField(
        max_length=20,
        choices=BaselineStrategy.choices,
        default=BaselineStrategy.ROLLING,
    )
    supplied_baseline = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    include_in_reports = models.BooleanField(default=True)
    calculation_status = models.CharField(
        max_length=30,
        choices=CalculationStatus.choices,
        default=CalculationStatus.NEEDS_CONFIGURATION,
    )
    last_calculated_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["site__name"]

    def __str__(self):
        return f"{self.site} business impact"

    def clean(self):
        super().clean()
        if self.site_id and self.team_id and self.site.team_id != self.team_id:
            raise ValidationError("The site must belong to the same team as the impact profile.")

    def save(self, *args, **kwargs):
        if self.site_id and not self.vertical_profile:
            self.vertical_profile = self.site.solution_profile
        super().save(*args, **kwargs)


class ImpactAssumptionRevision(BaseTeamModel):
    """Immutable, effective-dated inputs used by impact calculations."""

    site_profile = models.ForeignKey(
        SiteImpactProfile,
        on_delete=models.CASCADE,
        related_name="assumption_revisions",
    )
    revision = models.PositiveIntegerField(default=1)
    effective_from = models.DateTimeField(default=timezone.now)
    currency = models.CharField(max_length=3, default="SGD")
    tariff_per_kwh = models.DecimalField(max_digits=12, decimal_places=5, null=True, blank=True)
    expected_after_hours_base_kw = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    abnormal_tolerance_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("15"))
    downtime_cost_per_hour = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    labor_cost_per_hour = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    cold_min_temperature = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    cold_max_temperature = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    excursion_delay_minutes = models.PositiveIntegerField(default=5)
    cold_loss_per_critical_excursion = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    cold_critical_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    baseline_monthly_downtime_minutes = models.PositiveIntegerField(null=True, blank=True)
    baseline_monthly_labor_minutes = models.PositiveIntegerField(null=True, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impact_assumption_changes",
    )
    change_note = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["-effective_from", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_profile", "revision"],
                name="impact_unique_assumption_revision",
            ),
        ]

    def __str__(self):
        return f"{self.site_profile} assumptions v{self.revision}"

    def clean(self):
        super().clean()
        if self.site_profile_id and self.team_id != self.site_profile.team_id:
            raise ValidationError("Assumptions must belong to the same team as the site profile.")
        self.currency = (self.currency or "SGD").upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValidationError({"currency": "Enter a three-letter ISO currency code."})
        if (
            self.cold_min_temperature is not None
            and self.cold_max_temperature is not None
            and self.cold_min_temperature >= self.cold_max_temperature
        ):
            raise ValidationError("The cold-chain minimum must be below the maximum.")
        for field_name in (
            "tariff_per_kwh",
            "expected_after_hours_base_kw",
            "abnormal_tolerance_pct",
            "downtime_cost_per_hour",
            "labor_cost_per_hour",
            "cold_loss_per_critical_excursion",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValidationError({field_name: "This value cannot be negative."})

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values().first()
            if previous:
                immutable_fields = {
                    field.name for field in self._meta.fields if field.name not in {"id", "created_at", "updated_at"}
                }
                for field_name in immutable_fields:
                    field = self._meta.get_field(field_name)
                    current_value = field.value_from_object(self)
                    if previous.get(field.attname) != current_value:
                        raise ValidationError("Impact assumption revisions are immutable; create a new revision.")
        super().save(*args, **kwargs)


class ImpactDataSource(BaseTeamModel):
    """Customer-confirmed mapping from telemetry to a business metric."""

    class QuantityKind(models.TextChoices):
        POWER = "power", "Power"
        ENERGY = "energy", "Energy"
        POWER_FACTOR = "power_factor", "Power factor"
        TEMPERATURE = "temperature", "Temperature"
        RUNTIME = "runtime", "Runtime"
        STATUS = "status", "Status"
        GENERATION = "generation", "Generation"

    class Aggregation(models.TextChoices):
        INSTANTANEOUS = "instantaneous", "Instantaneous"
        CUMULATIVE_COUNTER = "cumulative_counter", "Cumulative counter"
        INTERVAL_TOTAL = "interval_total", "Interval total"
        STATE = "state", "State"
        EVENT = "event", "Event"

    class SourceRole(models.TextChoices):
        SITE_BOUNDARY = "site_boundary", "Site boundary / main meter"
        SUBMETER = "submeter", "Submeter"
        GENERATION = "generation", "Generation meter"
        INDEPENDENT = "independent", "Independent equipment meter"
        MONITORING_ONLY = "monitoring_only", "Monitoring only / excluded"

    class VerificationStatus(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Customer confirmed"
        REJECTED = "rejected", "Rejected"

    class CalibrationStatus(models.TextChoices):
        NOT_APPLICABLE = "not_applicable", "Not applicable"
        CURRENT = "current", "Current"
        EXPIRED = "expired", "Expired"
        UNKNOWN = "unknown", "Unknown"

    site_profile = models.ForeignKey(SiteImpactProfile, on_delete=models.CASCADE, related_name="data_sources")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="impact_data_sources")
    telemetry_key = models.CharField(max_length=100)
    quantity_kind = models.CharField(max_length=30, choices=QuantityKind.choices)
    aggregation = models.CharField(max_length=30, choices=Aggregation.choices)
    canonical_unit = models.CharField(max_length=20)
    conversion_factor = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    source_role = models.CharField(max_length=30, choices=SourceRole.choices)
    include_in_totals = models.BooleanField(default=False)
    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.SUGGESTED,
    )
    calibration_status = models.CharField(
        max_length=20,
        choices=CalibrationStatus.choices,
        default=CalibrationStatus.NOT_APPLICABLE,
    )
    calibration_accuracy = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    calibration_expires_at = models.DateField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(default=50)

    class Meta:
        ordering = ["priority", "device__name", "telemetry_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_profile", "device", "telemetry_key"],
                name="impact_unique_site_device_metric",
            ),
        ]

    def __str__(self):
        return f"{self.device}: {self.telemetry_key} ({self.get_source_role_display()})"

    def clean(self):
        super().clean()
        if not self.site_profile_id or not self.device_id:
            return
        if self.team_id != self.site_profile.team_id or self.team_id != self.device.team_id:
            raise ValidationError("The source, device, and profile must belong to the same team.")
        if self.device.site_id != self.site_profile.site_id:
            raise ValidationError("The source device must belong to the configured site.")
        if self.source_role == self.SourceRole.MONITORING_ONLY and self.include_in_totals:
            raise ValidationError("Monitoring-only sources cannot be included in financial totals.")
        if self.include_in_totals and self.quantity_kind not in {
            self.QuantityKind.POWER,
            self.QuantityKind.ENERGY,
        }:
            raise ValidationError("Only consumption power or energy sources can be included in totals.")
        if self.source_role == self.SourceRole.SITE_BOUNDARY and self.quantity_kind not in {
            self.QuantityKind.POWER,
            self.QuantityKind.ENERGY,
        }:
            raise ValidationError("A site boundary source must measure consumption power or energy.")
        if self.conversion_factor <= 0:
            raise ValidationError({"conversion_factor": "The conversion factor must be greater than zero."})


class ImpactBaseline(BaseTeamModel):
    class Status(models.TextChoices):
        COLLECTING = "collecting", "Collecting"
        READY = "ready", "Ready"
        INVALID = "invalid", "Invalid"

    site_profile = models.ForeignKey(
        SiteImpactProfile,
        on_delete=models.CASCADE,
        related_name="baselines",
    )
    source = models.ForeignKey(
        ImpactDataSource,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="baselines",
    )
    metric_key = models.CharField(max_length=100)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    strategy = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COLLECTING)
    values = models.JSONField(default=dict)
    coverage_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    methodology_version = models.CharField(max_length=20, default="1.0")
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-period_end", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["site_profile", "metric_key", "revision"],
                condition=models.Q(source__isnull=True),
                name="impact_unique_site_baseline_revision",
            ),
            models.UniqueConstraint(
                fields=["site_profile", "source", "metric_key", "revision"],
                condition=models.Q(source__isnull=False),
                name="impact_unique_source_baseline_revision",
            ),
        ]


class ImpactMetricSnapshot(BaseTeamModel):
    class PeriodType(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        MONTHLY = "monthly", "Monthly"

    class EvidenceClass(models.TextChoices):
        MEASURED = "measured", "Measured"
        CALCULATED = "calculated", "Calculated"
        ESTIMATED = "estimated", "Estimated"

    class Confidence(models.TextChoices):
        WITHHELD = "withheld", "Withheld"
        LOW = "low", "Low"
        NORMAL = "normal", "Normal"

    site_profile = models.ForeignKey(SiteImpactProfile, on_delete=models.CASCADE, related_name="snapshots")
    source = models.ForeignKey(
        ImpactDataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="snapshots",
    )
    period_type = models.CharField(max_length=20, choices=PeriodType.choices)
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    metric_key = models.CharField(max_length=100)
    evidence_class = models.CharField(max_length=20, choices=EvidenceClass.choices)
    value = models.DecimalField(max_digits=22, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)
    monetary_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    coverage_pct = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    confidence = models.CharField(max_length=20, choices=Confidence.choices, default=Confidence.WITHHELD)
    methodology_version = models.CharField(max_length=20, default="1.0")
    assumption_revision = models.ForeignKey(
        ImpactAssumptionRevision,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="snapshots",
    )
    breakdown = models.JSONField(default=dict, blank=True)
    warnings = models.JSONField(default=list, blank=True)
    revision = models.PositiveIntegerField(default=1)
    finalized = models.BooleanField(default=False)

    class Meta:
        ordering = ["period_start", "metric_key", "-revision"]
        indexes = [
            models.Index(fields=["team", "period_type", "period_start"]),
            models.Index(fields=["site_profile", "metric_key", "period_start"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "site_profile",
                    "period_type",
                    "period_start",
                    "period_end",
                    "metric_key",
                    "methodology_version",
                    "revision",
                ],
                condition=models.Q(source__isnull=True),
                name="impact_unique_site_metric_revision",
            ),
            models.UniqueConstraint(
                fields=[
                    "site_profile",
                    "source",
                    "period_type",
                    "period_start",
                    "period_end",
                    "metric_key",
                    "methodology_version",
                    "revision",
                ],
                condition=models.Q(source__isnull=False),
                name="impact_unique_source_metric_revision",
            ),
        ]


class ImpactOpportunity(BaseTeamModel):
    class OpportunityType(models.TextChoices):
        AFTER_HOURS = "after_hours", "After-hours consumption"
        ABNORMAL_LOAD = "abnormal_load", "Abnormal load"
        TEMPERATURE_EXCURSION = "temperature_excursion", "Temperature excursion"
        RECURRING_FAULT = "recurring_fault", "Recurring fault"
        MAINTENANCE = "maintenance", "Maintenance improvement"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACTIONED = "actioned", "Actioned"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Not actionable"

    site_profile = models.ForeignKey(SiteImpactProfile, on_delete=models.CASCADE, related_name="opportunities")
    source = models.ForeignKey(
        ImpactDataSource,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="opportunities",
    )
    opportunity_type = models.CharField(max_length=30, choices=OpportunityType.choices)
    fingerprint = models.CharField(max_length=64)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    quantity = models.DecimalField(max_digits=22, decimal_places=6, null=True, blank=True)
    unit = models.CharField(max_length=20, blank=True)
    estimated_value = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    detected_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_impact_opportunities",
    )
    dismissed_reason = models.TextField(blank=True)
    alerts = models.ManyToManyField("alerts.Alert", blank=True, related_name="impact_opportunities")
    tickets = models.ManyToManyField(
        "maintenance.MaintenanceTicket",
        blank=True,
        related_name="impact_opportunities",
    )

    class Meta:
        ordering = ["-detected_at"]
        constraints = [
            models.UniqueConstraint(fields=["team", "fingerprint"], name="impact_unique_opportunity_fingerprint"),
        ]


class ImpactReport(BaseTeamModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        GENERATING = "generating", "Generating"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"

    site = models.ForeignKey(
        "devices.Site",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="impact_reports",
    )
    period_start = models.DateField()
    period_end = models.DateField()
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    snapshot_json = models.JSONField(default=dict)
    methodology_version = models.CharField(max_length=20, default="1.0")
    private_file_name = models.CharField(max_length=300, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-period_start", "-revision"]
        constraints = [
            models.UniqueConstraint(
                fields=["team", "period_start", "period_end", "revision"],
                condition=models.Q(site__isnull=True),
                name="impact_unique_team_report_revision",
            ),
            models.UniqueConstraint(
                fields=["team", "site", "period_start", "period_end", "revision"],
                condition=models.Q(site__isnull=False),
                name="impact_unique_site_report_revision",
            ),
        ]

    def __str__(self):
        scope = self.site.name if self.site_id else self.team.name
        return f"{scope} impact report {self.period_start:%Y-%m}"
