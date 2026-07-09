from django.test import TestCase
from django.urls import reverse

from apps.devices.models import Site
from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_OWNER
from apps.users.models import CustomUser


class TeamHomeRoutingTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Novena", slug="novena")
        self.user = CustomUser.objects.create_user(
            email="dashboard-owner@example.com",
            username="dashboard-owner@example.com",
            password="testpass123",
        )
        Membership.objects.create(user=self.user, team=self.team, role=ROLE_OWNER)
        self.client.force_login(self.user)

    def test_team_home_without_sites_redirects_to_onboarding(self):
        response = self.client.get(reverse("web_team:home", args=[self.team.slug]))

        self.assertRedirects(response, reverse("web_team:onboarding:start", args=[self.team.slug]))

    def test_team_home_with_one_site_renders_dashboard(self):
        site = Site.objects.create(team=self.team, name="Factory A")

        response = self.client.get(reverse("web_team:home", args=[self.team.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "web/app_home.html")
        self.assertContains(response, "Command Center")
        self.assertContains(response, 'id="app-shell"')
        self.assertContains(response, 'hx-select="#app-shell"')
        site_detail_url = reverse("web_team:devices:site_detail", args=[self.team.slug, site.pk])
        self.assertNotEqual(getattr(response, "url", None), site_detail_url)
