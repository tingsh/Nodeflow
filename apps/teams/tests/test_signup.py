from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.teams.models import Team
from apps.users.models import CustomUser


@override_settings(ACCOUNT_ADAPTER="apps.teams.adapter.AcceptInvitationAdapter", TURNSTILE_SECRET=None)
class TestSignupView(TestCase):
    def test_signup_normal(self):
        self._run_test(team_name="Alice Team", expected_slug="alice-team")

    def test_signup_no_team(self):
        password = "Super Secret Pa$$word!"
        response = self.client.post(
            reverse("account_signup"),
            data={
                "email": "alice@example.com",
                "password1": password,
                "password2": password,
                "team_name": "",
                "terms_agreement": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(0, CustomUser.objects.count())
        self.assertEqual(0, Team.objects.count())
        self.assertFormError(response.context["form"], "team_name", "Please provide a Company or Team Name.")

    def test_signup_unicode_team(self):
        # unicode team names will fall back to the email address
        self._run_test(team_name="Сергей Петров", expected_slug="alice")

    def _run_test(self, team_name: str, expected_slug: str):
        password = "Super Secret Pa$$word!"
        data = {
            "email": "alice@example.com",
            "password1": password,
            "team_name": team_name,
            "terms_agreement": True,
        }
        data["password2"] = password

        response = self.client.post(
            reverse("account_signup"),
            data=data,
            follow=True,
        )
        if (response.status_code != 200 or CustomUser.objects.count() == 0) and "form" in response.context:
            print(f"FORM ERRORS: {response.context['form'].errors}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, CustomUser.objects.count())
        self.assertEqual(1, Team.objects.count())
        team = Team.objects.get()
        self.assertEqual(team_name or expected_slug, team.name)
        self.assertEqual(expected_slug, team.slug)
