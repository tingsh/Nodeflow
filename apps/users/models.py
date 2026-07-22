import hashlib
import uuid
from functools import cached_property

from allauth.account.models import EmailAddress
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.users.helpers import validate_profile_picture


def _get_avatar_filename(instance, filename):
    """Use random filename prevent overwriting existing files & to fix caching issues."""
    return f"profile-pictures/{uuid.uuid4()}.{filename.split('.')[-1]}"


class CustomUser(AbstractUser):
    """
    Add additional fields to the user model here.
    """

    avatar = models.FileField(upload_to=_get_avatar_filename, blank=True, validators=[validate_profile_picture])
    language = models.CharField(max_length=10, blank=True, null=True)
    timezone = models.CharField(max_length=100, blank=True, default="")
    phone_number = models.CharField(max_length=20, blank=True, help_text="Format: +65XXXXXXXX for Singapore numbers.")
    job_title = models.CharField(max_length=100, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.CharField(max_length=100, blank=True, default="", db_default="")
    original_email_hash = models.CharField(max_length=64, blank=True, default="", db_default="")

    def __str__(self):
        return f"{self.get_full_name()} <{self.email or self.username}>"

    def get_display_name(self) -> str:
        if self.closed_at:
            return "Closed account"
        if self.get_full_name().strip():
            return self.get_full_name()
        return self.email or self.username

    @property
    def avatar_url(self) -> str:
        if self.avatar:
            return self.avatar.url
        else:
            return f"https://www.gravatar.com/avatar/{self.gravatar_id}?s=128&d=identicon"

    @property
    def gravatar_id(self) -> str:
        # https://en.gravatar.com/site/implement/hash/
        return hashlib.md5(self.email.lower().strip().encode("utf-8")).hexdigest()

    @cached_property
    def has_verified_email(self):
        return EmailAddress.objects.filter(user=self, verified=True).exists()
