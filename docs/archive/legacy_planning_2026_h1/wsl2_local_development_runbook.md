> **Historical reference — do not use as current implementation guidance.** Use the active `novena-hub-development-workflow` and `novena-local-dev` skills listed in the [documentation authority index](../../README.md).

# Novena Native WSL2 Local Development Runbook

This is the current local development path for hardware testing. It mirrors the production service topology without requiring Docker on the laptop.

## Service Topology

Run these services natively inside WSL2:

- PostgreSQL or Timescale-compatible database
- Redis
- Mosquitto
- Django web process
- Celery worker
- Celery Beat
- MQTT consumer
- Vite frontend server

Docker remains the production deployment reference. Local WSL2 should use the same logical services and environment variables so hardware-test behavior stays close to production.

## Status Model

Novena now separates three different health signals:

- Gateway health means cloud-to-edge connectivity. It is based on MQTT LWT or gateway heartbeat attributes.
- Device freshness means field-device telemetry age. It is based on the device sample timestamp and template polling interval.
- Browser stream state means UI delivery mode. It tells the user whether WebSocket or polling fallback is feeding the page.

Customer-facing copy should avoid bare online or offline labels. Prefer examples like:

- Live · updated 4s ago
- Delayed · last sample 42s ago
- Offline · last sample 5m ago
- Gateway online · heartbeat 18s ago
- Gateway offline · last heartbeat 3m ago

## Historical Windows Workarounds

The following items were useful during the Windows Redis and Mosquitto troubleshooting period, but they are not the default local path anymore:

- Mini Redis helper
- Manual Redis queue flusher
- Windows Mosquitto LAN configs
- Sandboxed PowerShell startup notes

Keep them as historical references only unless a Windows-only hardware test explicitly needs them again.
