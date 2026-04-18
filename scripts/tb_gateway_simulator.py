import json
import random
import time

import paho.mqtt.client as mqtt

# ThingsBoard Gateway standard telemetry format
# Topic: v1/gateway/telemetry
# Payload: {"Device Name": [{"ts": 123456789, "values": {"key": "value"}}]}

BROKER = "localhost"
PORT = 1883
TOPIC = "v1/gateway/telemetry"


def run_tb_simulator():
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

    try:
        client.connect(BROKER, PORT, 60)
        print(f"Connected to {BROKER}. Sending TB-format telemetry...")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # We use a device name that exists or will be auto-mapped
    # Note: For our consumer to accept it, there must be a Gateway in the DB
    # that we can attribute this to, or we identify it via the MQTT connection.
    # For this test, we'll send a payload that contains our 'Gateway SN' logic
    # mixed with TB structure to verify the parser handles the nesting.

    while True:
        payload = {
            "Main Power Meter": [
                {
                    "ts": int(time.time() * 1000),
                    "values": {
                        "active_power": round(random.uniform(400, 600), 2),
                        "voltage": round(random.uniform(230, 240), 1),
                    },
                }
            ],
            # To make our consumer happy without real auth, we inject the SN
            # into a known hidden field or just ensure a gateway exists for the test.
            "serial_number": "NODEFLOW-DEMO-01",
        }

        client.publish(TOPIC, json.dumps(payload))
        print(f"Published TB Data: {payload['Main Power Meter'][0]['values']}")
        time.sleep(5)


if __name__ == "__main__":
    run_tb_simulator()
