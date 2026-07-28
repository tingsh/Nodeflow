import json
import logging
from datetime import UTC, datetime

import redis
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.alerts.services import check_alerts_for_payload
from apps.automations.engine import evaluate_automations
from apps.devices.models import Device, Gateway
from apps.telemetry.models import GatewayLog, TelemetryData
from apps.telemetry.mqtt_parser import parse_mqtt_payload

logger = logging.getLogger("novena_hub")


def _parse_cloud_received_at(value):
    if not value:
        return timezone.now()
    if hasattr(value, "isoformat"):
        return value
    parsed = parse_datetime(str(value))
    if not parsed:
        return timezone.now()
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, UTC)
    return parsed


@shared_task
def flush_telemetry_buffer_task():
    r = redis.Redis.from_url(settings.REDIS_URL)
    queue_key = "telemetry_ingest_queue"

    with r.pipeline() as pipe:
        pipe.multi()
        pipe.lrange(queue_key, 0, -1)
        pipe.delete(queue_key)
        results = pipe.execute()

    if not results or not results[0]:
        return "No telemetry to ingest"

    payloads = results[0]
    logger.info("Popped %d raw telemetry payloads from Redis.", len(payloads))

    events = []
    for raw_payload in payloads:
        try:
            payload_dict = json.loads(raw_payload.decode("utf-8"))
            cloud_received_at = _parse_cloud_received_at(payload_dict.pop("_cloud_received_at", None))
            trusted_gateway_sn = payload_dict.pop("_topic_gateway_sn", None)
            trusted_gateway_id = payload_dict.pop("_topic_gateway_id", None)
            parsed_events = parse_mqtt_payload(
                "v1/gateway/telemetry",
                payload_dict,
                trusted_gateway_sn=trusted_gateway_sn,
            )
            for event in parsed_events:
                event["_cloud_received_at"] = cloud_received_at
                event["_topic_gateway_id"] = trusted_gateway_id
            events.extend(parsed_events)
        except Exception as e:
            logger.error("Error parsing buffered telemetry payload: %s", e)

    if not events:
        return "No events parsed"

    gateway_sns = {e.get("gateway_sn") for e in events if e.get("gateway_sn")}
    if not gateway_sns:
        return "No gateways identified in events"

    gateway_ids_from_transport = {
        int(e["_topic_gateway_id"])
        for e in events
        if e.get("_topic_gateway_id") is not None and str(e["_topic_gateway_id"]).isdigit()
    }
    gateways_by_id = {
        g.pk: g
        for g in Gateway.objects.filter(
            pk__in=gateway_ids_from_transport,
            inventory_record__status="claimed",
        ).exclude(lifecycle_status__in=["release_pending", "released"])
    }

    gateway_ids = list(gateways_by_id)
    devices = list(Device.objects.filter(gateway_id__in=gateway_ids))
    device_cache = {(d.gateway_id, d.name): d for d in devices}
    device_by_id = {d.id: d for d in devices}
    devices_by_gateway = {}
    for device in devices:
        devices_by_gateway.setdefault(device.gateway_id, []).append(device)

    telemetry_to_create = []
    gateway_updates = {}
    device_updates = {}
    alerts_to_check = []
    automations_to_eval = {}
    db_flushed_at = timezone.now()

    for event in events:
        gateway_sn = event.get("gateway_sn")
        gateway_id = event.get("_topic_gateway_id")
        try:
            gateway = gateways_by_id.get(int(gateway_id))
        except (TypeError, ValueError):
            gateway = None
        if not gateway or gateway.serial_number != gateway_sn:
            continue
        timestamp = event.get("timestamp") or timezone.now()
        cloud_received_at = event.get("_cloud_received_at") or db_flushed_at
        device_id = event.get("device_id")
        device_name = event.get("device_name")
        values = dict(event.get("values", {}))
        values.pop("device_name", None)

        target_device = None

        if device_id:
            try:
                d_id = int(device_id)
                matched = device_by_id.get(d_id)
                if matched and matched.gateway_id == gateway.id:
                    target_device = matched
                elif matched:
                    logger.warning(
                        "Telemetry device_id %s belongs to gateway %s, not payload gateway %s.",
                        device_id,
                        matched.gateway.serial_number if matched.gateway else "none",
                        gateway_sn,
                    )
            except (ValueError, TypeError):
                logger.warning("Invalid telemetry device_id %s from gateway %s.", device_id, gateway_sn)

        if not target_device and device_name:
            target_device = device_cache.get((gateway.id, device_name))

        if not target_device:
            gateway_devices = devices_by_gateway.get(gateway.id, [])
            if len(gateway_devices) == 1:
                target_device = gateway_devices[0]
                logger.warning(
                    "Using legacy first-device telemetry fallback for gateway %s (single configured device). "
                    "Payload device_id=%s device_name=%s resolved_device=%s.",
                    gateway_sn,
                    device_id,
                    device_name,
                    target_device.id,
                )
            elif len(gateway_devices) > 1:
                logger.warning(
                    "Rejected ambiguous telemetry for gateway %s. Payload device_id=%s device_name=%s; "
                    "the gateway has multiple configured devices.",
                    gateway_sn,
                    device_id,
                    device_name,
                )

        if not target_device:
            continue

        gateway_updates[gateway.id] = cloud_received_at
        device_updates[target_device.id] = timestamp

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

            telemetry_to_create.append(data_point)
            alerts_to_check.append((target_device, key, value))

        automations_to_eval.setdefault(target_device.id, {}).update(values)

    if telemetry_to_create:
        TelemetryData.objects.bulk_create(telemetry_to_create)
        logger.info("Bulk-created %d telemetry records.", len(telemetry_to_create))

    if gateway_updates:
        for g_id, last_seen_time in gateway_updates.items():
            Gateway.objects.filter(id=g_id).update(last_seen=last_seen_time, status="online")

    if device_updates:
        for d_id, last_seen_time in device_updates.items():
            Device.objects.filter(id=d_id, status="alarm").update(last_telemetry_at=last_seen_time)
            Device.objects.filter(id=d_id).exclude(status="alarm").update(
                last_telemetry_at=last_seen_time,
                status="online",
            )

    for device, key, value in alerts_to_check:
        try:
            check_alerts_for_payload(device, key, value)
        except Exception as e:
            logger.error("Alert check failed for device %s, key %s: %s", device.id, key, e)

    for d_id, vals in automations_to_eval.items():
        device = device_by_id.get(d_id)
        if device:
            try:
                evaluate_automations(device, vals)
            except Exception as e:
                logger.error("Automation evaluation failed for device %s: %s", device.id, e)

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
            gateway_sn = payload.pop("_topic_gateway_sn", None) or payload.get("serial_number")
            gateway_id = payload.pop("_topic_gateway_id", None)
            if not gateway_sn or gateway_id is None:
                continue
            grouped_logs.setdefault((str(gateway_id), gateway_sn), []).extend(payload.get("logs", []))
        except Exception as e:
            logger.error("Error parsing buffered log payload: %s", e)

    if not grouped_logs:
        return "No logs grouped"

    gateway_ids = [int(key[0]) for key in grouped_logs if key[0].isdigit()]
    gateways = {
        str(g.pk): g
        for g in Gateway.objects.filter(pk__in=gateway_ids, inventory_record__status="claimed").exclude(
            lifecycle_status__in=["release_pending", "released"]
        )
    }

    logs_to_create = []
    for (gateway_id, gateway_sn), entries in grouped_logs.items():
        gateway = gateways.get(gateway_id)
        if not gateway or gateway.serial_number != gateway_sn:
            logger.warning("Gateway %s not found for log batch.", gateway_sn)
            continue

        for entry in entries:
            ts = entry.get("ts")
            dt = datetime.fromtimestamp(ts / 1000.0, tz=UTC) if ts else timezone.now()

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
        logger.info("Bulk-created %d gateway logs.", len(logs_to_create))

    return f"Ingested {len(logs_to_create)} logs."
