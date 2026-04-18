import logging
from django.utils import timezone
from apps.devices.models import Gateway, Device
from .models import TelemetryData

logger = logging.getLogger('iot_platform')

def ingest_telemetry_data(gateway_sn, values, timestamp=None):
    """
    Ingests telemetry data from a gateway. 
    Matches the gateway and its devices, and saves data to TimescaleDB.
    """
    if timestamp is None:
        timestamp = timezone.now()

    try:
        gateway = Gateway.objects.get(serial_number=gateway_sn)
    except Gateway.DoesNotExist:
        logger.warning(f"Gateway with SN {gateway_sn} not found. Ingestion skipped.")
        return

    # Update gateway heartbeat
    gateway.last_seen = timestamp
    gateway.status = 'online'
    gateway.save(update_fields=['last_seen', 'status'])

    # Find devices associated with this gateway
    # Note: In a production version, we would use a more robust mapping (e.g., payloads containing device IDs)
    # For the MVP, we assume the gateway is sending data for its primary devices or the payload identifies the device.
    
    # Simple mapping logic for MVP: 
    # If the gateway has only one device, we attribute all values to it.
    # Otherwise, we look for device-specific keys in the payload or specific device identification.
    
    # We'll support a 'device_name' key in 'values' to identify sub-devices
    target_device = None
    # Make a copy so we don't mutate the caller's dict; pop device_name cleanly
    values = dict(values)
    device_name = values.pop('device_name', None)
    
    if device_name:
        try:
            target_device = gateway.devices.get(name=device_name)
        except Device.DoesNotExist:
            logger.info(f"Device {device_name} not found for gateway {gateway_sn}. Creating record...")
            # Optional: auto-provisioning logic
            pass
    
    # Fallback to the first device if none identified
    if not target_device and gateway.devices.exists():
        target_device = gateway.devices.first()

    if not target_device:
        logger.warning(f"No target device identified for telemetry from gateway {gateway_sn}")
        return

    # Create TelemetryData records for each key
    telemetry_objects = []
    for key, value in values.items():
        data_point = TelemetryData(
            device=target_device,
            timestamp=timestamp,
            key=key
        )
        
        # Determine value type
        if isinstance(value, (int, float)):
            data_point.value_numeric = float(value)
        elif isinstance(value, bool):
            data_point.value_bool = value
        else:
            data_point.value_string = str(value)
            
        telemetry_objects.append(data_point)

    if telemetry_objects:
        TelemetryData.objects.bulk_create(telemetry_objects)
        
        # Check for alerts
        from apps.alerts.services import check_alerts_for_payload
        for key, value in values.items():
            check_alerts_for_payload(target_device, key, value)
            
        # Evaluate automations
        from apps.automations.engine import evaluate_automations
        evaluate_automations(target_device, values)

        # Update device last seen
        target_device.last_telemetry_at = timestamp
        target_device.status = 'online'
        target_device.save(update_fields=['last_telemetry_at', 'status'])
        
        logger.info(f"Ingested {len(telemetry_objects)} points for device {target_device.name}")
        
    return target_device

def get_latest_telemetry_for_chart(device, key, limit=20):
    """
    Fetches the latest data points for a specific key/device combination.
    Returns lists of timestamps and values formatted for Chart.js.
    """
    data = TelemetryData.objects.filter(
        device=device,
        key=key
    ).order_by('-timestamp')[:limit]
    
    # Reverse to get chronological order (evaluate queryset to list first)
    data = list(reversed(list(data)))
    
    labels = []
    values = []
    
    for point in data:
        labels.append(point.timestamp.strftime("%H:%M:%S"))
        values.append(point.value_numeric or 0)
        
    return {
        "labels": labels,
        "values": values,
        "key": key
    }

def get_latest_telemetry_value(device, key):
    """Fetches the single most recent data point for a key."""
    point = TelemetryData.objects.filter(
        device=device,
        key=key
    ).order_by('-timestamp').first()
    
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
        cursor.execute("""
            SELECT SUM(kwh_total) 
            FROM daily_energy_stats 
            WHERE device_id IN (SELECT id FROM devices_device WHERE site_id = %s)
            AND bucket >= CURRENT_DATE;
        """, [site.id])
        daily_kwh = cursor.fetchone()[0] or 0.0
        
        # Get current avg power (from the last hour bucket)
        cursor.execute("""
            SELECT SUM(avg_power)
            FROM hourly_power_stats
            WHERE device_id IN (SELECT id FROM devices_device WHERE site_id = %s)
            AND bucket >= NOW() - INTERVAL '1 hour';
        """, [site.id])
        current_power = cursor.fetchone()[0] or 0.0
        
    return {
        "daily_kwh": daily_kwh,
        "current_power": current_power
    }
