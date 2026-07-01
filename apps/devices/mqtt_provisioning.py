"""
Mosquitto Dynamic Security provisioning.

Manages MQTT client credentials for edge gateways by publishing commands to
the Mosquitto dynamic security plugin's control topic.

Requires:
- Mosquitto 2.x with dynamic-security plugin enabled
- An admin client configured in dynamic-security.json
- Settings: MQTT_DYNSEC_ADMIN_USER, MQTT_DYNSEC_ADMIN_PASS
"""

import json
import logging
import time

import paho.mqtt.client as mqtt
from django.conf import settings

logger = logging.getLogger("novena_hub")

DYNSEC_TOPIC = "$CONTROL/dynamic-security/v1"
RESPONSE_TOPIC = "$CONTROL/dynamic-security/v1/response"

# Singleton client for dynsec commands (connects on port 1884 with admin creds)
_dynsec_client = None


def _get_dynsec_client():
    """Get or create the singleton MQTT client for dynamic security commands."""
    global _dynsec_client
    if _dynsec_client is not None and _dynsec_client.is_connected():
        return _dynsec_client

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="novena-dynsec-provisioner",
        protocol=mqtt.MQTTv311,
    )

    admin_user = getattr(settings, "MQTT_DYNSEC_ADMIN_USER", "dynsec-admin")
    admin_pass = getattr(settings, "MQTT_DYNSEC_ADMIN_PASS", "dynsec-password")
    client.username_pw_set(admin_user, admin_pass)

    dynsec_port = getattr(settings, "MQTT_DYNSEC_PORT", 1884)

    try:
        client.connect(settings.MQTT_BROKER_HOST, dynsec_port, 60)
        client.loop_start()
        # Brief wait for connection
        for _ in range(10):
            if client.is_connected():
                break
            time.sleep(0.1)
        _dynsec_client = client
    except Exception as e:
        logger.error("Failed to connect dynsec MQTT client: %s", e)
        raise

    return _dynsec_client


def _publish_dynsec_command(command):
    """Publish a command to the dynamic security control topic."""
    client = _get_dynsec_client()
    payload = json.dumps({"commands": [command]})
    result = client.publish(DYNSEC_TOPIC, payload, qos=1)
    logger.debug("Dynsec command published (rc=%s): %s", result.rc, command.get("command"))
    return result


def provision_gateway_mqtt(gateway, password):
    """
    Create an MQTT client in Mosquitto for a newly registered gateway.

    Creates the client with the given password and assigns:
    - 'gateway' role (shared inbound topic ACLs)
    - Per-gateway topic ACLs for its serial-number-scoped topics

    Args:
        gateway: Gateway model instance (must have serial_number set)
        password: str — plaintext password (Mosquitto hashes it internally)
    """
    sn = gateway.serial_number

    # Step 1: Create the client with password and assign the shared gateway role
    create_cmd = {
        "command": "createClient",
        "username": sn,
        "password": password,
        "textName": f"Edge Gateway {sn}",
        "textDescription": f"Auto-provisioned for gateway {gateway.name}",
        "roles": [
            {"roleName": "gateway", "priority": -1}
        ],
    }
    _publish_dynsec_command(create_cmd)

    # Step 2: Create a per-gateway role with scoped topic ACLs
    role_name = f"gw-{sn}"
    create_role_cmd = {
        "command": "createRole",
        "roleName": role_name,
        "textDescription": f"Per-gateway ACLs for {sn}",
        "acls": [
            # Subscribe to per-gateway inbound topics (cloud → edge)
            {"acltype": "subscribePattern", "topic": f"v1/gateway/{sn}/#", "allow": True},
            # Receive messages on per-gateway topics
            {"acltype": "publishClientReceive", "topic": f"v1/gateway/{sn}/#", "allow": True},
        ],
    }
    _publish_dynsec_command(create_role_cmd)

    # Step 3: Assign the per-gateway role to the client
    add_role_cmd = {
        "command": "addClientRole",
        "username": sn,
        "roleName": role_name,
        "priority": -1,
    }
    _publish_dynsec_command(add_role_cmd)

    logger.info("Provisioned MQTT credentials for gateway %s on Mosquitto", sn)


def rotate_gateway_password(gateway, new_password):
    """
    Rotate an MQTT client's password in Mosquitto via dynamic security.

    Args:
        gateway: Gateway model instance
        new_password: str — new plaintext password
    """
    sn = gateway.serial_number

    modify_cmd = {
        "command": "modifyClient",
        "username": sn,
        "password": new_password,
    }
    _publish_dynsec_command(modify_cmd)

    logger.info("Rotated MQTT password for gateway %s on Mosquitto", sn)


def deprovision_gateway_mqtt(gateway):
    """
    Remove an MQTT client and its per-gateway role from Mosquitto.

    Args:
        gateway: Gateway model instance
    """
    sn = gateway.serial_number

    # Delete the client
    delete_client_cmd = {
        "command": "deleteClient",
        "username": sn,
    }
    _publish_dynsec_command(delete_client_cmd)

    # Delete the per-gateway role
    role_name = f"gw-{sn}"
    delete_role_cmd = {
        "command": "deleteRole",
        "roleName": role_name,
    }
    _publish_dynsec_command(delete_role_cmd)

    logger.info("Deprovisioned MQTT credentials for gateway %s from Mosquitto", sn)
