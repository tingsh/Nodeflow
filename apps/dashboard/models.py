import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.teams.models import BaseTeamModel


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
