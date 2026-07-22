import asyncio
import logging

from amqtt.broker import Broker

logger = logging.getLogger(__name__)

# Basic amqtt broker configuration
config = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "127.0.0.1:1883",
        }
    },
    "sys_interval": 10,
    "auth": {
        "allow-anonymous": True,
    },
}


async def start_broker():
    broker = Broker(config)
    await broker.start()
    logger.info("Local MQTT Broker started on 127.0.0.1:1883")
    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        logger.info("Shutting down MQTT Broker...")
        await broker.shutdown()


if __name__ == "__main__":
    formatter = "[%(asctime)s] %(levelname)s [%(name)s] - %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        asyncio.run(start_broker())
    except KeyboardInterrupt:
        print("Broker stopped by keyboard interrupt.")
