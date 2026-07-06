from unittest.mock import patch

from django.contrib.auth.hashers import check_password
from django.test import override_settings
from django.test import TestCase

from apps.devices.config_generator import generate_connector_config
from apps.devices.models import Device, DeviceTemplate, Gateway, GatewayInventory, Site
from apps.devices.services import GatewayClaimError, claim_gateway_for_team, compute_claim_code
from apps.teams.models import Team


class GatewayClaimWorkflowTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Acme", slug="acme")
        self.other_team = Team.objects.create(name="Other", slug="other")
        self.site = Site.objects.create(team=self.team, name="Factory")
        self.serial = "NF-EDGE-001"
        self.claim_code = compute_claim_code(self.serial)
        self.inventory = GatewayInventory.objects.create(serial_number=self.serial)

    @patch("apps.devices.mqtt_provisioning.provision_gateway_mqtt")
    def test_valid_inventory_claim_creates_gateway_and_marks_inventory_claimed(self, mock_provision):
        gateway = claim_gateway_for_team(self.team, self.site, "Main Gateway", self.serial, self.claim_code)

        self.assertEqual(gateway.team, self.team)
        self.assertEqual(gateway.site, self.site)
        self.assertEqual(gateway.serial_number, self.serial)
        self.assertEqual(gateway.mqtt_username, self.serial)
        self.assertNotEqual(gateway.mqtt_password, self.claim_code)
        self.assertTrue(check_password(mock_provision.call_args.args[1], gateway.mqtt_password))
        self.assertEqual(gateway.lifecycle_status, "claimed")
        self.assertEqual(gateway.mqtt_provisioning_status, "success")

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.status, "claimed")
        self.assertEqual(self.inventory.claimed_by_team, self.team)
        self.assertEqual(self.inventory.gateway, gateway)
        self.assertIsNotNone(self.inventory.claimed_at)
        mock_provision.assert_called_once()

    @override_settings(MQTT_PROVISIONING_REQUIRED=True)
    @patch("apps.devices.mqtt_provisioning.provision_gateway_mqtt", side_effect=RuntimeError("broker down"))
    def test_required_broker_provisioning_failure_blocks_claim(self, mock_provision):
        with self.assertRaises(GatewayClaimError):
            claim_gateway_for_team(self.team, self.site, "Main Gateway", self.serial, self.claim_code)

        self.assertFalse(Gateway.objects.filter(serial_number=self.serial).exists())
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.status, "unclaimed")

    def test_invalid_claim_code_fails(self):
        with self.assertRaises(GatewayClaimError):
            claim_gateway_for_team(self.team, self.site, "Main Gateway", self.serial, "BADCODE")

    def test_serial_must_exist_in_factory_inventory(self):
        serial = "NF-NOT-MADE"
        with self.assertRaises(GatewayClaimError):
            claim_gateway_for_team(self.team, self.site, "Unknown Gateway", serial, compute_claim_code(serial))

    @patch("apps.devices.mqtt_provisioning.provision_gateway_mqtt")
    def test_claimed_gateway_cannot_move_to_another_team(self, mock_provision):
        gateway = claim_gateway_for_team(self.team, self.site, "Main Gateway", self.serial, self.claim_code)
        other_site = Site.objects.create(team=self.other_team, name="Other Site")

        with self.assertRaises(GatewayClaimError):
            claim_gateway_for_team(self.other_team, other_site, "Stolen Gateway", self.serial, self.claim_code)

        gateway.refresh_from_db()
        self.assertEqual(gateway.team, self.team)


class EdgeConfigGenerationTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Acme", slug="acme")
        self.site = Site.objects.create(team=self.team, name="Factory")
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="Main Gateway",
            serial_number="NF-CFG-001",
            access_token="tok_cfg_001",
        )
        self.template = DeviceTemplate.objects.create(
            name="Schneider PM5350",
            manufacturer="Schneider",
            model_number="PM5350",
            device_type="power_meter",
            protocol="modbus_tcp",
            register_map={
                "voltage": {"address": 3028, "type": "float32", "functionCode": 3},
                "active_power": {"address": 3054, "type": "float32", "functionCode": 3},
                "run_command": {"address": 1, "type": "bool", "functionCode": 5, "writable": True},
            },
        )

    def test_modbus_tcp_config_matches_edge_connector_contract(self):
        device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            name="Power Meter 1",
            template=self.template,
            device_type="power_meter",
            protocol="modbus_tcp",
            discovery_meta={"interface": "10.0.0.20:502", "slave_id": 3},
        )

        connectors = generate_connector_config(self.gateway)

        self.assertEqual(len(connectors), 1)
        connector = connectors[0]
        self.assertEqual(connector["type"], "modbus")
        self.assertIn("config", connector)
        slave = connector["config"]["master"]["slaves"][0]
        self.assertEqual(slave["host"], "10.0.0.20")
        self.assertEqual(slave["port"], 502)
        self.assertEqual(slave["unitId"], 3)
        self.assertEqual(slave["deviceId"], str(device.id))
        self.assertEqual(slave["type"], "tcp")
        tags = {entry["tag"]: entry for entry in slave["timeseries"]}
        self.assertEqual(tags["voltage"]["type"], "32float")
        self.assertEqual(tags["voltage"]["objectsCount"], 2)
        self.assertNotIn("run_command", tags)

    def test_modbus_rtu_config_keeps_serial_settings_in_slave(self):
        self.template.protocol = "modbus_rtu"
        self.template.save(update_fields=["protocol"])
        Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            name="RTU Meter",
            template=self.template,
            device_type="power_meter",
            protocol="modbus_rtu",
            discovery_meta={"interface": "/dev/ttyUSB0", "baud_rate": 19200, "slave_id": 7},
        )

        connectors = generate_connector_config(self.gateway)
        slave = connectors[0]["config"]["master"]["slaves"][0]

        self.assertEqual(connectors[0]["type"], "modbus")
        self.assertEqual(slave["type"], "serial")
        self.assertEqual(slave["port"], "/dev/ttyUSB0")
        self.assertEqual(slave["baudrate"], 19200)
        self.assertEqual(slave["unitId"], 7)


class GatewayDeleteReleaseViewTest(TestCase):
    def setUp(self):
        from django.test import Client
        from django.utils import timezone

        from apps.teams.models import Membership
        from apps.teams.roles import ROLE_ADMIN, ROLE_VIEWER
        from apps.users.models import CustomUser

        self.client = Client()
        self.team = Team.objects.create(name="Acme", slug="acme")
        self.other_team = Team.objects.create(name="Other", slug="other")
        self.admin = CustomUser.objects.create(username="admin@example.com", email="admin@example.com")
        self.viewer = CustomUser.objects.create(username="viewer@example.com", email="viewer@example.com")
        Membership.objects.create(user=self.admin, team=self.team, role=ROLE_ADMIN)
        Membership.objects.create(user=self.viewer, team=self.team, role=ROLE_VIEWER)
        self.site = Site.objects.create(team=self.team, name="Factory")
        self.other_site = Site.objects.create(team=self.other_team, name="Other Factory")
        self.serial = "NF-DELETE-001"
        self.claim_code = compute_claim_code(self.serial)
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="Delete Me",
            serial_number=self.serial,
            access_token="delete-token-001",
            mqtt_username=self.serial,
            mqtt_password=self.claim_code,
        )
        self.inventory = GatewayInventory.objects.create(
            serial_number=self.serial,
            status="claimed",
            gateway=self.gateway,
            claimed_by_team=self.team,
            claimed_at=timezone.now(),
        )

    def _delete_url(self):
        from django.urls import reverse

        return reverse("web_team:devices:gateway_delete", args=[self.team.slug, self.gateway.pk])

    def test_admin_can_view_confirmation_page(self):
        self.client.force_login(self.admin)

        response = self.client.get(self._delete_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Deleting this gateway will disconnect any devices connected through it.")
        self.assertContains(response, self.serial)

    def test_viewer_cannot_delete_gateway(self):
        self.client.force_login(self.viewer)

        response = self.client.post(self._delete_url(), {"confirmation_serial": self.serial})

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Gateway.objects.filter(pk=self.gateway.pk).exists())

    @patch("apps.devices.mqtt_provisioning.deprovision_gateway_mqtt")
    def test_missing_serial_confirmation_does_not_delete(self, mock_deprovision):
        self.client.force_login(self.admin)

        response = self.client.post(self._delete_url(), {"confirmation_serial": ""})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Type the gateway serial number exactly to confirm deletion.")
        self.assertTrue(Gateway.objects.filter(pk=self.gateway.pk).exists())
        mock_deprovision.assert_not_called()

    @patch("apps.devices.mqtt_provisioning.deprovision_gateway_mqtt")
    def test_wrong_serial_confirmation_does_not_delete(self, mock_deprovision):
        self.client.force_login(self.admin)

        response = self.client.post(self._delete_url(), {"confirmation_serial": "WRONG-SERIAL"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Type the gateway serial number exactly to confirm deletion.")
        self.assertTrue(Gateway.objects.filter(pk=self.gateway.pk).exists())
        mock_deprovision.assert_not_called()

    @patch("apps.devices.mqtt_provisioning.deprovision_gateway_mqtt")
    def test_matching_serial_releases_gateway_for_redo(self, mock_deprovision):
        device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            name="Power Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
        )
        self.client.force_login(self.admin)

        response = self.client.post(self._delete_url(), {"confirmation_serial": self.serial.lower()})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Gateway.objects.filter(pk=self.gateway.pk).exists())
        self.assertFalse(Device.objects.filter(pk=device.pk).exists())
        mock_deprovision.assert_called_once()
        self.assertEqual(mock_deprovision.call_args.args[0].serial_number, self.serial)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.status, "released")
        self.assertEqual(self.inventory.gateway, self.gateway)
        self.assertIsNone(self.inventory.claimed_by_team)
        self.assertIsNone(self.inventory.claimed_at)
        self.gateway.refresh_from_db()
        self.assertEqual(self.gateway.lifecycle_status, "release_pending")

    @patch("apps.devices.mqtt_provisioning.provision_gateway_mqtt")
    @patch("apps.devices.mqtt_provisioning.deprovision_gateway_mqtt")
    def test_released_gateway_can_be_onboarded_by_another_team(self, mock_deprovision, mock_provision):
        self.client.force_login(self.admin)
        self.client.post(self._delete_url(), {"confirmation_serial": self.serial})

        gateway = claim_gateway_for_team(
            self.other_team, self.other_site, "Reclaimed Gateway", self.serial, self.claim_code
        )

        self.assertEqual(gateway.team, self.other_team)
        self.assertEqual(gateway.site, self.other_site)
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.status, "claimed")
        self.assertEqual(self.inventory.claimed_by_team, self.other_team)
        self.assertEqual(self.inventory.gateway, gateway)
        self.assertEqual(gateway.team, self.other_team)
        mock_deprovision.assert_called_once()
        self.assertEqual(mock_deprovision.call_args.args[0].serial_number, self.serial)
        mock_provision.assert_called_once()



class CommissioningContextTest(TestCase):
    def setUp(self):
        from django.utils import timezone

        self.team = Team.objects.create(name="Commissioning", slug="commissioning")
        self.site = Site.objects.create(team=self.team, name="Factory")
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="Gateway",
            serial_number="GW-COMM-001",
            access_token="comm-token",
            status="offline",
            lifecycle_status="claimed",
        )
        self.template = DeviceTemplate.objects.create(
            name="Matched Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
            register_map={"active_power": {"unit": "W"}},
        )
        self.now = timezone.now()

    def test_claimed_gateway_waits_for_connection(self):
        from apps.devices.services import build_commissioning_context

        context = build_commissioning_context(self.team, gateway=self.gateway)

        self.assertEqual(context["current_stage"], "gateway_connected")
        self.assertIn("gateway_claimed", context["completed_stages"])
        self.assertEqual(context["primary_action"]["label"], "Power on gateway")

    def test_online_gateway_with_discovery_splits_ready_and_needs_template(self):
        from django.utils import timezone
        from apps.devices.services import build_commissioning_context

        self.gateway.status = "online"
        self.gateway.last_seen = timezone.now()
        self.gateway.lifecycle_status = "commissioning"
        self.gateway.discovery_data = {
            "devices": [
                {"interface": "10.0.0.2:502", "signature": "Matched", "matched_template_id": self.template.id},
                {"interface": "10.0.0.3:502", "signature": "Unknown"},
            ]
        }
        self.gateway.save(update_fields=["status", "last_seen", "lifecycle_status", "discovery_data"])

        context = build_commissioning_context(self.team, gateway=self.gateway)

        self.assertEqual(len(context["ready_candidates"]), 1)
        self.assertEqual(len(context["needs_template_candidates"]), 1)
        self.assertEqual(context["current_stage"], "config_pushed")

    def test_config_push_and_first_telemetry_make_dashboard_ready(self):
        import uuid
        from django.utils import timezone
        from apps.devices.models import GatewayConfig
        from apps.devices.services import build_commissioning_context

        self.gateway.status = "online"
        self.gateway.last_seen = timezone.now()
        self.gateway.lifecycle_status = "commissioning"
        self.gateway.save(update_fields=["status", "last_seen", "lifecycle_status"])
        GatewayConfig.objects.create(
            team=self.team,
            gateway=self.gateway,
            config_json={"connectors": []},
            request_id=uuid.uuid4(),
            status="success",
        )
        device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            name="Live Device",
            template=self.template,
            device_type="power_meter",
            protocol="modbus_tcp",
            last_telemetry_at=timezone.now(),
        )

        context = build_commissioning_context(self.team, gateway=self.gateway)

        self.assertTrue(context["dashboard_ready"])
        self.assertEqual(context["first_live_device"], device)
        self.assertIn("config_pushed", context["completed_stages"])
