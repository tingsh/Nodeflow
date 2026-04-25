"""
Edge Connector Config Generator

Transforms Cloud DeviceTemplate register maps into Edge-compatible connector
configurations that can be pushed via MQTT config update.

The generated config follows the Nodeflow Edge connector schema:
- Groups devices by protocol (modbus_tcp, modbus_rtu, etc.)
- Each device becomes a slave entry with register mappings
- Includes device_id (UUID) for unambiguous telemetry matching
"""

import logging

logger = logging.getLogger("iot_platform")


def generate_connector_config(gateway):
    """
    Generate the complete Edge connector config from all devices
    registered on this gateway + their templates.

    Returns a list of connector config dicts ready to push to the Edge.
    """
    devices = gateway.devices.select_related("template").all()

    # Group devices by protocol
    protocol_groups = {}
    for device in devices:
        protocol = device.protocol or "modbus_tcp"
        if protocol not in protocol_groups:
            protocol_groups[protocol] = []
        protocol_groups[protocol].append(device)

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
    """
    Build a Modbus connector config from a group of devices.

    Returns a connector dict in Nodeflow Edge format.
    """
    is_tcp = protocol == "modbus_tcp"
    connector_name = "Modbus TCP" if is_tcp else "Modbus RTU"
    connector_type = "modbus_tcp" if is_tcp else "modbus_rtu"

    slaves = []
    for device in devices:
        slave = _build_slave_config(device, is_tcp)
        if slave:
            slaves.append(slave)

    if not slaves:
        return None

    connector = {
        "name": connector_name,
        "type": connector_type,
        "enabled": True,
        "slaves": slaves,
    }

    # For RTU connectors, add serial port config from the first device's discovery_meta
    if not is_tcp and devices:
        first_meta = devices[0].discovery_meta or {}
        connector["port"] = first_meta.get("interface", "/dev/ttyUSB0")
        connector["baudrate"] = first_meta.get("baud_rate", 9600)
        connector["stopbits"] = first_meta.get("stopbits", 1)
        connector["bytesize"] = first_meta.get("bytesize", 8)
        connector["parity"] = first_meta.get("parity", "N")
        connector["timeout"] = first_meta.get("timeout", 3)

    return connector


def _build_slave_config(device, is_tcp):
    """
    Build a single slave config from a Device + its DeviceTemplate.

    Returns a slave dict or None if no template.
    """
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
        "timeseries": [],
        "attributes": [],
    }

    # TCP-specific fields
    if is_tcp:
        # Determine host/port from discovery_meta or connection_config
        interface = discovery.get("interface", "")
        if ":" in interface:
            parts = interface.rsplit(":", 1)
            slave["host"] = parts[0]
            slave["port"] = int(parts[1]) if parts[1].isdigit() else 502
        else:
            slave["host"] = connection.get("host", interface or "127.0.0.1")
            slave["port"] = connection.get("port", 502)
        slave["type"] = "tcp"

    # Transform register_map to timeseries/attributes
    for key, reg in template.register_map.items():
        entry = {
            "tag": key,
            "type": reg.get("type", "16int"),
            "functionCode": reg.get("functionCode", 3),
            "objectsCount": reg.get("objectsCount", 1),
            "address": reg.get("address", 0),
        }

        if reg.get("attribute"):
            slave["attributes"].append(entry)
        else:
            slave["timeseries"].append(entry)

    return slave


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

    # Build the full config payload
    config_payload = {
        "connectors": connectors,
    }

    config_record = publish_config_update(gateway, "connector_update", config_payload)
    logger.info(
        "Pushed connector config to %s: %d connectors, request_id=%s",
        gateway.serial_number,
        len(connectors),
        config_record.request_id,
    )
    return config_record
