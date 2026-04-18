import json
import logging
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger("iot_platform")


def parse_mqtt_payload(topic, payload):
    """
    Parses MQTT payloads from either our custom simulator or ThingsBoard Gateway format.
    Returns a list of normalized ingestion events.

    Format A (Nodeflow Simulator):
    {"serial_number": "GW-001", "values": {"device_name": "Device 1", "active_power": 100}}

    Format B (ThingsBoard Gateway):
    {"Device A": [{"ts": 1714000000000, "values": {"temp": 25}}, ...]}
    """
    events = []

    # Ensure payload is a dict
    if isinstance(payload, bytes):
        try:
            payload = json.loads(payload.decode())
        except Exception as e:
            logger.error(f"Failed to decode MQTT payload: {e}")
            return []

    # Detect Format A (Nodeflow Simulator)
    if "serial_number" in payload and "values" in payload:
        gateway_sn = payload.get("serial_number")
        values = payload.get("values", {})
        # Extracts device_name from values if present (our current logic handle this in services.py too)
        device_name = values.get("device_name")

        events.append(
            {
                "gateway_sn": gateway_sn,
                "device_name": device_name,
                "values": values,
                "timestamp": None,  # Use server time
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
                            dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)

                        events.append(
                            {
                                "gateway_sn": None,  # In TB format, SN is usually tied to the connection/topic
                                "device_name": device_name,
                                "values": point.get("values", {}),
                                "timestamp": dt,
                            }
                        )

    return events
