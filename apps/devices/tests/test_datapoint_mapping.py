from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.dashboard.services import generate_default_dashboard
from apps.devices.config_generator import generate_connector_config
from apps.devices.datapoint_maps import (
    clone_device_datapoint_map,
    confirm_device_datapoint_map,
    effective_register_map,
    mapping_checksum,
    record_device_datapoint_validation,
    register_map_to_datapoints,
    save_device_datapoint_map,
)
from apps.devices.models import Device, DeviceDatapointMap, DeviceTemplate, Gateway, Site
from apps.teams.models import Team
from apps.users.models import CustomUser


class DeviceDatapointMappingTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="PLC Team", slug="plc-team")
        self.user = CustomUser.objects.create(email="plc@example.com", username="plc-user")
        self.site = Site.objects.create(team=self.team, name="Factory")
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="Gateway",
            serial_number="NF-PLC-001",
            access_token="token",
        )
        self.starter = DeviceTemplate.objects.create(
            name="Siemens S7-1200 Modbus TCP",
            manufacturer="Siemens",
            model_number="S7-1200",
            device_type="plc",
            protocol="modbus_tcp",
            mapping_strategy="site_defined",
            register_map={},
            is_verified=True,
        )
        self.device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            template=self.starter,
            name="Line PLC",
            device_type="plc",
            protocol="modbus_tcp",
            port="192.168.1.50:502",
            connection_config={
                "host": "192.168.1.50",
                "port": 502,
                "slave_id": 1,
                "byteOrder": "BIG",
                "wordOrder": "BIG",
                "requested_polling_interval": 5,
            },
        )
        self.datapoints = [
            {
                "key": "process_temperature",
                "label": "Process Temperature",
                "address": 100,
                "read_function_code": 3,
                "data_type": "float32",
                "objects_count": 2,
                "unit": "°C",
                "multiplier": 0.1,
                "offset": -5,
                "access": "read_only",
                "display_type": "trend",
                "normal_min": 20,
                "normal_max": 80,
                "safety_min": -50,
                "safety_max": 200,
                "alert_suggestion": "Warn above 80 °C",
            }
        ]

    def _save_and_confirm(self):
        mapping = save_device_datapoint_map(device=self.device, team=self.team, datapoints=self.datapoints)
        checksum = mapping_checksum(self.device, mapping.datapoints)
        mapping = record_device_datapoint_validation(
            device=self.device,
            result={
                "status": "success",
                "mode": "datapoints",
                "mapping_checksum": checksum,
                "signals": [
                    {
                        "key": "process_temperature",
                        "status": "success",
                        "address": 100,
                        "sample": [16830, 0],
                        "value": 20.0,
                        "unit": "°C",
                    }
                ],
            },
        )
        return confirm_device_datapoint_map(device=self.device, team=self.team, confirmed_by=self.user)

    def test_unconfirmed_site_mapping_is_excluded_from_connector_config(self):
        save_device_datapoint_map(device=self.device, team=self.team, datapoints=self.datapoints)

        self.assertEqual(generate_connector_config(self.gateway), [])
        self.assertEqual(effective_register_map(self.device), {})

    def test_confirmed_mapping_generates_edge_config_with_semantic_conversion(self):
        self._save_and_confirm()

        connectors = generate_connector_config(self.gateway)
        point = connectors[0]["config"]["master"]["slaves"][0]["timeseries"][0]

        self.assertEqual(point["tag"], "process_temperature")
        self.assertEqual(point["functionCode"], 3)
        self.assertEqual(point["type"], "32float")
        self.assertEqual(point["objectsCount"], 2)
        self.assertEqual(point["multiplier"], 0.1)
        self.assertEqual(point["offset"], -5.0)

    def test_fixed_function_template_keeps_existing_config_path(self):
        fixed = DeviceTemplate.objects.create(
            name="Fixed Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
            mapping_strategy="fixed",
            register_map={"active_power": {"address": 12, "type": "float32", "unit": "kW"}},
        )
        Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            template=fixed,
            name="Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
            connection_config={"host": "192.168.1.60", "port": 502},
        )

        connectors = generate_connector_config(self.gateway)
        slaves = connectors[0]["config"]["master"]["slaves"]

        self.assertEqual([slave["deviceName"] for slave in slaves], ["Meter"])
        self.assertEqual(slaves[0]["timeseries"][0]["tag"], "active_power")

    def test_legacy_writable_function_code_is_split_into_read_and_write_intent(self):
        datapoints = register_map_to_datapoints(
            {
                "digital_output": {
                    "address": 10,
                    "type": "bool",
                    "functionCode": 5,
                    "writable": True,
                },
                "speed_setpoint": {
                    "address": 20,
                    "type": "uint16",
                    "functionCode": 6,
                    "writable": True,
                },
            }
        )

        self.assertEqual(datapoints[0]["read_function_code"], 1)
        self.assertEqual(datapoints[0]["write_function_code"], 5)
        self.assertEqual(datapoints[1]["read_function_code"], 3)
        self.assertEqual(datapoints[1]["write_function_code"], 6)

    def test_stale_validation_cannot_confirm_after_connection_change(self):
        mapping = save_device_datapoint_map(device=self.device, team=self.team, datapoints=self.datapoints)
        checksum = mapping_checksum(self.device, mapping.datapoints)
        record_device_datapoint_validation(
            device=self.device,
            result={
                "status": "success",
                "mapping_checksum": checksum,
                "signals": [{"key": "process_temperature", "status": "success"}],
            },
        )
        self.device.connection_config["slave_id"] = 2
        self.device.save(update_fields=["connection_config"])

        with self.assertRaisesRegex(ValidationError, "changed after the live test"):
            confirm_device_datapoint_map(device=self.device, team=self.team, confirmed_by=self.user)

    def test_failed_live_read_cannot_be_confirmed(self):
        mapping = save_device_datapoint_map(device=self.device, team=self.team, datapoints=self.datapoints)
        record_device_datapoint_validation(
            device=self.device,
            result={
                "status": "failed",
                "mapping_checksum": mapping_checksum(self.device, mapping.datapoints),
                "signals": [
                    {
                        "key": "process_temperature",
                        "status": "failed",
                        "reason": "Decoded value 9000 °C is outside the safety range.",
                    }
                ],
            },
        )

        with self.assertRaisesRegex(ValidationError, "successful live validation"):
            confirm_device_datapoint_map(device=self.device, team=self.team, confirmed_by=self.user)

    def test_mapping_limit_matches_single_gateway_validation_batch(self):
        datapoints = [
            {
                "key": f"signal_{index}",
                "address": index,
                "data_type": "uint16",
            }
            for index in range(21)
        ]

        with self.assertRaisesRegex(ValidationError, "at most 20 signals"):
            save_device_datapoint_map(device=self.device, team=self.team, datapoints=datapoints)

    def test_confirmed_display_type_generates_requested_widget(self):
        self._save_and_confirm()

        dashboard = generate_default_dashboard(self.device)
        widget = dashboard.widgets.get(telemetry_key="process_temperature")

        self.assertEqual(widget.widget_type, "timeseries")
        self.assertEqual(widget.unit, "°C")

    def test_clone_is_team_scoped_and_requires_revalidation(self):
        source = self._save_and_confirm()
        target = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            template=self.starter,
            name="Second PLC",
            device_type="plc",
            protocol="modbus_tcp",
            connection_config={"host": "192.168.1.51", "port": 502},
        )

        cloned = clone_device_datapoint_map(source_device=self.device, target_device=target, team=self.team)

        self.assertEqual(cloned.status, DeviceDatapointMap.Status.DRAFT)
        self.assertEqual(cloned.cloned_from, source)
        self.assertFalse(cloned.tested_checksum)
        self.assertFalse(cloned.confirmed_checksum)

        other_team = Team.objects.create(name="Other", slug="other")
        with self.assertRaisesRegex(ValidationError, "current team"):
            clone_device_datapoint_map(source_device=self.device, target_device=target, team=other_team)
