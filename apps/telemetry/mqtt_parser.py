import json
import logging
from datetime import UTC, datetime

logger = logging.getLogger("novena_hub")


def parse_mqtt_payload(topic, payload, trusted_gateway_sn=None):
    """
    Parses MQTT payloads from either our custom simulator or ThingsBoard Gateway format.
    Returns a list of normalized ingestion events.

    Format A (Novena Simulator):
    {"serial_number": "GW-001", "values": {"device_name": "Device 1", "active_power": 100}}

    Format B (ThingsBoard Gateway):
    {"Device A": [{"ts": 1714000000000, "values": {"temp": 25}}, ...]}
    """
    events = []

    # Ensure payload is a dict
    if isinstance(payload, bytes | str):
        try:
            payload = json.loads(payload)
        except Exception as e:
            logger.error(f"Failed to decode MQTT payload: {e}")
            return []

    # Detect Format A (Novena Simulator / Novena Gateway)
    if "values" in payload and ("serial_number" in payload or trusted_gateway_sn):
        gateway_sn = trusted_gateway_sn or payload.get("serial_number")
        values = payload.get("values", {})
        # device_id is a top-level field (Cloud-assigned UUID, set by Edge when deviceId is in connector config)
        device_id = payload.get("device_id")
        # device_name can be top-level or inside values
        device_name = payload.get("device_name") or values.get("device_name")

        # Parse edge-provided timestamp (ms epoch); fall back to server time
        ts = payload.get("ts")
        dt = datetime.fromtimestamp(ts / 1000.0, tz=UTC) if ts else None

        events.append(
            {
                "gateway_sn": gateway_sn,
                "device_id": device_id,
                "device_name": device_name,
                "values": values,
                "timestamp": dt,
            }
        )

    # Detect Format B (ThingsBoard Gateway)
    # TB Gateway format is a dict where keys are device names and values are lists of telemetry points
    else:
        # We might need gateway_sn from elsewhere (e.g. inferred from credentials)
        # but for now we look for any key that has a list of dicts with 'values'
        for device_name, points in payload.items():
            if isinstance(points, list):
                for point in points:
                    if "values" in point:
                        ts = point.get("ts")
                        dt = None
                        if ts:
                            # TB timestamps are usually milliseconds
                            dt = datetime.fromtimestamp(ts / 1000.0, tz=UTC)

                        events.append(
                            {
                                "gateway_sn": trusted_gateway_sn,
                                "device_name": device_name,
                                "values": point.get("values", {}),
                                "timestamp": dt,
                            }
                        )

    return events
