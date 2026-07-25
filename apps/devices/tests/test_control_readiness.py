from django.test import TestCase
from django.utils import timezone

from apps.devices.control_readiness import (
    ReadinessDenied,
    activate_control_key,
    approve_command,
    assess_control_readiness,
    complete_commissioning_session,
    emergency_disable,
    open_commissioning_session,
)
from apps.devices.control_recovery import disaster_recovery_control_reset
from apps.devices.models import (
    CommandPolicy,
    CommissionedControlEnvelope,
    ControlActivation,
    Device,
    DeviceTemplate,
    Gateway,
    GatewayControlPolicyBundle,
    RemoteCommand,
    RemoteControlScope,
    Site,
    TemplateControlDefinition,
)
from apps.devices.remote_control import CommandDenied, request_remote_command
from apps.teams.models import Membership, Team
from apps.users.models import CustomUser


class ControlReadinessWorkflowTest(TestCase):
    def setUp(self):
        self.owner = CustomUser.objects.create(email="owner@example.com", username="owner")
        self.manager = CustomUser.objects.create(email="manager@example.com", username="manager")
        self.team = Team.objects.create(name="Customer", slug="customer")
        Membership.objects.create(team=self.team, user=self.owner, role="owner")
        Membership.objects.create(team=self.team, user=self.manager, role="manager")
        self.site = Site.objects.create(team=self.team, name="Cold Store")
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="GW",
            serial_number="GW-READY-001",
            access_token="ready-token",
            remote_control_protocol_version=1,
            remote_control_local_writeback_enabled=True,
            remote_control_policy_loaded=True,
            remote_control_policy_revision=1,
            remote_control_epoch=1,
            remote_control_clock_ready=True,
            remote_control_journal_ready=True,
        )
        self.template = DeviceTemplate.objects.create(
            name="Chiller",
            device_type="chiller",
            protocol="modbus_tcp",
            is_verified=True,
            register_map={
                "setpoint": {
                    "address": 10,
                    "functionCode": 6,
                    "type": "16int",
                    "writable": True,
                }
            },
        )
        self.device = Device.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            template=self.template,
            name="Chiller 1",
            device_type="chiller",
            protocol="modbus_tcp",
            metadata={"last_values": {"setpoint": 5}},
        )
        TemplateControlDefinition.objects.create(
            template=self.template,
            command_key="setpoint",
            data_type="int16",
            unit="C",
            connector_mapping={"address": 10, "functionCode": 6, "type": "16int"},
            technical_limits={"min": 2, "max": 8},
            checksum="template-1",
            is_verified=True,
            is_enabled=True,
        )
        CommissionedControlEnvelope.objects.create(
            team=self.team,
            device=self.device,
            command_key="setpoint",
            operating_limits={"min": 3, "max": 7},
            commissioned_by=self.manager,
            checksum="commission-1",
            is_active=True,
        )
        self.policy = CommandPolicy.objects.create(
            team=self.team,
            site=self.site,
            gateway=self.gateway,
            device=self.device,
            command_key="setpoint",
            allowed_roles=["manager"],
            customer_limits={"min": 4, "max": 6},
            approval_required=True,
            checksum="policy-1",
            is_enabled=True,
        )

    def test_one_month_does_not_automatically_enable_control(self):
        assessment = assess_control_readiness(
            gateway=self.gateway,
            assessed_by=self.manager,
            observation_days=30,
            telemetry_coverage_percent=99,
        )
        self.team.refresh_from_db()
        self.assertEqual(assessment.state, assessment.State.READY_FOR_COMMISSIONING)
        self.assertEqual(self.team.remote_control_mode, Team.RemoteControlMode.MONITORING_ONLY)
        self.assertFalse(RemoteControlScope.objects.exists())

    def test_missing_gateway_safety_evidence_blocks_readiness(self):
        self.gateway.remote_control_clock_ready = False
        self.gateway.save(update_fields=["remote_control_clock_ready"])
        assessment = assess_control_readiness(
            gateway=self.gateway,
            assessed_by=self.manager,
            observation_days=30,
            telemetry_coverage_percent=99,
        )
        self.assertEqual(assessment.state, assessment.State.EVIDENCE_COLLECTING)
        self.assertTrue(any("clock" in blocker.lower() for blocker in assessment.blockers))

    def _activate(self):
        assessment = assess_control_readiness(
            gateway=self.gateway,
            assessed_by=self.manager,
            observation_days=7,
            telemetry_coverage_percent=95,
        )
        session = open_commissioning_session(
            assessment=assessment,
            commissioner=self.manager,
            scope={"controls": [{"device_id": str(self.device.pk), "command_key": "setpoint"}]},
        )
        complete_commissioning_session(
            session=session,
            evidence={
                "equipment_identity": {"serial": "CH-1"},
                "operating_envelope": {"min": 3, "max": 7},
                "interlocks": ["compressor-safe"],
                "prerequisites": ["auto-mode"],
                "supervised_tests": [{"value": 5, "result": "passed"}],
            },
        )
        assessment.refresh_from_db()
        GatewayControlPolicyBundle.objects.create(
            team=self.team,
            gateway=self.gateway,
            revision=1,
            control_epoch=1,
            payload={},
            checksum="bundle",
            signing_key_id="key",
            signature="signature",
            is_active=True,
            acknowledged_at=timezone.now(),
        )
        activation = activate_control_key(
            assessment=assessment,
            session=session,
            device=self.device,
            command_key="setpoint",
            activated_by=self.owner,
        )
        return activation

    def test_customer_admin_activates_only_commissioned_exact_key(self):
        activation = self._activate()
        self.assertEqual(activation.status, ControlActivation.Status.ACTIVE)
        self.assertEqual(
            RemoteControlScope.objects.get().mode,
            RemoteControlScope.Mode.ENABLED,
        )
        self.team.refresh_from_db()
        self.assertEqual(self.team.remote_control_mode, Team.RemoteControlMode.CONTROLLED)

    def test_separate_user_mfa_and_recent_auth_are_required(self):
        self._activate()
        command = request_remote_command(
            gateway=self.gateway,
            operation="write_device",
            requested_by=self.manager,
            device=self.device,
            command_key="setpoint",
            value=5,
        )
        self.assertEqual(command.status, RemoteCommand.Status.AWAITING_APPROVAL)
        with self.assertRaisesRegex(ReadinessDenied, "own command"):
            approve_command(
                command=command,
                approver=self.manager,
                mfa_verified=True,
                recent_auth_at=timezone.now(),
            )
        with self.assertRaisesRegex(ReadinessDenied, "MFA"):
            approve_command(
                command=command,
                approver=self.owner,
                mfa_verified=False,
                recent_auth_at=timezone.now(),
            )
        approved = approve_command(
            command=command,
            approver=self.owner,
            mfa_verified=True,
            recent_auth_at=timezone.now(),
        )
        self.assertEqual(approved.status, RemoteCommand.Status.QUEUED)

    def test_approval_invalidates_when_current_value_changes(self):
        self._activate()
        command = request_remote_command(
            gateway=self.gateway,
            operation="write_device",
            requested_by=self.manager,
            device=self.device,
            command_key="setpoint",
            value=5,
        )
        self.device.metadata["last_values"]["setpoint"] = 6
        self.device.save(update_fields=["metadata"])
        with self.assertRaisesRegex(ReadinessDenied, "context changed"):
            approve_command(
                command=command,
                approver=self.owner,
                mfa_verified=True,
                recent_auth_at=timezone.now(),
            )

    def test_emergency_disable_blocks_hub_and_increments_epoch(self):
        self._activate()
        epoch = emergency_disable(
            team=self.team,
            actor=self.owner,
            reason="Incident",
            gateway=self.gateway,
        )
        self.assertEqual(epoch, 2)
        self.assertEqual(RemoteControlScope.objects.get().mode, RemoteControlScope.Mode.SUSPENDED)
        with self.assertRaises(CommandDenied):
            request_remote_command(
                gateway=self.gateway,
                operation="write_device",
                requested_by=self.manager,
                device=self.device,
                command_key="setpoint",
                value=5,
            )

    def test_restore_reset_cancels_pending_approval_and_locks_control(self):
        self._activate()
        command = request_remote_command(
            gateway=self.gateway,
            operation="write_device",
            requested_by=self.manager,
            device=self.device,
            command_key="setpoint",
            value=5,
        )
        self.assertEqual(command.status, RemoteCommand.Status.AWAITING_APPROVAL)
        disaster_recovery_control_reset(reason="restore test")
        command.refresh_from_db()
        self.team.refresh_from_db()
        self.assertEqual(command.status, RemoteCommand.Status.CANCELLED)
        self.assertEqual(command.approval.status, command.approval.Status.INVALIDATED)
        self.assertEqual(self.team.remote_control_mode, Team.RemoteControlMode.LOCKED_DOWN)
        self.assertEqual(self.team.remote_control_epoch, 2)
