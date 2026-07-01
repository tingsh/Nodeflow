# Edge Simulation Strategy & Integration Blueprint

> **Date:** April 14, 2026
> **Focus:** Validating the 3-device simulation topology, defining the integration contract between Novena Hub and Novena Gateway, and providing a blueprint for the separate Edge codebase.

---

## 1. The 3-Device Simulation Topology: Brilliant Approach

Your idea to use three separate computers on a local network (LAN) is a **fantastic and highly professional approach**. 

Why is this better than testing everything on one PC or diving straight into the Siemens PLC?
1. **It proves the network architecture.** You will deal with real IP addresses, port routing, and firewall rules across three different OS environments—exactly what happens in a real factory.
2. **It isolates the Modbus protocol.** By running a Modbus TCP server on Laptop 2, we prove that Laptop 1 can actually read standard industrial protocols, rather than just mocking data internally.
3. **No PLC programming required.** Wiring and programming the Siemens S7-1200 takes hours. A Python Modbus simulator takes minutes.

### The Network Topology

```text
┌───────────────────────────┐        ┌────────────────────────────┐        ┌─────────────────────────┐
│     LAPTOP 2 (Equipment)  │        │ LAPTOP 1 (Novena Gateway)   │        │   PC (Novena Hub)   │
│                           │        │                            │        │                         │
│ Runs: Modbus TCP Server   │        │ Runs: Python Edge Gateway  │        │ Runs: Django + Postgres │
│ OS: Windows/Mac/Linux     │        │ OS: Windows/Mac/Linux      │        │ Runs: Mosquitto Broker  │
│ IP: 192.168.1.102         │        │ IP: 192.168.1.101          │        │ IP: 192.168.1.100       │
│                           │        │                            │        │                         │
│ Behavior: Hosts port 502. ◄────────┼─ Modbus Polling (TCP 502) ─┤        │                         │
│ Generates fake kW/V data  │        │ Validates data, converts   │        │                         │
│ in holding registers 1-10.│        │ to Novena JSON schema.   ├────────┼─► MQTT Publish Auth'd   │
└───────────────────────────┘        └────────────────────────────┘        │   (TCP 1883 or 9001)    │
                                                                           └─────────────────────────┘
```

---

## 2. Phase 1 Testing: The "50-Line" Custom Scripts

As discussed, before we fork the massive ThingsBoard gateway codebase, we should do a minimalist proof-of-concept across these three devices. 

I will write two Python scripts (savable in an `edge_sim/` folder in this repo for easy copying):

**Script A for Laptop 2 (`modbus_equipment_sim.py`):**
Uses the Python `pymodbus` library to launch an asynchronous Modbus TCP Server on port 502. It will have a background task that constantly randomly fluctuates the values in holding registers (e.g., simulating Voltage on Register 1, Power on Register 2).

**Script B for Laptop 1 (`simple_edge_gateway.py`):**
Uses `pymodbus` to read registers from Laptop 2. Takes those numbers, packages them into our expected MQTT JSON format, and uses `paho-mqtt` to publish to the Mosquitto broker running on the PC.

**Success Criteria:** You run script A on Laptop 2, script B on Laptop 1. You look at your PC monitor, and the Novena web dashboard charts are updating in real-time.

---

## 3. Novena Gateway Blueprint (For the New Workspace)

When you are ready to open a new AntiGravity workspace to build the actual **Novena Gateway** repository (the TB Gateway fork), you need to give the AI agent context.

**Copy and paste the following specification into the new workspace's initial prompt or save it as a `blueprint.md` file in the new repo:**

---

### 📄 BLUEPRINT: NOVENA EDGE GATEWAY (DO NOT REMOVE)

**Project Goal:** 
You are building `Novena Gateway`, a Python-based IoT gateway software designed to run on industrial hardware (Raspberry Pi CM4, Teltonika, etc.). Your goal is to securely read data from local industrial equipment (Modbus TCP/RTU) and publish it to a cloud MQTT broker.

**Architecture:**
This project is a strategic fork of the open-source `thingsboard-gateway`. We are utilizing their robust protocol connectors (Modbus, OPC-UA), but we are **stripping out their server dependencies**. We do NOT connect to a Java ThingsBoard server. We connect to a custom Django backend (`Novena Hub`).

**Integration Contract with Novena Hub:**
You must format all outbound MQTT payloads to match the exact schema expected by the Novena Hub MQTT Consumer.

1. **MQTT Broker Details:**
   - Mosquitto Broker running at the cloud IP address.
   - Port: `1883`
   - Topic: `v1/gateway/telemetry`
   - Auth: Username/Password OR Access Token (to be configured).

2. **Required Outbound JSON Payload Schema:**
```json
{
  "serial_number": "NF-EDGE-001",  // The unique identifier of this gateway hardware
  "values": {
    "device_name": "Power Meter 1", // The name of the specific equipment polled
    "active_power": 450.2,          // Floating point data
    "voltage": 230.1,
    "status": "active"
  }
}
```

3. **Primary Tasks for this Workspace:**
   * Initialize a clean Python environment.
   * Extract the necessary `Modbus` polling logic from the TB Gateway source.
   * Implement a standard `paho-mqtt` publisher that uses the schema above.
   * Build a local configuration JSON file format (`config.json`) where mapping Modbus registers to keys (e.g., `Register 3060` -> `active_power`) is defined.
   * Make it runnable as a systemd background service.

---
