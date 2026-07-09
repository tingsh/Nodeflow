import contextlib
import hashlib
import hmac
import json
import logging
import secrets
import uuid

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from .models import DeviceCommand, Gateway, GatewayInventory

logger = logging.getLogger("novena_hub")


def compute_claim_code(serial_number: str) -> str:
    """
    Derive a deterministic claim code from a gateway serial number using HMAC-SHA256.
    The claim code is printed on the gateway sticker and used as the initial MQTT password.
    """
    return hmac.new(
        settings.GATEWAY_CLAIM_SECRET.encode(),
        serial_number.strip().upper().encode(),
        hashlib.sha256,
    ).hexdigest()[:8].upper()


def validate_claim_code(serial_number: str, claim_code: str) -> bool:
    """
    Validate a claim code against a serial number. Pure HMAC check — no DB lookup needed.
    """
    expected = compute_claim_code(serial_number)
    return hmac.compare_digest(expected, claim_code.strip().upper())


class GatewayClaimError(ValueError):
    """Raised when a gateway claim cannot be completed safely."""


def normalize_gateway_serial(serial_number: str) -> str:
    return serial_number.strip().upper()


def validate_gateway_claim(serial_number: str, claim_code: str):
    """Validate a sticker claim against factory inventory and HMAC claim code."""
    serial_number = normalize_gateway_serial(serial_number)
    if not validate_claim_code(serial_number, claim_code):
        raise GatewayClaimError("Invalid claim code. Please check the sticker on the bottom of your gateway.")

    inventory = GatewayInventory.objects.filter(serial_number__iexact=serial_number).first()
    existing_gateway = Gateway.objects.filter(serial_number=serial_number).first()
    if not inventory and not existing_gateway:
        raise GatewayClaimError(
            "This serial number is not in the Novena factory inventory. Please contact support."
        )
    if inventory and inventory.status == "retired":
        raise GatewayClaimError("This gateway has been retired and cannot be claimed.")
    return inventory


def generate_operational_mqtt_password() -> str:
    """Create the random credential the gateway uses after claim activation."""
    return secrets.token_urlsafe(32)


@transaction.atomic
def claim_gateway_for_team(team, site, name: str, serial_number: str, claim_code: str):
    """Bind a manufactured gateway to a customer team/site after sticker validation."""
    serial_number = normalize_gateway_serial(serial_number)
    inventory = validate_gateway_claim(serial_number, claim_code)
    operational_password = generate_operational_mqtt_password()

    existing_gateway = Gateway.objects.select_for_update().filter(serial_number=serial_number).first()
    existing_can_transfer = (
        existing_gateway
        and inventory
        and inventory.status in ("unclaimed", "released")
        and existing_gateway.lifecycle_status == "release_pending"
    )
    if existing_gateway and existing_gateway.team != team and not existing_can_transfer:
        raise GatewayClaimError(
            "This serial number is already registered to another team. Please contact support if this is an error."
        )
    is_new_for_team = not Gateway.objects.filter(team=team, serial_number=serial_number).exists()
    if (not existing_gateway or existing_can_transfer) and is_new_for_team:
        from apps.subscriptions.enforcement import can_add_gateway, get_gateway_limit_for_team

        if not can_add_gateway(team):
            limit = get_gateway_limit_for_team(team)
            raise GatewayClaimError(
                f"Your current plan supports up to {limit} gateway{'s' if limit != 1 else ''}. "
                "Upgrade your plan or release an unused gateway before adding another."
            )

    if inventory:
        inventory = GatewayInventory.objects.select_for_update().get(pk=inventory.pk)
        if inventory.status == "claimed" and inventory.claimed_by_team and inventory.claimed_by_team != team:
            raise GatewayClaimError(
                "This serial number is already registered to another team. Please contact support if this is an error."
            )

    if existing_gateway:
        gateway = existing_gateway
        gateway.team = team
        gateway.site = site
        gateway.name = name
        gateway.mqtt_username = serial_number
        gateway.mqtt_password = make_password(operational_password)
        gateway.mqtt_provisioning_status = "pending"
        gateway.mqtt_provisioning_error = ""
        gateway.credential_rotation_status = "pending"
        if gateway.status == "online":
            gateway.lifecycle_status = "activating"
        elif gateway.lifecycle_status not in ("commissioning", "active"):
            gateway.lifecycle_status = "claimed"
        gateway.save(update_fields=[
            "team", "site", "name", "mqtt_username", "mqtt_password",
            "mqtt_provisioning_status", "mqtt_provisioning_error",
            "credential_rotation_status", "lifecycle_status",
        ])
    else:
        gateway = Gateway.objects.create(
            team=team,
            site=site,
            name=name,
            serial_number=serial_number,
            access_token=secrets.token_hex(20),
            mqtt_username=serial_number,
            mqtt_password=make_password(operational_password),
            mqtt_provisioning_status="pending",
            credential_rotation_status="pending",
            lifecycle_status="claimed",
        )

    if inventory:
        inventory.status = "claimed"
        inventory.claimed_by_team = team
        inventory.gateway = gateway
        if not inventory.claimed_at:
            inventory.claimed_at = timezone.now()
        inventory.save(update_fields=["status", "claimed_by_team", "gateway", "claimed_at"])

    try:
        from .mqtt_provisioning import provision_gateway_mqtt

        provision_gateway_mqtt(gateway, operational_password)
        gateway.mqtt_provisioning_status = "success"
        gateway.mqtt_provisioning_error = ""
        gateway.mqtt_provisioned_at = timezone.now()
        gateway.save(update_fields=["mqtt_provisioning_status", "mqtt_provisioning_error", "mqtt_provisioned_at"])
        try:
            from apps.telemetry.mqtt_publisher import publish_gateway_activation

            publish_gateway_activation(gateway, operational_password)
        except Exception as e:
            logger.info("Gateway activation publish deferred for %s: %s", gateway.serial_number, e)
    except Exception as e:
        gateway.mqtt_provisioning_status = "failed"
        gateway.mqtt_provisioning_error = str(e)
        gateway.save(update_fields=["mqtt_provisioning_status", "mqtt_provisioning_error"])
        logger.warning(
            "Mosquitto provisioning failed for gateway %s: %s (gateway saved, manual setup may be required)",
            gateway.serial_number,
            e,
        )
        if getattr(settings, "MQTT_PROVISIONING_REQUIRED", False):
            raise GatewayClaimError(
                "Gateway ownership verified, but MQTT access could not be provisioned. Please retry."
            ) from e

    return gateway


@transaction.atomic
def release_gateway_for_redo(gateway):
    """
    Release a gateway for customer self-serve onboarding redo.

    The Gateway row is kept so the physical device can fall back to bootstrap mode
    and be re-claimed with the same serial number + printed claim code.
    """
    gateway = Gateway.objects.select_for_update().get(pk=gateway.pk)
    gateway.devices.all().delete()
    gateway.config_history.all().delete()
    gateway.rpc_commands.all().delete()

    inventory = GatewayInventory.objects.select_for_update().filter(gateway=gateway).first()
    if inventory:
        inventory.status = "released"
        inventory.claimed_by_team = None
        inventory.claimed_at = None
        inventory.save(update_fields=["status", "claimed_by_team", "claimed_at"])

    gateway.status = "offline"
    gateway.lifecycle_status = "release_pending"
    gateway.discovery_data = {}
    gateway.config = {}
    gateway.connected_devices = []
    gateway.active_connectors = []
    gateway.mqtt_provisioning_status = "not_started"
    gateway.mqtt_provisioning_error = ""
    gateway.credential_rotation_status = "not_started"
    gateway.last_seen = None
    gateway.save(update_fields=[
        "status", "lifecycle_status", "discovery_data", "config",
        "connected_devices", "active_connectors", "mqtt_provisioning_status",
        "mqtt_provisioning_error", "credential_rotation_status", "last_seen",
    ])
    return gateway


READ_FUNCTION_CODES = {1, 2, 3, 4}
WRITE_FUNCTION_CODES = {5, 6, 15, 16}


def _normalize_command_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        with contextlib.suppress(ValueError):
            return float(value)
    return value


def _register_params_from_template(device, key, command_type, value):
    register = None
    if device.template and device.template.register_map:
        register = device.template.register_map.get(key)

    if not register or "address" not in register:
        if command_type == "write":
            logger.warning(
                "No register map entry for key '%s' on device %s — using fallback FC6/addr0",
                key,
                device.name,
            )
            return {"functionCode": 6, "address": 0, "value": value}
        raise ValueError(f"No readable register map entry found for '{key}'.")

    params = {
        "address": register["address"],
        "functionCode": register.get("functionCode", 6 if command_type == "write" else 3),
    }
    if register.get("type") and register["type"] != "bool":
        params["type"] = register["type"]
    if "objectsCount" in register:
        params["objectsCount"] = register["objectsCount"]
    elif command_type == "read":
        params["objectsCount"] = 1
    if command_type == "write":
        params["value"] = value
    return params


def _validate_device_command_params(command_type, params):
    function_code = params.get("functionCode")
    if function_code is None:
        raise ValueError("Missing functionCode.")
    function_code = int(function_code)
    params["functionCode"] = function_code

    if "address" not in params:
        raise ValueError("Missing register address.")
    params["address"] = int(params["address"])

    if command_type == "write":
        if function_code not in WRITE_FUNCTION_CODES:
            raise ValueError("Write commands must use function code 5, 6, 15, or 16.")
        if "value" not in params:
            raise ValueError("Write commands require a value.")
        params["value"] = _normalize_command_value(params["value"])
    elif command_type == "read":
        if function_code not in READ_FUNCTION_CODES:
            raise ValueError("Read commands must use function code 1, 2, 3, or 4.")
        params["objectsCount"] = int(params.get("objectsCount", 1))
    else:
        raise ValueError("Command type must be 'read' or 'write'.")


def send_device_command(device, user, key, value=None, *, command_type="write", params=None):
    """
    Sends a customer-facing command to a device via the associated gateway.
    DeviceCommand is the customer audit record; RpcCommand is the transport record.
    """
    from apps.telemetry.mqtt_publisher import publish_rpc_command

    if not device.gateway:
        raise ValueError("Device is not assigned to a gateway.")
    if command_type not in {"read", "write"}:
        raise ValueError("Command type must be 'read' or 'write'.")

    value = _normalize_command_value(value)
    command_key = key or f"manual_{command_type}"
    rpc_params = dict(params or _register_params_from_template(device, command_key, command_type, value))
    rpc_params["device_name"] = device.name
    _validate_device_command_params(command_type, rpc_params)

    transaction_id = str(uuid.uuid4())

    command = DeviceCommand.objects.create(
        team=device.team,
        device=device,
        created_by=user,
        command_type=command_type,
        command_key=command_key,
        value=rpc_params.get("value") if command_type == "write" else None,
        transaction_id=transaction_id,
        payload={
            "method": f"{command_type}_device",
            "params": rpc_params,
        },
        status="pending",
    )

    try:
        rpc = publish_rpc_command(
            device.gateway,
            method=f"{command_type}_device",
            params=rpc_params,
        )

        command.payload = {
            "rpc_request_id": str(rpc.request_id),
            "method": f"{command_type}_device",
            "device_name": device.name,
            "params": rpc_params,
        }
        command.rpc_command = rpc
        command.status = "sent"
        command.save(update_fields=["payload", "rpc_command", "status", "updated_at"])
        logger.info(
            "%s command %s sent to %s (tx: %s, rpc: %s)",
            command_type.title(),
            command_key,
            device.name,
            transaction_id,
            rpc.request_id,
        )
        return command
    except Exception as e:
        command.status = "failed"
        command.error_message = str(e)
        command.save(update_fields=["status", "error_message", "updated_at"])
        logger.error("Failed to publish command to MQTT: %s", e)
        raise


def sync_device_command_from_rpc(rpc_record):
    """Mirror a transport-level RpcCommand result onto its customer-facing DeviceCommand."""
    try:
        command = rpc_record.device_command
    except DeviceCommand.DoesNotExist:
        return None

    command.response_payload = {
        "status": rpc_record.status,
        "result": rpc_record.result,
        "error": rpc_record.error_message or "",
    }
    if rpc_record.status == "success":
        command.status = "executed"
        command.error_message = ""
        command.executed_at = rpc_record.responded_at or timezone.now()
    elif rpc_record.status == "timeout":
        command.status = "timed_out"
        command.error_message = rpc_record.error_message or "Timed out waiting for gateway response."
    elif rpc_record.status == "error":
        command.status = "failed"
        command.error_message = rpc_record.error_message or "Gateway command failed."
        command.executed_at = rpc_record.responded_at or timezone.now()
    else:
        return command

    command.save(update_fields=["status", "response_payload", "error_message", "executed_at", "updated_at"])
    return command


def process_command_response(payload_str):
    """
    Processes an incoming command response.
    Supports the current gateway RPC response shape and the legacy id/data shape.
    """
    try:
        payload = json.loads(payload_str)
        request_id = payload.get("request_id")
        if request_id:
            from .models import RpcCommand

            rpc = RpcCommand.objects.filter(request_id=request_id).first()
            if not rpc:
                return
            rpc.status = payload.get("status", "error")
            rpc.result = payload.get("result")
            rpc.error_message = payload.get("error", "") or ""
            rpc.responded_at = timezone.now()
            rpc.save(update_fields=["status", "result", "error_message", "responded_at", "updated_at"])
            sync_device_command_from_rpc(rpc)
            return

        tx_id = payload.get("id")

        if not tx_id:
            return

        command = DeviceCommand.objects.filter(transaction_id=tx_id).first()
        if command:
            command.response_payload = payload
            command.executed_at = timezone.now()

            data = payload.get("data", {})
            if data.get("success") is True or data.get("status") == "OK":
                command.status = "executed"
            else:
                command.status = "failed"
                command.error_message = data.get("error", "Execution failed at edge")

            command.save()
            logger.info(f"Command {command.transaction_id} updated to {command.status}")
    except Exception as e:
        logger.error(f"Error processing command response: {e}")


COMMISSIONING_STAGES = [
    ("site_created", "Site created"),
    ("gateway_claimed", "Gateway claimed"),
    ("gateway_connected", "Gateway connected"),
    ("device_scan_running", "Device scan running"),
    ("devices_discovered", "Devices discovered"),
    ("templates_selected", "Templates selected"),
    ("config_pushed", "Config pushed to gateway"),
    ("first_telemetry_received", "First telemetry received"),
    ("dashboard_ready", "Dashboard ready"),
]


def _session_value(session, key):
    if not session:
        return None
    try:
        return session.get(key)
    except AttributeError:
        return None


def _gateway_from_context(team, gateway=None, session=None):
    if gateway:
        return gateway
    gateway_id = _session_value(session, "onboarding_gateway_id")
    if gateway_id:
        return Gateway.objects.filter(id=gateway_id, team=team).select_related("site").first()
    return Gateway.objects.filter(team=team).select_related("site").order_by("-created_at").first()


def _site_from_context(team, gateway=None, session=None):
    if gateway:
        return gateway.site
    site_id = _session_value(session, "onboarding_site_id")
    if site_id:
        return team.site_set.filter(id=site_id).first()
    return team.site_set.order_by("created_at").first()


def _commissioning_candidates(gateway):
    if not gateway:
        return []

    from .models import DeviceTemplate

    registered_ports = {
        str(device.port): device.name
        for device in gateway.devices.exclude(port__isnull=True).exclude(port="")
    }
    candidates = []
    for index, discovery in enumerate((gateway.discovery_data or {}).get("devices", [])):
        interface = str(discovery.get("interface") or discovery.get("port") or "")
        matched_template = None
        matched_template_id = discovery.get("matched_template_id")
        if matched_template_id:
            matched_template = DeviceTemplate.objects.filter(id=matched_template_id).first()
        status = "ready" if matched_template else "needs_template"
        if interface and interface in registered_ports:
            status = "registered"
        candidates.append({
            "index": index,
            "interface": interface,
            "signature": discovery.get("signature") or "Unknown device",
            "connection": discovery.get("connection") or "unknown",
            "slave_id": discovery.get("slave_id"),
            "baud_rate": discovery.get("baud_rate"),
            "matched_template": matched_template,
            "matched_template_name": discovery.get("matched_template_name") or (matched_template.name if matched_template else ""),
            "status": status,
            "recommended": status == "ready",
            "raw": discovery,
        })
    return candidates


def build_commissioning_context(team, gateway=None, session=None):
    """Return a normalized, template-friendly commissioning state for onboarding and gateway pages."""
    gateway = _gateway_from_context(team, gateway=gateway, session=session)
    site = _site_from_context(team, gateway=gateway, session=session)
    devices = list(gateway.devices.select_related("template", "site") if gateway else [])
    candidates = _commissioning_candidates(gateway)
    latest_config = gateway.config_history.first() if gateway else None
    first_live_device = next((device for device in devices if device.last_telemetry_at), None)

    completed = []
    if site:
        completed.append("site_created")
    if gateway:
        completed.append("gateway_claimed")
    gateway_state = gateway.freshness if gateway else None
    if gateway_state and gateway_state.status == "live":
        completed.append("gateway_connected")
    if gateway and (gateway.lifecycle_status == "commissioning" or devices or candidates):
        completed.append("device_scan_running")
    if devices or candidates:
        completed.append("devices_discovered")
    if devices or any(candidate["matched_template"] for candidate in candidates):
        completed.append("templates_selected")
    if latest_config:
        completed.append("config_pushed")
    if first_live_device:
        completed.append("first_telemetry_received")
        completed.append("dashboard_ready")

    stage_keys = [stage[0] for stage in COMMISSIONING_STAGES]
    current_stage = next((stage for stage in stage_keys if stage not in completed), "dashboard_ready")
    blocking_stage = current_stage if current_stage != "dashboard_ready" else None

    primary_actions = {
        "site_created": "Create site",
        "gateway_claimed": "Claim gateway",
        "gateway_connected": "Power on gateway",
        "device_scan_running": "Scan for devices",
        "devices_discovered": "Wait for scan results",
        "templates_selected": "Select templates",
        "config_pushed": "Provision selected devices",
        "first_telemetry_received": "Wait for first telemetry",
        "dashboard_ready": "Open dashboard",
    }
    messages = {
        "site_created": "Create the physical site where this gateway will be installed.",
        "gateway_claimed": "Claim the gateway using the serial number and sticker claim code.",
        "gateway_connected": "Gateway claimed. Power it on and connect it to the network.",
        "device_scan_running": "Gateway is online. Start or wait for the device discovery scan.",
        "devices_discovered": "Review discovered devices and pick the correct hardware templates.",
        "templates_selected": "Templates are selected. Provision devices to push config to the gateway.",
        "config_pushed": "Config has been sent. Waiting for the gateway to apply it.",
        "first_telemetry_received": "Devices are configured. Waiting for the first live telemetry sample.",
        "dashboard_ready": "Live data is flowing. The dashboard is ready.",
    }

    checklist = [
        {"key": key, "label": label, "complete": key in completed, "current": key == current_stage}
        for key, label in COMMISSIONING_STAGES
    ]
    return {
        "current_stage": current_stage,
        "completed_stages": completed,
        "blocking_stage": blocking_stage,
        "primary_action": {"label": primary_actions[current_stage], "stage": current_stage},
        "status_message": messages[current_stage],
        "checklist": checklist,
        "site": site,
        "gateway": gateway,
        "gateway_state": gateway_state,
        "device_candidates": candidates,
        "ready_candidates": [candidate for candidate in candidates if candidate["status"] == "ready"],
        "needs_template_candidates": [candidate for candidate in candidates if candidate["status"] == "needs_template"],
        "registered_candidates": [candidate for candidate in candidates if candidate["status"] == "registered"],
        "provisioned_devices": devices,
        "latest_config_status": latest_config.status if latest_config else None,
        "latest_config": latest_config,
        "first_live_device": first_live_device,
        "dashboard_ready": current_stage == "dashboard_ready",
    }
