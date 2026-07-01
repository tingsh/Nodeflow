# Hardware Test Handoff - 2026-06-26

This note captures the local end-to-end hardware test performed with Laptop 1, Raspberry Pi CM4, and Laptop 2. Use it to resume in a fresh Codex chat.

## Verified End-to-End Flow

The test was successfully verified:

```text
Laptop 2 modbus_simulator.py
  -> Ethernet / Modbus TCP
Pi CM4 running novena-gateway
  -> Wi-Fi / MQTT port 1883
Laptop 1 Mosquitto broker + Novena Hub backend
  -> Django dashboard
Novena Hub UI device page
```

Important correction: this is the local Novena Hub UI running on Laptop 1, not production cloud. It simulates the intended production architecture.

## Current Test Entities

- Team: `novena`
- Gateway page: `/a/novena/devices/gateways/11/`
- Device page: `/a/novena/devices/8/`
- Device: `Power meter 1`
- Gateway serial: `GW-TEST-001`
- Gateway MQTT username: `GW-TEST-001`
- Gateway claim/password used for test: `57AD1321`
- Pi Wi-Fi IP observed: `192.168.100.178`
- Laptop 1 broker IP from Pi: `192.168.100.7`
- MQTT test port: `1883`
- Production MQTT target later: `8883` with TLS

## Pi Edge Config Notes

The active systemd service uses:

```text
/opt/novena-gateway/config.json
```

The user had also edited:

```text
~/novena-gateway/config_local.json
```

For the service to use a config, it must be copied to `/opt/novena-gateway/config.json` or the systemd unit must be changed.

Working local test values:

- MQTT host: `192.168.100.7`
- MQTT port: `1883`
- MQTT topic: `v1/gateway/telemetry`
- Modbus target from Pi to Laptop 2: `10.0.0.1:502`

Laptop 2 simulator register mapping that matched the Pi config:

- `current`: holding register `3000`, `float32`, 2 registers
- `voltage`: holding register `3028`, `float32`, 2 registers
- `active_power`: holding register `3060`, `float32`, 2 registers
- Function code: `3`
- Byte order: `BIG`
- Word order: `BIG`

## Issues Encountered

1. **Django and Vite startup friction on Windows/sandbox**

   Django and Vite did run, but launching them through the Codex sandbox was slow and occasionally unreliable. Vite hit `spawn EPERM` around `esbuild` in the sandbox. Django startup could run into duplicated `Path` / `PATH` environment behavior when launched through `Start-Process`.

2. **Mosquitto listener confusion**

   The installed Windows Mosquitto service was seen listening on `127.0.0.1:1883`, which is fine for local-only clients but not reachable by the Pi over Wi-Fi. For Pi testing, Mosquitto needs to listen on the Laptop 1 LAN IP, using the local `mosquitto/lan-test.conf`.

3. **MQTT port clarification**

   Local test uses non-TLS MQTT on `1883`. Production should use TLS MQTT on `8883`. The codebase also references `1884` for Mosquitto dynamic-security admin/provisioning, but that is not the telemetry port.

4. **Pi edge service used the wrong config path at first**

   Editing `~/novena-gateway/config_local.json` alone did not affect the running service because systemd starts novena-gateway with `/opt/novena-gateway/config.json`.

5. **Pi pymodbus version mismatch**

   The Pi had `pymodbus 3.13.1`, but the connector code expected APIs available in older versions, resulting in errors such as missing `pymodbus.payload`, missing `pymodbus.device`, and missing `Endian` import behavior. Installing `pymodbus==3.8.0` in `/opt/novena-gateway/venv` allowed the Modbus connector to load.

6. **Modbus register mismatch**

   Earlier Pi config used incorrect addresses/types. The Laptop 2 simulator was producing non-zero values, but the Pi was not reading the intended registers until the config matched `3000`, `3028`, and `3060` as `float32`.

7. **Redis was missing locally**

   Real Redis was not installed/running on Laptop 1. A lightweight development Redis-compatible shim was created at `scripts/dev_miniredis.py` and started on `127.0.0.1:6379` to let ingestion queues work during the test.

8. **Celery worker was not running**

   Since Celery was not running, telemetry queued in Redis needed flushing. A helper script `scripts/dev_flush_redis_queues.py` was created to call telemetry/log flush tasks every few seconds.

9. **Dashboard Chart.js import issue**

   The generic Chart.js CDN URL did not expose the expected global `Chart` reliably. The template was changed to load:

   ```html
   https://cdn.jsdelivr.net/npm/chart.js@4.4.9/dist/chart.umd.min.js
   ```

10. **Dashboard WebSocket live updates failed with mini Redis**

   The local mini Redis shim supports enough list commands for ingestion queues, but not the full Redis feature set needed by Django Channels. As a result, WebSocket live streaming showed reconnecting. A 5-second dashboard polling fallback was added in `templates/devices/device_detail.html`, and the badge now shows `Polling 5s`.

## Verification Evidence

Backend logs showed telemetry flushing repeatedly:

```text
Popped raw telemetry payloads from Redis.
Bulk-created telemetry records.
```

Recent database values for device `8` showed changing telemetry:

```text
active_power 2.426
voltage      223.789993
current      10.84
```

The browser dashboard was sampled over time and values changed, for example:

```text
active_power: 3.3 -> 3.1
current:      14.5 -> 12.9
voltage:      224.8 -> 237.0
```

## Follow-Up Work For Next Session

- Replace `scripts/dev_miniredis.py` with real local Redis for development.
- Run proper Celery worker locally instead of the queue flush helper.
- Fix or document the reliable Windows startup commands for Django, Vite, Mosquitto, Redis, MQTT consumer, and Celery.
- Decide whether the dashboard should keep polling fallback permanently, or only use it when WebSocket connection fails.
- Review dynamic-security provisioning design: decide whether admin provisioning should stay on separate port `1884`, use `1883` locally, or use `8883` with strict TLS/ACLs in production.
- Add a first-class local hardware test runbook for Laptop 1 + Pi CM4 + Laptop 2.
- Fix the Pi edge dependency pinning so `pymodbus==3.8.0` or a compatible connector version is installed consistently.
