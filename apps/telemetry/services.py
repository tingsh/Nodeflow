import logging

from django.utils import timezone

from apps.devices.models import Device
from apps.devices.services import current_claimed_gateway
from apps.utils.timezones import format_site_datetime

from .models import TelemetryData

logger = logging.getLogger("novena_hub")


def ingest_telemetry_data(gateway_sn, values, timestamp=None, device_id=None):
    """
    Ingests telemetry data from a gateway.
    Matches by device ID first, then exact device name, with legacy fallback logged.
    """
    cloud_received_at = timezone.now()
    if timestamp is None:
        timestamp = cloud_received_at

    gateway = current_claimed_gateway(gateway_sn)
    if not gateway:
        logger.warning("Gateway with SN %s not found. Ingestion skipped.", gateway_sn)
        return

    gateway.last_seen = cloud_received_at
    gateway.status = "online"
    gateway.save(update_fields=["last_seen", "status"])

    target_device = None
    values = dict(values)
    device_name = values.pop("device_name", None)

    if device_id:
        try:
            target_device = gateway.devices.filter(pk=int(device_id)).first()
        except (TypeError, ValueError):
            logger.warning("Invalid telemetry device_id %s from gateway %s.", device_id, gateway_sn)
        if not target_device:
            logger.debug("device_id %s not found on gateway %s, falling back to name match", device_id, gateway_sn)

    if not target_device and device_name:
        try:
            target_device = gateway.devices.get(name=device_name)
        except Device.DoesNotExist:
            logger.info("Device %s not found for gateway %s.", device_name, gateway_sn)

    legacy_fallback_used = False
    if not target_device:
        legacy_candidates = list(gateway.devices.order_by("id")[:2])
        if len(legacy_candidates) == 1:
            target_device = legacy_candidates[0]
            legacy_fallback_used = True
        elif len(legacy_candidates) > 1:
            logger.warning(
                "Rejected ambiguous telemetry for gateway %s. Payload device_id=%s device_name=%s; "
                "the gateway has multiple configured devices.",
                gateway_sn,
                device_id,
                device_name,
            )

    if legacy_fallback_used:
        logger.warning(
            "Using legacy first-device telemetry fallback for gateway %s (single configured device). "
            "Payload device_id=%s device_name=%s resolved_device=%s.",
            gateway_sn,
            device_id,
            device_name,
            target_device.id,
        )

    if not target_device:
        logger.warning("No target device identified for telemetry from gateway %s", gateway_sn)
        return

    db_flushed_at = timezone.now()
    telemetry_objects = []
    for key, value in values.items():
        data_point = TelemetryData(
            device=target_device,
            timestamp=timestamp,
            cloud_received_at=cloud_received_at,
            db_flushed_at=db_flushed_at,
            key=key,
        )

        if isinstance(value, bool):
            data_point.value_bool = value
        elif isinstance(value, int | float):
            data_point.value_numeric = float(value)
        else:
            data_point.value_string = str(value)

        telemetry_objects.append(data_point)

    if telemetry_objects:
        TelemetryData.objects.bulk_create(telemetry_objects)

        from apps.alerts.services import check_alerts_for_payload

        for key, value in values.items():
            check_alerts_for_payload(target_device, key, value)

        from apps.automations.engine import evaluate_automations

        evaluate_automations(target_device, values)

        target_device.last_telemetry_at = timestamp
        if target_device.status != "alarm":
            target_device.status = "online"
            target_device.save(update_fields=["last_telemetry_at", "status"])
        else:
            target_device.save(update_fields=["last_telemetry_at"])

        logger.info("Ingested %d points for device %s", len(telemetry_objects), target_device.name)

    return target_device


def get_latest_telemetry_for_chart(device, key, limit=20):
    """
    Fetches the latest data points for a specific key/device combination.
    Returns lists of timestamps and values formatted for Chart.js.
    """
    data = TelemetryData.objects.filter(device=device, key=key).order_by("-timestamp")[:limit]

    # Reverse to get chronological order (evaluate queryset to list first)
    data = list(reversed(list(data)))

    labels = []
    values = []

    for point in data:
        labels.append(format_site_datetime(point.timestamp, device.site, "%H:%M:%S"))
        values.append(point.value_numeric or 0)

    return {"labels": labels, "values": values, "key": key}


def get_latest_telemetry_value(device, key):
    """Fetches the single most recent data point for a key."""
    point = TelemetryData.objects.filter(device=device, key=key).order_by("-timestamp").first()

    if point:
        if point.value_numeric is not None:
            return point.value_numeric
        return point.value_string or point.value_bool
    return None


def get_site_summary_stats(site):
    """
    Fetches aggregate energy stats for a site using Continuous Aggregates.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        # Get total kWh for the current day across all devices in the site
        cursor.execute(
            """
            SELECT SUM(avg_value) / 1000 
            FROM hourly_telemetry_stats 
            WHERE key = 'active_power'
            AND device_id IN (SELECT id FROM devices_device WHERE site_id = %s)
            AND bucket >= CURRENT_DATE;
        """,
            [site.id],
        )
        daily_kwh = cursor.fetchone()[0] or 0.0

        # Get current avg power (from the last hour bucket)
        cursor.execute(
            """
            SELECT SUM(avg_value)
            FROM hourly_telemetry_stats
            WHERE key = 'active_power'
            AND device_id IN (SELECT id FROM devices_device WHERE site_id = %s)
            AND bucket >= NOW() - INTERVAL '1 hour';
        """,
            [site.id],
        )
        current_power = cursor.fetchone()[0] or 0.0

    return {"daily_kwh": daily_kwh, "current_power": current_power}
