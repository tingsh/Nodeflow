import json
import logging
import uuid
import paho.mqtt.publish as publish
from django.conf import settings
from django.utils import timezone
from .models import DeviceCommand

logger = logging.getLogger('iot_platform')

def send_device_command(device, user, key, value):
    """
    Sends a remote control command to a device via the associated gateway.
    """
    if not device.gateway:
        raise ValueError("Device is not assigned to a gateway.")

    # 1. Create Command Record
    transaction_id = str(uuid.uuid4())
    
    # Prepare the payload (Compatible with TB Gateway RPC format)
    # { "device": "Device A", "data": { "id": 123, "method": "set_power", "params": 100 } }
    rpc_payload = {
        "device": device.name,
        "data": {
            "id": transaction_id,
            "method": key,
            "params": value
        }
    }

    command = DeviceCommand.objects.create(
        team=device.team,
        device=device,
        created_by=user,
        command_key=key,
        value=value,
        transaction_id=transaction_id,
        payload=rpc_payload,
        status='pending'
    )

    # 2. Publish to MQTT
    try:
        topic = "v1/gateway/rpc"
        publish.single(
            topic,
            payload=json.dumps(rpc_payload),
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            client_id=f"nodeflow_srv_{uuid.uuid4().hex[:8]}"
        )
        command.status = 'sent'
        command.save()
        logger.info(f"Command {key}={value} sent to {device.name} (tx: {transaction_id})")
        return command
    except Exception as e:
        command.status = 'failed'
        command.error_message = str(e)
        command.save()
        logger.error(f"Failed to publish command to MQTT: {e}")
        raise e

def process_command_response(payload_str):
    """
    Processes an incoming RPC response from the gateway.
    Payload format: {"device": "Device A", "id": "uuid", "data": {"success": true}}
    """
    try:
        payload = json.loads(payload_str)
        tx_id = payload.get('id')
        device_name = payload.get('device')
        
        if not tx_id:
            return

        command = DeviceCommand.objects.filter(transaction_id=tx_id).first()
        if command:
            command.response_payload = payload
            command.executed_at = timezone.now()
            
            data = payload.get('data', {})
            if data.get('success') is True or data.get('status') == 'OK':
                command.status = 'executed'
            else:
                command.status = 'failed'
                command.error_message = data.get('error', 'Execution failed at edge')
            
            command.save()
            logger.info(f"Command {command.transaction_id} updated to {command.status}")
    except Exception as e:
        logger.error(f"Error processing command response: {e}")
