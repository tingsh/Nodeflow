# Novena Hardware Replay Runbook - Round 2

Use this for the Laptop 2 -> Raspberry Pi CM4 -> Laptop 1 Novena Hub test.

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

`192.168.100.7` is the Laptop 1 broker IP from the previous verified run. Re-check it on test day and replace it in the CM4 config if Windows/WSL reports a different Wi-Fi LAN IP.

## Laptop 1 - Novena Hub

From WSL:

```bash
cd /home/shouheng/projects/Novena-Hub
.agents/skills/novena-local-dev/scripts/start-novena-local-dev.sh
.agents/skills/novena-local-dev/scripts/health-check.sh
~/.venvs/novena/bin/python manage.py pilot_readiness_audit prepare
```

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

## Pi CM4 - Gateway Install

Use the Gateway release archive from:

```text
/home/shouheng/projects/Novena-Gateway/dist/novena-gateway-cm4-field-test-2026-07-09.tar.gz
```

On the Pi:

```bash
tar -xzf novena-gateway-cm4-field-test-2026-07-09.tar.gz
cd novena-gateway-cm4-field-test-2026-07-09
sudo NOVENA_DEPLOYMENT_MODE=local bash install.sh
sudo cp install/field-test-configs/nov-audit-factory-hw.local.json /etc/novena-gateway/config.json
sudo systemctl restart novena-gateway
sudo journalctl -u novena-gateway -f
```

If Laptop 1 is not `192.168.100.7`, edit `/etc/novena-gateway/config.json` before restart:

```bash
sudo nano /etc/novena-gateway/config.json
```

Change:

```json
"host": "192.168.100.7"
```


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
