import hashlib
import hmac
import json
import logging
import uuid

from django.conf import settings
from django.utils import timezone

from .models import DeviceCommand

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
