import json
import logging
from datetime import datetime, timezone as dt_timezone

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.telemetry.services import ingest_telemetry_data

logger = logging.getLogger("iot_platform")


class Command(BaseCommand):
    help = "Starts the MQTT consumer service to ingest device telemetry and edge gateway messages"

    def handle(self, *args, **options):
        import redis
        self.redis_client = redis.Redis.from_url(settings.REDIS_URL)

        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=settings.MQTT_CONSUMER_CLIENT_ID
        )

        client.on_connect = self.on_connect
        client.on_message = self.on_message

        # Connect to broker
        broker_host = settings.MQTT_BROKER_HOST
        broker_port = settings.MQTT_BROKER_PORT

        self.stdout.write(self.style.SUCCESS(f"Connecting to MQTT Broker at {broker_host}:{broker_port}..."))

        try:
            client.connect(broker_host, broker_port, 60)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not connect to MQTT Broker: {e}"))
            return

        # Start the loop
        client.loop_forever()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.stdout.write(self.style.SUCCESS("Connected to MQTT Broker successfully."))
            # Subscribe to all inbound topics
            client.subscribe("v1/gateway/telemetry")
            client.subscribe("v1/gateway/logs")
            client.subscribe("v1/gateway/attributes")
            client.subscribe("v1/gateway/rpc/response")
            self.stdout.write(
                self.style.NOTICE("Subscribed to: telemetry, logs, attributes, rpc/response")
            )
        else:
            self.stdout.write(self.style.ERROR(f"Connection failed with code {reason_code}"))

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())

            if msg.topic == "v1/gateway/telemetry":
                self._handle_telemetry(payload)
            elif msg.topic == "v1/gateway/logs":
                self._handle_logs(payload)
            elif msg.topic == "v1/gateway/attributes":
                self._handle_attributes(payload)
            elif msg.topic == "v1/gateway/rpc/response":
                self._handle_rpc_response(payload)
            else:
                logger.warning("Unknown MQTT topic: %s", msg.topic)
        except Exception as e:
            logger.error("Error processing MQTT message on %s: %s", msg.topic, e, exc_info=True)

    # ── Telemetry (Ingestion queueing and WebSockets broadcast) ──────────

    def _handle_telemetry(self, payload):
        """Ingest telemetry data from a gateway."""
        # 1. Queue to Redis
        try:
            self.redis_client.rpush("telemetry_ingest_queue", json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to queue telemetry raw payload to Redis: {e}")

        # 2. Broadcast via WebSockets
        try:
            from apps.telemetry.mqtt_parser import parse_mqtt_payload
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            from apps.devices.models import Device, Gateway
            
            events = parse_mqtt_payload("v1/gateway/telemetry", payload)
            channel_layer = get_channel_layer()

            gateway_cache = {}
            device_cache = {}
            device_by_id = {}

            for event in events:
                gateway_sn = event.get("gateway_sn")
                device_name = event.get("device_name")
                device_id = event.get("device_id")
                values = dict(event.get("values", {}))
                timestamp = event.get("timestamp") or timezone.now()

                if device_name and "device_name" not in values:
                    values["device_name"] = device_name

                if not gateway_sn:
                    continue

                # Cache lookup for Gateway
                if gateway_sn not in gateway_cache:
                    try:
                        gateway_cache[gateway_sn] = Gateway.objects.get(serial_number=gateway_sn)
                    except Gateway.DoesNotExist:
                        continue
                gateway = gateway_cache[gateway_sn]

                # Cache lookup for Device
                target_device = None
                if device_id:
                    try:
                        d_id = int(device_id)
                        if d_id not in device_by_id:
                            device_by_id[d_id] = Device.objects.filter(id=d_id, gateway=gateway).first()
                        target_device = device_by_id[d_id]
                    except (ValueError, TypeError):
                        pass
                
                if not target_device and device_name:
                    cache_key = (gateway.id, device_name)
                    if cache_key not in device_cache:
                        device_cache[cache_key] = Device.objects.filter(gateway=gateway, name=device_name).first()
                    target_device = device_cache[cache_key]

                if not target_device:
                    target_device = Device.objects.filter(gateway=gateway).first()

                if target_device:
                    # Broadcast to WebSocket channel group
                    async_to_sync(channel_layer.group_send)(
                        f"device_{target_device.id}",
                        {
                            "type": "telemetry_message",
                            "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                            "values": values,
                        }
                    )
        except Exception as e:
            logger.error(f"Error broadcasting WebSocket telemetry: {e}", exc_info=True)

    # ── Remote Logging ──────────────────────────────────────────────────

    def _handle_logs(self, payload):
        """Queue log entries from a gateway to Redis."""
        try:
            self.redis_client.rpush("logs_ingest_queue", json.dumps(payload))
        except Exception as e:
            logger.error(f"Failed to queue logs raw payload to Redis: {e}")


    # ── Attribute Sync / Heartbeat ──────────────────────────────────────

    def _handle_attributes(self, payload):
        """Update gateway status from heartbeat attributes or LWT."""
        from apps.devices.models import Gateway, GatewayConfig

        gateway_sn = payload.get("serial_number")
        if not gateway_sn:
            return

        try:
            gateway = Gateway.objects.get(serial_number=gateway_sn)
        except Gateway.DoesNotExist:
            logger.warning("Gateway %s not found for attribute sync", gateway_sn)
            return

        attrs = payload.get("attributes", {})

        # Update gateway fields
        update_fields = ["last_seen"]
        gateway.last_seen = timezone.now()

        field_mapping = {
            "status": "status",
            "firmware_version": "firmware_version",
            "ip_address": "ip_address",
            "uptime_seconds": "uptime_seconds",
            "python_version": "python_version",
            "platform": "platform_info",
            "connected_devices": "connected_devices",
            "active_connectors": "active_connectors",
        }

        for attr_key, model_field in field_mapping.items():
            if attr_key in attrs:
                setattr(gateway, model_field, attrs[attr_key])
                update_fields.append(model_field)

        gateway.save(update_fields=update_fields)

        # Handle discovery report from Edge auto-scan
        discovery_report = attrs.get("discovery_report")
        if discovery_report:
            self._process_discovery_report(gateway, discovery_report)

        # Handle config update acknowledgement
        config_request_id = attrs.get("config_update_request_id")
        if config_request_id:
            try:
                config_record = GatewayConfig.objects.get(request_id=config_request_id)
                config_record.status = attrs.get("config_update_status", "unknown")
                config_record.error_message = attrs.get("config_update_error", "") or ""
                config_record.acknowledged_at = timezone.now()
                config_record.save()
                logger.info(
                    "Config update %s acknowledged: %s", config_request_id, config_record.status
                )
            except GatewayConfig.DoesNotExist:
                pass

        logger.debug("Updated attributes for gateway %s (status=%s)", gateway_sn, attrs.get("status"))

    # ── RPC Response ────────────────────────────────────────────────────

    def _handle_rpc_response(self, payload):
        """Process RPC command response from a gateway."""
        from apps.devices.models import RpcCommand

        request_id = payload.get("request_id")
        if not request_id:
            return

        try:
            rpc_record = RpcCommand.objects.get(request_id=request_id)
            rpc_record.status = payload.get("status", "unknown")
            rpc_record.result = payload.get("result")
            rpc_record.error_message = payload.get("error", "") or ""
            rpc_record.responded_at = timezone.now()
            rpc_record.save()
            logger.info(
                "RPC response for %s (%s): %s",
                request_id,
                payload.get("method"),
                rpc_record.status,
            )
        except RpcCommand.DoesNotExist:
            logger.warning("RPC response for unknown request_id: %s", request_id)

    # ── Discovery Report Processing ─────────────────────────────────────

    def _process_discovery_report(self, gateway, report):
        """
        Process a discovery report from the Edge gateway.
        Stores it in Gateway.discovery_data and auto-matches against DeviceTemplates.
        """
        from apps.devices.models import DeviceTemplate

        discovered_devices = report.get("discovered_devices", [])

        # Auto-match each discovered device against templates
        for device in discovered_devices:
            identification = device.get("identification") or {}
            vendor = (identification.get("vendor") or "").strip().lower()
            model = (identification.get("model") or "").strip().lower()
            signature = (device.get("signature") or "").strip().lower()

            matched_template = None

            # 1. Try exact vendor + model match
            if vendor and model:
                matched_template = DeviceTemplate.objects.filter(
                    manufacturer__iexact=vendor,
                    model_number__iexact=model,
                ).first()

            # 2. Fallback: match by signature against template name
            if not matched_template and signature and signature != "unknown":
                matched_template = (
                    DeviceTemplate.objects.filter(name__icontains=signature).first()
                    or DeviceTemplate.objects.filter(manufacturer__icontains=signature).first()
                )

            if matched_template:
                device["matched_template_id"] = matched_template.id
                device["matched_template_name"] = matched_template.name

        # Store enriched discovery data
        gateway.discovery_data = {
            "last_discovered_at": str(timezone.now()),
            "scan_ts": report.get("scan_ts"),
            "scan_type": report.get("scan_type", "unknown"),
            "interfaces": report.get("interfaces", []),
            "devices": discovered_devices,
            "errors": report.get("errors", []),
        }
        gateway.save(update_fields=["discovery_data"])

        logger.info(
            "Discovery report processed for %s: %d devices found, %d matched",
            gateway.serial_number,
            len(discovered_devices),
            sum(1 for d in discovered_devices if d.get("matched_template_id")),
        )
