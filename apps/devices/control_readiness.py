from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.teams.models import Team
from apps.teams.roles import has_permission

from .control_governance import create_gateway_policy_bundle
from .models import (
    CommandOutbox,
    ControlActivation,
    ControlCommissioningSession,
    ControlReadinessAssessment,
    GatewayControlPolicyBundle,
    RemoteCommand,
    RemoteCommandApproval,
    RemoteControlScope,
)
from .remote_control import actor_snapshot, append_command_event
from .remote_control_crypto import payload_checksum


class ReadinessDenied(ValueError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


def command_binding(command: RemoteCommand) -> str:
    current_value = None
    if command.device_id:
        current_value = (command.device.metadata or {}).get("last_values", {}).get(command.command_key)
    return payload_checksum(
        {
            "command_id": str(command.pk),
            "operation": command.operation,
            "target": [command.gateway_id, command.device_id, command.command_key],
            "value": command.normalized_value,
            "current_value": current_value,
            "control_epoch": command.control_epoch,
            "revisions": [
                command.template_revision,
                command.commissioning_revision,
                command.policy_revision,
            ],
            "policy_checksum": command.policy_checksum,
            "expires_at": command.expires_at.isoformat(),
        }
    )


def assess_control_readiness(
    *,
    gateway,
    assessed_by,
    observation_days,
    telemetry_coverage_percent,
    evidence=None,
    waiver_reason="",
) -> ControlReadinessAssessment:
    if not has_permission(assessed_by, gateway.team, "perform_commissioning", site=gateway.site):
        raise ReadinessDenied("You cannot assess this site.", code="permission_denied")
    blockers = []
    evidence_blockers = []
    if float(observation_days) < 7:
        evidence_blockers.append("At least seven days of representative monitoring evidence is required.")
    if float(telemetry_coverage_percent) < 95:
        evidence_blockers.append("Telemetry coverage must be at least 95%.")
    if gateway.remote_control_protocol_version < 1:
        blockers.append("Gateway does not support governed-command protocol v1.")
    if not gateway.remote_control_local_writeback_enabled:
        blockers.append("The installer-controlled local write-back switch is disabled.")
    if not gateway.remote_control_policy_loaded:
        blockers.append("Gateway has not loaded a valid retained policy.")
    if gateway.remote_control_epoch != gateway.team.remote_control_epoch:
        blockers.append("Gateway has not acknowledged the current control epoch.")
    if not gateway.remote_control_clock_ready:
        blockers.append("Gateway trusted clock is not ready.")
    if not gateway.remote_control_journal_ready:
        blockers.append("Gateway command journal is not ready.")
    if not gateway.devices.exclude(template__isnull=True).exists():
        blockers.append("No exact template-mapped device identity is available.")

    waiver_approved_by = None
    if evidence_blockers:
        if waiver_reason and has_permission(assessed_by, gateway.team, "toggle_remote_control", site=gateway.site):
            waiver_approved_by = assessed_by
        else:
            blockers.extend(evidence_blockers)
    state = (
        ControlReadinessAssessment.State.READY_FOR_COMMISSIONING
        if not blockers
        else ControlReadinessAssessment.State.EVIDENCE_COLLECTING
    )
    return ControlReadinessAssessment.objects.create(
        team=gateway.team,
        site=gateway.site,
        gateway=gateway,
        state=state,
        observation_days=observation_days,
        telemetry_coverage_percent=telemetry_coverage_percent,
        evidence=evidence or {},
        blockers=blockers,
        waiver_reason=waiver_reason,
        waiver_approved_by=waiver_approved_by,
        assessed_by=assessed_by,
    )


def open_commissioning_session(*, assessment, commissioner, scope) -> ControlCommissioningSession:
    if assessment.state != ControlReadinessAssessment.State.READY_FOR_COMMISSIONING:
        raise ReadinessDenied("Readiness evidence has not passed.", code="readiness_incomplete")
    if not has_permission(
        commissioner,
        assessment.team,
        "perform_commissioning",
        site=assessment.site,
    ):
        raise ReadinessDenied("A qualified commissioner is required.", code="commissioner_required")
    assessment.state = ControlReadinessAssessment.State.COMMISSIONING
    assessment.save(update_fields=["state", "updated_at"])
    return ControlCommissioningSession.objects.create(
        team=assessment.team,
        site=assessment.site,
        gateway=assessment.gateway,
        commissioner=commissioner,
        scope=scope,
        expires_at=timezone.now() + timedelta(hours=2),
    )


def complete_commissioning_session(*, session, evidence) -> ControlCommissioningSession:
    if session.status != ControlCommissioningSession.Status.OPEN or session.expires_at <= timezone.now():
        raise ReadinessDenied("Commissioning session is closed or expired.", code="commissioning_expired")
    required = {"equipment_identity", "operating_envelope", "interlocks", "prerequisites", "supervised_tests"}
    if not required.issubset(evidence):
        raise ReadinessDenied("Commissioning evidence is incomplete.", code="commissioning_evidence_incomplete")
    session.evidence = evidence
    session.status = ControlCommissioningSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["evidence", "status", "completed_at", "updated_at"])
    ControlReadinessAssessment.objects.filter(
        gateway=session.gateway,
        state=ControlReadinessAssessment.State.COMMISSIONING,
    ).update(state=ControlReadinessAssessment.State.READY_FOR_ACTIVATION)
    return session


@transaction.atomic
def activate_control_key(*, assessment, session, device, command_key, activated_by) -> ControlActivation:
    team = Team.objects.select_for_update().get(pk=device.team_id)
    if not has_permission(activated_by, team, "toggle_remote_control", site=device.site):
        raise ReadinessDenied("Customer control administrator approval is required.", code="activation_permission_denied")
    if assessment.state != ControlReadinessAssessment.State.READY_FOR_ACTIVATION:
        raise ReadinessDenied("Readiness is not ready for activation.", code="readiness_incomplete")
    if session.status != ControlCommissioningSession.Status.COMPLETED:
        raise ReadinessDenied("Commissioning is not complete.", code="commissioning_incomplete")
    scope_keys = session.scope.get("controls", [])
    if {"device_id": str(device.pk), "command_key": command_key} not in scope_keys:
        raise ReadinessDenied("Key is outside the commissioned session scope.", code="scope_mismatch")
    if not device.commissioned_control_envelopes.filter(command_key=command_key, is_active=True).exists():
        raise ReadinessDenied("No active commissioned envelope exists.", code="commissioning_missing")
    if not device.commandpolicy_set.filter(command_key=command_key, is_enabled=True).exists():
        raise ReadinessDenied("No enabled customer command policy exists.", code="policy_missing")
    bundle = GatewayControlPolicyBundle.objects.filter(
        gateway=device.gateway,
        control_epoch=team.remote_control_epoch,
        is_active=True,
        acknowledged_at__isnull=False,
    ).order_by("-revision").first()
    if not bundle:
        raise ReadinessDenied("Gateway has not acknowledged the active policy.", code="policy_not_acknowledged")

    RemoteControlScope.objects.update_or_create(
        team=team,
        site=device.site,
        gateway=device.gateway,
        device=device,
        command_key=command_key,
        defaults={
            "mode": RemoteControlScope.Mode.ENABLED,
            "control_epoch": team.remote_control_epoch,
            "reason": "",
        },
    )
    activation = ControlActivation.objects.create(
        team=team,
        device=device,
        command_key=command_key,
        readiness_assessment=assessment,
        commissioning_session=session,
        activated_by=activated_by,
        control_epoch=team.remote_control_epoch,
        expires_at=timezone.now() + timedelta(days=365),
    )
    team.remote_control_mode = Team.RemoteControlMode.CONTROLLED
    team.save(update_fields=["remote_control_mode", "updated_at"])
    assessment.state = ControlReadinessAssessment.State.ACTIVE
    assessment.save(update_fields=["state", "updated_at"])
    return activation


def create_approval(command: RemoteCommand) -> RemoteCommandApproval:
    return RemoteCommandApproval.objects.create(
        command=command,
        requested_by_snapshot=command.actor_snapshot,
        binding_checksum=command_binding(command),
        expires_at=min(command.expires_at, timezone.now() + timedelta(minutes=15)),
    )


@transaction.atomic
def approve_command(*, command, approver, mfa_verified, recent_auth_at, reason=""):
    command = RemoteCommand.objects.select_for_update().get(pk=command.pk)
    approval = RemoteCommandApproval.objects.select_for_update().get(command=command)
    if command.requested_by_id == approver.pk:
        raise ReadinessDenied("The requester cannot approve their own command.", code="self_approval")
    permission = (
        "approve_critical_commands"
        if command.risk == RemoteCommand.Risk.CRITICAL
        else "approve_high_risk_commands"
    )
    if not has_permission(approver, command.team, permission, site=command.gateway.site):
        raise ReadinessDenied("You cannot approve this command.", code="approval_permission_denied")
    if approval.expires_at <= timezone.now() or command.expires_at <= timezone.now():
        approval.status = RemoteCommandApproval.Status.EXPIRED
        approval.save(update_fields=["status"])
        raise ReadinessDenied("Approval request has expired.", code="approval_expired")
    if not mfa_verified:
        raise ReadinessDenied("MFA verification is required.", code="mfa_required")
    if not recent_auth_at or timezone.now() - recent_auth_at > timedelta(minutes=5):
        raise ReadinessDenied("Recent authentication is required.", code="recent_auth_required")
    if command_binding(command) != approval.binding_checksum:
        approval.status = RemoteCommandApproval.Status.INVALIDATED
        approval.save(update_fields=["status"])
        raise ReadinessDenied("Command context changed; request approval again.", code="approval_invalidated")

    approval.status = RemoteCommandApproval.Status.APPROVED
    approval.approver = approver
    approval.approver_snapshot = actor_snapshot(approver)
    approval.decided_at = timezone.now()
    approval.decision_reason = reason
    approval.mfa_verified = True
    approval.recent_auth_at = recent_auth_at
    approval.save()
    previous = command.status
    command.status = RemoteCommand.Status.QUEUED
    command.save(update_fields=["status", "updated_at"])
    outbox = CommandOutbox.objects.create(command=command)
    append_command_event(
        command,
        "command_approved",
        actor=approver,
        from_status=previous,
        to_status=command.status,
        evidence={"approval_id": approval.pk},
    )
    transaction.on_commit(lambda: _schedule_dispatch(outbox.pk))
    return command


def _schedule_dispatch(outbox_id):
    from .tasks import dispatch_remote_command_outbox

    dispatch_remote_command_outbox.delay(outbox_id)


@transaction.atomic
def emergency_disable(*, team, actor, reason, site=None, gateway=None, device=None):
    team = Team.objects.select_for_update().get(pk=team.pk)
    if not has_permission(actor, team, "toggle_remote_control", site=site or getattr(device, "site", None)):
        raise ReadinessDenied("You cannot disable this control scope.", code="permission_denied")
    team.remote_control_epoch += 1
    if not any([site, gateway, device]):
        team.remote_control_mode = Team.RemoteControlMode.LOCKED_DOWN
    team.save(update_fields=["remote_control_epoch", "remote_control_mode", "updated_at"])
    scopes = RemoteControlScope.objects.filter(team=team)
    activations = ControlActivation.objects.filter(team=team, status=ControlActivation.Status.ACTIVE)
    if site:
        scopes = scopes.filter(site=site)
        activations = activations.filter(device__site=site)
    if gateway:
        scopes = scopes.filter(gateway=gateway)
        activations = activations.filter(device__gateway=gateway)
    if device:
        scopes = scopes.filter(device=device)
        activations = activations.filter(device=device)
    scopes.update(mode=RemoteControlScope.Mode.SUSPENDED, reason=reason)
    activations.update(status=ControlActivation.Status.SUSPENDED, suspended_reason=reason)
    return team.remote_control_epoch
