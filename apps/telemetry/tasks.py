import json
import logging
import time
from datetime import datetime, timezone as dt_timezone
from celery import shared_task
import redis

from django.conf import settings
from django.utils import timezone

from apps.devices.models import Device, Gateway
from apps.telemetry.models import TelemetryData, GatewayLog
from apps.telemetry.mqtt_parser import parse_mqtt_payload
from apps.alerts.services import check_alerts_for_payload
from apps.automations.engine import evaluate_automations

logger = logging.getLogger("iot_platform")

@shared_task
def flush_telemetry_buffer_task():
    r = redis.Redis.from_url(settings.REDIS_URL)
    queue_key = "telemetry_ingest_queue"
    
    # 1. Pop all payloads atomically using a Redis pipeline transaction
    with r.pipeline() as pipe:
        pipe.multi()
        pipe.lrange(queue_key, 0, -1)
        pipe.delete(queue_key)
        results = pipe.execute()
    
    if not results or not results[0]:
        return "No telemetry to ingest"
    
    payloads = results[0]
    logger.info(f"Popped {len(payloads)} raw telemetry payloads from Redis.")
    
    # 2. Parse all raw JSON payloads into normalization dicts
    events = []
    for raw_payload in payloads:
        try:
            payload_dict = json.loads(raw_payload.decode("utf-8"))
            parsed_events = parse_mqtt_payload("v1/gateway/telemetry", payload_dict)
            events.extend(parsed_events)
        except Exception as e:
            logger.error(f"Error parsing buffered telemetry payload: {e}")

    if not events:
        return "No events parsed"

    # 3. Gather unique gateway SNs and bulk-fetch model cache
    gateway_sns = {e.get("gateway_sn") for e in events if e.get("gateway_sn")}
    if not gateway_sns:
        return "No gateways identified in events"
    
    gateways = {g.serial_number: g for g in Gateway.objects.filter(serial_number__in=gateway_sns)}
    
    # 4. Bulk-fetch devices and build lookups to prevent N+1 DB hits
    gateway_ids = [g.id for g in gateways.values()]
    devices_qs = Device.objects.filter(gateway_id__in=gateway_ids)
    
    device_cache = {}
    device_by_id = {}
    for d in devices_qs:
        device_cache[(d.gateway_id, d.name)] = d
        device_by_id[d.id] = d
        
    telemetry_to_create = []
    gateway_updates = {}
    device_updates = {}
    alerts_to_check = []
    automations_to_eval = {}

    # 5. Process events and resolve targets
    for event in events:
        gateway_sn = event.get("gateway_sn")
        if not gateway_sn or gateway_sn not in gateways:
            continue
        
        gateway = gateways[gateway_sn]
        timestamp = event.get("timestamp") or timezone.now()
        device_id = event.get("device_id")
        device_name = event.get("device_name")
        values = dict(event.get("values", {}))
        
        # Remove device_name value helper
        values.pop("device_name", None)
        
        target_device = None
        
        # A. Match by device_id
        if device_id:
            try:
                d_id = int(device_id)
                target_device = device_by_id.get(d_id)
            except (ValueError, TypeError):
                pass
                
        # B. Fallback: match by device_name string
        if not target_device and device_name:
            target_device = device_cache.get((gateway.id, device_name))
            
        # C. Final fallback: first registered device on the gateway
        if not target_device:
            gateway_devices = [d for d in devices_qs if d.gateway_id == gateway.id]
            if gateway_devices:
                target_device = gateway_devices[0]
                
        if not target_device:
            continue
            
        # Update heartbeat logs
        gateway_updates[gateway.id] = timestamp
        device_updates[target_device.id] = timestamp
        
        # Build TelemetryData rows
        for key, value in values.items():
            data_point = TelemetryData(device=target_device, timestamp=timestamp, key=key)
            
            if isinstance(value, (int, float)):
                data_point.value_numeric = float(value)
            elif isinstance(value, bool):
                data_point.value_bool = value
            else:
                data_point.value_string = str(value)
                
            telemetry_to_create.append(data_point)
            
            # Queue for alerts check
            alerts_to_check.append((target_device, key, value))
            
        # Accumulate metrics per device/timestamp for automations engine
        if target_device.id not in automations_to_eval:
            automations_to_eval[target_device.id] = {}
        automations_to_eval[target_device.id].update(values)

    # 6. Execute database transactions in bulk
    if telemetry_to_create:
        TelemetryData.objects.bulk_create(telemetry_to_create)
        logger.info(f"Bulk-created {len(telemetry_to_create)} telemetry records.")
        
    # Bulk update Gateway heartbeats
    if gateway_updates:
        for g_id, last_seen_time in gateway_updates.items():
            Gateway.objects.filter(id=g_id).update(last_seen=last_seen_time, status="online")
            
    # Bulk update Device heartbeats
    if device_updates:
        for d_id, last_seen_time in device_updates.items():
            Device.objects.filter(id=d_id).update(last_telemetry_at=last_seen_time, status="online")
            
    # 7. Evaluate alerts and rules on the batch asynchronously (safe loops)
    for device, key, value in alerts_to_check:
        try:
            check_alerts_for_payload(device, key, value)
        except Exception as e:
            logger.error(f"Alert check failed for device {device.id}, key {key}: {e}")
            
    for d_id, vals in automations_to_eval.items():
        device = device_by_id.get(d_id)
        if device:
            try:
                evaluate_automations(device, vals)
            except Exception as e:
                logger.error(f"Automation evaluation failed for device {device.id}: {e}")
                
    return f"Ingested {len(telemetry_to_create)} points."


@shared_task
def flush_logs_buffer_task():
    r = redis.Redis.from_url(settings.REDIS_URL)
    queue_key = "logs_ingest_queue"
    
    with r.pipeline() as pipe:
        pipe.multi()
        pipe.lrange(queue_key, 0, -1)
        pipe.delete(queue_key)
        results = pipe.execute()
        
    if not results or not results[0]:
        return "No logs to ingest"
        
    payloads = results[0]
    
    grouped_logs = {}
    for raw_payload in payloads:
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
            gateway_sn = payload.get("serial_number")
            if not gateway_sn:
                continue
            if gateway_sn not in grouped_logs:
                grouped_logs[gateway_sn] = []
            grouped_logs[gateway_sn].extend(payload.get("logs", []))
        except Exception as e:
            logger.error(f"Error parsing buffered log payload: {e}")
            
    if not grouped_logs:
        return "No logs grouped"
        
    gateways = {g.serial_number: g for g in Gateway.objects.filter(serial_number__in=grouped_logs.keys())}
    
    logs_to_create = []
    for gateway_sn, entries in grouped_logs.items():
        gateway = gateways.get(gateway_sn)
        if not gateway:
            logger.warning(f"Gateway {gateway_sn} not found for log batch.")
            continue
            
        for entry in entries:
            ts = entry.get("ts")
            dt = (
                datetime.fromtimestamp(ts / 1000.0, tz=dt_timezone.utc)
                if ts
                else timezone.now()
            )
            
            logs_to_create.append(
                GatewayLog(
                    gateway=gateway,
                    timestamp=dt,
                    level=entry.get("level", "INFO"),
                    logger_name=entry.get("logger", ""),
                    message=entry.get("message", ""),
                    module=entry.get("module", ""),
                    line=entry.get("line"),
                )
            )
            
    if logs_to_create:
        GatewayLog.objects.bulk_create(logs_to_create)
        logger.info(f"Bulk-created {len(logs_to_create)} gateway logs.")
        
    return f"Ingested {len(logs_to_create)} logs."
