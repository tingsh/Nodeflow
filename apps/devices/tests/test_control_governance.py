import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.test import TestCase, override_settings

from apps.devices.control_governance import (
    create_gateway_policy_bundle,
    effective_control_envelope,
)
from apps.devices.models import (
    CommandPolicy,
    CommissionedControlEnvelope,
    Device,
    DeviceTemplate,
    Gateway,
    RemoteCommand,
    RemoteControlScope,
    Site,
    TemplateControlDefinition,
)
from apps.devices.remote_control import CommandDenied, request_remote_command
from apps.devices.remote_control_crypto import build_signed_command_envelope, canonical_bytes
from apps.teams.models import Membership, Team
from apps.users.models import CustomUser


class GovernedControlPolicyTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(email="engineer@example.com", username="engineer")
        self.team = Team.objects.create(
            name="Factory",
            slug="factory",
            remote_control_mode=Team.RemoteControlMode.CONTROLLED,
        )
        Membership.objects.create(team=self.team, user=self.user, role="manager")
        self.site = Site.objects.create(team=self.team, name="Plant")
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="GW",
            serial_number="GW-GOV-001",
            access_token="gov-token",
            remote_control_protocol_version=1,
            remote_control_capabilities=[
                "governed_commands_v1",
                "local_writeback_v1",
                "lifecycle_stages_v1",
                "idempotent_replay_v1",
            ],
            remote_control_local_writeback_enabled=True,
        )
        self.template = DeviceTemplate.objects.create(
            name="Exact VFD",
            device_type="vfd",
            protocol="modbus_tcp",
            is_verified=True,
            register_map={
                "speed": {
                    "address": 100,
                    "functionCode": 6,
                    "type": "16uint",
                    "writable": True,
                }
            },
        )
        self.device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            template=self.template,
            name="VFD 1",
            device_type="vfd",
            protocol="modbus_tcp",
            metadata={"last_values": {"speed": 900}},
        )
        self.definition = TemplateControlDefinition.objects.create(
            template=self.template,
            command_key="speed",
            data_type="uint16",
            unit="RPM",
            connector_mapping={"address": 100, "functionCode": 6, "type": "16uint"},
            technical_limits={"min": 0, "max": 1500, "max_delta": 600},
            revision=3,
            checksum="technical-v3",
            is_verified=True,
            is_enabled=True,
        )
        self.commissioned = CommissionedControlEnvelope.objects.create(
            team=self.team,
            device=self.device,
            command_key="speed",
            operating_limits={"min": 100, "max": 1400},
            commissioned_by=self.user,
            revision=2,
            checksum="commissioned-v2",
            is_active=True,
        )
        self.policy = CommandPolicy.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            device=self.device,
            command_key="speed",
            allowed_roles=["manager"],
            customer_limits={"min": 200, "max": 2000},
            revision=4,
            checksum="customer-v4",
            is_enabled=True,
        )
        RemoteControlScope.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            device=self.device,
            command_key="speed",
            mode=RemoteControlScope.Mode.ENABLED,
            control_epoch=self.team.remote_control_epoch,
        )

    def test_customer_policy_can_narrow_but_cannot_widen_safe_envelope(self):
        envelope = effective_control_envelope(
            device=self.device,
            command_key="speed",
            user=self.user,
        )
        self.assertEqual(envelope.limits["min"], 200)
        self.assertEqual(envelope.limits["max"], 1400)
        self.assertEqual(envelope.limits["max_delta"], 600)

    def test_out_of_range_value_is_denied_and_audited(self):
        with self.assertRaises(CommandDenied) as raised:
            request_remote_command(
                gateway=self.gateway,
                operation="write_device",
                requested_by=self.user,
                device=self.device,
                command_key="speed",
                value=1450,
            )
        self.assertEqual(raised.exception.code, "value_above_maximum")
        command = RemoteCommand.objects.get()
        self.assertEqual(command.status, RemoteCommand.Status.POLICY_DENIED)
        self.assertEqual(command.error_code, "value_above_maximum")

    def test_command_captures_immutable_revisions_and_scaled_mapping(self):
        command = request_remote_command(
            gateway=self.gateway,
            operation="write_device",
            requested_by=self.user,
            device=self.device,
            command_key="speed",
            value=1200,
        )
        self.assertEqual(command.template_revision, 3)
        self.assertEqual(command.commissioning_revision, 2)
        self.assertEqual(command.policy_revision, 4)
        self.assertEqual(command.policy_checksum, "customer-v4")
        self.assertEqual(command.request_payload["params"]["address"], 100)
        self.assertEqual(command.request_payload["params"]["expected_value"], 1200)

    def test_signed_command_and_retained_policy_share_contract(self):
        private_key = Ed25519PrivateKey.generate()
        private_raw = private_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        with override_settings(
            REMOTE_CONTROL_SIGNING_KEY_ID="test-key",
            REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID="test-key",
            REMOTE_CONTROL_SIGNING_KEYS={},
            REMOTE_CONTROL_SIGNING_PRIVATE_KEY=base64.b64encode(private_raw).decode(),
        ):
            command = request_remote_command(
                gateway=self.gateway,
                operation="write_device",
                requested_by=self.user,
                device=self.device,
                command_key="speed",
                value=1200,
            )
            envelope = build_signed_command_envelope(command)
            bundle = create_gateway_policy_bundle(self.gateway)

        signature = base64.b64decode(envelope.pop("signature"))
        envelope.pop("signing_key_id")
        private_key.public_key().verify(signature, canonical_bytes(envelope))
        self.assertIn(f"{self.device.pk}:speed", bundle.payload["controls"])
        self.assertEqual(bundle.payload["control_epoch"], self.team.remote_control_epoch)
