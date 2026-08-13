# Novena Hardware Replay Guide - Round 2

This guide walks through the full live hardware/software integration test.

```text
Laptop 2 Modbus simulator
  -> Pi CM4 Novena Gateway
  -> Laptop 1 MQTT broker
  -> local Novena Hub
```

Last reviewed: 2026-08-11.

## Quick Reference

Test journey:

```text
Factory Owner / Modbus TCP
```

Hub URL:

```text
http://localhost:8000/
```

Onboarding URL:

```text
http://localhost:8000/a/pilot-factory-energy/onboarding/
```

Hub login:

```text
pilot.audit@novena.local / PilotReady123!
```

Gateway serial and claim code:

```text
Serial: NOV-AUDIT-FACTORY-HW
Claim:  F157DFD4
```

Laptop 1 MQTT broker:

```text
192.168.100.7:1883
```

Laptop 2 Modbus simulator:

```text
10.0.0.20:502
```

Gateway Git branch:

```text
main
```

## Network Layout

```text
Laptop 2
  Ethernet IP: 10.0.0.20/24
  Runs:        Modbus TCP simulator on port 502

Pi CM4 Novena Gateway
  Ethernet IP: 10.0.0.10/24
  Ethernet to: Laptop 2 / same unmanaged switch
  Wi-Fi to:    same LAN as Laptop 1

Laptop 1
  LAN IP:      192.168.100.7
  Runs:        Novena Hub + Mosquitto MQTT broker on port 1883
```

Teacher note: `localhost` means "this same machine." Hub can use `MQTT_BROKER_HOST=localhost` because Django and Mosquitto both run on Laptop 1. The Pi must not use `localhost` for MQTT, because on the Pi that would mean "connect to the Pi itself." The Pi must use Laptop 1's LAN IP.

## Before You Start

Keep three terminals available.

Terminal A:

```text
Laptop 1 / WSL
Purpose: Start Hub, MQTT, Celery, MQTT consumer, and prepare audit data
```

Terminal B:

```text
Laptop 2
Purpose: Run the Modbus simulator
```

Terminal C:

```text
Pi CM4
Purpose: Install/start Gateway and watch logs
```

If Laptop 1 no longer uses this IP, replace it everywhere in this guide before running commands:

```text
192.168.100.7
```

# Step 1 - Laptop 1: Prepare Novena Hub

## 1.1 Open The Hub Repo

Copy this into WSL on Laptop 1:

```bash
cd /home/shouheng/Novena-Platform/Novena-Hub
```

## 1.2 Confirm Laptop 1 IP

Copy:

```bash
hostname -I
```

Expected: one printed address should be reachable by the Pi. The previous working value was:

```text
192.168.100.7
```

## 1.3 Stop Conflicting Mosquitto

Copy:

```bash
sudo service mosquitto stop || sudo systemctl stop mosquitto
```

Why: the Novena dev stack starts its own MQTT broker configured for LAN testing. It must listen on:

```text
0.0.0.0:1883
```

It should not listen only on:

```text
127.0.0.1:1883
```

## 1.4 Update Hub Local MQTT Settings

Copy this whole block:

```bash
python3 - <<'PY'
from pathlib import Path

path = Path('.env')
values = {
    'MQTT_BROKER_HOST': 'localhost',
    'MQTT_BROKER_PORT': '1883',
    'PUBLIC_MQTT_BROKER_HOST': '192.168.100.7',
    'PUBLIC_MQTT_BROKER_PORT': '1883',
    'PUBLIC_MQTT_BROKER_SCHEME': 'mqtt',
    'MQTT_ACCEPT_LEGACY_SHARED_INBOUND': 'False',
}

lines = path.read_text().splitlines() if path.exists() else []
seen = set()
out = []

for line in lines:
    key = line.split('=', 1)[0] if '=' in line else None
    if key in values:
        out.append(f'{key}={values[key]}')
        seen.add(key)
    else:
        out.append(line)

for key, value in values.items():
    if key not in seen:
        out.append(f'{key}={value}')

path.write_text('\n'.join(out).rstrip() + '\n')
PY
```

Teacher note: this value is for Hub's internal connection:

```text
MQTT_BROKER_HOST=localhost
```

This value is what the Gateway should use from the network:

```text
PUBLIC_MQTT_BROKER_HOST=192.168.100.7
```

## 1.5 Generate The Guided Setup Signing Key

Copy this whole block:

```bash
~/.venvs/novena/bin/python - <<'PY'
import base64
import json
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

hub_env = Path('.env')
lines = hub_env.read_text().splitlines() if hub_env.exists() else []
values = {}

for line in lines:
    if '=' in line and not line.lstrip().startswith('#'):
        key, value = line.split('=', 1)
        values[key] = value

key_id = values.get('REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID') or 'local-replay-2026-08'
seed = ''

try:
    signing_keys = json.loads(values.get('REMOTE_CONTROL_SIGNING_KEYS') or '{}')
    seed = signing_keys.get(key_id, '')
except json.JSONDecodeError:
    seed = ''

seed = seed or values.get('REMOTE_CONTROL_SIGNING_PRIVATE_KEY', '')

if seed:
    private_key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(seed, validate=True))
else:
    private_key = Ed25519PrivateKey.generate()
    raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    seed = base64.b64encode(raw).decode()

public_raw = private_key.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw,
)
public_b64 = base64.b64encode(public_raw).decode()

updates = {
    'REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID': key_id,
    'REMOTE_CONTROL_SIGNING_KEYS': json.dumps({key_id: seed}, separators=(',', ':')),
    'REMOTE_CONTROL_SIGNING_PRIVATE_KEY': seed,
}

out = []
written = set()

for line in lines:
    key = line.split('=', 1)[0] if '=' in line else None
    if key in updates:
        out.append(f'{key}={updates[key]}')
        written.add(key)
    else:
        out.append(line)

for key, value in updates.items():
    if key not in written:
        out.append(f'{key}={value}')

hub_env.write_text('\n'.join(out).rstrip() + '\n')

Path('/tmp/novena-replay-gateway-public-key.env').write_text(
    f'GATEWAY_CONFIG_KEY_ID={key_id}\nGATEWAY_CONFIG_PUBLIC_KEY_B64={public_b64}\n'
)

print('Updated .env signing settings.')
print('Copy these two values to the Pi before rendering config:')
print(Path('/tmp/novena-replay-gateway-public-key.env').read_text())
PY
```

After it runs, keep the printed output. It should look like this:

```text
GATEWAY_CONFIG_KEY_ID=local-replay-2026-08
GATEWAY_CONFIG_PUBLIC_KEY_B64=<long-public-key-value>
```

You will paste those values into the Pi in Step 3.3.

## 1.6 Start Hub Services

Copy:

```bash
bash .agents/skills/novena-local-dev/scripts/start-novena-local-dev.sh
```

Then copy:

```bash
bash .agents/skills/novena-local-dev/scripts/health-check.sh
```

Expected services:

```text
Django
Redis
PostgreSQL
Mosquitto
Celery
MQTT consumer
Vite
```

## 1.7 Prepare Audit User And Gateway Inventory

Copy:

```bash
~/.venvs/novena/bin/python manage.py pilot_readiness_audit prepare
```

Expected login:

```text
pilot.audit@novena.local / PilotReady123!
```

Expected hardware replay gateway:

```text
NOV-AUDIT-FACTORY-HW / F157DFD4
```

## 1.8 Confirm MQTT Is LAN-Reachable

Copy:

```bash
ss -ltnp | grep ':1883'
```

Good result:

```text
LISTEN ... 0.0.0.0:1883 ... mosquitto
```

Bad result:

```text
LISTEN ... 127.0.0.1:1883 ... mosquitto
```

If you see only the bad result, the Pi cannot reach Laptop 1 MQTT over Wi-Fi.

# Step 2 - Laptop 2: Run The Modbus Simulator

## 2.1 Set Laptop 2 Ethernet IP

Configure the Ethernet adapter connected to the Pi:

```text
IP address: 10.0.0.20
Netmask:    255.255.255.0
Gateway:    blank
```

## 2.2 Get The Simulator Script

Use this file:

```text
/home/shouheng/Novena-Platform/Novena-Hub/scripts/modbus_simulator.py
```

You can copy just that file to Laptop 2, or clone/copy the Hub repo and run it from the `scripts/` directory.

## 2.3 Install Simulator Dependency

Copy on Laptop 2:

```bash
python -m pip install "pymodbus==3.8.0"
```

## 2.4 Start The Factory Power-Meter Simulator

Use an Administrator/elevated terminal because port `502` may require elevated permission.

Copy:

```bash
python scripts/modbus_simulator.py --host 10.0.0.20 --port 502 --scenario factory
```

Expected output:

```text
[modbus-sim] power=740.0 W current=3.20 A voltage=231.5 V mode=normal
```

Leave this running. Every ~90 seconds it moves between normal, incident, and recovery behavior.

# Step 3 - Pi CM4: Clone And Install Novena Gateway

## 3.1 Clone Gateway Main

Copy on the Pi:

```bash
cd ~
git clone git@github.com:tingsh/Novena-Gateway.git
cd Novena-Gateway
```

If the repo already exists on the Pi, copy this instead:

```bash
cd ~/Novena-Gateway
git fetch origin
git checkout main
git pull --ff-only origin main
```

## 3.2 Confirm You Are On Main

Copy:

```bash
git status --short --branch
```

Expected shape:

```text
## main...origin/main
```

## 3.3 Paste The Signing Public Key Values

Use the values printed by Laptop 1 in Step 1.5.

Copy these two lines, but replace the placeholder with the real value:

```bash
export GATEWAY_CONFIG_KEY_ID='local-replay-2026-08'
export GATEWAY_CONFIG_PUBLIC_KEY_B64='PASTE_PUBLIC_KEY_FROM_LAPTOP_1'
```

The second line must not contain this placeholder when you actually run the test:

```text
PASTE_PUBLIC_KEY_FROM_LAPTOP_1
```

## 3.4 Render The Local Gateway Config

Copy this whole block on the Pi:

```bash
python3 - <<'PY'
import json
import os
from pathlib import Path

src = Path('install/field-test-configs/nov-audit-factory-hw.local.json')
dst = Path('/tmp/nov-audit-factory-hw.rendered.json')
cfg = json.loads(src.read_text())

cfg.setdefault('deployment', {})['mode'] = 'local'
cfg['mqtt']['host'] = '192.168.100.7'
cfg['mqtt']['port'] = 1883
cfg['mqtt']['password'] = 'F157DFD4'
cfg['mqtt']['allow_insecure_private_mqtt'] = True
cfg['mqtt'].pop('tls', None)
cfg['bootstrap_mqtt']['password'] = 'F157DFD4'

features = cfg.setdefault('features', {})
remote_config = features.setdefault('remote_config', {})
rpc = features.setdefault('rpc', {})
key_id = os.environ['GATEWAY_CONFIG_KEY_ID']
public_key = os.environ['GATEWAY_CONFIG_PUBLIC_KEY_B64']

remote_config['trusted_clock'] = True
remote_config['trusted_config_keys'] = {key_id: public_key}
remote_config['revoked_config_key_ids'] = []
remote_config['config_journal_path'] = '/var/lib/novena-gateway/deployment_setup/config_journal.json'

rpc['trusted_clock'] = True
rpc['trusted_command_keys'] = {key_id: public_key}
rpc['revoked_command_key_ids'] = []

discovery = features.setdefault('discovery', {})
discovery['tcp_subnet_scan'] = False
discovery['tcp_hosts'] = ['10.0.0.20:502']
discovery['tcp_ports'] = [502]

cfg['connectors'] = []

dst.write_text(json.dumps(cfg, indent=2) + '\n')
print(dst)
PY
```

Expected output:

```text
/tmp/nov-audit-factory-hw.rendered.json
```

## 3.5 Install Gateway

Copy:

```bash
sudo mkdir -p /etc/novena-gateway
sudo cp /tmp/nov-audit-factory-hw.rendered.json /etc/novena-gateway/config.json
sudo NOVENA_DEPLOYMENT_MODE=local bash install.sh
```

If the installer says hardware overlays changed, reboot once:

```bash
sudo reboot
```

After reboot, return to the repo:

```bash
cd ~/Novena-Gateway
```

## 3.6 Validate Gateway Config

Copy:

```bash
/opt/novena-gateway/venv/bin/python -m novena_gateway.main --config /etc/novena-gateway/config.json --validate-only
```

Expected:

```text
Configuration is VALID.
```

## 3.7 Run Gateway Preflight

Copy:

```bash
/opt/novena-gateway/venv/bin/python -m novena_gateway.main --config /etc/novena-gateway/config.json --preflight
```

Expected: JSON output showing hardware/network checks. Save this output as evidence.

## 3.8 Check Network Reachability From The Pi

Copy:

```bash
ping -c 3 192.168.100.7
timeout 3 bash -c '</dev/tcp/192.168.100.7/1883' && echo 'Laptop 1 MQTT reachable'
ping -c 3 10.0.0.20
timeout 3 bash -c '</dev/tcp/10.0.0.20/502' && echo 'Laptop 2 Modbus reachable'
```

Expected:

```text
Laptop 1 MQTT reachable
Laptop 2 Modbus reachable
```

## 3.9 Start Gateway Service

Copy:

```bash
sudo systemctl restart novena-gateway
```

Then follow logs:

```bash
sudo journalctl -u novena-gateway -f
```

Look for:

```text
MQTT connected
Remote config handler started, listening on: v1/gateway/NOV-AUDIT-FACTORY-HW/config
Published gateway attributes
Discovery found/reported 10.0.0.20:502
```

# Step 4 - Laptop 1 Browser: Run Onboarding

## 4.1 Open The Factory Onboarding Page

Open this in the browser on Laptop 1:

```text
http://localhost:8000/a/pilot-factory-energy/onboarding/
```

Login:

```text
pilot.audit@novena.local / PilotReady123!
```

## 4.2 Claim The Gateway

Use:

```text
Gateway name: Factory Energy Gateway
Serial:       NOV-AUDIT-FACTORY-HW
Claim code:   F157DFD4
```

## 4.3 Complete Guided Setup

Expected flow:

```text
1. Hub accepts the serial and claim code.
2. Gateway connects and sends heartbeat attributes.
3. Hub shows the Gateway online.
4. Hub sees gateway_capabilities: ["guided_setup_v1"].
5. Discovery finds the Modbus simulator at 10.0.0.20:502.
6. Select the suggested power-meter template.
7. Run live validation/test read if prompted.
8. Apply the connector config.
9. Gateway acknowledges the config and starts polling Modbus.
10. Device dashboard receives voltage, current, active power, frequency, and energy.
```

Expected MQTT topics:

```text
v1/gateway/NOV-AUDIT-FACTORY-HW/attributes
v1/gateway/NOV-AUDIT-FACTORY-HW/telemetry
```

# Step 5 - Evidence Checklist

Capture these during the test:

```text
[ ] Laptop 1 broker check showing 0.0.0.0:1883.
[ ] Laptop 1 health check output.
[ ] Laptop 2 simulator console with changing readings.
[ ] Pi --validate-only output.
[ ] Pi --preflight output.
[ ] Pi journal lines for MQTT connection.
[ ] Pi journal lines for scoped attributes.
[ ] Pi journal lines for discovery.
[ ] Pi journal lines for config accepted/applied.
[ ] Pi journal lines for Modbus polling.
[ ] Hub screenshots for claim accepted, Gateway online, discovery match, validation, and config applied.
[ ] Hub dashboard showing live voltage/current/active power/frequency/energy.
[ ] Alert and recovery evidence from simulator incident mode.
```

# Troubleshooting

Pi cannot reach MQTT.

```text
Most likely cause: Laptop 1 broker bound only to loopback, wrong Wi-Fi IP, or firewall.
Check: Laptop 1 ss -ltnp output and Pi /dev/tcp/192.168.100.7/1883.
```

Gateway online but Guided Setup unavailable.

```text
Most likely cause: Missing signing public key or trusted_clock in Pi config.
Check: Gateway attributes must include gateway_capabilities: ["guided_setup_v1"].
```

Claim accepted but Gateway waits forever.

```text
Most likely cause: Activation not delivered/acknowledged or MQTT credentials mismatch.
Check: Hub activation records and Pi bootstrap credential logs.
```

Discovery finds nothing.

```text
Most likely cause: Laptop 2 IP/port wrong or simulator not elevated.
Check: Pi /dev/tcp/10.0.0.20/502 and Laptop 2 simulator console.
```

Config push fails.

```text
Most likely cause: Signing key mismatch or stale rendered config.
Check: Hub config error and Pi remote_config rejection logs.
```

Discovery works but no telemetry.

```text
Most likely cause: Connector config not applied or Modbus map mismatch.
Check: Pi config ACK, connector start logs, simulator output.
```

Hub dashboard stale.

```text
Most likely cause: MQTT consumer/Celery not running or scoped topic mismatch.
Check: Laptop 1 health check and mqtt-consumer-wsl.log.
```

# Scope Notes

This guide proves:

```text
Factory Owner Modbus TCP path with a Laptop 2 simulator
```

Still separate tests:

```text
Cold-chain Modbus RTU hardware replay
Facilities/HVAC BACnet hardware replay
Governed write-back on representative devices
Offline buffering across Gateway restart and MQTT reconnect
```
