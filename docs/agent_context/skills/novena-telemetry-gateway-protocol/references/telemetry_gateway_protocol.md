# Telemetry And Gateway Protocol Reference

## MQTT Topics
Inbound Edge to Cloud:

- v1/gateway/{serial}/telemetry: telemetry payloads.
- v1/gateway/{serial}/attributes: heartbeat, firmware, network, and gateway attributes.
- v1/gateway/{serial}/logs: gateway log events.
- v1/gateway/{serial}/rpc/response: RPC responses.
- v1/gateway/{serial}/bootstrap/hello: activation or automatic credential-reissue hello.

Hub must derive Gateway identity from the topic serial and the factory inventory's current claimed Gateway. Payload `serial_number` is diagnostic metadata only; if present and different from the topic serial, reject the message. Released or historical Gateway rows must never receive inbound traffic.

Outbound Cloud to Edge:

- v1/gateway/{serial}/config: remote connector config push.
- v1/gateway/{serial}/rpc/request: command/RPC request.
- v1/gateway/{serial}/attributes/request: attribute sync request.
- v1/gateway/{serial}/bootstrap/activate: time-bounded activation credentials.

Remote configuration is available only to Gateways advertising `guided_setup_v1`. Hub sends a signed, idempotent envelope and never falls back to unsigned configuration. Gateway acknowledgements arrive on the attributes topic and must exactly match request ID, revision, checksum, and idempotency key. Broker publication means `published`; it does not mean the Gateway accepted or applied the configuration.

## Device Matching
- Generated Hub connector configs should include deviceId for each configured field device.
- Gateway Modbus conversion preserves that as ConvertedData.device_id.
- Gateway payload formatting sends top-level device_id.
- Hub ingestion matches by device_id first, then exact device name.
- First-device-on-gateway fallback is backward compatibility only and should log a warning.

## Important Hub Files
- MQTT consumer: apps/telemetry/management/commands/mqtt_consumer.py.
- MQTT parser: apps/telemetry/mqtt_parser.py.
- Ingestion tasks/services: apps/telemetry/tasks.py, apps/telemetry/services.py.
- Publisher: apps/telemetry/mqtt_publisher.py.
- Config generator: apps/devices/config_generator.py.
- Freshness: apps/devices/freshness.py, apps/devices/tasks.py.
- Device detail UI: templates/devices/device_detail.html.

## Freshness Model
- Device freshness is based on last_telemetry_at, template default_polling_interval, and settings thresholds.
- Gateway freshness is based on last_seen and GATEWAY_OFFLINE_SECONDS.
- Alarm status has higher priority than normal freshness status.
- Customer-safe wording should include last seen context, such as Live - updated 4s ago, Delayed - last sample 42s ago, or Gateway offline - last heartbeat 3m ago.

## Browser Stream Model
- WebSocket is the normal production live-data path.
- Polling is a degraded fallback when WebSocket fails, closes, or becomes stale.
- Polling should not run immediately in parallel with a healthy WebSocket.
- Fallback interval should respect plan latency and use at least max(5s, team latency limit).
- Badge language should distinguish Live, Reconnecting, and Polling fallback.

## Telemetry Samples API
- Endpoint: GET /a/<team_slug>/telemetry/api/samples/<device_id>/?limit=20.
- Allowed sample limits: 10, 20, 30, 40, 50.
- Rows are grouped by telemetry timestamp, newest first.
- Columns come from template/register metadata first, then discovered telemetry keys.
- Units belong in column headers, not repeated in every cell.
