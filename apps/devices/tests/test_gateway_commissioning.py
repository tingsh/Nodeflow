from unittest.mock import patch

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
        self.assertEqual(gateway.mqtt_password, self.claim_code)
        self.assertEqual(gateway.lifecycle_status, "claimed")

        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.status, "claimed")
        self.assertEqual(self.inventory.claimed_by_team, self.team)
        self.assertEqual(self.inventory.gateway, gateway)
        self.assertIsNotNone(self.inventory.claimed_at)
        mock_provision.assert_called_once_with(gateway, self.claim_code)

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
        Device.objects.create(
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
