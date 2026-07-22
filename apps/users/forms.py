import logging

import requests
from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserChangeForm
from django.utils.translation import gettext_lazy as _

from apps.utils.timezones import get_timezones_display

from .helpers import validate_profile_picture
from .models import CustomUser


class TurnstileSignupForm(SignupForm):
    """
    Sign up form that includes a turnstile captcha.
    """

    turnstile_token = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean_turnstile_token(self):
        if not settings.TURNSTILE_SECRET:
            logging.info("No turnstile secret found, not checking captcha")
            return

        turnstile_token = self.cleaned_data.get("turnstile_token", None)
        if not turnstile_token:
            raise forms.ValidationError("Missing captcha. Please try again.")

        turnstile_url = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
        payload = {
            "secret": settings.TURNSTILE_SECRET,
            "response": turnstile_token,
        }
        try:
            response = requests.post(turnstile_url, data=payload, timeout=10).json()
            if not response["success"]:
                raise forms.ValidationError("Invalid captcha. Please try again.")
        except requests.Timeout:
            raise forms.ValidationError("Captcha verification timed out. Please try again.") from None

        return turnstile_token


class CustomUserChangeForm(UserChangeForm):
    email = forms.EmailField(label=_("Email"), required=True)
    phone_number = forms.CharField(
        label=_("WhatsApp Number"),
        required=False,
        help_text=_("Include country code (e.g. +1234567890) for alerts."),
    )
    job_title = forms.CharField(label=_("Job Title"), required=False)
    department = forms.CharField(label=_("Department"), required=False)
    language = forms.ChoiceField(label=_("Language"))
    timezone = forms.ChoiceField(label=_("Time Zone"), required=False)

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "phone_number", "job_title", "department", "language", "timezone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        timezone = self.fields.get("timezone")
        timezone.choices = get_timezones_display()
        if settings.USE_I18N and len(settings.LANGUAGES) > 1:
            language = self.fields.get("language")
            language.choices = settings.LANGUAGES
        else:
            self.fields.pop("language")


class UploadAvatarForm(forms.Form):
    avatar = forms.FileField(validators=[validate_profile_picture])


class CloseAccountForm(forms.Form):
    current_password = forms.CharField(label=_("Current Password"), widget=forms.PasswordInput)
    confirmation_email = forms.EmailField(label=_("Account Email"))


class CustomSocialSignupForm(SocialSignupForm):
    """Custom social signup form to work around this issue:
    https://github.com/pennersr/django-allauth/issues/3266."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prevent_enumeration = False
