from django.test import TestCase, Client
from django.urls import reverse
from apps.teams.models import Team
from apps.users.models import CustomUser
from apps.devices.models import Site, Gateway, Device, DeviceTemplate
from apps.alerts.models import AlertRule

class DeviceInfrastructureTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.user = CustomUser.objects.create(email="test@example.com", username="testuser")
        self.team.members.add(self.user)
        self.site = Site.objects.create(team=self.team, name="Test Site")
        self.client = Client()

    def test_direct_to_cloud_connectivity(self):
        """Phase 1: Verify device creation without gateway."""
        device = Device.objects.create(
            team=self.team,
            site=self.site,
            name="Cloud Sensor",
            device_type="sensor",
            protocol="mqtt"
        )
        self.assertIsNone(device.gateway)
        self.assertEqual(device.site, self.site)

    def test_gateway_discovery_api(self):
        """Phase 3: Verify Discovery API updates gateway data."""
        gateway = Gateway.objects.create(
            team=self.team, site=self.site, serial_number="NF-TEST-999", name="Discovery Gateway"
        )
        url = reverse('web_team:devices:gateway_discovery_api', args=[self.team.slug])
        payload = {
            "serial_number": "NF-TEST-999",
            "discovered_devices": [
                {"port": 1, "protocol": "modbus", "slave_id": 5, "signature": "Eastron-SDM630"}
            ]
        }
        response = self.client.post(url, data=payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        gateway.refresh_from_db()
        self.assertIn("Eastron-SDM630", str(gateway.discovery_data))

    def test_alert_automation_presets(self):
        """Phase 3: Verify automatic alert creation via template presets."""
        template = DeviceTemplate.objects.create(
            name="Smart Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
            register_map={},
            alert_presets=[
                {"key": "voltage", "condition": "gt", "threshold": 240.0, "severity": "critical"}
            ]
        )
        
        # Creating a device with this template should trigger the signal
        device = Device.objects.create(
            team=self.team,
            site=self.site,
            name="Meter 1",
            template=template
        )
        
        # Check if AlertRule was created
        rules = AlertRule.objects.filter(device=device)
        self.assertEqual(rules.count(), 1)
        self.assertEqual(rules.first().telemetry_key, "voltage")
        self.assertEqual(rules.first().threshold, 240.0)

class NotificationTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")

    def test_notification_aggregation(self):
        """Verify the template tag aggregates data correctly."""
        from apps.alerts.templatetags.notification_tags import get_unread_notifications
        
        site = Site.objects.create(team=self.team, name="Disco Site")
        # Mock a discovery
        Gateway.objects.create(
            team=self.team, 
            site=site,
            serial_number="NF-DISCO", 
            discovery_data={"devices": [{"port": 1}]}
        )
        
        data = get_unread_notifications(self.team)
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(len(data['discoveries']), 1)
