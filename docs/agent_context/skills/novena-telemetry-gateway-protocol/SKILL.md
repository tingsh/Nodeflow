---
name: novena-telemetry-gateway-protocol
description: Use for Hub or Gateway changes involving MQTT telemetry, gateway attributes, RPC, remote config, deviceId/device_id matching, telemetry samples APIs, freshness states, WebSocket live updates, or polling fallback behavior.
---

# Novena Telemetry Gateway Protocol

Read references/telemetry_gateway_protocol.md before changing MQTT consumers/publishers, gateway config generation, payload formatting, device matching, live telemetry UI, heartbeat freshness, or telemetry APIs.

Keep three states conceptually separate:

1. Gateway health: cloud-to-edge connectivity and gateway heartbeat.
2. Device freshness: field-device telemetry recency.
3. Browser stream: WebSocket or polling delivery mode.
