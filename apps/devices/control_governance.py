from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from apps.teams.models import Membership

from .models import (
    CommandPolicy,
    CommissionedControlEnvelope,
    GatewayControlPolicyBundle,
    RemoteCommand,
    RemoteControlScope,
    TemplateControlDefinition,
)
from .remote_control_crypto import payload_checksum, sign_policy_bundle


class GovernanceDenied(ValueError):
    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class EffectiveControlEnvelope:
    template: TemplateControlDefinition
    commissioned: CommissionedControlEnvelope
    policy: CommandPolicy
    limits: dict
    prerequisites: list

    def snapshot(self) -> dict:
        return {
            "template_definition_id": self.template.pk,
            "template_revision": self.template.revision,
            "template_checksum": self.template.checksum,
            "commissioning_id": self.commissioned.pk,
            "commissioning_revision": self.commissioned.revision,
            "commissioning_checksum": self.commissioned.checksum,
            "policy_id": self.policy.pk,
            "policy_revision": self.policy.revision,
            "policy_checksum": self.policy.checksum,
            "limits": self.limits,
            "prerequisites": self.prerequisites,
            "approval_required": self.policy.approval_required,
        }


def _latest(queryset):
    return queryset.order_by("-revision").first()


def _number(value, label):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise GovernanceDenied(f"{label} must be numeric.", code="invalid_data_type") from exc


def _intersect_limits(*sources: dict) -> dict:
    minima = [source["min"] for source in sources if source.get("min") is not None]
    maxima = [source["max"] for source in sources if source.get("max") is not None]
    enum_sets = [set(source["enum"]) for source in sources if source.get("enum") is not None]
    result = {}
    if minima:
        result["min"] = float(max(_number(value, "Minimum") for value in minima))
    if maxima:
        result["max"] = float(min(_number(value, "Maximum") for value in maxima))
    if result.get("min") is not None and result.get("max") is not None and result["min"] > result["max"]:
        raise GovernanceDenied("Configured safety envelopes do not overlap.", code="empty_policy_intersection")
    if enum_sets:
        allowed = set.intersection(*enum_sets)
        if not allowed:
            raise GovernanceDenied("Configured allowed-value sets do not overlap.", code="empty_policy_intersection")
        result["enum"] = sorted(allowed, key=str)
    for field in ("max_delta", "max_rate", "cooldown_seconds"):
        values = [source[field] for source in sources if source.get(field) is not None]
        if values:
            result[field] = float(min(_number(value, field) for value in values))
    return result


def effective_control_envelope(*, device, command_key: str, user) -> EffectiveControlEnvelope:
    scope = RemoteControlScope.objects.filter(
        team=device.team,
        site=device.site,
        gateway=device.gateway,
        device=device,
        command_key=command_key,
        mode=RemoteControlScope.Mode.ENABLED,
        control_epoch=device.team.remote_control_epoch,
    ).first()
    if not scope:
        raise GovernanceDenied("This exact device key has not been activated.", code="activation_missing")
    if not device.template_id:
        raise GovernanceDenied("Control requires an exact verified device template.", code="missing_template")
    template = _latest(
        TemplateControlDefinition.objects.filter(
            template=device.template,
            command_key=command_key,
            operation="write_device",
            is_verified=True,
            is_enabled=True,
        )
    )
    commissioned = _latest(
        CommissionedControlEnvelope.objects.filter(
            team=device.team,
            device=device,
            command_key=command_key,
            is_active=True,
        )
    )
    policy = _latest(
        CommandPolicy.objects.filter(
            team=device.team,
            device=device,
            command_key=command_key,
            is_enabled=True,
        )
    )
    if not template:
        raise GovernanceDenied(
            "No verified technical control definition is enabled.",
            code="technical_definition_missing",
        )
    if not commissioned or (commissioned.expires_at and commissioned.expires_at <= timezone.now()):
        raise GovernanceDenied("The control key is not actively commissioned.", code="commissioning_missing")
    if not policy:
        raise GovernanceDenied("The customer has not enabled a command policy for this key.", code="policy_missing")
    membership = Membership.objects.filter(team=device.team, user=user).first()
    if not membership or membership.role not in policy.allowed_roles:
        raise GovernanceDenied("Your role is not allowed by the customer command policy.", code="policy_role_denied")

    limits = _intersect_limits(
        template.technical_limits,
        commissioned.operating_limits,
        policy.customer_limits,
    )
    prerequisites = template.prerequisites + commissioned.prerequisites + policy.prerequisites
    return EffectiveControlEnvelope(template, commissioned, policy, limits, prerequisites)


def validate_control_value(*, envelope: EffectiveControlEnvelope, value, device) -> tuple[object, object]:
    data_type = envelope.template.data_type.lower()
    if data_type in {"int", "integer", "uint16", "int16", "uint32", "int32"}:
        numeric = _number(value, "Value")
        if numeric != numeric.to_integral_value():
            raise GovernanceDenied("Value must be an integer.", code="invalid_data_type")
        normalized = int(numeric)
    elif data_type in {"float", "float32", "float64", "number", "decimal"}:
        normalized = float(_number(value, "Value"))
    elif data_type in {"bool", "boolean"}:
        if not isinstance(value, bool):
            raise GovernanceDenied("Value must be true or false.", code="invalid_data_type")
        normalized = value
    elif data_type in {"str", "string", "enum"}:
        if not isinstance(value, str):
            raise GovernanceDenied("Value must be text.", code="invalid_data_type")
        normalized = value
    else:
        raise GovernanceDenied("Unsupported control data type.", code="invalid_data_type")

    limits = envelope.limits
    if limits.get("enum") is not None and normalized not in limits["enum"]:
        raise GovernanceDenied("Value is not in the effective allowed set.", code="value_not_allowed")
    if limits.get("min") is not None and _number(normalized, "Value") < _number(limits["min"], "Minimum"):
        raise GovernanceDenied("Value is below the effective safe minimum.", code="value_below_minimum")
    if limits.get("max") is not None and _number(normalized, "Value") > _number(limits["max"], "Maximum"):
        raise GovernanceDenied("Value is above the effective safe maximum.", code="value_above_maximum")

    current = (device.metadata or {}).get("last_values", {}).get(envelope.template.command_key)
    if (
        current is not None
        and limits.get("max_delta") is not None
        and (
            abs(_number(normalized, "Value") - _number(current, "Current value"))
            > _number(limits["max_delta"], "Maximum delta")
        )
    ):
        raise GovernanceDenied("Requested change exceeds the effective delta limit.", code="delta_exceeded")
    if limits.get("cooldown_seconds"):
        recent = (
            RemoteCommand.objects.filter(
                device=device,
                command_key=envelope.template.command_key,
                status__in=[
                    RemoteCommand.Status.PUBLISH_ACCEPTED,
                    RemoteCommand.Status.GATEWAY_RECEIVED,
                    RemoteCommand.Status.EXECUTING,
                    RemoteCommand.Status.FIELD_PROTOCOL_ACCEPTED,
                    RemoteCommand.Status.VERIFIED,
                ],
            )
            .order_by("-created_at")
            .first()
        )
        if recent and (timezone.now() - recent.created_at).total_seconds() < limits["cooldown_seconds"]:
            raise GovernanceDenied("Command key is in its configured cooldown period.", code="cooldown_active")

    scale = envelope.template.connector_mapping.get("scale", 1)
    offset = envelope.template.connector_mapping.get("offset", 0)
    encoded = float(_number(normalized, "Value") * _number(scale, "Scale") + _number(offset, "Offset"))
    if data_type in {"int", "integer", "uint16", "int16", "uint32", "int32"} and encoded.is_integer():
        encoded = int(encoded)
    return normalized, encoded


def definition_checksum(definition: dict) -> str:
    return payload_checksum(definition)


def create_gateway_policy_bundle(gateway) -> GatewayControlPolicyBundle:
    controls = {}
    policies = (
        CommandPolicy.objects.filter(
            team=gateway.team,
            gateway=gateway,
            device__gateway=gateway,
            is_enabled=True,
        )
        .select_related("device__template")
        .order_by("device_id", "command_key", "-revision")
    )
    seen = set()
    for policy in policies:
        identity = (policy.device_id, policy.command_key)
        if identity in seen:
            continue
        seen.add(identity)
        membership = policy.team.membership_set.filter(role__in=policy.allowed_roles).first()
        if not membership:
            continue
        try:
            envelope = effective_control_envelope(
                device=policy.device,
                command_key=policy.command_key,
                user=membership.user,
            )
        except GovernanceDenied:
            continue
        controls[f"{policy.device_id}:{policy.command_key}"] = {
            "device_id": str(policy.device_id),
            "command_key": policy.command_key,
            "mapping": envelope.template.connector_mapping,
            "data_type": envelope.template.data_type,
            "unit": envelope.template.unit,
            "limits": envelope.limits,
            "prerequisites": envelope.prerequisites,
            "revisions": {
                "template": envelope.template.revision,
                "commissioning": envelope.commissioned.revision,
                "policy": envelope.policy.revision,
            },
            "policy_checksum": envelope.policy.checksum,
        }
    latest = GatewayControlPolicyBundle.objects.filter(gateway=gateway).order_by("-revision").first()
    payload = {
        "schema_version": 1,
        "gateway_serial": gateway.serial_number,
        "revision": (latest.revision + 1) if latest else 1,
        "control_epoch": gateway.team.remote_control_epoch,
        "generated_at": timezone.now().isoformat(),
        "controls": controls,
    }
    signed = sign_policy_bundle(payload)
    return GatewayControlPolicyBundle.objects.create(
        team=gateway.team,
        gateway=gateway,
        revision=payload["revision"],
        control_epoch=payload["control_epoch"],
        payload=payload,
        checksum=signed["checksum"],
        signing_key_id=signed["signing_key_id"],
        signature=signed["signature"],
    )
