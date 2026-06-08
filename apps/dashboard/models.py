import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.teams.models import BaseTeamModel
from apps.devices.models import Site, Device


class SharedDashboard(BaseTeamModel):
    """A public, shareable link to a team's dashboard."""

    name = models.CharField(max_length=200, help_text=_("e.g. Reception TV, External Audit"))
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text=_("Optional expiration date"))

    password_hash = models.CharField(max_length=128, blank=True, help_text=_("Optional password protection"))
    view_count = models.PositiveIntegerField(default=0)

    last_viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.team.name})"

    def get_absolute_url(self):
        # This will be completely outside the team auth middleware
        return reverse("dashboard_public:view", args=[str(self.token)])

    def set_password(self, raw_password):
        if raw_password:
            self.password_hash = make_password(raw_password)
        else:
            self.password_hash = ""

    def check_password(self, raw_password):
        if not self.password_hash:
            return True
        return check_password(raw_password, self.password_hash)

    @property
    def is_expired(self):
        from django.utils import timezone

        return bool(self.expires_at and timezone.now() > self.expires_at)


class Dashboard(BaseTeamModel):
    """A team operational dashboard, linked to a Site or a Device."""

    name = models.CharField(max_length=200)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="dashboards", null=True, blank=True)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="dashboards", null=True, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        if self.site:
            return f"Dashboard: {self.name} - Site: {self.site.name}"
        if self.device:
            return f"Dashboard: {self.name} - Device: {self.device.name}"
        return f"Dashboard: {self.name}"


class Widget(BaseTeamModel):
    """A visual widget on a Dashboard."""

    WIDGET_TYPE_CHOICES = (
        ("gauge", _("Gauge")),
        ("timeseries", _("Line Chart / Time Series")),
        ("indicator", _("Status Indicator")),
        ("value", _("Live Value")),
    )

    dashboard = models.ForeignKey(Dashboard, on_delete=models.CASCADE, related_name="widgets")
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="widgets", null=True, blank=True)
    title = models.CharField(max_length=200)
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPE_CHOICES, default="value")
    telemetry_key = models.CharField(max_length=100)
    unit = models.CharField(max_length=20, blank=True)
    row = models.PositiveIntegerField(default=0)
    col = models.PositiveIntegerField(default=0)
    width = models.PositiveIntegerField(default=4)
    height = models.PositiveIntegerField(default=4)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["row", "col"]

    def __str__(self):
        return f"{self.title} ({self.get_widget_type_display()})"

