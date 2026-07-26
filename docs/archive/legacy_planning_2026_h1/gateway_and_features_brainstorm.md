> **Historical reference — do not use as current implementation guidance.** See the [documentation authority index](../../README.md).

# Strategy Brainstorm: The Edge Gateway & Next Features

> **Date:** April 13, 2026
> **Focus:** Answering your feedback on architecture, the hardware gateway approach, integrating your Siemens S7-1200 PLC locally, and brainstorming new platform features.

---

## 1. Hardware Strategy: Is Raspberry Pi Professional?

**Your Question:** *"You mention a lot on raspberry pi, is this really the best approach? I have not really seen raspberry pi used in actual business, I mostly see it used in school or hobbyist projects."*

You have great instincts. A bare Raspberry Pi circuit board lying in a dusty factory is a hobbyist project, not an enterprise solution. Let's clarify the hardware approach.

### The Truth About Raspberry Pi in Industry
You're right that standard Pi's are for hobbyists. However, the **Raspberry Pi Compute Module (CM4/CM5)** is actually the brains inside many highly respected industrial brands. Companies buy the Compute Module, place it inside a ruggedized aluminum DIN-rail chassis, add industrial RS-485/CAN-bus ports, and slap a $400 price tag on it. 

Examples of "Industrial PIs" used by real businesses:
* **Kunbus RevPi** (Revolution Pi)
* **OnLogic Factor 200 Series**
* **Brainboxes Edge Controllers**

### Our Production Hardware Options (For when we launch)
When we sell to actual SME factories, we will NOT ship them a bare Raspberry Pi. We will ship an **Industrial Edge PC**. We have three main paths:

1. **The "Industrial Pi" ($200-$350):** We buy RevPis or OnLogic units empty, flash our Python code onto them, and ship them. They are rugged, handle extreme factory temperatures, and look professional.
2. **The Teltonika Route ($150-$250):** Teltonika (e.g., RUT955, TRB140) makes extremely reliable 4G/LTE industrial gateways that run embedded Linux. We can load our Python scripts onto them.
3. **The IPC Route ($300+):** Things like the **Siemens SIMATIC IoT2050** or an Advantech UNO. They run standard Linux and are universally trusted by factory engineers.

### How We Test NOW (No Hardware Needed Yet)
Since you want to roleplay the customer locally: **You don't need to buy a Gateway device today.**
Your development laptop *is* the Edge Gateway for now. You will run the Python Gateway script in a terminal on your computer, it will securely talk to your Siemens PLC over the network, and push data to your local Django server instance.

---

## 2. Setting Up Your Siemens S7-1200 PLC

**Your Comment:** *"I have a Siemens S7-1200 PLC with me. It has ethernet port. I think we can run some test."*

This is perfect. Siemens S7-1200 is one of the most common PLCs in the world. 

To roleplay pulling data from this PLC into Novena, here is what we'll do:
1. **PLC Config:** You will need to open **TIA Portal** on your machine and configure the S7-1200 to act as an **OPC UA Server** (supported on firmware 4.4+) OR a **Modbus TCP Server** (using the `MB_SERVER` block).
2. **Simulated Environment:** Let's say you map an arbitrary memory address `MW100` on the PLC to represent "Pump Speed."
3. **The Gateway Script:** We will build a simple Python script running on your laptop. It will use the Python `opcua` or `pymodbus` library to read `MW100` over your local Ethernet cable, format it into JSON, and push it to Novena (Mosquitto) on `localhost`.

---

## 3. The ThingsBoard Fork: Software & Repositories

**Your Question:** *"For the forked python TB iot gateway, do we do this in a separate code repo? Or do we do this in this current code repo Novena? What are their server dependencies?"*

### One Repo or Two?
**Two completely separate repositories.**
* `Repo 1 (Novena Hub)`: What we have now (Django, HTMX, Tailwind, TimescaleDB). It runs in the cloud (or your localhost docker).
* `Repo 2 (Novena Gateway)`: The Python script that sits in the factory. It reads Modbus/OPC-UA and publishes MQTT.

*Why?* You absolutely do not want your web framework, billing code, and database schema deployed to a piece of hardware sitting in a customer's unguarded warehouse. The Edge repo should be incredibly small, lightweight, and stupid—its only job is "read sensor, send to cloud."

### What does "Stripping Server Dependencies" mean?
ThingsBoard Gateway is open source, but it is highly opinionated. If you download it today, the code assumes you are talking to a Java-based ThingsBoard server. 

Specifically, TB Gateway dependencies we'd strip or replace:
* **The TB MQTT Client (`tb-mqtt-client`):** We replace this with the standard Python `paho-mqtt` library pointing to our Mosquitto broker.
* **The Telemetry Formatter:** TB expects data explicitly as `{"Device A": [{"ts": 12345, "values": {"temp": 42}}]}`. We would intercept the Modbus connectors to format the payload in our own schema (e.g., `{"serial_number": "GW-001", "device_name": "Device A", "values":...}`).
* **Configuration Sync:** TB pulls its Modbus register config from the Java server. We need to rewrite that to pull the JSON config from our Django server instead.

**Recommendation for Now:** Because TB Gateway is large, for our *very first Siemens test*, I recommend we don't even use TB Gateway. We write a custom 50-line Python script using `pymodbus` or `asyncua` just to prove we can read the S7-1200 and get it into Novena. Once that works, we can talk about building the full Edge Gateway software.

---

## 4. Brainstorming Missing Features for an "IIoT Shopify"

If Novena is to dominate, here are high-value features missing from the platform that factories actively pay for:

| Feature | Concept | Why Customers Buy It |
|---------|---------|----------------------|
| **Write-back / Control Commands** | Not just reading data, but turning things ON/OFF. From the web dashboard, click a toggle switch that sends a Modbus write command back to the PLC to stop a motor. | Transforms Novena from a "dashboard" into a "Remote SCADA" system. |
| **Logic & Automations** | "If Temperature > 50°C for 5 minutes, automatically turn on Chiller 2 via Modbus." Novena handles logic in the cloud. | Saves labor costs. Automation without needing a PLC programmer. |
| **Role-Based Access (RBAC)** | Factory Owner sees billing. Plant Manager sees dashboards. Shift Operator can only acknowledge alarms but cannot change configurations. | Essential for medium/large SME environments. |
| **Maintenance Ticketing** | When an alert fires (e.g. VFD Fault), it auto-generates a Maintenance Ticket. Technicians can mark it "Resolved" with notes. | Keeps maintenance workflows inside the platform rather than email/WhatsApp. |
| **Public Shareable Links** | Generate a read-only live URL for a specific dashboard to share with third-party vendors or display on a TV screen in the factory manager's office. | Massive growth driver (creates organic virality). |
| **WhatsApp/Telegram Integration** | Instead of just Email alerts, dispatch critical alerts directly to a WhatsApp group chat for the engineering team. | Emails are ignored on the factory floor; WhatsApp is checked instantly. |

---

## 5. The AI "Chat With Data" 

**Your Comment:** *"we should work on this as saaspegasus already comes built in with AI chat functionality. We may still need to build around it"*

Perfect angle. Pegasus gives us the chat interface and the OpenAI connection logic. 
What we need to build is the **RAG (Retrieval-Augmented Generation) Tooling**.

An LLM cannot naturally query TimescaleDB. We will need to build "Tools" (using OpenAI Function Calling) that the LLM can use invisibly during the chat.
For example:
1. User types: *"How much energy did the Siemens PLC consume yesterday?"*
2. ChatGPT identifies what they want, and invisibly calls our custom function: `get_energy_consumption(device="Siemens PLC", time="yesterday")`.
3. Our Django backend executes the SQL query against TimescaleDB.
4. Django passes the raw numbers back to ChatGPT.
5. ChatGPT responds to the user: *"The Siemens PLC consumed 45.2 kWh yesterday, which is 5% lower than the weekly average."*

This is entirely manageable within the Pegasus chat framework and will look like magic in demos.

---

## Summary of Next Action Plans (Localhost & Siemens Focus)

1. **Do not deploy to the cloud yet**. You'll stay on Localhost.
2. **Build a Python PLC Script (Repo 2)**. A lightweight script on your laptop to read data from your S7-1200 via Ethernet and push it to Novena's local MQTT broker. 
3. **Configure the S7-1200**. You'll open TIA Portal to set up some test data registers.
4. **Develop AI Chat**. Enhance the Pegasus chat to query the telemetry database using OpenAI function calls.
