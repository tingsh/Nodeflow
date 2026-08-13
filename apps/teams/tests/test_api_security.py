from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.devices.models import Site
from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_ADMIN, ROLE_OWNER
from apps.users.models import CustomUser


class TeamApiAuthorizationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.team = Team.objects.create(name="Protected Team", slug="protected-team")
        cls.owner = CustomUser.objects.create(username="owner-api@example.com")
        cls.admin = CustomUser.objects.create(username="admin-api@example.com")
        Membership.objects.create(team=cls.team, user=cls.owner, role=ROLE_OWNER)
        Membership.objects.create(team=cls.team, user=cls.admin, role=ROLE_ADMIN)
        cls.site = Site.objects.create(team=cls.team, name="Retained Site")

    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse("teams:team-list")
        self.detail_url = reverse("teams:team-detail", args=[self.team.pk])

    def test_only_existing_owner_can_create_another_team(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(self.list_url, {"name": "Admin Team"}, format="json")
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(self.owner)
        response = self.client.post(self.list_url, {"name": "Owner Team"}, format="json")
        self.assertEqual(response.status_code, 201)
        created_team = Team.objects.get(pk=response.data["id"])
        self.assertTrue(
            Membership.objects.filter(team=created_team, user=self.owner, role=ROLE_OWNER).exists()
        )

    def test_admin_cannot_delete_team_through_api(self):
        self.client.force_authenticate(self.admin)
        response = self.client.delete(
            self.detail_url,
            {"confirmation_team_name": self.team.name},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.team.refresh_from_db()
        self.assertEqual(self.team.status, Team.Status.ACTIVE)

    def test_owner_api_delete_requires_exact_name_and_soft_closes(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(
            self.detail_url,
            {"confirmation_team_name": "Wrong Team"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.delete(
            self.detail_url,
            {"confirmation_team_name": self.team.name},
            format="json",
        )
        self.assertEqual(response.status_code, 204)

        self.team.refresh_from_db()
        self.assertEqual(self.team.status, Team.Status.CLOSED)
        self.assertEqual(self.team.closed_by, self.owner)
        self.assertTrue(Site.objects.filter(pk=self.site.pk, team=self.team).exists())
