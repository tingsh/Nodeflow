"""Durable guided equipment setup orchestration."""

from __future__ import annotations

import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.dashboard.services import generate_default_dashboard

from .config_generator import normalized_datapoints
from .models import (
    DeploymentSetupEvent,
    DeploymentSetupItem,
    DeploymentSetupRun,
    Gateway,
    RpcCommand,
)

TERMINAL_RUN_STATES = {
    DeploymentSetupRun.State.COMPLETED,
    DeploymentSetupRun.State.COMPLETED_ATTENTION,
    DeploymentSetupRun.State.FAILED,
    DeploymentSetupRun.State.CANCELLED,
}
SENSITIVE_EVIDENCE_KEYS = {
    "access_token",
    "api_key",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "private_key",
    "secret",
    "token",
}


def redact_support_evidence(value):
    """Remove credentials while retaining diagnostic structure."""
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if str(key).lower() in SENSITIVE_EVIDENCE_KEYS else redact_support_evidence(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_support_evidence(item) for item in value]
    if isinstance(value, str):
        return re.sub(
            r"(?i)\b(password|token|secret|access_token)\s*[:=]\s*[^\s,;]+",
            r"\1=[redacted]",
            value,
        )
    return value


def customer_safe_error(error: str, *, target: str = "") -> str:
    normalized = str(error or "").lower()
    if "timed out" in normalized or "timeout" in normalized:
        return (
            f"The Gateway cannot reach {target}. Check its address, network route, and Modbus port."
            if target
            else "The Gateway could not reach the equipment in time. Check its address, wiring, and power."
        )
    if "connection refused" in normalized or "refused" in normalized:
        return (
            "The equipment address is reachable, but it is not accepting a connection. "
            "Check its communication settings."
        )
    if "serial interface" in normalized or "no such file" in normalized:
        return "The selected RS485 interface is not available. Check the adapter and wiring, then retry."
    if "permission" in normalized:
        return "The Gateway cannot access the selected equipment interface. Check its installation permissions."
    if "stale" in normalized or "expired" in normalized:
        return "This setup request is no longer current. Retry to create a fresh request."
    return "Novena could not complete this setup step. Review the connection details and retry."


def confidence_label(score: int) -> str:
    if score >= 80:
        return "High confidence"
    if score >= 45:
        return "Possible match"
    return "Needs setup"


def confidence_explanation(discovery: dict) -> str:
    reasons = discovery.get("matched_template_reasons") or []
    labels = {
        "protocol": "the communication protocol matches",
        "manufacturer": "the manufacturer matches",
        "manufacturer hint": "a known manufacturer name matches",
        "model": "the exact model matches",
        "model hint": "the model resembles a known template",
        "signature": "the equipment identity matches",
        "signature hint": "a known equipment signature matches",
    }
    readable = [labels.get(reason, str(reason)) for reason in reasons]
    if not readable:
        return "Novena could not confirm enough identity details to apply a template automatically."
    return "Suggested because " + ", ".join(readable) + "."


def trust_level_for_template(template) -> str:
    if template.is_verified:
        return DeploymentSetupItem.Trust.NOVENA_VERIFIED
    if template.source == "ai_generated":
        return DeploymentSetupItem.Trust.AI_DRAFT
    if template.source == "user_created":
        return DeploymentSetupItem.Trust.UNVALIDATED
    return DeploymentSetupItem.Trust.UNVALIDATED


def connection_from_candidate(candidate: dict) -> dict:
    interface = str(candidate.get("interface") or candidate.get("port") or "")
    protocol = candidate.get("connection") or candidate.get("protocol")
    connection = {
        "slave_id": int(candidate.get("slave_id") or 1),
        "timeout": 3,
    }
    if protocol == "modbus_tcp":
        host, separator, raw_port = interface.rpartition(":")
        connection.update(
            {
                "host": host if separator else interface,
                "port": int(raw_port) if separator and raw_port.isdigit() else 502,
            }
        )
    elif protocol == "modbus_rtu":
        connection.update(
            {
                "serial_port": interface,
                "baudrate": int(candidate.get("baud_rate") or 9600),
                "parity": candidate.get("parity") or "N",
                "stopbits": int(candidate.get("stopbits") or 1),
            }
        )
    return connection


@transaction.atomic
def append_setup_event(
    run: DeploymentSetupRun,
    event_type: str,
    message: str,
    *,
    item: DeploymentSetupItem | None = None,
    evidence: dict | None = None,
    actor=None,
) -> DeploymentSetupEvent:
    locked_run = DeploymentSetupRun.objects.select_for_update().get(pk=run.pk)
    previous = locked_run.events.order_by("-sequence_number").first()
    return DeploymentSetupEvent.objects.create(
        run=locked_run,
        item=item,
        sequence_number=(previous.sequence_number + 1 if previous else 1),
        event_type=event_type,
        message=message,
        evidence=evidence or {},
        actor=actor if getattr(actor, "is_authenticated", False) else None,
    )


@transaction.atomic
def get_or_create_setup_run(*, team, gateway: Gateway, initiated_by=None) -> DeploymentSetupRun:
    active = (
        DeploymentSetupRun.objects.select_for_update()
        .filter(team=team, gateway=gateway)
        .exclude(state__in=TERMINAL_RUN_STATES)
        .order_by("-created_at")
        .first()
    )
    if active:
        return active
    run = DeploymentSetupRun.objects.create(
        team=team,
        site=gateway.site,
        gateway=gateway,
        state=DeploymentSetupRun.State.GATEWAY_CHECK,
        current_step="gateway",
        initiated_by=initiated_by if getattr(initiated_by, "is_authenticated", False) else None,
    )
    append_setup_event(
        run,
        "setup_started",
        "Guided Setup started.",
        actor=initiated_by,
        evidence={"gateway_serial": gateway.serial_number},
    )
    return run


def gateway_readiness(gateway: Gateway) -> dict:
    freshness = gateway.freshness
    capability_ready = "guided_setup_v1" in set(gateway.gateway_capabilities or [])
    checks = [
        {
            "key": "gateway_online",
            "label": "Gateway online",
            "status": "pass" if freshness.status == "live" else "fail",
            "message": freshness.display,
            "action": "Check power, Ethernet or Wi-Fi, then retry.",
            "blocking": True,
        },
        {
            "key": "mqtt_connected",
            "label": "Secure cloud connection",
            "status": "pass" if gateway.mqtt_connected else "fail",
            "message": (
                "Secure cloud connection established."
                if gateway.mqtt_connected
                else "The Gateway is not connected to the Novena service."
            ),
            "action": "Check the site internet connection and ask IT to allow secure Novena traffic.",
            "blocking": True,
        },
        {
            "key": "tls",
            "label": "Connection security",
            "status": "pass" if gateway.tls_ok is not False else "fail",
            "message": (
                "Secure connection verified."
                if gateway.tls_ok is not False
                else "The secure connection could not be verified."
            ),
            "action": (
                "Check the Gateway date and time. If the problem continues, "
                "ask a technician to check its security certificate."
            ),
            "blocking": True,
        },
        {
            "key": "firmware",
            "label": "Gateway software",
            "status": "pass" if gateway.firmware_version else "warning",
            "message": (
                f"Gateway software {gateway.firmware_version} detected."
                if gateway.firmware_version
                else "The Gateway has not reported its software version yet."
            ),
            "action": "Wait for the next heartbeat or restart the Gateway.",
            "blocking": False,
        },
        {
            "key": "guided_setup",
            "label": "Guided setup",
            "status": "pass" if capability_ready else "warning",
            "message": (
                "Secure Guided Setup is available."
                if capability_ready
                else "This Gateway can continue with basic setup, but some guided checks are unavailable."
            ),
            "action": "Ask a technician to update the Gateway software before the next commissioning visit.",
            "blocking": False,
        },
        {
            "key": "interfaces",
            "label": "Equipment interfaces",
            "status": "pass" if gateway.active_interface else "warning",
            "message": (
                "An equipment connection is available."
                if gateway.active_interface
                else "The Gateway has not detected an equipment connection."
            ),
            "action": "Reconnect the equipment interface, then rerun readiness checks.",
            "blocking": False,
        },
    ]
    return {
        "status": "blocked" if any(c["blocking"] and c["status"] == "fail" for c in checks) else "ready",
        "checks": checks,
        "technical_evidence": {
            "internet_reachable": gateway.internet_reachable,
            "dns_ok": gateway.dns_ok,
            "broker_tcp_ok": gateway.broker_tcp_ok,
            "tls_ok": gateway.tls_ok,
            "mqtt_connected": gateway.mqtt_connected,
            "buffered_event_count": gateway.buffered_event_count,
        },
    }


def create_or_update_candidate_item(*, run, index: int, candidate: dict) -> DeploymentSetupItem:
    score = min(100, max(0, int(candidate.get("matched_template_score") or 0)))
    item, _ = DeploymentSetupItem.objects.update_or_create(
        run=run,
        discovery_index=index,
        defaults={
            "team": run.team,
            "candidate_data": candidate,
            "confidence_score": score,
            "confidence_explanation": confidence_explanation(candidate),
            "connection": connection_from_candidate(candidate),
        },
    )
    return item


def start_validation(*, item: DeploymentSetupItem, template, requested_by):
    from .remote_control import request_remote_command

    item.selected_template = template
    item.trust_level = trust_level_for_template(template)
    item.datapoints = normalized_datapoints(template)
    item.state = DeploymentSetupItem.State.VALIDATING
    item.save()
    command = request_remote_command(
        gateway=item.run.gateway,
        operation="deployment_validate",
        requested_by=requested_by,
        params={
            "protocol": template.protocol,
            "connection": item.connection,
            "datapoints": [
                {
                    "key": point["key"],
                    "address": point["address"],
                    "functionCode": point["functionCode"],
                    "objectsCount": point["objectsCount"],
                    "data_type": point["data_type"],
                    "scale": point["scale"],
                    "offset": point["offset"],
                    "unit": point["unit"],
                    "quality": point["quality"],
                }
                for point in item.datapoints
                if point["access"] == "read"
            ][:20],
        },
        reason="Validate equipment during Guided Setup",
        ttl_seconds=120,
    )
    item.validation_command = command
    item.save(update_fields=["validation_command", "updated_at"])
    append_setup_event(
        item.run,
        "validation_started",
        f"Checking live signals for {template.name}.",
        item=item,
        actor=requested_by,
        evidence={"command_id": str(command.pk), "template_id": template.pk},
    )
    return command


def sync_setup_run(run: DeploymentSetupRun) -> DeploymentSetupRun:
    """Fold asynchronous command/config/telemetry evidence into setup state."""
    run = DeploymentSetupRun.objects.select_related("gateway", "site").get(pk=run.pk)
    preflight = (
        RpcCommand.objects.filter(
            gateway=run.gateway,
            method="deployment_preflight",
            sent_at__gte=run.created_at,
        )
        .order_by("-sent_at")
        .first()
    )
    if preflight and preflight.status in {"success", "error", "timeout"}:
        if preflight.status == "success" and isinstance(preflight.result, dict):
            run.readiness = preflight.result
            run.save(update_fields=["readiness", "updated_at"])
            if not run.events.filter(event_type="gateway_preflight_completed").exists():
                append_setup_event(
                    run,
                    "gateway_preflight_completed",
                    preflight.result.get("message") or "Gateway readiness checks completed.",
                    evidence=redact_support_evidence(preflight.result),
                )
        elif not run.events.filter(event_type="gateway_preflight_failed").exists():
            append_setup_event(
                run,
                "gateway_preflight_failed",
                customer_safe_error(preflight.error_message),
                evidence={"retryable": True},
            )

    discovery = run.gateway.discovery_data or {}
    discovery_status = discovery.get("status")
    if run.state == DeploymentSetupRun.State.DISCOVERING and discovery_status in {
        "complete",
        "cancelled",
    }:
        run.state = DeploymentSetupRun.State.CONFIGURING
        run.current_step = "equipment"
        event_type = "discovery_cancelled" if discovery_status == "cancelled" else "discovery_completed"
        if not run.events.filter(event_type=event_type).exists():
            append_setup_event(
                run,
                event_type,
                (
                    "Equipment discovery was cancelled. Partial results were preserved."
                    if discovery_status == "cancelled"
                    else f"Equipment discovery found {len(discovery.get('devices') or [])} candidate(s)."
                ),
                evidence={
                    "device_count": len(discovery.get("devices") or []),
                    "error_count": len(discovery.get("errors") or []),
                },
            )

    for item in run.items.select_related("device", "selected_template", "validation_command"):
        if item.state == DeploymentSetupItem.State.VALIDATING and item.validation_command_id:
            rpc = RpcCommand.objects.filter(remote_command=item.validation_command).order_by("-sent_at").first()
            if rpc and rpc.status in {"success", "error", "timeout"}:
                result = rpc.result or {}
                item.validation_result = {
                    **result,
                    "transport_status": rpc.status,
                    "error": customer_safe_error(
                        rpc.error_message,
                        target=item.device.port if item.device else "",
                    )
                    if rpc.error_message
                    else result.get("error", ""),
                    "technical_error": rpc.error_message,
                }
                if rpc.status == "success" and result.get("status") == "success":
                    item.state = DeploymentSetupItem.State.VALIDATED
                    item.trust_level = (
                        DeploymentSetupItem.Trust.NOVENA_VERIFIED
                        if item.selected_template and item.selected_template.is_verified
                        else DeploymentSetupItem.Trust.CUSTOMER_VALIDATED
                    )
                    message = result.get("message") or "Selected live signals were read successfully."
                    event_type = "validation_succeeded"
                    if item.device:
                        metadata = dict(item.device.metadata or {})
                        metadata["guided_setup_validation"] = "validated"
                        item.device.metadata = metadata
                        item.device.save(update_fields=["metadata", "updated_at"])
                else:
                    item.state = DeploymentSetupItem.State.NEEDS_ATTENTION
                    message = (
                        result.get("message") or rpc.error_message or "Novena could not validate the selected signals."
                    )
                    event_type = "validation_failed"
                    if item.device:
                        metadata = dict(item.device.metadata or {})
                        metadata["guided_setup_validation"] = "failed"
                        item.device.metadata = metadata
                        item.device.save(update_fields=["metadata", "updated_at"])
                item.save()
                append_setup_event(run, event_type, message, item=item, evidence=item.validation_result)

        if (
            item.device_id
            and item.device.last_telemetry_at
            and item.state
            in {
                DeploymentSetupItem.State.APPLIED,
            }
        ):
            item.state = DeploymentSetupItem.State.TELEMETRY_CONFIRMED
            item.first_telemetry_at = item.device.last_telemetry_at
            item.save(update_fields=["state", "first_telemetry_at", "updated_at"])
            generate_default_dashboard(item.device)
            append_setup_event(
                run,
                "first_telemetry_received",
                f"Live data arrived from {item.device.name}; its dashboard is ready.",
                item=item,
            )

    latest_config = run.configurations.first()
    if latest_config:
        if latest_config.status in {"queued", "delivered", "accepted"}:
            run.state = DeploymentSetupRun.State.DEPLOYING
            run.current_step = "verify"
            event_type = f"configuration_{latest_config.status}"
            if not run.events.filter(event_type=event_type).exists():
                append_setup_event(
                    run,
                    event_type,
                    {
                        "queued": "Configuration is queued for secure delivery.",
                        "delivered": "The Gateway received the configuration.",
                        "accepted": "The Gateway accepted and is validating the configuration.",
                    }[latest_config.status],
                    evidence={
                        "request_id": str(latest_config.request_id),
                        "revision": latest_config.revision,
                        "checksum": latest_config.checksum,
                    },
                )
        elif latest_config.status == "active":
            run.items.filter(state=DeploymentSetupItem.State.QUEUED).update(state=DeploymentSetupItem.State.APPLIED)
            run.state = DeploymentSetupRun.State.VERIFYING
            run.current_step = "verify"
            if not run.events.filter(event_type="configuration_active").exists():
                append_setup_event(
                    run,
                    "configuration_active",
                    "Connectors started and equipment communication was established.",
                    evidence={
                        "request_id": str(latest_config.request_id),
                        "connector_results": latest_config.connector_results,
                    },
                )
            if not run.events.filter(event_type="alerts_ready_for_review").exists():
                append_setup_event(
                    run,
                    "alerts_ready_for_review",
                    "Recommended alerts are ready for customer review.",
                )
            telemetry_deadline = latest_config.acknowledged_at or latest_config.pushed_at
            timeout_seconds = int(getattr(settings, "GUIDED_SETUP_FIRST_TELEMETRY_TIMEOUT_SECONDS", 180))
            if telemetry_deadline and timezone.now() >= telemetry_deadline + timedelta(seconds=timeout_seconds):
                for item in run.items.filter(
                    state=DeploymentSetupItem.State.APPLIED,
                    first_telemetry_at__isnull=True,
                ):
                    item.state = DeploymentSetupItem.State.NEEDS_ATTENTION
                    item.save(update_fields=["state", "updated_at"])
                    if not run.events.filter(
                        event_type="first_telemetry_timeout",
                        item=item,
                    ).exists():
                        append_setup_event(
                            run,
                            "first_telemetry_timeout",
                            f"Live data has not arrived from {item.device.name}; check its connection and retry.",
                            item=item,
                            evidence={"retryable": True},
                        )
        elif latest_config.status == "rolled_back":
            run.items.filter(state__in=[DeploymentSetupItem.State.QUEUED, DeploymentSetupItem.State.APPLIED]).update(
                state=DeploymentSetupItem.State.ROLLED_BACK
            )
            run.state = DeploymentSetupRun.State.FAILED
            if not run.events.filter(event_type="configuration_rolled_back").exists():
                append_setup_event(
                    run,
                    "configuration_rolled_back",
                    "The configuration failed and the Gateway restored its last working configuration.",
                    evidence={
                        "request_id": str(latest_config.request_id),
                        "error_code": latest_config.error_code,
                    },
                )
        elif latest_config.status == "failed":
            run.items.filter(state=DeploymentSetupItem.State.QUEUED).update(state=DeploymentSetupItem.State.FAILED)
            run.state = DeploymentSetupRun.State.FAILED
            if not run.events.filter(event_type="configuration_failed").exists():
                append_setup_event(
                    run,
                    "configuration_failed",
                    latest_config.error_message or "The Gateway could not activate this configuration.",
                    evidence={
                        "request_id": str(latest_config.request_id),
                        "error_code": latest_config.error_code,
                    },
                )

    states = list(run.items.values_list("state", flat=True))
    if states and all(state == DeploymentSetupItem.State.TELEMETRY_CONFIRMED for state in states):
        run.state = DeploymentSetupRun.State.COMPLETED
        run.current_step = "go_live"
        run.completed_at = timezone.now()
    elif DeploymentSetupItem.State.TELEMETRY_CONFIRMED in states and any(
        state
        in {
            DeploymentSetupItem.State.NEEDS_ATTENTION,
            DeploymentSetupItem.State.FAILED,
            DeploymentSetupItem.State.ROLLED_BACK,
        }
        for state in states
    ):
        run.state = DeploymentSetupRun.State.COMPLETED_ATTENTION
        run.current_step = "go_live"
        run.completed_at = timezone.now()
    elif states and all(
        state
        in {
            DeploymentSetupItem.State.NEEDS_ATTENTION,
            DeploymentSetupItem.State.FAILED,
            DeploymentSetupItem.State.ROLLED_BACK,
        }
        for state in states
    ):
        run.state = DeploymentSetupRun.State.FAILED
        run.current_step = "verify"
    run.save(update_fields=["state", "current_step", "completed_at", "updated_at"])
    return run


def deployment_progress(run: DeploymentSetupRun) -> list[dict]:
    latest_config = run.configurations.first()
    config_status = latest_config.status if latest_config else ""
    status_order = {
        "": -1,
        "queued": 0,
        "delivered": 1,
        "accepted": 2,
        "active": 3,
        "failed": 3,
        "rolled_back": 3,
    }
    level = status_order.get(config_status, -1)
    item_states = set(run.items.values_list("state", flat=True))
    telemetry_ready = DeploymentSetupItem.State.TELEMETRY_CONFIRMED in item_states
    equipment_ready = bool(
        item_states
        & {
            DeploymentSetupItem.State.APPLIED,
            DeploymentSetupItem.State.TELEMETRY_CONFIRMED,
        }
    )
    failed = config_status in {"failed", "rolled_back"}

    def state(completed):
        if completed:
            return "complete"
        if failed:
            return "attention"
        return "pending"

    return [
        {"label": "Configuration queued", "status": state(level >= 0)},
        {"label": "Gateway received configuration", "status": state(level >= 1)},
        {"label": "Configuration validated", "status": state(level >= 3 and not failed)},
        {"label": "Connectors started", "status": state(level >= 3 and not failed)},
        {"label": "Equipment communication established", "status": state(equipment_ready)},
        {"label": "First telemetry received", "status": state(telemetry_ready)},
        {"label": "Dashboard generated", "status": state(telemetry_ready)},
        {"label": "Alerts ready for review", "status": state(level >= 3 and not failed)},
    ]


def support_bundle(run: DeploymentSetupRun) -> dict:
    run = sync_setup_run(run)
    latest_config = run.configurations.first()
    return {
        "support_reference": str(run.run_id),
        "state": run.state,
        "site": run.site.name,
        "gateway": {
            "name": run.gateway.name,
            "serial_number": run.gateway.serial_number,
            "firmware_version": run.gateway.firmware_version,
            "capabilities": run.gateway.gateway_capabilities,
        },
        "readiness": run.readiness or gateway_readiness(run.gateway),
        "equipment": [
            {
                "name": item.device.name if item.device else item.candidate_data.get("signature"),
                "state": item.state,
                "confidence": item.confidence_score,
                "confidence_explanation": item.confidence_explanation,
                "template": item.selected_template.name if item.selected_template else None,
                "trust": item.trust_level,
                "validation": redact_support_evidence(item.validation_result),
                "first_telemetry_at": item.first_telemetry_at,
            }
            for item in run.items.select_related("device", "selected_template")
        ],
        "configuration": {
            "request_id": str(latest_config.request_id) if latest_config else None,
            "revision": latest_config.revision if latest_config else None,
            "checksum": latest_config.checksum if latest_config else None,
            "status": latest_config.status if latest_config else None,
            "connector_results": redact_support_evidence(latest_config.connector_results) if latest_config else [],
            "rollback_connector_results": redact_support_evidence(latest_config.rollback_connector_results)
            if latest_config
            else [],
            "rollback_performed": latest_config.rollback_performed if latest_config else False,
            "error_code": latest_config.error_code if latest_config else "",
            "error_message": latest_config.error_message if latest_config else "",
            "technical_error": redact_support_evidence(latest_config.technical_error) if latest_config else "",
        },
        "timeline": [
            {
                "sequence": event.sequence_number,
                "type": event.event_type,
                "message": event.message,
                "created_at": event.created_at,
            }
            for event in run.events.all()
        ],
    }
