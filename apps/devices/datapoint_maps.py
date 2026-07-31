"""Canonical per-device datapoint maps for programmable equipment."""

from __future__ import annotations

import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import DeviceDatapointMap

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,99}$")
DATA_TYPES = {"bool", "uint16", "int16", "uint32", "int32", "float32", "uint64", "int64", "float64"}
DISPLAY_TYPES = {"value", "gauge", "trend", "status"}
ACCESS_TYPES = {"read_only", "read_write"}
READ_FUNCTION_CODES = {1, 2, 3, 4}
WRITE_FUNCTION_CODES = {5, 6, 15, 16}


def device_requires_mapping(device) -> bool:
    return bool(device.template and device.template.mapping_strategy == "site_defined")


def _integer(value, *, field, minimum, maximum):
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: "Enter a whole number."}) from exc
    if not minimum <= parsed <= maximum:
        raise ValidationError({field: f"Enter a value from {minimum} to {maximum}."})
    return parsed


def _number(value, *, field, default=None):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: "Enter a valid number."}) from exc


def normalize_datapoints(datapoints) -> list[dict]:
    """Validate and normalize user-entered Modbus datapoints."""
    if not isinstance(datapoints, list) or not datapoints:
        raise ValidationError("Add at least one signal.")
    if len(datapoints) > 20:
        raise ValidationError("A device can contain at most 20 signals in Guided Setup.")

    normalized = []
    seen = set()
    for position, raw in enumerate(datapoints, start=1):
        if not isinstance(raw, dict):
            raise ValidationError(f"Signal {position} is invalid.")
        key = re.sub(r"[^a-z0-9_]+", "_", str(raw.get("key") or "").strip().lower()).strip("_")
        if not KEY_RE.fullmatch(key):
            raise ValidationError(f"Signal {position}: use a key such as process_temperature.")
        if key in seen:
            raise ValidationError(f"Signal key '{key}' is duplicated.")
        seen.add(key)

        data_type = str(raw.get("data_type") or raw.get("type") or "uint16").lower()
        if data_type not in DATA_TYPES:
            raise ValidationError(f"Signal '{key}' has an unsupported data type.")
        read_function_code = _integer(
            raw.get("read_function_code", raw.get("functionCode", 3)),
            field="read_function_code",
            minimum=1,
            maximum=4,
        )
        if read_function_code not in READ_FUNCTION_CODES:
            raise ValidationError(f"Signal '{key}' must use a read-only Modbus function code.")
        default_count = 4 if "64" in data_type else 2 if "32" in data_type else 1
        objects_count = _integer(
            raw.get("objects_count") or raw.get("objectsCount") or default_count,
            field="objects_count",
            minimum=1,
            maximum=4,
        )
        if objects_count < default_count:
            raise ValidationError(f"Signal '{key}' needs at least {default_count} Modbus object(s).")
        access = str(raw.get("access") or ("read_write" if raw.get("writable") else "read_only"))
        if access not in ACCESS_TYPES:
            raise ValidationError(f"Signal '{key}' has an invalid access setting.")
        write_function_code = None
        if access == "read_write":
            default_write = 5 if data_type == "bool" else (16 if objects_count > 1 else 6)
            write_function_code = _integer(
                raw.get("write_function_code") or raw.get("writeFunctionCode") or default_write,
                field="write_function_code",
                minimum=5,
                maximum=16,
            )
            if write_function_code not in WRITE_FUNCTION_CODES:
                raise ValidationError(f"Signal '{key}' has an invalid write function code.")

        default_display = "status" if data_type == "bool" else "value"
        display_type = str(raw.get("display_type") or default_display)
        if display_type not in DISPLAY_TYPES:
            raise ValidationError(f"Signal '{key}' has an invalid display type.")
        multiplier = _number(raw.get("multiplier", raw.get("scale", 1)), field="multiplier", default=1.0)
        if multiplier == 0:
            raise ValidationError(f"Signal '{key}' multiplier cannot be zero.")
        offset = _number(raw.get("offset", 0), field="offset", default=0.0)
        normal_min = _number(raw.get("normal_min"), field="normal_min")
        normal_max = _number(raw.get("normal_max"), field="normal_max")
        safety_min = _number(raw.get("safety_min", raw.get("min")), field="safety_min")
        safety_max = _number(raw.get("safety_max", raw.get("max")), field="safety_max")
        if normal_min is not None and normal_max is not None and normal_min > normal_max:
            raise ValidationError(f"Signal '{key}' normal minimum cannot exceed its maximum.")
        if safety_min is not None and safety_max is not None and safety_min > safety_max:
            raise ValidationError(f"Signal '{key}' safety minimum cannot exceed its maximum.")

        normalized.append(
            {
                "key": key,
                "label": str(raw.get("label") or key.replace("_", " ").title()).strip()[:200],
                "address": _integer(raw.get("address", 0), field="address", minimum=0, maximum=65535),
                "read_function_code": read_function_code,
                "data_type": data_type,
                "objects_count": objects_count,
                "unit": str(raw.get("unit") or "").strip()[:32],
                "multiplier": multiplier,
                "offset": offset,
                "access": access,
                "write_function_code": write_function_code,
                "display_type": display_type,
                "normal_min": normal_min,
                "normal_max": normal_max,
                "safety_min": safety_min,
                "safety_max": safety_max,
                "alert_suggestion": str(raw.get("alert_suggestion") or "").strip()[:300],
            }
        )
    return normalized


def register_map_to_datapoints(register_map) -> list[dict]:
    rows = []
    for key, config in (register_map or {}).items():
        if not isinstance(config, dict):
            continue
        legacy_function_code = config.get("functionCode", 3)
        read_function_code = config.get("readFunctionCode")
        if read_function_code is None:
            read_function_code = legacy_function_code if legacy_function_code in READ_FUNCTION_CODES else (
                1 if config.get("type") == "bool" else 3
            )
        write_function_code = config.get("writeFunctionCode")
        if write_function_code is None and legacy_function_code in WRITE_FUNCTION_CODES:
            write_function_code = legacy_function_code
        rows.append(
            {
                "key": key,
                "label": config.get("label") or key.replace("_", " ").title(),
                "address": config.get("address", 0),
                "read_function_code": read_function_code,
                "data_type": config.get("type", "uint16"),
                "objects_count": config.get("objectsCount"),
                "unit": config.get("unit", ""),
                "multiplier": config.get("multiplier", config.get("scale", 1)),
                "offset": config.get("offset", 0),
                "access": "read_write" if config.get("writable") else "read_only",
                "write_function_code": write_function_code,
                "display_type": config.get("display_type", "status" if config.get("type") == "bool" else "value"),
                "normal_min": config.get("normal_min"),
                "normal_max": config.get("normal_max"),
                "safety_min": config.get("safety_min", config.get("min")),
                "safety_max": config.get("safety_max", config.get("max")),
                "alert_suggestion": config.get("alert_suggestion", ""),
            }
        )
    return normalize_datapoints(rows) if rows else []


def datapoints_to_register_map(datapoints) -> dict:
    result = {}
    for point in datapoints or []:
        config = {
            "label": point["label"],
            "address": point["address"],
            "functionCode": point["read_function_code"],
            "readFunctionCode": point["read_function_code"],
            "type": point["data_type"],
            "objectsCount": point["objects_count"],
            "unit": point["unit"],
            "multiplier": point["multiplier"],
            "offset": point["offset"],
            "writable": point["access"] == "read_write",
            "poll": True,
            "display_type": point["display_type"],
            "normal_min": point.get("normal_min"),
            "normal_max": point.get("normal_max"),
            "safety_min": point.get("safety_min"),
            "safety_max": point.get("safety_max"),
            "alert_suggestion": point.get("alert_suggestion", ""),
        }
        if point.get("write_function_code"):
            config["writeFunctionCode"] = point["write_function_code"]
        result[point["key"]] = config
    return result


def mapping_checksum(device, datapoints=None) -> str:
    if datapoints is None:
        mapping = getattr(device, "datapoint_map", None)
        datapoints = mapping.datapoints if mapping else []
    payload = {
        "protocol": device.protocol,
        "connection": device.connection_config or {},
        "datapoints": datapoints or [],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(canonical).hexdigest()


def effective_register_map(device, *, require_confirmed=True) -> dict:
    """Return deployable/display metadata without confusing a PLC starter with its site map."""
    if not device_requires_mapping(device):
        if device.template and isinstance(device.template.register_map, dict):
            return device.template.register_map
        return {}
    mapping = DeviceDatapointMap.objects.filter(device_id=device.pk).first()
    if mapping is None:
        return {}
    if require_confirmed:
        if mapping.status != DeviceDatapointMap.Status.CONFIRMED:
            return {}
        if not mapping.confirmed_checksum or mapping.confirmed_checksum != mapping_checksum(device, mapping.datapoints):
            return {}
    return datapoints_to_register_map(mapping.datapoints)


def datapoints_for_device(device, *, require_confirmed=True) -> list[dict]:
    if device_requires_mapping(device):
        mapping = DeviceDatapointMap.objects.filter(device_id=device.pk).first()
        if mapping is None:
            return []
        if require_confirmed and not effective_register_map(device, require_confirmed=True):
            return []
        return list(mapping.datapoints or [])
    return register_map_to_datapoints(device.template.register_map if device.template else {})


@transaction.atomic
def ensure_device_datapoint_map(device) -> DeviceDatapointMap:
    if not device_requires_mapping(device):
        raise ValidationError("This equipment uses a fixed Novena template and does not need a site map.")
    mapping, _ = DeviceDatapointMap.objects.get_or_create(
        team=device.team,
        device=device,
        defaults={"datapoints": register_map_to_datapoints(device.template.register_map)},
    )
    return mapping


@transaction.atomic
def save_device_datapoint_map(*, device, team, datapoints) -> DeviceDatapointMap:
    if device.team_id != team.id:
        raise ValidationError("Equipment does not belong to this team.")
    normalized = normalize_datapoints(datapoints)
    mapping = ensure_device_datapoint_map(device)
    mapping.datapoints = normalized
    mapping.status = DeviceDatapointMap.Status.DRAFT
    mapping.last_validation = {}
    mapping.tested_checksum = ""
    mapping.confirmed_checksum = ""
    mapping.last_tested_at = None
    mapping.confirmed_by = None
    mapping.confirmed_at = None
    mapping.save()
    return mapping


@transaction.atomic
def record_device_datapoint_validation(*, device, result) -> DeviceDatapointMap:
    mapping = ensure_device_datapoint_map(device)
    mapping.last_validation = result if isinstance(result, dict) else {}
    mapping.last_tested_at = timezone.now()
    signals = mapping.last_validation.get("signals") or []
    successful = bool(signals) and len(signals) == len(mapping.datapoints) and all(
        signal.get("status") == "success" for signal in signals
    )
    current_checksum = mapping_checksum(device, mapping.datapoints)
    tested_checksum = str(mapping.last_validation.get("mapping_checksum") or "")
    if mapping.last_validation.get("status") == "success" and successful and tested_checksum == current_checksum:
        mapping.status = DeviceDatapointMap.Status.AWAITING_CONFIRMATION
        mapping.tested_checksum = tested_checksum
    else:
        mapping.status = DeviceDatapointMap.Status.NEEDS_ATTENTION
        mapping.tested_checksum = ""
    mapping.confirmed_checksum = ""
    mapping.confirmed_by = None
    mapping.confirmed_at = None
    mapping.save()
    return mapping


@transaction.atomic
def confirm_device_datapoint_map(*, device, team, confirmed_by) -> DeviceDatapointMap:
    if device.team_id != team.id:
        raise ValidationError("Equipment does not belong to this team.")
    mapping = ensure_device_datapoint_map(device)
    current_checksum = mapping_checksum(device, mapping.datapoints)
    if mapping.status != DeviceDatapointMap.Status.AWAITING_CONFIRMATION:
        raise ValidationError("Run a successful live validation before confirming these signals.")
    if not mapping.tested_checksum or mapping.tested_checksum != current_checksum:
        raise ValidationError("Connection or signal settings changed after the live test. Test them again.")
    mapping.status = DeviceDatapointMap.Status.CONFIRMED
    mapping.confirmed_checksum = current_checksum
    mapping.confirmed_by = confirmed_by if getattr(confirmed_by, "is_authenticated", False) else None
    mapping.confirmed_at = timezone.now()
    mapping.save()
    return mapping


@transaction.atomic
def clone_device_datapoint_map(*, source_device, target_device, team) -> DeviceDatapointMap:
    if source_device.team_id != team.id or target_device.team_id != team.id:
        raise ValidationError("Mappings can only be cloned within the current team.")
    if source_device.protocol != target_device.protocol:
        raise ValidationError("Choose equipment using the same protocol.")
    source = ensure_device_datapoint_map(source_device)
    if source.status != DeviceDatapointMap.Status.CONFIRMED:
        raise ValidationError("Only a confirmed mapping can be cloned.")
    target = save_device_datapoint_map(device=target_device, team=team, datapoints=source.datapoints)
    target.cloned_from = source
    target.save(update_fields=["cloned_from", "updated_at"])
    return target
