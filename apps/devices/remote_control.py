from __future__ import annotations

import contextlib
import hashlib
import json
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.teams.models import Team

from .control_governance import GovernanceDenied
from .models import CommandEvent, CommandOutbox, CommandTransportAttempt, Device, RemoteCommand


class CommandDenied(ValueError):
    def __init__(self, message: str, *, code: str, command: RemoteCommand | None = None):
        super().__init__(message)
        self.code = code
        self.command = command


@dataclass(frozen=True)
class CommandDefinition:
    operation: str
    risk: str
    state_changing: bool
    permission: str
    device_required: bool = False


COMMAND_CATALOG = {
    "ping": CommandDefinition("ping", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"),
    "get_status": CommandDefinition("get_status", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"),
    "get_devices": CommandDefinition("get_devices", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"),
    "get_config_status": CommandDefinition(
        "get_config_status", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"
    ),
    "network_preflight": CommandDefinition(
        "network_preflight", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"
    ),
    "hardware_preflight": CommandDefinition(
        "hardware_preflight", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"
    ),
    "privilege_preflight": CommandDefinition(
        "privilege_preflight", RemoteCommand.Risk.DIAGNOSTIC, False, "request_low_risk_commands"
    ),
    "scan_devices": CommandDefinition("scan_devices", RemoteCommand.Risk.LOW, False, "request_low_risk_commands"),
    "read_device": CommandDefinition(
        "read_device",
        RemoteCommand.Risk.DIAGNOSTIC,
        False,
        "request_low_risk_commands",
        device_required=True,
    ),
    "write_device": CommandDefinition(
        "write_device",
        RemoteCommand.Risk.HIGH,
        True,
        "request_high_risk_commands",
        device_required=True,
    ),
    "restart_connector": CommandDefinition(
        "restart_connector", RemoteCommand.Risk.HIGH, True, "request_high_risk_commands"
    ),
    "restart_all": CommandDefinition("restart_all", RemoteCommand.Risk.HIGH, True, "request_high_risk_commands"),
    "set_log_level": CommandDefinition("set_log_level", RemoteCommand.Risk.HIGH, True, "request_high_risk_commands"),
    "reboot": CommandDefinition("reboot", RemoteCommand.Risk.CRITICAL, True, "request_critical_commands"),
    "update_firmware": CommandDefinition(
        "update_firmware", RemoteCommand.Risk.CRITICAL, True, "request_critical_commands"
    ),
}


def actor_snapshot(user) -> dict:
    if not user or not getattr(user, "is_authenticated", False):
        return {"type": "system"}
    display = user.get_display_name() if hasattr(user, "get_display_name") else str(user)
    return {
        "type": "user",
        "id": user.pk,
        "email": getattr(user, "email", ""),
        "display_name": display,
    }


def append_command_event(
    command: RemoteCommand,
    event_type: str,
    *,
    actor=None,
    from_status: str = "",
    to_status: str = "",
    evidence: dict | None = None,
) -> CommandEvent:
    previous = command.events.order_by("-happened_at", "-id").first()
    payload = {
        "command": str(command.pk),
        "event_type": event_type,
        "from_status": from_status,
        "to_status": to_status,
        "actor": actor_snapshot(actor),
        "evidence": evidence or {},
        "previous": previous.checksum if previous else "",
    }
    checksum = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return CommandEvent.objects.create(
        command=command,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        actor_snapshot=payload["actor"],
        evidence=evidence or {},
        checksum=checksum,
    )


def _has_permission(user, team, permission: str, *, site=None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    from apps.teams.roles import has_permission

    return has_permission(user, team, permission, site=site)


def _normalize_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        lowered = stripped.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        with contextlib.suppress(ValueError):
            return float(stripped)
    return value


def resolve_device_params(device: Device, command_key: str, operation: str, value=None) -> tuple[dict, dict]:
    register_map = device.template.register_map if device.template and device.template.register_map else {}
    register = register_map.get(command_key)
    if not isinstance(register, dict) or "address" not in register:
        raise CommandDenied(
            f"No mapped register is configured for '{command_key}'.",
            code="unmapped_command_key",
        )

    is_write = operation == "write_device"
    if is_write and not register.get("writable"):
        raise CommandDenied(f"'{command_key}' is not configured as writable.", code="key_not_writable")
    if is_write and not device.template.is_verified:
        raise CommandDenied(
            "Remote writes require a verified exact-device template.",
            code="template_not_verified",
        )

    normalized = _normalize_value(value)
    if is_write:
        allowed_values = register.get("enum") or register.get("allowed_values")
        if allowed_values is not None and normalized not in allowed_values:
            raise CommandDenied("Value is not in the configured allowed set.", code="value_not_allowed")
        minimum = register.get("min")
        maximum = register.get("max")
        if minimum is not None and (not isinstance(normalized, int | float) or normalized < minimum):
            raise CommandDenied(f"Value must be at least {minimum}.", code="value_below_minimum")
        if maximum is not None and (not isinstance(normalized, int | float) or normalized > maximum):
            raise CommandDenied(f"Value must be at most {maximum}.", code="value_above_maximum")

    params = {
        "device_id": str(device.pk),
        "device_name": device.name,
        "functionCode": int(register.get("functionCode", 6 if is_write else 3)),
        "address": int(register["address"]),
    }
    if register.get("type") and register.get("type") != "bool":
        params["type"] = register["type"]
    if is_write:
        params["value"] = normalized
    else:
        params["objectsCount"] = int(register.get("objectsCount", 1))

    definition_snapshot = {
        "template_id": device.template_id,
        "template_verified": bool(device.template and device.template.is_verified),
        "command_key": command_key,
        "unit": register.get("unit", ""),
        "data_type": register.get("type", ""),
        "minimum": register.get("min"),
        "maximum": register.get("max"),
        "allowed_values": register.get("enum") or register.get("allowed_values"),
    }
    return params, definition_snapshot


@transaction.atomic
def _request_remote_command_atomic(
    *,
    gateway,
    operation: str,
    requested_by,
    params: dict | None = None,
    device: Device | None = None,
    command_key: str = "",
    value=None,
    reason: str = "",
    source: str = RemoteCommand.Source.USER,
    ttl_seconds: int = 30,
) -> RemoteCommand:
    definition = COMMAND_CATALOG.get(operation)
    if not definition:
        raise CommandDenied(f"Unsupported remote operation '{operation}'.", code="unsupported_operation")
    if definition.device_required and not device:
        raise CommandDenied("This operation requires an exact device target.", code="device_required")
    if device and (device.team_id != gateway.team_id or device.gateway_id != gateway.id):
        raise CommandDenied("The target device does not belong to this Gateway.", code="target_mismatch")

    team = Team.objects.select_for_update().get(pk=gateway.team_id)
    denial: tuple[str, str] | None = None
    if source == RemoteCommand.Source.USER and not _has_permission(
        requested_by,
        team,
        definition.permission,
        site=device.site if device else gateway.site,
    ):
        denial = ("permission_denied", "You do not have permission to request this command.")
    elif definition.state_changing and team.remote_control_mode != Team.RemoteControlMode.CONTROLLED:
        denial = ("monitoring_only", "Remote state-changing commands are disabled for this team.")

    normalized = _normalize_value(value)
    request_params = dict(params or {})
    policy_snapshot = {
        "phase": "governance",
        "team_mode": team.remote_control_mode,
        "permission": definition.permission,
        "state_changing": definition.state_changing,
    }
    template_revision = 0
    commissioning_revision = 0
    policy_revision = 0
    policy_checksum = ""
    if device:
        if operation in {"read_device", "write_device"}:
            try:
                request_params, register_snapshot = resolve_device_params(device, command_key, operation, value)
                policy_snapshot["register"] = register_snapshot
                normalized = request_params.get("value")
                if operation == "write_device" and team.remote_control_mode == Team.RemoteControlMode.CONTROLLED:
                    from .control_governance import (
                        effective_control_envelope,
                        validate_control_value,
                    )

                    envelope = effective_control_envelope(
                        device=device,
                        command_key=command_key,
                        user=requested_by,
                    )
                    normalized, encoded = validate_control_value(
                        envelope=envelope,
                        value=value,
                        device=device,
                    )
                    mapping = envelope.template.connector_mapping
                    request_params = {
                        "device_id": str(device.pk),
                        "device_name": device.name,
                        "command_key": command_key,
                        "functionCode": int(mapping["functionCode"]),
                        "address": int(mapping["address"]),
                        "value": encoded,
                        "expected_value": normalized,
                        "unit": envelope.template.unit,
                        "data_type": envelope.template.data_type,
                        "prerequisites": envelope.prerequisites,
                    }
                    if mapping.get("type"):
                        request_params["type"] = mapping["type"]
                    policy_snapshot["effective_envelope"] = envelope.snapshot()
                    template_revision = envelope.template.revision
                    commissioning_revision = envelope.commissioned.revision
                    policy_revision = envelope.policy.revision
                    policy_checksum = envelope.policy.checksum
            except CommandDenied as exc:
                denial = denial or (exc.code, str(exc))
            except GovernanceDenied as exc:
                denial = denial or (exc.code, str(exc))
        request_params["device_id"] = str(device.pk)
        request_params["device_name"] = device.name

    previous = RemoteCommand.objects.filter(device=device).order_by("-sequence_number").first() if device else None
    sequence_number = (previous.sequence_number + 1) if previous else 1
    approval_required = bool(policy_snapshot.get("effective_envelope", {}).get("approval_required"))
    status = (
        RemoteCommand.Status.POLICY_DENIED
        if denial
        else (RemoteCommand.Status.AWAITING_APPROVAL if approval_required else RemoteCommand.Status.QUEUED)
    )
    command = RemoteCommand.objects.create(
        team=team,
        gateway=gateway,
        device=device,
        requested_by=requested_by if getattr(requested_by, "is_authenticated", False) else None,
        source=source,
        operation=operation,
        command_key=command_key,
        requested_value=value,
        normalized_value=normalized,
        reason=reason,
        risk=definition.risk,
        status=status,
        actor_snapshot=actor_snapshot(requested_by),
        policy_snapshot=policy_snapshot,
        request_payload={"method": operation, "params": request_params},
        template_revision=template_revision,
        commissioning_revision=commissioning_revision,
        policy_revision=policy_revision,
        policy_checksum=policy_checksum,
        control_epoch=team.remote_control_epoch,
        sequence_number=sequence_number,
        expires_at=timezone.now() + timedelta(seconds=max(5, min(ttl_seconds, 300))),
        error_code=denial[0] if denial else "",
        error_message=denial[1] if denial else "",
    )
    append_command_event(
        command,
        "policy_denied" if denial else ("approval_requested" if approval_required else "command_queued"),
        actor=requested_by,
        from_status=RemoteCommand.Status.REQUESTED,
        to_status=status,
        evidence={"code": denial[0]} if denial else {"operation": operation},
    )
    if denial:
        return command, denial
    if approval_required:
        from .control_readiness import create_approval

        create_approval(command)
        return command, None

    outbox = CommandOutbox.objects.create(command=command)
    transaction.on_commit(lambda: _schedule_outbox_dispatch(outbox.pk))
    return command, None


def request_remote_command(*args, **kwargs) -> RemoteCommand:
    """Persist every policy decision, then surface denials after the audit transaction commits."""
    command, denial = _request_remote_command_atomic(*args, **kwargs)
    if denial:
        raise CommandDenied(denial[1], code=denial[0], command=command)
    return command


def _schedule_outbox_dispatch(outbox_id: int) -> None:
    from .tasks import dispatch_remote_command_outbox

    dispatch_remote_command_outbox.delay(outbox_id)


def dispatch_outbox(outbox_id: int) -> RemoteCommand | None:
    from apps.telemetry.mqtt_publisher import MqttPublishOutcomeUnknown, publish_rpc_command

    from .remote_control_crypto import build_signed_command_envelope

    with transaction.atomic():
        outbox = (
            CommandOutbox.objects.select_for_update(skip_locked=True)
            .select_related("command__gateway")
            .filter(pk=outbox_id, status=CommandOutbox.Status.PENDING)
            .first()
        )
        if not outbox:
            return None
        command = outbox.command
        if command.expires_at <= timezone.now():
            outbox.status = CommandOutbox.Status.CANCELLED
            command.status = RemoteCommand.Status.EXPIRED
            outbox.save(update_fields=["status", "updated_at"])
            command.save(update_fields=["status", "updated_at"])
            append_command_event(
                command,
                "command_expired",
                from_status=RemoteCommand.Status.QUEUED,
                to_status=RemoteCommand.Status.EXPIRED,
            )
            return command
        outbox.status = CommandOutbox.Status.CLAIMED
        outbox.claimed_at = timezone.now()
        outbox.attempt_count += 1
        outbox.save(update_fields=["status", "claimed_at", "attempt_count", "updated_at"])
        command.status = RemoteCommand.Status.DISPATCHING
        command.save(update_fields=["status", "updated_at"])
        attempt = CommandTransportAttempt.objects.create(
            command=command,
            outbox=outbox,
            attempt_number=outbox.attempt_count,
        )

    try:
        envelope = build_signed_command_envelope(command)
        command.signing_key_id = envelope["signing_key_id"]
        command.signature = envelope["signature"]
        command.save(update_fields=["signing_key_id", "signature", "updated_at"])
        rpc = publish_rpc_command(
            command.gateway,
            command.operation,
            command.request_payload.get("params", {}),
            remote_command=command,
            governed_envelope=envelope,
        )
    except MqttPublishOutcomeUnknown as exc:
        with transaction.atomic():
            outbox = CommandOutbox.objects.select_for_update().get(pk=outbox_id)
            command = RemoteCommand.objects.select_for_update().get(pk=outbox.command_id)
            attempt = CommandTransportAttempt.objects.select_for_update().get(pk=attempt.pk)
            attempt.request_id = exc.rpc_record.request_id
            attempt.state = "outcome_unknown"
            attempt.error = str(exc)
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=["request_id", "state", "error", "completed_at"])
            outbox.status = CommandOutbox.Status.PUBLISHED
            outbox.last_error = str(exc)
            command.status = RemoteCommand.Status.OUTCOME_UNKNOWN
            command.error_code = "broker_ack_unknown"
            command.error_message = str(exc)
            outbox.save(update_fields=["status", "last_error", "updated_at"])
            command.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            append_command_event(
                command,
                "broker_ack_unknown",
                from_status=RemoteCommand.Status.DISPATCHING,
                to_status=RemoteCommand.Status.OUTCOME_UNKNOWN,
                evidence={"request_id": str(exc.rpc_record.request_id)},
            )
        return command
    except Exception as exc:
        with transaction.atomic():
            outbox = CommandOutbox.objects.select_for_update().get(pk=outbox_id)
            command = RemoteCommand.objects.select_for_update().get(pk=outbox.command_id)
            attempt = CommandTransportAttempt.objects.select_for_update().get(pk=attempt.pk)
            attempt.state = "failed_before_ack"
            attempt.error = str(exc)
            attempt.completed_at = timezone.now()
            attempt.save(update_fields=["state", "error", "completed_at"])
            outbox.status = CommandOutbox.Status.FAILED
            outbox.last_error = str(exc)
            command.status = RemoteCommand.Status.FAILED
            command.error_code = "publish_failed_before_ack"
            command.error_message = str(exc)
            outbox.save(update_fields=["status", "last_error", "updated_at"])
            command.save(update_fields=["status", "error_code", "error_message", "updated_at"])
            append_command_event(
                command,
                "publish_failed",
                from_status=RemoteCommand.Status.DISPATCHING,
                to_status=RemoteCommand.Status.FAILED,
                evidence={"error": str(exc)},
            )
        return command

    with transaction.atomic():
        outbox = CommandOutbox.objects.select_for_update().get(pk=outbox_id)
        command = RemoteCommand.objects.select_for_update().get(pk=outbox.command_id)
        outbox.status = CommandOutbox.Status.PUBLISHED
        outbox.published_at = timezone.now()
        command.status = RemoteCommand.Status.BROKER_ACKNOWLEDGED
        command.broker_acknowledged_at = timezone.now()
        attempt = CommandTransportAttempt.objects.select_for_update().get(pk=attempt.pk)
        attempt.request_id = rpc.request_id
        attempt.state = "broker_acknowledged"
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["request_id", "state", "completed_at"])
        outbox.save(update_fields=["status", "published_at", "updated_at"])
        command.save(update_fields=["status", "broker_acknowledged_at", "updated_at"])
        append_command_event(
            command,
            "broker_acknowledged",
            from_status=RemoteCommand.Status.DISPATCHING,
            to_status=RemoteCommand.Status.BROKER_ACKNOWLEDGED,
            evidence={"rpc_request_id": str(rpc.request_id)},
        )
    return command
