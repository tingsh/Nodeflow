from django.conf import settings
from django.db import models

from apps.teams.models import BaseTeamModel


class ActivityLog(BaseTeamModel):
    CATEGORY_CHOICES = (
        ("infrastructure", "Infrastructure"),
        ("alert", "Alert"),
        ("audit", "Action Log"),
    )

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    message = models.TextField()

    # Optional links to objects
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, null=True, blank=True)
    site = models.ForeignKey("devices.Site", on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name_plural = "Activity logs"

    def __str__(self):
        return f"[{self.category}] {self.message[:50]}..."
