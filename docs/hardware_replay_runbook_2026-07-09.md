# Novena Hardware Replay Runbook - Round 2

Use this for the Laptop 2 -> Raspberry Pi CM4 -> Laptop 1 Novena Hub test.

Last reviewed against the hardened Hub/Gateway codebases on 2026-07-20.

## Topology

```text
Laptop 2 Modbus simulator
  Ethernet: 10.0.0.20:502
  -> Pi CM4 Novena Gateway
     Ethernet: 10.0.0.10/24
     Wi-Fi: same network as Laptop 1
     -> Laptop 1 Novena Hub + Mosquitto
        MQTT: 192.168.100.7:1883
```

`192.168.100.7` is the Laptop 1 broker IP from the previous verified run. Re-check it on test day and replace it in the Hub public MQTT settings and CM4 config if Windows/WSL reports a different Wi-Fi LAN IP.

Teacher note: `MQTT_BROKER_HOST=localhost` is correct for Django and the MQTT consumer because they run on Laptop 1. The CM4 cannot use `localhost`, because on the CM4 that means "the CM4 itself". The CM4 must use Laptop 1's LAN IP, for example `192.168.100.7`.

## Laptop 1 - Novena Hub

From WSL:

```bash
cd /home/shouheng/projects/Novena-Hub

# Stop a loopback-only system Mosquitto if it owns 1883.
# The Novena LAN test broker must listen on 0.0.0.0:1883.
sudo service mosquitto stop || sudo systemctl stop mosquitto

# Keep the Hub backend on localhost, but make customer-facing onboarding copy show the CM4-reachable broker.
grep -q '^PUBLIC_MQTT_BROKER_HOST=' .env && sed -i 's/^PUBLIC_MQTT_BROKER_HOST=.*/PUBLIC_MQTT_BROKER_HOST=192.168.100.7/' .env || printf '\nPUBLIC_MQTT_BROKER_HOST=192.168.100.7\n' >> .env
grep -q '^PUBLIC_MQTT_BROKER_PORT=' .env && sed -i 's/^PUBLIC_MQTT_BROKER_PORT=.*/PUBLIC_MQTT_BROKER_PORT=1883/' .env || printf 'PUBLIC_MQTT_BROKER_PORT=1883\n' >> .env
grep -q '^PUBLIC_MQTT_BROKER_SCHEME=' .env && sed -i 's/^PUBLIC_MQTT_BROKER_SCHEME=.*/PUBLIC_MQTT_BROKER_SCHEME=mqtt/' .env || printf 'PUBLIC_MQTT_BROKER_SCHEME=mqtt\n' >> .env

.agents/skills/novena-local-dev/scripts/start-novena-local-dev.sh
.agents/skills/novena-local-dev/scripts/health-check.sh
~/.venvs/novena/bin/python manage.py pilot_readiness_audit prepare
```

The final broker check must show `0.0.0.0:1883`, not only `127.0.0.1:1883`:

```bash
ss -ltnp | grep ':1883'
```

Expected:

```text
LISTEN ... 0.0.0.0:1883 ... mosquitto
```

If it shows only `127.0.0.1:1883`, the Pi will not reach the broker over Wi-Fi. Stop the system Mosquitto service, then restart the Novena dev stack.

Login:

```text
pilot.audit@novena.local / PilotReady123!
```

Hardware replay serials:

```text
NOV-AUDIT-COLD-HW     claim 4C9DFAA0
NOV-AUDIT-FACTORY-HW  claim F157DFD4
NOV-AUDIT-FACILITY-HW claim 695E82D6
```

For the Modbus TCP laptop simulator, start with the Factory Owner journey:

```text
/a/pilot-factory-energy/onboarding/
Serial: NOV-AUDIT-FACTORY-HW
Claim:  F157DFD4
```

Scope note: this runbook proves the Factory Owner Modbus TCP replay with the Laptop 2 simulator. It does not fully prove the cold-chain Modbus RTU journey or the facilities chiller/BACnet journey. Those still need either matching physical devices/adapters or a deliberate separate test template that represents the hardware you actually connect.

## Laptop 2 - Modbus Simulator

Set the Ethernet adapter connected to the Pi to:

```text
IP:      10.0.0.20
Netmask: 255.255.255.0
Gateway: blank
```

Install the simulator dependency and run the power-meter scenario:

```bash
python -m pip install "pymodbus==3.8.0"
python scripts/modbus_simulator.py --host 10.0.0.20 --port 502 --scenario factory
```

Use an administrator/elevated shell for port `502`.

Smoke-test from the Pi before starting the Gateway service:

```bash
ping -c 3 10.0.0.20
timeout 3 bash -c '</dev/tcp/10.0.0.20/502' && echo 'Modbus TCP reachable'
```

Teacher note: this only proves the TCP port is reachable. It does not prove the register map is correct. The register map is proven later when telemetry values land on the Hub dashboard with the expected labels and units.

## Pi CM4 - Gateway Install

Build a fresh Gateway release archive from the current Gateway source before copying it to the Pi:

```bash
cd /home/shouheng/projects/Novena-Gateway
mkdir -p dist
tar --exclude='__pycache__' --exclude='*.pyc' --exclude='*.log' --exclude='.pytest_cache' --exclude='.venv' --exclude='storage/sqlite' --exclude='storage/update' --exclude='dist' \
  -czf dist/novena-gateway-cm4-field-test-2026-07-20.tar.gz \
  --transform 's,^,novena-gateway-cm4-field-test-2026-07-20/,' \
  novena_gateway install requirements.txt setup.py install.sh novena-gateway.service config.json ARCHITECTURE.md
```

Copy `dist/novena-gateway-cm4-field-test-2026-07-20.tar.gz` to the Pi.

On the Pi:

```bash
tar -xzf novena-gateway-cm4-field-test-2026-07-20.tar.gz
cd novena-gateway-cm4-field-test-2026-07-20
```

Render the factory replay config for local plaintext MQTT. The packaged field-test config is a hardened template; this command fills the LAN values and removes the TLS block for the local `1883` broker:

```bash
python3 - <<'PY'
import json
from pathlib import Path

src = Path("install/field-test-configs/nov-audit-factory-hw.local.json")
dst = Path("/tmp/nov-audit-factory-hw.rendered.json")
cfg = json.loads(src.read_text())

cfg.setdefault("deployment", {})["mode"] = "local"
cfg["mqtt"]["host"] = "192.168.100.7"
cfg["mqtt"]["port"] = 1883
cfg["mqtt"]["password"] = "F157DFD4"
cfg["mqtt"]["allow_insecure_private_mqtt"] = True
cfg["mqtt"].pop("tls", None)
cfg["bootstrap_mqtt"]["password"] = "F157DFD4"

dst.write_text(json.dumps(cfg, indent=2) + "\n")
print(dst)
PY
```

Install with the rendered config already in `/etc/novena-gateway/config.json`. The installer preserves an existing config and validates it:

```bash
sudo mkdir -p /etc/novena-gateway
sudo cp /tmp/nov-audit-factory-hw.rendered.json /etc/novena-gateway/config.json

# First install applies hardware overlays/helper and may require a reboot.
sudo NOVENA_DEPLOYMENT_MODE=local bash install.sh

# If hardware setup changed boot overlays, reboot once, then continue.
sudo reboot
```

After reboot, validate, preflight, and start:

```bash
/opt/novena-gateway/venv/bin/python -m novena_gateway.main --config /etc/novena-gateway/config.json --validate-only
/opt/novena-gateway/venv/bin/python -m novena_gateway.main --config /etc/novena-gateway/config.json --preflight

sudo systemctl restart novena-gateway
sudo journalctl -u novena-gateway -f
```

If Laptop 1 is not `192.168.100.7`, edit `/etc/novena-gateway/config.json` before restart:

```bash
sudo nano /etc/novena-gateway/config.json
```

Confirm:

```json
"host": "192.168.100.7",
"port": 1883,
"allow_insecure_private_mqtt": true
```

Also confirm there is no `tls` block in `mqtt` for this local laptop replay.

## Critical Pre-Flight Checks

Before opening the browser onboarding flow, verify these from the Pi:

```bash
ping -c 3 192.168.100.7
timeout 3 bash -c '</dev/tcp/192.168.100.7/1883' && echo 'Laptop 1 MQTT reachable'
ping -c 3 10.0.0.20
timeout 3 bash -c '</dev/tcp/10.0.0.20/502' && echo 'Laptop 2 Modbus reachable'
sudo systemctl status novena-gateway --no-pager
```

Teacher note: these checks separate the two networks. Wi-Fi must reach Laptop 1 MQTT, while Ethernet must reach Laptop 2 Modbus. If either side fails, the Hub UI will look like a software problem even though the root cause is network reachability.

## Expected Sequence

1. Gateway connects to Mosquitto and sends heartbeat on `v1/gateway/attributes`.
2. Hub gateway page moves from claimed/offline to online.
3. Gateway discovery scans `10.0.0.20:502` and reports a Modbus TCP device.
4. Hub shows a suggested `Novena Power Meter PM-100` match.
5. Claim/setup flow creates the device and Hub pushes connector config.
6. Gateway acknowledges config, starts the Modbus connector, and publishes telemetry.
7. Device dashboard shows voltage, current, active power, frequency, and energy.
8. Simulator incident mode should trigger the power-spike alert; recovery mode should show values returning to normal.

Do not run `pilot_readiness_audit keepalive` during hardware replay. Keepalive refreshes simulated database state, while this replay needs the CM4 to prove the live heartbeat, discovery, config push, telemetry, alert, and recovery path.

## Evidence To Capture

- `ss -ltnp | grep ':1883'` on Laptop 1 showing `0.0.0.0:1883`.
- Laptop 2 simulator console showing changing factory readings.
- Pi `--validate-only` success.
- Pi `--preflight` output.
- Pi journal lines for MQTT connect, discovery report, config ACK, and Modbus polling.
- Hub onboarding screenshots: claim, wait/online, discovery match, config applied.
- Device dashboard with live voltage/current/active power/frequency/energy.
- Alert/recovery evidence and the maintenance ticket/work item.
