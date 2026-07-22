import json
import logging

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger("novena_hub")

SCOPED_INBOUND_TOPICS = {
    "telemetry": "v1/gateway/+/telemetry",
    "logs": "v1/gateway/+/logs",
    "attributes": "v1/gateway/+/attributes",
    "rpc_response": "v1/gateway/+/rpc/response",
    "bootstrap_hello": "v1/gateway/+/bootstrap/hello",
}
LEGACY_SHARED_TOPICS = {
    "v1/gateway/telemetry": "telemetry",
    "v1/gateway/logs": "logs",
    "v1/gateway/attributes": "attributes",
    "v1/gateway/rpc/response": "rpc_response",
}


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
            for topic in SCOPED_INBOUND_TOPICS.values():
                client.subscribe(topic)
            if getattr(settings, "MQTT_ACCEPT_LEGACY_SHARED_INBOUND", False):
                for topic in LEGACY_SHARED_TOPICS:
                    client.subscribe(topic)
            self.stdout.write(
                self.style.NOTICE("Subscribed to scoped gateway inbound topics")
            )
        else:
            self.stdout.write(self.style.ERROR(f"Connection failed with code {reason_code}"))

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            message_type, gateway = self._resolve_inbound_gateway(msg.topic, payload)
            if not message_type or not gateway:
                return

            if message_type == "telemetry":
                self._handle_telemetry(payload, gateway=gateway, topic=msg.topic)
            elif message_type == "logs":
                self._handle_logs(payload, gateway=gateway)
            elif message_type == "attributes":
                self._handle_attributes(payload, gateway=gateway)
            elif message_type == "rpc_response":
                self._handle_rpc_response(payload, gateway=gateway)
            elif message_type == "bootstrap_hello":
                self._handle_bootstrap_hello(payload, gateway=gateway)
            else:
                logger.warning("Unknown MQTT topic: %s", msg.topic)
        except Exception as e:
            logger.error("Error processing MQTT message on %s: %s", msg.topic, e, exc_info=True)

    def _resolve_inbound_gateway(self, topic, payload):
        from apps.devices.models import Gateway

        parts = topic.split("/")
        message_type = None
        topic_serial = None

        if len(parts) >= 4 and parts[:2] == ["v1", "gateway"]:
            topic_serial = parts[2]
            suffix = "/".join(parts[3:])
            message_type = {
                "telemetry": "telemetry",
                "logs": "logs",
                "attributes": "attributes",
                "rpc/response": "rpc_response",
                "bootstrap/hello": "bootstrap_hello",
            }.get(suffix)

        if not message_type and topic in LEGACY_SHARED_TOPICS:
            if not getattr(settings, "MQTT_ACCEPT_LEGACY_SHARED_INBOUND", False):
                logger.warning("Rejected legacy shared MQTT topic while bridge is disabled: %s", topic)
                return None, None
            message_type = LEGACY_SHARED_TOPICS[topic]
            topic_serial = payload.get("serial_number")
            logger.warning(
                "Accepted legacy shared MQTT topic %s using payload serial %s. "
                "Enable only during Gateway migration.",
                topic,
                topic_serial or "missing",
            )

        if not message_type:
            logger.warning("Unknown MQTT topic: %s", topic)
            return None, None

        payload_serial = payload.get("serial_number")
        if topic_serial and payload_serial and payload_serial != topic_serial:
            logger.warning(
                "Rejected MQTT %s from topic serial %s with payload serial %s.",
                message_type,
                topic_serial,
                payload_serial,
            )
            return None, None

        if not topic_serial:
            logger.warning("Rejected MQTT %s on %s because no gateway serial was identified.", message_type, topic)
            return None, None

        gateway = Gateway.objects.filter(serial_number=topic_serial).first()
        if not gateway:
            logger.warning("Rejected MQTT %s for unknown gateway serial %s.", message_type, topic_serial)
            return None, None

        return message_type, gateway

    # ── Telemetry (Ingestion queueing and WebSockets broadcast) ──────────

    def _handle_telemetry(self, payload, gateway=None, topic="v1/gateway/telemetry"):
        """Queue telemetry data and broadcast it to the browser live stream."""
        cloud_received_at = timezone.now()
        trusted_gateway_sn = gateway.serial_number if gateway else None

        try:
            queued_payload = dict(payload)
            queued_payload['_cloud_received_at'] = cloud_received_at.isoformat()
            if trusted_gateway_sn:
                queued_payload['_topic_gateway_sn'] = trusted_gateway_sn
            self.redis_client.rpush('telemetry_ingest_queue', json.dumps(queued_payload))
        except Exception as e:
            logger.error('Failed to queue telemetry raw payload to Redis: %s', e)

        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer

            from apps.devices.models import Device, Gateway
            from apps.telemetry.mqtt_parser import parse_mqtt_payload
            from apps.utils.timezones import format_site_datetime, site_timezone_metadata

            events = parse_mqtt_payload(topic, payload, trusted_gateway_sn=trusted_gateway_sn)
            channel_layer = get_channel_layer()

            gateway_cache = {gateway.serial_number: gateway} if gateway else {}
            device_cache = {}
            device_by_id = {}

            for event in events:
                gateway_sn = event.get('gateway_sn')
                device_name = event.get('device_name')
                device_id = event.get('device_id')
                values = dict(event.get('values', {}))
                timestamp = event.get('timestamp') or cloud_received_at

                if device_name and 'device_name' not in values:
                    values['device_name'] = device_name

                if not gateway_sn:
                    continue

                if gateway_sn not in gateway_cache:
                    try:
                        gateway_cache[gateway_sn] = Gateway.objects.get(serial_number=gateway_sn)
                    except Gateway.DoesNotExist:
                        continue
                gateway = gateway_cache[gateway_sn]

                target_device = None
                if device_id:
                    try:
                        d_id = int(device_id)
                        if d_id not in device_by_id:
                            device_by_id[d_id] = Device.objects.filter(id=d_id, gateway=gateway).first()
                        target_device = device_by_id[d_id]
                    except (ValueError, TypeError):
                        logger.warning('Invalid telemetry device_id %s from gateway %s.', device_id, gateway_sn)

                if not target_device and device_name:
                    cache_key = (gateway.id, device_name)
                    if cache_key not in device_cache:
                        device_cache[cache_key] = Device.objects.filter(gateway=gateway, name=device_name).first()
                    target_device = device_cache[cache_key]

                if not target_device:
                    target_device = Device.objects.filter(gateway=gateway).first()
                    if target_device:
                        logger.warning(
                            'Using legacy first-device telemetry fallback for gateway %s. '
                            'Payload device_id=%s device_name=%s resolved_device=%s.',
                            gateway_sn,
                            device_id,
                            device_name,
                            target_device.id,
                        )

                if target_device:
                    timezone_data = site_timezone_metadata(target_device.site)
                    async_to_sync(channel_layer.group_send)(
                        f'device_{target_device.id}',
                        {
                            'type': 'telemetry_message',
                            'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                            'timestamp_local': format_site_datetime(timestamp, target_device.site),
                            **timezone_data,
                            'values': values,
                        },
                    )
        except Exception as e:
            logger.error('Error broadcasting WebSocket telemetry: %s', e, exc_info=True)

    # ── Remote Logging ──────────────────────────────────────────────────

    def _handle_logs(self, payload, gateway=None):
        """Queue log entries from a gateway to Redis."""
        try:
            queued_payload = dict(payload)
            if gateway:
                queued_payload["_topic_gateway_sn"] = gateway.serial_number
            self.redis_client.rpush("logs_ingest_queue", json.dumps(queued_payload))
        except Exception as e:
            logger.error(f"Failed to queue logs raw payload to Redis: {e}")


    # ── Attribute Sync / Heartbeat ──────────────────────────────────────

    def _handle_bootstrap_hello(self, payload, gateway=None):
        """Mark a released/unclaimed gateway as visible in bootstrap mode."""
        from apps.devices.models import Gateway
        from apps.devices.activation import retry_activation_for_gateway

        gateway_sn = gateway.serial_number if gateway else payload.get("serial_number")
        if not gateway_sn:
            return
        gateway = gateway or Gateway.objects.filter(serial_number=gateway_sn).first()
        if not gateway:
            logger.info("Bootstrap hello from unknown gateway %s", gateway_sn)
            return
        gateway.last_bootstrap_seen_at = timezone.now()
        if gateway.lifecycle_status in ("claimed", "release_pending"):
            gateway.lifecycle_status = "bootstrap_seen"
            gateway.save(update_fields=["last_bootstrap_seen_at", "lifecycle_status"])
        else:
            gateway.save(update_fields=["last_bootstrap_seen_at"])
        retry_activation_for_gateway(gateway)

    def _handle_attributes(self, payload, gateway=None):
        """Update gateway status from heartbeat attributes or LWT."""
        from apps.devices.models import Gateway, GatewayConfig

        gateway_sn = gateway.serial_number if gateway else payload.get("serial_number")
        if not gateway_sn:
            return

        if not gateway:
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
            "active_interface": "active_interface",
            "failover_count": "failover_count",
            "ethernet_status": "ethernet_status",
            "wifi_status": "wifi_status",
            "fourg_status": "fourg_status",
            "signal_strength": "signal_strength",
            "buffered_event_count": "buffered_event_count",
            "last_replay_status": "last_replay_status",
            "replay_failure_count": "replay_failure_count",
            "connectivity_checked_ts": "connectivity_checked_ts",
            "internet_reachable": "internet_reachable",
            "default_route_ok": "default_route_ok",
            "default_route_error": "default_route_error",
            "dns_ok": "dns_ok",
            "dns_error": "dns_error",
            "broker_host": "broker_host",
            "broker_port": "broker_port",
            "broker_tcp_ok": "broker_tcp_ok",
            "broker_tcp_error": "broker_tcp_error",
            "tls_ok": "tls_ok",
            "tls_error": "tls_error",
            "mqtt_connected": "mqtt_connected",
            "mqtt_last_error": "mqtt_last_error",
            "device_health": "device_health",
            "ota_status": "ota_status",
            "ota_version": "ota_version",
            "ota_error": "ota_error",
            "ota_rollback_performed": "ota_rollback_performed",
        }

        for attr_key, model_field in field_mapping.items():
            if attr_key in attrs:
                setattr(gateway, model_field, attrs[attr_key])
                update_fields.append(model_field)

        if attrs.get("status") == "online" and gateway.lifecycle_status == "claimed":
            gateway.lifecycle_status = "online"
            update_fields.append("lifecycle_status")

        gateway.save(update_fields=list(dict.fromkeys(update_fields)))

        # Handle discovery report from Edge auto-scan
        discovery_report = attrs.get("discovery_report")
        if discovery_report:
            self._process_discovery_report(gateway, discovery_report)

        # Handle config update acknowledgement
        config_request_id = attrs.get("config_update_request_id")
        if config_request_id:
            try:
                config_record = GatewayConfig.objects.get(request_id=config_request_id, gateway=gateway)
                config_status = attrs.get("config_update_status", "unknown")
                config_record.status = config_status
                config_record.error_message = attrs.get("config_update_error", "") or ""
                config_record.rollback_performed = bool(attrs.get("rollback_performed", False))
                config_record.connector_results = attrs.get("connector_results", []) or []
                config_record.acknowledged_at = timezone.now()
                config_record.save(update_fields=[
                    "status",
                    "error_message",
                    "rollback_performed",
                    "connector_results",
                    "acknowledged_at",
                ])
                if config_status == "success":
                    gateway.lifecycle_status = "active"
                    gateway.save(update_fields=["lifecycle_status"])
                logger.info(
                    "Config update %s acknowledged: %s", config_request_id, config_record.status
                )
            except GatewayConfig.DoesNotExist:
                pass

        credential_status = attrs.get("credential_update_status")
        if credential_status:
            credential_action = attrs.get("credential_update_action")
            credential_request_id = attrs.get("credential_update_request_id")
            if credential_action == "activate" and credential_request_id:
                from apps.devices.activation import acknowledge_gateway_activation

                activation = acknowledge_gateway_activation(
                    gateway,
                    credential_request_id,
                    credential_status,
                    attrs.get("credential_update_error", "") or "",
                )
                if activation and credential_status == "success":
                    gateway.credential_rotation_status = "success"
                    if gateway.lifecycle_status in ("claimed", "bootstrap_seen", "activating"):
                        gateway.lifecycle_status = "online"
                    gateway.save(update_fields=["credential_rotation_status", "lifecycle_status"])
                elif activation:
                    gateway.credential_rotation_status = credential_status
                    gateway.save(update_fields=["credential_rotation_status"])
            else:
                gateway.credential_rotation_status = credential_status
                gateway.save(update_fields=["credential_rotation_status"])

        logger.debug("Updated attributes for gateway %s (status=%s)", gateway_sn, attrs.get("status"))

    # ── RPC Response ────────────────────────────────────────────────────

    def _handle_rpc_response(self, payload, gateway=None):
        """Process RPC command response from a gateway."""
        from apps.devices.models import RpcCommand

        request_id = payload.get("request_id")
        if not request_id:
            return

        try:
            if gateway:
                rpc_record = RpcCommand.objects.get(request_id=request_id, gateway=gateway)
            else:
                rpc_record = RpcCommand.objects.get(request_id=request_id)
            rpc_record.status = payload.get("status", "unknown")
            rpc_record.result = payload.get("result")
            rpc_record.error_message = payload.get("error", "") or ""
            rpc_record.responded_at = timezone.now()
            rpc_record.save()
            from apps.devices.services import sync_device_command_from_rpc

            sync_device_command_from_rpc(rpc_record)
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
        discovered_devices = report.get("discovered_devices", [])
        from apps.devices.discovery_matching import enrich_discovered_device

        discovered_devices = [enrich_discovered_device(device) for device in discovered_devices]

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
