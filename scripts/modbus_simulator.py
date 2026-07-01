"""
Novena Gateway — Modbus TCP Field Device Simulator
=================================================
Simulates a power meter with 3 registers:
  - Holding Register 3000: Current       (32-bit float, Big Endian)
  - Holding Register 3028: Voltage       (32-bit float, Big Endian)
  - Holding Register 3060: Active Power  (32-bit float, Big Endian)

These register addresses match the default config.json in Novena Gateway.

SETUP:
  1. Set this laptop's Ethernet adapter to static IP: 10.0.0.1
  2. Install dependency: pip install pymodbus
  3. Run as Administrator (required for port 502):
       python modbus_simulator.py
  4. Connect an Ethernet cable from this laptop to the Pi CM4.

The Pi will poll these registers every 5 seconds and stream the values
to Novena Hub via MQTT.
"""

import random
import struct
import threading
import time

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.server import StartTcpServer

# ── Register addresses (must match Novena Gateway config.json) ──────────────
REG_CURRENT     = 3000   # FC3 read, 2 registers (32-bit float)
REG_VOLTAGE     = 3028   # FC3 read, 2 registers (32-bit float)
REG_ACTIVE_PWR  = 3060   # FC3 read, 2 registers (32-bit float)

# ── Total holding register block (0 to 4000) ───────────────────────────────
store = ModbusSequentialDataBlock(0, [0] * 4000)
slave_context = ModbusSlaveContext(hr=store, zero_mode=True)
context = ModbusServerContext(slaves=slave_context, single=True)

# ── Device identity ────────────────────────────────────────────────────────
identity = ModbusDeviceIdentification()
identity.VendorName  = "Novena"
identity.ProductCode = "NF-PM-SIM-001"
identity.ProductName = "Novena Simulated Power Meter"
identity.ModelName   = "Sim Power Meter v1.0"
identity.VendorUrl   = "https://${NOVENA_DOMAIN}"


def float_to_registers(value: float):
    """
    Pack a 32-bit float into two 16-bit Modbus holding registers.
    Uses Big Endian byte order and Big Word order (most common in industrial devices).
    """
    packed = struct.pack(">f", value)          # Big-endian 32-bit float -> 4 bytes
    high_word = struct.unpack(">H", packed[0:2])[0]  # First 2 bytes -> high word
    low_word  = struct.unpack(">H", packed[2:4])[0]  # Last 2 bytes  -> low word
    return [high_word, low_word]


def update_values():
    """
    Continuously updates the simulated register values with realistic power meter readings.
    Runs in a background thread every 5 seconds.
    """
    print("\n[Simulator] Data update thread started.", flush=True)
    while True:
        # Generate realistic simulated readings
        current      = round(random.uniform(10.0, 15.0), 2)  # Amps
        voltage      = round(random.uniform(220.0, 240.0), 2)  # Volts
        active_power = round((current * voltage) / 1000.0, 3)  # kW

        # Convert floats to pairs of 16-bit Modbus registers
        store.setValues(REG_CURRENT,    float_to_registers(current))
        store.setValues(REG_VOLTAGE,    float_to_registers(voltage))
        store.setValues(REG_ACTIVE_PWR, float_to_registers(active_power))

        print(
            f"[Simulator] ⚡ Current: {current:.2f} A  |  "
            f"Voltage: {voltage:.2f} V  |  "
            f"Power: {active_power:.3f} kW",
            flush=True
        )
        time.sleep(5)


if __name__ == "__main__":
    print("==========================================", flush=True)
    print("  Novena Modbus TCP Simulator (V2.0)  ", flush=True)
    print("==========================================", flush=True)
    print("  Simulating a Power Meter at 10.0.0.1  ", flush=True)
    print("  Registers:                            ", flush=True)
    print("    3000 -> Current      (A)            ", flush=True)
    print("    3028 -> Voltage      (V)            ", flush=True)
    print("    3060 -> Active Power (kW)           ", flush=True)
    print("==========================================", flush=True)
    print("  ⚠ Make sure this laptop's Ethernet   ", flush=True)
    print("    adapter is set to: 10.0.0.1        ", flush=True)
    print("==========================================", flush=True)
    print("  Starting server on 10.0.0.1:502...   ", flush=True)
    print("  Press Ctrl+C to stop.                ", flush=True)
    print("==========================================\n", flush=True)

    # Start background thread to update register values
    updater = threading.Thread(target=update_values, daemon=True)
    updater.start()

    # Give the updater a moment to write initial values
    time.sleep(1)

    try:
        # Bind to this laptop's static IP on the standard Modbus port
        StartTcpServer(
            context=context,
            identity=identity,
            address=("10.0.0.1", 502)
        )
    except PermissionError:
        print("\n[ERROR] Binding to port 502 requires Administrator privileges!", flush=True)
        print("[INFO]  Please close this window and re-run as Administrator:", flush=True)
        print("        Right-click on CMD -> 'Run as administrator'", flush=True)
        print("        Then run: python modbus_simulator.py\n", flush=True)
    except OSError as e:
        print(f"\n[ERROR] Could not bind to 10.0.0.1:502 — {e}", flush=True)
        print("[INFO]  Make sure your Ethernet adapter is configured with static IP 10.0.0.1", flush=True)
        print("[INFO]  Check: Control Panel -> Network Adapters -> Ethernet -> IPv4 Properties\n", flush=True)
