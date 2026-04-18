import logging

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.telemetry.services import ingest_telemetry_data

logger = logging.getLogger("iot_platform")


class Command(BaseCommand):
    help = "Starts the MQTT consumer service to ingest device telemetry"

    def handle(self, *args, **options):
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2, client_id=settings.MQTT_CONSUMER_CLIENT_ID
        )

        client.on_connect = self.on_connect
        client.on_message = self.on_message

        # Connect to broker
        broker_host = settings.MQTT_BROKER_HOST
        broker_port = settings.MQTT_BROKER_PORT

        self.stdout.write(self.style.SUCCESS(f"Connecting to MQTT Broker at {broker_host}:{broker_port}..."))

        try:
            client.connect(broker_host, broker_port, 60)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Could not connect to MQTT Broker: {e}"))
            return

        # Start the loop
        client.loop_forever()

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            self.stdout.write(self.style.SUCCESS("Connected to MQTT Broker successfully."))
            # Subscribe to topics
            client.subscribe("v1/gateway/telemetry")
            client.subscribe("v1/gateway/rpc")  # Listen for command responses
            self.stdout.write(self.style.NOTICE("Subscribed to telemetry and RPC response topics"))
        else:
            self.stdout.write(self.style.ERROR(f"Connection failed with code {reason_code}"))

    def on_message(self, client, userdata, msg):
        try:
            payload_str = msg.payload.decode()

            # Route based on topic
            if msg.topic == "v1/gateway/rpc":
                from apps.devices.services import process_command_response

                process_command_response(payload_str)
                return

            from apps.telemetry.mqtt_parser import parse_mqtt_payload

            events = parse_mqtt_payload(msg.topic, payload_str)

            for event in events:
                gateway_sn = event.get("gateway_sn")
                device_name = event.get("device_name")
                values = event.get("values", {})
                timestamp = event.get("timestamp")

                # Inject device_name for the services layer if found via parser
                if device_name and "device_name" not in values:
                    values["device_name"] = device_name

                # Filter out anonymous events if not identifying the gateway
                if not gateway_sn:
                    # For testing: if gateway_sn is missing, we could try to find
                    # the first active gateway, but it's safer to require it
                    # in your test payloads for now.
                    continue

                ingest_telemetry_data(gateway_sn, values, timestamp=timestamp)

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
