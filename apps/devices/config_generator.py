"""
Edge Connector Config Generator

Transforms Cloud DeviceTemplate register maps into Edge-compatible connector
configurations that can be pushed via MQTT config update.

The generated config follows the Nodeflow Edge connector schema:
- Groups devices by protocol (modbus_tcp, modbus_rtu, etc.)
- Emits Edge connector objects with top-level type/name and nested config
- Includes device_id (UUID) for unambiguous telemetry matching
"""

import logging

logger = logging.getLogger("iot_platform")

MODBUS_TYPE_MAP = {
    "float32": "32float",
    "float64": "64float",
    "int16": "16int",
    "uint16": "16uint",
    "int32": "32int",
    "uint32": "32uint",
    "int64": "64int",
    "uint64": "64uint",
    "bool": "bits",
}


def generate_connector_config(gateway):
    """
    Generate the complete Edge connector config from all devices
    registered on this gateway + their templates.

    Returns a list of connector config dicts ready to push to the Edge.
    """
    devices = gateway.devices.select_related("template").all()

    protocol_groups = {}
    for device in devices:
        protocol = device.protocol or "modbus_tcp"
        protocol_groups.setdefault(protocol, []).append(device)

    connectors = []
    for protocol, devices_in_group in protocol_groups.items():
        if protocol in ("modbus_tcp", "modbus_rtu"):
            connector = _build_modbus_connector(protocol, devices_in_group)
            if connector:
                connectors.append(connector)
        else:
            logger.warning("Unsupported protocol '%s' for config generation, skipping", protocol)

    return connectors


def _build_modbus_connector(protocol, devices):
    """Build an Edge-compatible Modbus connector config."""
    is_tcp = protocol == "modbus_tcp"
    connector_name = "Modbus TCP Connector" if is_tcp else "Modbus RTU Connector"

    slaves = []
    for device in devices:
        slave = _build_slave_config(device, is_tcp)
        if slave:
            slaves.append(slave)

    if not slaves:
        return None

    return {
        "name": connector_name,
        "type": "modbus",
        "config": {
            "master": {
                "slaves": slaves,
            },
        },
    }


def _build_slave_config(device, is_tcp):
    """Build a single Modbus slave config from a Device + DeviceTemplate."""
    template = device.template
    if not template or not template.register_map:
        logger.info("Device %s has no template/register_map, skipping config generation", device.name)
        return None

    discovery = device.discovery_meta or {}
    connection = device.connection_config or {}

    slave = {
        "deviceName": device.name,
        "deviceId": str(device.pk),
        "unitId": discovery.get("slave_id", connection.get("slave_id", 1)),
        "pollPeriod": (template.default_polling_interval or 5) * 1000,
        "method": connection.get("method", "socket"),
        "timeout": connection.get("timeout", 35),
        "byteOrder": connection.get("byteOrder", "BIG"),
        "wordOrder": connection.get("wordOrder", "BIG"),
        "retries": connection.get("retries", True),
        "retryOnEmpty": connection.get("retryOnEmpty", True),
        "retryOnInvalid": connection.get("retryOnInvalid", True),
        "sendDataOnlyOnChange": connection.get("sendDataOnlyOnChange", False),
        "connectAttemptTimeMs": connection.get("connectAttemptTimeMs", 5000),
        "connectAttemptCount": connection.get("connectAttemptCount", 5),
        "waitAfterFailedAttemptsMs": connection.get("waitAfterFailedAttemptsMs", 300000),
        "timeseries": [],
        "attributes": [],
    }

    if is_tcp:
        interface = discovery.get("interface", "")
        if ":" in interface:
            host, port = interface.rsplit(":", 1)
            slave["host"] = host
            slave["port"] = int(port) if port.isdigit() else 502
        else:
            slave["host"] = connection.get("host", interface or "127.0.0.1")
            slave["port"] = connection.get("port", 502)
        slave["type"] = "tcp"
    else:
        slave["type"] = "serial"
        slave["port"] = discovery.get("interface", connection.get("serial_port", "/dev/ttyUSB0"))
        slave["baudrate"] = discovery.get("baud_rate", connection.get("baudrate", 9600))
        slave["stopbits"] = connection.get("stopbits", 1)
        slave["bytesize"] = connection.get("bytesize", 8)
        slave["parity"] = connection.get("parity", "N")

    for key, reg in template.register_map.items():
        if not isinstance(reg, dict):
            continue
        entry = {
            "tag": key,
            "type": _normalize_modbus_type(reg.get("type", "16int")),
            "functionCode": reg.get("functionCode", 3),
            "objectsCount": reg.get("objectsCount", _default_objects_count(reg.get("type"))),
            "address": reg.get("address", 0),
        }
        if "scale" in reg:
            entry["multiplier"] = reg["scale"]
        if "multiplier" in reg:
            entry["multiplier"] = reg["multiplier"]

        if reg.get("attribute"):
            slave["attributes"].append(entry)
        elif not reg.get("writable"):
            slave["timeseries"].append(entry)

    return slave


def _normalize_modbus_type(type_name):
    if not type_name:
        return "16int"
    normalized = str(type_name).replace("_", "").lower()
    return MODBUS_TYPE_MAP.get(normalized, type_name)


def _default_objects_count(type_name):
    normalized = _normalize_modbus_type(type_name)
    if normalized.startswith("64"):
        return 4
    if normalized.startswith("32"):
        return 2
    return 1


def generate_and_push_config(gateway):
    """
    Generate connector config for a gateway and push it via MQTT.

    Returns the GatewayConfig record or None.
    """
    from apps.telemetry.mqtt_publisher import publish_config_update

    connectors = generate_connector_config(gateway)

    if not connectors:
        logger.info("No connectors to push for gateway %s", gateway.serial_number)
        return None

    config_payload = {
        "connectors": connectors,
    }

    gateway.lifecycle_status = "commissioning"
    gateway.save(update_fields=["lifecycle_status"])

    config_record = publish_config_update(gateway, "connector_update", config_payload)
    logger.info(
        "Pushed connector config to %s: %d connectors, request_id=%s",
        gateway.serial_number,
        len(connectors),
        config_record.request_id,
    )
    return config_record
