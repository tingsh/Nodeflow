from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.alerts.models import AlertRule
from apps.automations.models import Automation
from apps.dashboard.models import SharedDashboard
from apps.devices.models import Device, Gateway, Site
from apps.maintenance.models import MaintenanceTicket, PreventiveSchedule, SharedTicketLink
from apps.teams.models import Team
from apps.teams.roles import ROLE_OWNER
from apps.users.models import CustomUser


class TeamClosureTest(TestCase):
    password = "team-close-123"

    def setUp(self):
        self.owner = CustomUser.objects.create_user(
            username="owner@test.com", email="owner@test.com", password=self.password
        )
        self.team = Team.objects.create(name="Closeable Team", slug="closeable-team")
        self.team.members.add(self.owner, through_defaults={"role": ROLE_OWNER})

    def test_close_team_blocks_active_subscription(self):
        self.client.login(username=self.owner.username, password=self.password)
        with patch.object(Team, "has_active_subscription", return_value=True):
            response = self.client.post(
                reverse("single_team:delete_team", args=[self.team.slug]),
                {"confirmation_team_name": self.team.name},
            )

        self.assertRedirects(response, reverse("single_team:manage_team", args=[self.team.slug]))
        self.team.refresh_from_db()
        self.assertEqual(Team.Status.ACTIVE, self.team.status)

    def test_closed_team_is_excluded_from_normal_access(self):
        self.client.login(username=self.owner.username, password=self.password)
        response = self.client.post(
            reverse("single_team:delete_team", args=[self.team.slug]),
            {"confirmation_team_name": self.team.name},
        )
        self.assertEqual(302, response.status_code)

        response = self.client.get(reverse("teams:manage_teams"))
        self.assertEqual(list(response.context["teams"]), [])
        response = self.client.get(reverse("single_team:manage_team", args=[self.team.slug]))
        self.assertEqual(404, response.status_code)

    def test_close_team_disables_operational_surfaces(self):
        site = Site.objects.create(team=self.team, name="Main Site")
        gateway = Gateway.objects.create(
            team=self.team,
            site=site,
            name="Main Gateway",
            serial_number="GW-CLOSE-001",
            access_token="close-token-001",
            status="online",
        )
        device = Device.objects.create(
            team=self.team,
            site=site,
            gateway=gateway,
            name="Power Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
        )
        alert_rule = AlertRule.objects.create(
            team=self.team,
            device=device,
            telemetry_key="temperature",
            condition="gt",
            threshold=8,
            notify_email=True,
            notify_whatsapp=True,
            notify_webhook="https://example.com/hook",
            create_maintenance_ticket=True,
        )
        automation = Automation.objects.create(team=self.team, name="Fan Control")
        schedule = PreventiveSchedule.objects.create(team=self.team, device=device, title="Monthly Check")
        shared_dashboard = SharedDashboard.objects.create(team=self.team, name="Lobby")
        ticket = MaintenanceTicket.objects.create(team=self.team, device=device, title="Inspect panel")
        shared_ticket = SharedTicketLink.objects.create(team=self.team, ticket=ticket)

        self.client.login(username=self.owner.username, password=self.password)
        self.client.post(
            reverse("single_team:delete_team", args=[self.team.slug]),
            {"confirmation_team_name": self.team.name},
        )

        alert_rule.refresh_from_db()
        automation.refresh_from_db()
        schedule.refresh_from_db()
        shared_dashboard.refresh_from_db()
        shared_ticket.refresh_from_db()
        gateway.refresh_from_db()
        self.assertFalse(alert_rule.is_active)
        self.assertFalse(alert_rule.notify_email)
        self.assertFalse(alert_rule.notify_whatsapp)
        self.assertEqual("", alert_rule.notify_webhook)
        self.assertFalse(alert_rule.create_maintenance_ticket)
        self.assertFalse(automation.is_active)
        self.assertFalse(schedule.is_active)
        self.assertFalse(schedule.send_email_notification)
        self.assertFalse(schedule.send_whatsapp_notification)
        self.assertFalse(shared_dashboard.is_active)
        self.assertFalse(shared_ticket.is_active)
        self.assertEqual("offline", gateway.status)
