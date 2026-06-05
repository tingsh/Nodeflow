from django.test import TestCase, Client
from django.urls import reverse
from apps.teams.models import Team, Membership
from apps.teams.roles import ROLE_ADMIN
from apps.users.models import CustomUser
from apps.devices.models import Device, DeviceTemplate, Gateway, Site

class OnboardingConnectionTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.user = CustomUser.objects.create(email="test@example.com", username="testuser")
        Membership.objects.create(team=self.team, user=self.user, role=ROLE_ADMIN)
        self.site = Site.objects.create(team=self.team, name="Test Site")
        self.gateway = Gateway.objects.create(team=self.team, site=self.site, name="GW-1", serial_number="SN-1234")
        self.template = DeviceTemplate.objects.create(
            name="Smart Meter",
            manufacturer="Schneider Electric",
            model_number="PM5350",
            device_type="power_meter",
            protocol="modbus_tcp",
            category="energy",
            register_map={
                "voltage": {"address": 3028, "type": "float32", "functionCode": 3, "unit": "V"},
                "active_power": {"address": 3054, "type": "float32", "functionCode": 3, "unit": "W", "writable": True}
            }
        )
        self.client = Client()
        self.client.force_login(self.user)

    def test_htmx_device_create_post_success(self):
        url = reverse("web_team:devices:htmx_device_create", args=[self.team.slug])
        url = f"{url}?site_id={self.site.id}&gateway_id={self.gateway.id}&port=1"
        
        response = self.client.post(url, {
            "name": "New Test Device",
            "template_id": self.template.id
        })
        
        # Check HTTP response code is 200 OK (replaces legacy 204)
        self.assertEqual(response.status_code, 200)
        
        # Check HX-Trigger header exists
        self.assertEqual(response.headers.get("HX-Trigger"), "infrastructureChanged")
        
        # Check that success view content is rendered
        self.assertContains(response, "Device Registered!")
        self.assertContains(response, "New Test Device")
        self.assertContains(response, "Live Connection Test")
        
        # Check that first readable register is identified and details shown
        self.assertContains(response, "voltage")
        self.assertContains(response, "(Address: 3028, FC: 3)")
        
        # Check that writable active_power is NOT chosen as test_register
        self.assertNotContains(response, "active_power")
        
        # Check device was created in DB
        device = Device.objects.get(name="New Test Device")
        self.assertEqual(device.gateway, self.gateway)
        self.assertEqual(device.site, self.site)
        self.assertEqual(device.port, "1")

    def test_htmx_device_create_no_readable_registers(self):
        # Create a template with ONLY writable registers
        write_only_template = DeviceTemplate.objects.create(
            name="Write Only Device",
            manufacturer="Danfoss",
            model_number="VLT",
            device_type="vfd",
            protocol="modbus_rtu",
            register_map={
                "speed_setpoint": {"address": 10, "type": "uint16", "functionCode": 6, "writable": True}
            }
        )
        
        url = reverse("web_team:devices:htmx_device_create", args=[self.team.slug])
        url = f"{url}?site_id={self.site.id}&gateway_id={self.gateway.id}&port=2"
        
        response = self.client.post(url, {
            "name": "Write Only Test Device",
            "template_id": write_only_template.id
        })
        
        self.assertEqual(response.status_code, 200)
        # Renders success page cleanly, saying no readable registers
        self.assertContains(response, "No readable registers found in this template to test")
