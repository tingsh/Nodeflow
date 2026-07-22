import json
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.devices.models import Device, DeviceCommand, Gateway, RpcCommand, Site
from apps.devices.services import process_command_response, send_device_command
from apps.teams.models import Team
from apps.users.models import CustomUser


class DeviceCommandTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(email="test@example.com", username="testuser")
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.site = Site.objects.create(team=self.team, name="Main Plant")
        self.gateway = Gateway.objects.create(
            team=self.team, site=self.site, name="GW-001", serial_number="SN123", access_token="token123"
        )
        self.device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            name="Motor 1",
            device_type="vfd",
            protocol="modbus_tcp",
        )

    @patch("apps.telemetry.mqtt_publisher.publish_rpc_command")
    def test_send_command_creates_record_and_publishes(self, mock_publish_rpc):
        mock_rpc = RpcCommand.objects.create(
            team=self.team,
            gateway=self.gateway,
            request_id="12345678-1234-1234-1234-123456789012",
            method="write_device",
            params={},
        )
        mock_publish_rpc.return_value = mock_rpc

        command = send_device_command(self.device, self.user, "toggle_switch", True)

        # Verify DB record
        self.assertEqual(command.status, "sent")
        self.assertEqual(command.command_key, "toggle_switch")
        self.assertEqual(command.value, True)
        self.assertEqual(command.command_type, "write")
        self.assertEqual(command.rpc_command, mock_rpc)

        # Verify MQTT call
        self.assertTrue(mock_publish_rpc.called)
        args, kwargs = mock_publish_rpc.call_args

        # Check method argument
        method = kwargs.get("method") if "method" in kwargs else args[1]
        self.assertEqual(method, "write_device")

        # Check params argument
        params = kwargs.get("params") if "params" in kwargs else args[2]
        self.assertEqual(params["device_name"], self.device.name)
        self.assertEqual(params["value"], True)

    @patch("apps.telemetry.mqtt_publisher.publish_rpc_command")
    def test_send_read_command_creates_audited_record(self, mock_publish_rpc):
        mock_rpc = RpcCommand.objects.create(
            team=self.team,
            gateway=self.gateway,
            request_id="12345678-1234-1234-1234-123456789013",
            method="read_device",
            params={},
        )
        mock_publish_rpc.return_value = mock_rpc

        command = send_device_command(
            self.device,
            self.user,
            "manual_read",
            command_type="read",
            params={"functionCode": 3, "address": 100, "objectsCount": 2, "type": "32float"},
        )

        self.assertEqual(command.status, "sent")
        self.assertEqual(command.command_type, "read")
        self.assertIsNone(command.value)
        self.assertEqual(command.rpc_command, mock_rpc)
        params = mock_publish_rpc.call_args.kwargs["params"]
        self.assertEqual(params["device_name"], self.device.name)
        self.assertEqual(params["functionCode"], 3)
        self.assertEqual(params["objectsCount"], 2)

    def test_process_command_response_success(self):
        # Setup a pending command
        command = DeviceCommand.objects.create(
            team=self.team,
            device=self.device,
            command_key="set_speed",
            value=50,
            transaction_id="test-tx-123",
            status="sent",
        )

        response_payload = json.dumps({"device": self.device.name, "id": "test-tx-123", "data": {"success": True}})

        process_command_response(response_payload)

        command.refresh_from_db()
        self.assertEqual(command.status, "executed")
        self.assertIsNotNone(command.executed_at)

    def test_process_current_rpc_response_updates_linked_device_command(self):
        rpc = RpcCommand.objects.create(
            team=self.team,
            gateway=self.gateway,
            request_id="12345678-1234-1234-1234-123456789014",
            method="write_device",
            params={"device_name": self.device.name},
        )
        command = DeviceCommand.objects.create(
            team=self.team,
            device=self.device,
            command_type="write",
            command_key="set_speed",
            value=50,
            transaction_id="test-tx-current",
            rpc_command=rpc,
            status="sent",
        )

        response_payload = json.dumps(
            {
                "request_id": str(rpc.request_id),
                "method": "write_device",
                "status": "success",
                "result": {"operation": "write", "response": {"success": True}},
            }
        )

        process_command_response(response_payload)

        rpc.refresh_from_db()
        command.refresh_from_db()
        self.assertEqual(rpc.status, "success")
        self.assertEqual(command.status, "executed")
        self.assertEqual(command.response_payload["result"]["operation"], "write")

    def test_process_command_response_failure(self):
        command = DeviceCommand.objects.create(
            team=self.team,
            device=self.device,
            command_key="set_speed",
            value=100,
            transaction_id="test-tx-456",
            status="sent",
        )

        response_payload = json.dumps(
            {"device": self.device.name, "id": "test-tx-456", "data": {"success": False, "error": "Hardware failure"}}
        )

        process_command_response(response_payload)

        command.refresh_from_db()
        self.assertEqual(command.status, "failed")
        self.assertEqual(command.error_message, "Hardware failure")

    def test_rpc_timeout_updates_linked_device_command(self):
        from datetime import timedelta

        from apps.devices.tasks import check_rpc_timeouts

        rpc = RpcCommand.objects.create(
            team=self.team,
            gateway=self.gateway,
            request_id="12345678-1234-1234-1234-123456789015",
            method="read_device",
            params={"device_name": self.device.name},
        )
        RpcCommand.objects.filter(pk=rpc.pk).update(sent_at=timezone.now() - timedelta(seconds=90))
        command = DeviceCommand.objects.create(
            team=self.team,
            device=self.device,
            command_type="read",
            command_key="manual_read",
            transaction_id="test-tx-timeout",
            rpc_command=rpc,
            status="sent",
        )

        self.assertEqual(check_rpc_timeouts(), 1)

        rpc.refresh_from_db()
        command.refresh_from_db()
        self.assertEqual(rpc.status, "timeout")
        self.assertEqual(command.status, "timed_out")
