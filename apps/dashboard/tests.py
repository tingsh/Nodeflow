from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.dashboard.models import SharedDashboard
from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_MANAGER, ROLE_VIEWER
from apps.users.models import CustomUser


class SharedDashboardTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.user_manager = CustomUser.objects.create_user(username="manager", email="m@ex.com", password="pwd")
        self.user_viewer = CustomUser.objects.create_user(username="viewer", email="v@ex.com", password="pwd")

        Membership.objects.create(team=self.team, user=self.user_manager, role=ROLE_MANAGER)
        Membership.objects.create(team=self.team, user=self.user_viewer, role=ROLE_VIEWER)

        self.link = SharedDashboard.objects.create(team=self.team, name="Reception Screen", is_active=True)
        self.client = Client()

    def test_rbac_manage_links(self):
        # Viewer cannot manage links
        self.client.force_login(self.user_viewer)
        response = self.client.get(reverse("web_team:dashboard_team:list", args=[self.team.slug]))
        self.assertEqual(response.status_code, 403)

        # Manager can manage links
        self.client.force_login(self.user_manager)
        response = self.client.get(reverse("web_team:dashboard_team:list", args=[self.team.slug]))
        self.assertEqual(response.status_code, 200)

    def test_public_dashboard_unauthenticated(self):
        url = reverse("dashboard_public:view", args=[self.link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Team - Reception Screen")
        self.assertContains(response, "Powered by")

        # Check that view count increased
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    def test_public_dashboard_inactive(self):
        self.link.is_active = False
        self.link.save()

        url = reverse("dashboard_public:view", args=[self.link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_public_dashboard_expired(self):
        self.link.expires_at = timezone.now() - timedelta(days=1)
        self.link.save()

        url = reverse("dashboard_public:view", args=[self.link.token])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_public_dashboard_password_protected(self):
        self.link.set_password("secret123")
        self.link.save()

        url = reverse("dashboard_public:view", args=[self.link.token])

        # GET should prompt for password without incrementing view
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Protected Dashboard")
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

        # POST with wrong password
        response = self.client.post(url, {"password": "wrong"})
        self.assertContains(response, "Incorrect password.")
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 0)

        # POST with correct password
        response = self.client.post(url, {"password": "secret123"})
        self.assertEqual(response.status_code, 200)

        # Follow-up GET should now be allowed and increment view
        response = self.client.get(url)
        self.assertContains(response, "Test Team - Reception Screen")
        self.link.refresh_from_db()
        self.assertEqual(self.link.view_count, 1)

    def test_public_dashboard_kiosk_mode(self):
        url = reverse("dashboard_public:view", args=[self.link.token]) + "?kiosk=1"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # In kiosk mode, the header shouldn't be rendered
        self.assertNotContains(response, "Test Team - Reception Screen")


class AutoDashboardTests(TestCase):
    def setUp(self):
        from apps.devices.models import Site, DeviceTemplate
        self.team = Team.objects.create(name="IoT Team", slug="iot-team")
        self.site = Site.objects.create(team=self.team, name="Main Factory")
        
        # Create a mock template
        self.template = DeviceTemplate.objects.create(
            name="Test Meter",
            manufacturer="Schneider",
            model_number="M1",
            device_type="power_meter",
            protocol="modbus_tcp",
            register_map={
                "voltage": {"address": 100, "type": "float32", "unit": "V", "label": "Voltage"},
                "active_power": {"address": 102, "type": "float32", "unit": "kW", "label": "Active Power"},
                "status_bit": {"address": 104, "type": "bool", "label": "Status Coil"},
                "raw_val": {"address": 105, "type": "uint16", "label": "Raw Register"}
            }
        )

    def test_dashboard_and_widgets_generated_on_save(self):
        from apps.devices.models import Device
        from apps.dashboard.models import Dashboard, Widget

        # Provision a device matching the template
        device = Device.objects.create(
            team=self.team,
            site=self.site,
            name="Main Meter 1",
            template=self.template,
            device_type=self.template.device_type,
            protocol=self.template.protocol
        )

        # Check that dashboard was auto-generated
        dashboard = Dashboard.objects.filter(device=device, is_default=True).first()
        self.assertIsNotNone(dashboard)
        self.assertEqual(dashboard.name, "Main Meter 1 Overview")

        # Check that correct widgets were generated
        widgets = Widget.objects.filter(dashboard=dashboard)
        self.assertEqual(widgets.count(), 4)

        # Verify widget types
        voltage_widget = widgets.get(telemetry_key="voltage")
        self.assertEqual(voltage_widget.widget_type, "gauge")
        self.assertEqual(voltage_widget.unit, "V")

        power_widget = widgets.get(telemetry_key="active_power")
        self.assertEqual(power_widget.widget_type, "timeseries")
        self.assertEqual(power_widget.unit, "kW")

        status_widget = widgets.get(telemetry_key="status_bit")
        self.assertEqual(status_widget.widget_type, "indicator")

        raw_widget = widgets.get(telemetry_key="raw_val")
        self.assertEqual(raw_widget.widget_type, "value")

        # Idempotence: save device again, widget count should not double
        device.name = "Main Meter 1 Rename"
        device.save()
        self.assertEqual(Widget.objects.filter(dashboard=dashboard).count(), 4)

