from allauth.account.models import EmailAddress
from django.test import TestCase
from django.urls import reverse

from apps.api.models import UserAPIKey
from apps.teams.models import Team
from apps.teams.roles import ROLE_OWNER
from apps.users.models import CustomUser


class AccountClosureTest(TestCase):
    password = "close-me-123"

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password=self.password,
            first_name="Casey",
            last_name="Owner",
            phone_number="+6512345678",
            job_title="Ops Lead",
            department="Facilities",
            timezone="Asia/Singapore",
            language="en",
        )
        EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True, verified=True)
        self.team = Team.objects.create(name="Closure Team", slug="closure-team")
        self.team.members.add(self.user, through_defaults={"role": ROLE_OWNER})

    def test_close_account_requires_login(self):
        response = self.client.post(reverse("users:close_account"))
        self.assertEqual(302, response.status_code)
        self.assertIn(reverse("account_login"), response["Location"])

    def test_close_account_rejects_wrong_password(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(
            reverse("users:close_account"),
            {"current_password": "wrong", "confirmation_email": self.user.email},
        )
        self.assertRedirects(response, reverse("users:user_profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_close_account_rejects_wrong_confirmation_email(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(
            reverse("users:close_account"),
            {"current_password": self.password, "confirmation_email": "other@example.com"},
        )
        self.assertRedirects(response, reverse("users:user_profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_close_account_blocks_sole_owner_of_active_team(self):
        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(
            reverse("users:close_account"),
            {"current_password": self.password, "confirmation_email": self.user.email},
        )
        self.assertRedirects(response, reverse("users:user_profile"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_close_account_anonymizes_user_and_revokes_access(self):
        second_owner = CustomUser.objects.create_user(
            username="second@example.com", email="second@example.com", password=self.password
        )
        self.team.members.add(second_owner, through_defaults={"role": ROLE_OWNER})
        api_key, _ = UserAPIKey.objects.create_key(name="Test key", user=self.user)

        self.client.login(username=self.user.username, password=self.password)
        response = self.client.post(
            reverse("users:close_account"),
            {"current_password": self.password, "confirmation_email": self.user.email},
        )
        self.assertRedirects(response, reverse("web:home"))

        self.user.refresh_from_db()
        api_key.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(self.user.closed_at)
        self.assertEqual("self_service", self.user.closed_reason)
        self.assertEqual(f"closed-user-{self.user.id}@closed.novena.local", self.user.email)
        self.assertEqual(f"closed-user-{self.user.id}", self.user.username)
        self.assertEqual("", self.user.first_name)
        self.assertEqual("", self.user.last_name)
        self.assertEqual("", self.user.phone_number)
        self.assertEqual("", self.user.job_title)
        self.assertEqual("", self.user.department)
        self.assertEqual("", self.user.timezone)
        self.assertIsNone(self.user.language)
        self.assertTrue(self.user.original_email_hash)
        self.assertTrue(api_key.revoked)
        self.assertFalse(EmailAddress.objects.filter(user=self.user).exists())
        self.assertFalse(self.client.login(username=f"closed-user-{self.user.id}", password=self.password))
