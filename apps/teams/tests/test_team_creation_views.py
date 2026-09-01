from django.test import TestCase
from django.urls import reverse

from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_ADMIN, ROLE_OWNER
from apps.users.models import CustomUser


class TeamCreationViewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.existing_team = Team.objects.create(name="Existing Team", slug="existing-team")
        cls.owner = CustomUser.objects.create_user(username="owner@example.com", password="password123")
        cls.admin = CustomUser.objects.create_user(username="admin@example.com", password="password123")
        cls.no_team_user = CustomUser.objects.create_user(username="new@example.com", password="password123")
        Membership.objects.create(team=cls.existing_team, user=cls.owner, role=ROLE_OWNER)
        Membership.objects.create(team=cls.existing_team, user=cls.admin, role=ROLE_ADMIN)

    def test_existing_owner_can_create_team_from_customer_ui(self):
        self.client.force_login(self.owner)

        response = self.client.post(reverse("teams:create_team"), {"name": "  North   Plant Operations  "})

        created = Team.objects.get(name="North Plant Operations")
        self.assertRedirects(response, reverse("single_team:manage_team", args=[created.slug]))
        self.assertTrue(Membership.objects.filter(team=created, user=self.owner, role=ROLE_OWNER).exists())
        self.assertEqual(self.client.session["team"], created.pk)

    def test_admin_and_user_without_owned_team_cannot_create_team(self):
        for user in (self.admin, self.no_team_user):
            self.client.force_login(user)
            response = self.client.get(reverse("teams:create_team"))
            self.assertEqual(response.status_code, 403)

    def test_team_list_only_shows_create_action_to_owner(self):
        self.client.force_login(self.owner)
        owner_response = self.client.get(reverse("teams:manage_teams"))
        self.assertContains(owner_response, "Create Team")

        self.client.force_login(self.admin)
        admin_response = self.client.get(reverse("teams:manage_teams"))
        self.assertNotContains(admin_response, "Create Team")
