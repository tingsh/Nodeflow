# Telemetry And Gateway Protocol Reference

## MQTT Topics
Inbound Edge to Cloud:

- v1/gateway/telemetry: telemetry payloads.
- v1/gateway/attributes: heartbeat, firmware, network, and gateway attributes.
- v1/gateway/logs: gateway log events.
- v1/gateway/rpc/response: RPC responses.

Outbound Cloud to Edge:

- v1/gateway/{serial}/config: remote connector config push.
- v1/gateway/{serial}/rpc/request: command/RPC request.
- v1/gateway/{serial}/attributes/request: attribute sync request.
- v1/gateway/{serial}/provision: provisioning response.

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
