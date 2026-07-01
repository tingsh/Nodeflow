import json
import logging
import time

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURATION
# IMPORTANT: When running on 3 physical laptops, you must change these IP addresses.
# ==============================================================================

# Target: Laptop 2 (The Sensor/Equipment)
MODBUS_SERVER_IP = "127.0.0.1"  # <--- Change this to Laptop 2's LAN IP address
MODBUS_PORT = 5020

# Target: PC (Novena Hub / Mosquitto Broker)
MQTT_BROKER_IP = "127.0.0.1"  # <--- Change this to the PC's LAN IP address
MQTT_PORT = 1883
MQTT_TOPIC = "v1/gateway/telemetry"

# Identity
GATEWAY_SN = "12345678"
DEVICE_NAME = "test device 1"


def run_edge_gateway():
    # 1. Setup Modbus Client
    log.info(f"Attempting to connect to external Modbus Server at {MODBUS_SERVER_IP}:{MODBUS_PORT}...")
    try:
        modbus_client = ModbusTcpClient(MODBUS_SERVER_IP, port=MODBUS_PORT)
        if not modbus_client.connect():
            log.error("Failed to connect to Modbus server.")
            log.error(f"Ensure Laptop 2's script is running and firewalls are open for port {MODBUS_PORT}.")
            return
    except Exception as e:
        log.error(f"Modbus connection exception: {e}")
        return

    # 2. Setup MQTT Client
    log.info(f"Attempting to connect to Cloud MQTT Broker at {MQTT_BROKER_IP}:{MQTT_PORT}...")
    mqtt_client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    try:
        mqtt_client.connect(MQTT_BROKER_IP, MQTT_PORT, 60)
    except Exception as e:
        log.error(f"Failed to connect to MQTT broker: {e}")
        log.error(f"Ensure the PC's docker-compose is running Mosquitto, and firewalls allow port {MQTT_PORT}.")
        modbus_client.close()
        return

    log.info("✅ Edge Gateway is ONLINE. Polling started...")

    # 3. Main Polling Loop
    try:
        while True:
            # Read 2 holding registers starting at address 0 (Voltage & Power) from Laptop 2
            # slave=1 is the Unit ID (typical for Modbus TCP)
            result = modbus_client.read_holding_registers(0, count=2, slave=1)

            if not result.isError():
                # Divide by 10 to reverse the decimal scaling done on Laptop 2
                voltage = result.registers[0] / 10.0
                power = result.registers[1] / 10.0

                # Format exactly as Novena Hub expects
                payload = {
                    "serial_number": GATEWAY_SN,
                    "values": {
                        "device_name": DEVICE_NAME,
                        "voltage": voltage,
                        "active_power": power,
                        "status": "active",
                    },
                }

                # Publish to PC
                mqtt_client.publish(MQTT_TOPIC, json.dumps(payload))
                log.info(f"📡 PUBLISHED via MQTT -> Voltage: {voltage}V, Power: {power}W")
            else:
                log.warning("Failed to read registers from Modbus Server.")

            # Wait exactly 5 seconds before asking the sensor again
            time.sleep(5)

    except KeyboardInterrupt:
        log.info("Stopping Edge Gateway...")
    finally:
        modbus_client.close()
        mqtt_client.disconnect()


if __name__ == "__main__":
    run_edge_gateway()
