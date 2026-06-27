import hashlib
import hmac
import json
import logging
import secrets
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import DeviceCommand, Gateway, GatewayInventory

logger = logging.getLogger("iot_platform")


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
            "This serial number is not in the Nodeflow factory inventory. Please contact support."
        )
    if inventory and inventory.status == "retired":
        raise GatewayClaimError("This gateway has been retired and cannot be claimed.")
    return inventory


@transaction.atomic
def claim_gateway_for_team(team, site, name: str, serial_number: str, claim_code: str):
    """Bind a manufactured gateway to a customer team/site after sticker validation."""
    serial_number = normalize_gateway_serial(serial_number)
    inventory = validate_gateway_claim(serial_number, claim_code)
    mqtt_password = claim_code.strip().upper()

    existing_gateway = Gateway.objects.select_for_update().filter(serial_number=serial_number).first()
    if existing_gateway and existing_gateway.team != team:
        raise GatewayClaimError(
            "This serial number is already registered to another team. Please contact support if this is an error."
        )

    if inventory:
        inventory = GatewayInventory.objects.select_for_update().get(pk=inventory.pk)
        if inventory.status == "claimed" and inventory.claimed_by_team and inventory.claimed_by_team != team:
            raise GatewayClaimError(
                "This serial number is already registered to another team. Please contact support if this is an error."
            )

    if existing_gateway:
        gateway = existing_gateway
        gateway.site = site
        gateway.name = name
        gateway.mqtt_username = serial_number
        gateway.mqtt_password = mqtt_password
        if gateway.status == "online":
            gateway.lifecycle_status = "online"
        elif gateway.lifecycle_status not in ("commissioning", "active"):
            gateway.lifecycle_status = "claimed"
        gateway.save(update_fields=["site", "name", "mqtt_username", "mqtt_password", "lifecycle_status"])
    else:
        gateway = Gateway.objects.create(
            team=team,
            site=site,
            name=name,
            serial_number=serial_number,
            access_token=secrets.token_hex(20),
            mqtt_username=serial_number,
            mqtt_password=mqtt_password,
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

        provision_gateway_mqtt(gateway, mqtt_password)
    except Exception as e:
        logger.warning(
            "Mosquitto provisioning failed for gateway %s: %s (gateway saved, manual setup may be required)",
            gateway.serial_number,
            e,
        )

    return gateway


def send_device_command(device, user, key, value):
    """
    Sends a remote control command to a device via the associated gateway.
    Uses the persistent MQTT publisher and the per-gateway RPC topic.
    """
    from apps.telemetry.mqtt_publisher import publish_rpc_command

    if not device.gateway:
        raise ValueError("Device is not assigned to a gateway.")

    # 1. Create DeviceCommand record
    transaction_id = str(uuid.uuid4())

    command = DeviceCommand.objects.create(
        team=device.team,
        device=device,
        created_by=user,
        command_key=key,
        value=value,
        transaction_id=transaction_id,
        payload={},
        status="pending",
    )

    # 2. Build Modbus-aware params from the device template register map
    params = {"device_name": device.name}
    register = None
    if device.template and device.template.register_map:
        register = device.template.register_map.get(key)

    if register and "address" in register:
        params["address"] = register["address"]
        params["functionCode"] = register.get("functionCode", 6)
        params["value"] = value
        if register.get("type") and register["type"] != "bool":
            params["type"] = register["type"]
        if "objectsCount" in register:
            params["objectsCount"] = register["objectsCount"]
    else:
        # Fallback for devices without a template — caller must know the address
        params["functionCode"] = 6
        params["address"] = 0
        params["value"] = value
        logger.warning(
            "No register map entry for key '%s' on device %s — using fallback FC6/addr0",
            key, device.name,
        )

    # 3. Publish via the persistent MQTT publisher using write_device RPC
    try:
        rpc = publish_rpc_command(
            device.gateway,
            method="write_device",
            params=params,
        )

        # Link the RpcCommand to the DeviceCommand
        command.payload = {
            "rpc_request_id": str(rpc.request_id),
            "method": "write_device",
            "device_name": device.name,
        }
        command.status = "sent"
        command.save()
        logger.info("Command %s=%s sent to %s (tx: %s, rpc: %s)", key, value, device.name, transaction_id, rpc.request_id)
        return command
    except Exception as e:
        command.status = "failed"
        command.error_message = str(e)
        command.save()
        logger.error("Failed to publish command to MQTT: %s", e)
        raise


def process_command_response(payload_str):
    """
    Processes an incoming RPC response from the gateway.
    Payload format: {"device": "Device A", "id": "uuid", "data": {"success": true}}
    """
    try:
        payload = json.loads(payload_str)
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
