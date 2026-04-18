import json
import math
import random
import time

import paho.mqtt.client as mqtt

# Configuration
BROKER = "localhost"
PORT = 1883
TOPIC = "v1/gateway/telemetry"
GATEWAY_SN = "GW-SIM-ENERGY-001"
DEVICE_NAME = "Main Power Meter"


def generate_telemetry(t):
    """Generates synthetic energy data."""
    # Sine wave for usage patterns (peak at 12pm, low at night)
    hour = time.localtime(t).tm_hour + time.localtime(t).tm_min / 60.0
    base_load = 500  # Watts
    daily_pattern = math.sin((hour - 6) * math.pi / 12) * 1000
    usage = max(0, base_load + daily_pattern + random.uniform(-100, 100))

    voltage = 230 + random.uniform(-2, 2)
    grid_frequency = 50 + random.uniform(-0.05, 0.05)

    # Solar generation (only during day)
    solar_gen = 0
    if 7 <= hour <= 18:
        solar_gen = math.sin((hour - 7) * math.pi / 11) * 3000 + random.uniform(-200, 200)
        solar_gen = max(0, solar_gen)

    return {
        "serial_number": GATEWAY_SN,
        "values": {
            "device_name": DEVICE_NAME,
            "active_power": round(usage, 2),
            "voltage": round(voltage, 2),
            "frequency": round(grid_frequency, 2),
            "solar_generation": round(solar_gen, 2),
            "total_consumption": round(45000 + (t % 86400) / 10, 2),
        },
    }


def run_simulator():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    print(f"Connecting to MQTT Broker at {BROKER}...")
    try:
        client.connect(BROKER, PORT, 60)
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    print(f"Simulator Started. Gateway: {GATEWAY_SN}, Device: {DEVICE_NAME}")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            t = time.time()
            payload = generate_telemetry(t)

            client.publish(TOPIC, json.dumps(payload))
            print(
                f"[{time.strftime('%H:%M:%S')}] Published: {payload['values']['active_power']}W, Solar: {payload['values']['solar_generation']}W"
            )

            time.sleep(5)  # Matches our 5s polling goal
    except KeyboardInterrupt:
        print("Simulator stopped.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    run_simulator()
