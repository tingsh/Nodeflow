from django.test import TestCase
from django.urls import reverse

from apps.teams.models import Invitation, Team
from apps.teams.roles import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER
from apps.users.models import CustomUser

PASSWORD = "123"


class TeamsAuthTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sox = Team.objects.create(name="Red Sox", slug="sox")
        cls.yanks = Team.objects.create(name="Yankees", slug="yanks")

        cls.sox_admin = _create_user("tito@redsox.com", "tito@redsox.com")
        cls.sox.members.add(cls.sox_admin, through_defaults={"role": ROLE_OWNER})

        cls.yanks_admin = _create_user("joe.torre@yankees.com", "joe.torre@yankees.com")
        cls.yanks.members.add(cls.yanks_admin, through_defaults={"role": ROLE_ADMIN})

        cls.yanks_member = _create_user("derek.jeter@yankees.com", "derek.jeter@yankees.com")
        cls.yanks.members.add(cls.yanks_member, through_defaults={"role": ROLE_MANAGER})

    def test_unauthenticated_view(self):
        response = self.client.get(reverse("web:home"))
        self.assertEqual(200, response.status_code)
        self._assertRequestHasTeam(response, None)

    def test_authenticated_non_team_view(self):
        self._login(self.sox_admin)
        response = self.client.get(reverse("users:user_profile"))
        self.assertEqual(200, response.status_code, response)
        self._assertRequestHasTeam(response, self.sox, self.sox_admin, ROLE_OWNER)

    def test_team_view(self):
        self._login(self.sox_admin)
        response = self.client.get(reverse("single_team:manage_team", args=[self.sox.slug]))
        self.assertEqual(200, response.status_code)
        self._assertRequestHasTeam(response, self.sox, self.sox_admin, ROLE_OWNER)

    def test_team_view_no_membership(self):
        self._login(self.sox_admin)
        response = self.client.get(reverse("single_team:manage_team", args=[self.yanks.slug]))
        self.assertEqual(404, response.status_code)
        self._assertRequestHasTeam(response, self.yanks, None, None)

    def test_team_admin_view(self):
        self._login(self.sox_admin)
        invite = self._create_invitation()
        response = self.client.post(reverse("single_team:resend_invitation", args=[self.sox.slug, invite.id]))
        self.assertEqual(200, response.status_code)
        self._assertRequestHasTeam(response, self.sox, self.sox_admin, ROLE_OWNER)

    def test_team_admin_view_denied(self):
        self._login(self.yanks_member)
        invite = self._create_invitation()
        response = self.client.post(reverse("single_team:resend_invitation", args=[self.yanks.slug, invite.id]))
        self.assertEqual(404, response.status_code)
        self._assertRequestHasTeam(response, self.yanks, self.yanks_member, ROLE_MANAGER)

    def test_delete_team_not_allowed_by_member(self):
        self._login(self.yanks_member)
        response = self.client.post(
            reverse("single_team:delete_team", args=[self.yanks.slug]),
            {"confirmation_team_name": self.yanks.name},
        )
        self.assertEqual(403, response.status_code)
        self.assertTrue(Team.objects.filter(slug=self.yanks.slug).exists())

    def test_delete_team_not_allowed_by_admin(self):
        self._login(self.yanks_admin)
        response = self.client.post(
            reverse("single_team:delete_team", args=[self.yanks.slug]),
            {"confirmation_team_name": self.yanks.name},
        )
        self.assertEqual(403, response.status_code)
        self.assertTrue(Team.objects.filter(slug=self.yanks.slug).exists())

    def test_admin_does_not_see_delete_team_button(self):
        self._login(self.yanks_admin)
        response = self.client.get(reverse("single_team:manage_team", args=[self.yanks.slug]))
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, "Delete Team")

    def test_owner_sees_delete_team_button(self):
        self._login(self.sox_admin)
        response = self.client.get(reverse("single_team:manage_team", args=[self.sox.slug]))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Delete Team")

    def test_delete_team_requires_exact_team_name_confirmation(self):
        self._login(self.sox_admin)
        response = self.client.post(
            reverse("single_team:delete_team", args=[self.sox.slug]),
            {"confirmation_team_name": "Wrong Team"},
        )
        self.assertEqual(302, response.status_code)
        self.assertRedirects(response, reverse("single_team:manage_team", args=[self.sox.slug]))
        self.assertTrue(Team.objects.filter(slug=self.sox.slug).exists())

    def test_delete_team_requires_confirmation_team_name(self):
        self._login(self.sox_admin)
        response = self.client.post(reverse("single_team:delete_team", args=[self.sox.slug]), {})
        self.assertEqual(302, response.status_code)
        self.assertRedirects(response, reverse("single_team:manage_team", args=[self.sox.slug]))
        self.assertTrue(Team.objects.filter(slug=self.sox.slug).exists())

    def test_delete_team(self):
        self._login(self.sox_admin)
        response = self.client.post(
            reverse("single_team:delete_team", args=[self.sox.slug]),
            {"confirmation_team_name": self.sox.name},
        )
        self.assertEqual(302, response.status_code)
        self.assertFalse(Team.objects.filter(slug=self.sox.slug).exists())

    def _login(self, user):
        success = self.client.login(username=user.username, password="123")
        self.assertTrue(success, f"User login failed: {user.username}")

    def _create_invitation(self):
        return Invitation.objects.create(
            team=self.sox, email="dj@yankees.com", role=ROLE_MANAGER, invited_by=self.sox_admin
        )

    def _assertRequestHasTeam(self, response, team, user=None, role=None):
        request = response.wsgi_request
        self.assertTrue(hasattr(request, "team"))
        self.assertEqual(request.team, team)
        self.assertTrue(hasattr(request, "team_membership"))
        membership = request.team_membership
        if user or role:
            self.assertEqual(membership.user, user)
            self.assertEqual(membership.role, role)
        else:
            # use assertEqual to force setup of the lazy object
            self.assertEqual(membership, None)


def _create_user(username, email=None):
    user = CustomUser.objects.create(username=username, email=email or username)
    user.set_password(PASSWORD)
    user.save()
    return user
