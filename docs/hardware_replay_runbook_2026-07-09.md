# Novena Hardware Replay Guide - Round 2

This guide walks through the second-round live hardware/software integration test.

```text
Laptop 2 simulated Modbus device
  -> Pi CM4 Novena Gateway
  -> MQTT broker on Laptop 1 port 1883
  -> local Novena Hub on Laptop 1
```

Last reviewed: 2026-08-18.

## Quick Reference

Use these values unless your network has changed.

```text
Hub URL:                 http://localhost:8000/
Onboarding URL:          http://localhost:8000/a/pilot-factory-energy/onboarding/
Hub login:               pilot.audit@novena.local / PilotReady123!
Gateway serial:          NOV-AUDIT-FACTORY-HW
Gateway claim/password:  F157DFD4
Laptop 1 MQTT:           192.168.100.7:1883
Laptop 2 Modbus:         10.0.0.20:502
Gateway branch:          main
```

Teacher note: `localhost` means "this same machine." Hub can use `localhost` because Django, the MQTT consumer, and Mosquitto run on Laptop 1. The Pi must use Laptop 1's LAN IP, not `localhost`, because `localhost` on the Pi means the Pi itself.

## Network Layout

```text
Laptop 1
  Role:      Novena Hub + Mosquitto MQTT broker
  LAN IP:    192.168.100.7
  MQTT:      0.0.0.0:1883

Pi CM4 Gateway
  Role:      Novena Gateway
  Wi-Fi:     same LAN as Laptop 1
  Ethernet:  same wired test network as Laptop 2

Laptop 2
  Role:      Modbus TCP simulator
  Ethernet:  10.0.0.20/24
  Modbus:    10.0.0.20:502
```

Keep three terminals open: Laptop 1 WSL, Laptop 2, and Pi CM4 SSH/terminal.

# Step 1 - Laptop 1: Prepare Hub And MQTT

## 1.1 Confirm Laptop 1 IP

Run this in WSL on Laptop 1:

```bash
hostname -I
```

Expected: one address is reachable by the Pi over Wi-Fi. The previous working address was:

```text
192.168.100.7
```

Use your actual reachable IP in the next command.

## 1.2 Run The Hub Hardware-Test Helper

```bash
cd /home/shouheng/Novena-Platform/Novena-Hub
bash scripts/hardware-test/prepare_laptop1_hub.sh --mqtt-host 192.168.100.7
```

What this does:

- Sets Hub's internal MQTT connection to `localhost:1883`.
- Sets the Gateway-facing MQTT address to `192.168.100.7:1883`.
- Generates or reuses the Guided Setup signing key.
- Prints the Gateway-facing public key values.
- Starts local Hub services and runs the local health check.
- Prepares the pilot audit user and the replay Gateway inventory.

Expected success signals:

```text
Gateway-facing Guided Setup public key:
GATEWAY_CONFIG_KEY_ID=local-replay-2026-08
GATEWAY_CONFIG_PUBLIC_KEY_B64=<base64-public-key>

OK: MQTT is listening on 0.0.0.0:1883 for the Pi.
Laptop 1 is prepared for hardware replay.
```

Keep the two `GATEWAY_CONFIG_*` values. You will paste them into the Pi command in Step 3.3.

## 1.3 Verify Laptop 1 Services

```bash
bash .agents/skills/novena-local-dev/scripts/health-check.sh
ss -ltnp | grep ':1883'
```

Expected:

```text
Django, Redis, PostgreSQL, Mosquitto, Celery, MQTT consumer, and Vite are healthy.
LISTEN ... 0.0.0.0:1883 ... mosquitto
```

If MQTT shows only `127.0.0.1:1883`, the Pi will not be able to reach the broker.

# Step 2 - Laptop 2: Run The Modbus Simulator

## 2.1 Set Laptop 2 Ethernet IP

Configure the Ethernet adapter connected to the Pi test network:

```text
IP address: 10.0.0.20
Netmask:    255.255.255.0
Gateway:    blank
```

## 2.2 Start The Simulator

Copy `scripts/modbus_simulator.py` from the Hub repo to Laptop 2, or run it from a cloned Hub checkout.

Install the dependency:

```bash
python -m pip install "pymodbus==3.8.0"
```

Start the factory power-meter simulator:

```bash
python scripts/modbus_simulator.py --host 10.0.0.20 --port 502 --scenario factory
```

Expected output:

```text
[modbus-sim] power=740.0 W current=3.20 A voltage=231.5 V mode=normal
```

Leave this running. Port `502` may require an elevated terminal on some operating systems.

# Step 3 - Pi CM4: Install Gateway Config And Service

## 3.1 Clone Or Update Gateway Main

New Pi checkout:

```bash
cd ~
git clone git@github.com:tingsh/Novena-Gateway.git
cd Novena-Gateway
```

Existing Pi checkout:

```bash
cd ~/Novena-Gateway
git fetch origin
git checkout main
git pull --ff-only origin main
```

Verify:

```bash
git status --short --branch
```

Expected:

```text
## main...origin/main
```

## 3.2 Confirm Network Reachability From The Pi

```bash
ping -c 3 192.168.100.7
ping -c 3 10.0.0.20
timeout 3 bash -c '</dev/tcp/192.168.100.7/1883' && echo 'Laptop 1 MQTT reachable'
timeout 3 bash -c '</dev/tcp/10.0.0.20/502' && echo 'Laptop 2 Modbus reachable'
```

Expected:

```text
Laptop 1 MQTT reachable
Laptop 2 Modbus reachable
```

## 3.3 Render And Install The Local Gateway Config

Use the public key values printed by Laptop 1 in Step 1.2.

```bash
sudo python3 install/hardware-test/render_local_replay_config.py \
  --mqtt-host 192.168.100.7 \
  --mqtt-password F157DFD4 \
  --public-key-id local-replay-2026-08 \
  --public-key-b64 'PASTE_PUBLIC_KEY_FROM_LAPTOP_1' \
  --modbus-host 10.0.0.20
```

Expected:

```text
Wrote Gateway config: /etc/novena-gateway/config.json
MQTT target: 192.168.100.7:1883
Guided Setup key id: local-replay-2026-08
Manual fallback Modbus target: 10.0.0.20:502
```

Teacher note: this helper keeps the hardening requirement intact. Hub keeps the private signing key; the Pi only receives the public key and will reject Guided Setup/config commands that are not signed by the matching private key.

## 3.4 Install Or Refresh Gateway Service

```bash
sudo NOVENA_DEPLOYMENT_MODE=local bash install.sh
```

If the installer says hardware overlays changed, reboot once:

```bash
sudo reboot
```

After reboot:

```bash
cd ~/Novena-Gateway
```

## 3.5 Validate Gateway Before Starting The Test

```bash
/opt/novena-gateway/venv/bin/python -m novena_gateway.main \
  --config /etc/novena-gateway/config.json \
  --validate-only
```

Expected:

```text
Configuration is VALID.
```

Run preflight:

```bash
/opt/novena-gateway/venv/bin/python -m novena_gateway.main \
  --config /etc/novena-gateway/config.json \
  --preflight
```

Expected: JSON output showing Gateway hardware and network checks. Save this output as evidence.

## 3.6 Start Gateway And Watch Logs

```bash
sudo systemctl restart novena-gateway
sudo journalctl -u novena-gateway -f
```

Expected log signals:

```text
MQTT connected
Remote config handler started, listening on: v1/gateway/NOV-AUDIT-FACTORY-HW/config
Published gateway attributes
Discovery is ready for signed on-demand scans; background scanning is disabled.
```

No discovery result is expected during startup. Discovery now begins only after the
operator clicks **Scan for devices** in Hub. Gateway health reporting and configured
device telemetry polling remain active independently of discovery.

# Step 4 - Laptop 1 Browser: Claim And Complete Guided Setup

Open:

```text
http://localhost:8000/a/pilot-factory-energy/onboarding/
```

Login:

```text
pilot.audit@novena.local / PilotReady123!
```

Claim the Gateway:

```text
Gateway name: Factory Energy Gateway
Serial:       NOV-AUDIT-FACTORY-HW
Claim code:   F157DFD4
```

Expected flow:

```text
1. Hub accepts the serial and claim code.
2. Gateway connects and sends heartbeat attributes.
3. Hub shows the Gateway online.
4. Hub sees gateway_capabilities: ["guided_setup_v1"].
5. Hub shows Ready to scan. Click Scan for devices.
6. Hub shows Scanning connected devices and target progress.
7. Hub shows Found 1 device for 10.0.0.20:502. If it shows No devices found or Scan failed, use the manual fallback below.
8. Select the suggested power-meter template.
9. Run live validation/test read if prompted.
10. Apply the connector config. Continue remains disabled until equipment has validated successfully.
11. Gateway acknowledges the signed config and starts polling Modbus.
12. Device dashboard receives voltage, current, active power, frequency, and energy.
```

The scan button creates a new scan ID and sends a signed, serial-scoped command to
the Gateway. Retry creates a different scan ID, so a late result from the earlier
attempt cannot complete the new scan.

## 4.1 Manual Fallback If The Scan Finds Nothing

Select **Add device manually**, then enter:

```text
Equipment name:  Factory Replay Power Meter
Protocol:        Modbus TCP
Manufacturer:    Novena
Model:           NPM-100
Device type:     Power meter
Host:            10.0.0.20
Port:            502
Slave ID:        1
Timeout:         3 seconds
Byte order:      BIG
Word order:      BIG
```

Use these read-only holding-register signals from the factory simulator. Each value
is a big-endian 32-bit float occupying two registers:

```text
Key            Address  Function  Count  Type     Scale  Unit
current        3000     3         2      float32  1      A
voltage        3028     3         2      float32  1      V
active_power   3060     3         2      float32  1      W
frequency      3100     3         2      float32  1      Hz
energy         3200     3         2      float32  1      kWh
```

Save the manual equipment, run its read-only validation, confirm the decoded values,
then deploy. Manual entry bypasses device finding only; it does not bypass signed
commands, live validation, or configuration trust checks.

Expected MQTT topics:

```text
v1/gateway/NOV-AUDIT-FACTORY-HW/attributes
v1/gateway/NOV-AUDIT-FACTORY-HW/telemetry
v1/gateway/NOV-AUDIT-FACTORY-HW/config
```

# Evidence Checklist

Capture these during the test:

```text
[ ] Laptop 1 helper output showing public key and MQTT 0.0.0.0:1883.
[ ] Laptop 1 health check output.
[ ] Laptop 2 simulator console with changing readings.
[ ] Pi config-render helper output.
[ ] Pi --validate-only output.
[ ] Pi --preflight output.
[ ] Pi journal lines for MQTT connection.
[ ] Pi journal lines for scoped attributes.
[ ] Hub screenshot showing Ready to scan before the operator starts discovery.
[ ] Hub screenshot and Pi journal lines for the signed user-triggered scan and its scan ID.
[ ] Hub screenshot showing Found 1 device, or the completed manual fallback and validation.
[ ] Pi journal lines for signed config accepted/applied.
[ ] Pi journal lines for Modbus polling.
[ ] Hub screenshots for claim accepted, Gateway online, discovery match, validation, and config applied.
[ ] Hub dashboard showing live voltage/current/active power/frequency/energy.
[ ] Alert and recovery evidence from simulator incident mode.
```

# Troubleshooting

## MQTT Broker Not Reachable

Symptoms:

```text
Pi /dev/tcp check fails, Gateway logs show MQTT connect errors, or Hub never sees Gateway online.
```

Check on Laptop 1:

```bash
ss -ltnp | grep ':1883'
```

Good:

```text
LISTEN ... 0.0.0.0:1883 ... mosquitto
```

Fix: rerun the Laptop 1 helper, confirm Windows firewall allows inbound TCP `1883`, and make sure no separate system Mosquitto is bound only to `127.0.0.1`.

## Wrong Laptop 1 IP

Symptoms:

```text
Laptop 1 services are healthy, but the Pi cannot ping or open 192.168.100.7:1883.
```

Check the actual WSL/LAN IP:

```bash
hostname -I
```

Fix: rerun Laptop 1 helper with the correct `--mqtt-host`, then rerun the Pi config renderer with the same corrected IP.

## Modbus Simulator Not Reachable

Symptoms:

```text
Pi cannot open 10.0.0.20:502, discovery finds nothing, or Gateway logs show Modbus TCP connection failures.
```

Check from the Pi:

```bash
ping -c 3 10.0.0.20
timeout 3 bash -c '</dev/tcp/10.0.0.20/502' && echo 'Laptop 2 Modbus reachable'
```

Fix: confirm Laptop 2 Ethernet is `10.0.0.20/24`, the simulator is still running, and the simulator terminal has permission to bind port `502`.

## Scan Finds No Devices But TCP Is Reachable

Symptoms:

```text
The Pi can open 10.0.0.20:502, but Hub shows No devices found.
```

Check that the Pi Ethernet interface has an active private address in the same
directly attached network, for example `10.0.0.10/24`:

```bash
ip -4 addr show up
timeout 3 bash -c '</dev/tcp/10.0.0.20/502' && echo 'Laptop 2 Modbus reachable'
sudo journalctl -u novena-gateway -n 160 --no-pager | grep -E 'discovery|10.0.0.20|scan_id'
```

Then click **Retry scan**. Discovery deliberately scans only private physical
interfaces and at most the directly attached `/24` window. It excludes loopback,
containers, virtual interfaces, public addresses and cellular WAN. If the simulator
is routed rather than directly attached, use **Add device manually** with
`10.0.0.20:502`, slave `1`, and the register map in Step 4.1.

## Gateway Rejects Signed Config

Symptoms:

```text
Hub says config push failed, Gateway logs mention signature verification, untrusted key, or guided setup unavailable.
```

Check the Pi config:

```bash
sudo python3 - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path('/etc/novena-gateway/config.json').read_text())
print('remote_config:', cfg['features']['remote_config']['trusted_clock'], list(cfg['features']['remote_config']['trusted_config_keys']))
print('rpc:', cfg['features']['rpc']['trusted_clock'], list(cfg['features']['rpc']['trusted_command_keys']))
PY
```

Fix: copy the exact `GATEWAY_CONFIG_KEY_ID` and `GATEWAY_CONFIG_PUBLIC_KEY_B64` from Laptop 1 again, rerun the Pi config renderer, then restart `novena-gateway`.

## Telemetry Does Not Appear In Hub

Symptoms:

```text
Gateway is online, but the device dashboard is stale or empty.
```

Check Laptop 1 services:

```bash
bash .agents/skills/novena-local-dev/scripts/health-check.sh
tail -n 80 mqtt-consumer-wsl.log
```

Check Pi logs:

```bash
sudo journalctl -u novena-gateway -n 120 --no-pager
```

Fix: confirm the config was applied, Modbus polling started, and telemetry is publishing on `v1/gateway/NOV-AUDIT-FACTORY-HW/telemetry`.

# Scope Notes

This guide proves the Factory Owner Modbus TCP replay path with a Laptop 2 simulator.

Still separate tests:

```text
Cold-chain Modbus RTU hardware replay
Facilities/HVAC BACnet hardware replay
Governed write-back on representative devices
Offline buffering across Gateway restart and MQTT reconnect
```
