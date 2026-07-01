import json
import logging
import uuid

import paho.mqtt.client as mqtt
from django.conf import settings

logger = logging.getLogger("novena_hub")

# Singleton MQTT client for publishing (Cloud → Edge)
_client = None
_connected = False


def get_mqtt_client():
    """Get or create the singleton MQTT publish client."""
    global _client, _connected
    if _client is not None:
        return _client

    _client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=settings.MQTT_PUBLISHER_CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )

    def on_connect(client, userdata, flags, rc, properties=None):
        global _connected
        if rc == 0:
            _connected = True
            logger.info("MQTT publisher connected to broker")
        else:
            logger.error("MQTT publisher connection failed: %s", rc)

    def on_disconnect(client, userdata, flags, rc, properties=None):
        global _connected
        _connected = False
        logger.warning("MQTT publisher disconnected")

    _client.on_connect = on_connect
    _client.on_disconnect = on_disconnect

    try:
        _client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, 60)
        _client.loop_start()
    except Exception as e:
        logger.error("Failed to connect MQTT publisher: %s", e)

    return _client


def publish_config_update(gateway, action, config):
    """
    Push a config update to a gateway.

    Args:
        gateway: Gateway model instance
        action: 'full_update', 'connector_update', 'connector_add', 'connector_remove'
        config: dict — config content appropriate for the action

    Returns:
        GatewayConfig instance
    """
    from apps.devices.models import GatewayConfig

    request_id = uuid.uuid4()
    topic = f"v1/gateway/{gateway.serial_number}/config"
    payload = {
        "request_id": str(request_id),
        "action": action,
        "config": config,
    }

    # Store in DB
    config_record = GatewayConfig.objects.create(
        team=gateway.team,
        gateway=gateway,
        config_json=config,
        request_id=request_id,
        action=action,
    )

    # Publish
    client = get_mqtt_client()
    result = client.publish(topic, json.dumps(payload), qos=1)
    logger.info(
        "Published config update to %s (action=%s, request_id=%s, rc=%s)",
        gateway.serial_number,
        action,
        request_id,
        result.rc,
    )

    return config_record


def publish_rpc_command(gateway, method, params=None):
    """
    Send an RPC command to a gateway.

    Args:
        gateway: Gateway model instance
        method: str — command method name (ping, get_status, write_device, etc.)
        params: dict — command parameters

    Returns:
        RpcCommand instance
    """
    from apps.devices.models import RpcCommand

    request_id = uuid.uuid4()
    topic = f"v1/gateway/{gateway.serial_number}/rpc/request"
    payload = {
        "request_id": str(request_id),
        "method": method,
        "params": params or {},
    }

    # Store in DB
    rpc_record = RpcCommand.objects.create(
        team=gateway.team,
        gateway=gateway,
        request_id=request_id,
        method=method,
        params=params or {},
    )

    # Publish
    client = get_mqtt_client()
    result = client.publish(topic, json.dumps(payload), qos=1)
    logger.info(
        "Published RPC command '%s' to %s (request_id=%s, rc=%s)",
        method,
        gateway.serial_number,
        request_id,
        result.rc,
    )

    return rpc_record


def publish_credential_rotation(gateway, new_password):
    """
    Publish a credential rotation command to the Edge via the provision topic.
    The Edge will save the new password and reconnect.

    Args:
        gateway: Gateway model instance
        new_password: str — new plaintext password
    """
    topic = f"v1/gateway/{gateway.serial_number}/provision"
    payload = {
        "action": "rotate_password",
        "new_password": new_password,
    }

    client = get_mqtt_client()
    result = client.publish(topic, json.dumps(payload), qos=1)
    logger.info(
        "Published credential rotation to %s (rc=%s)",
        gateway.serial_number,
        result.rc,
    )


def publish_attribute_push(gateway, attributes):
    """
    Push attributes to a gateway.

    Args:
        gateway: Gateway model instance
        attributes: dict — key-value pairs to push
    """
    request_id = str(uuid.uuid4())
    topic = f"v1/gateway/{gateway.serial_number}/attributes/request"
    payload = {
        "request_id": request_id,
        "attributes": attributes,
    }

    client = get_mqtt_client()
    result = client.publish(topic, json.dumps(payload), qos=1)
    logger.info(
        "Published attribute push to %s (request_id=%s, rc=%s)",
        gateway.serial_number,
        request_id,
        result.rc,
    )
