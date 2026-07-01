import json
import time
import logging
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from apps.devices.models import Device
from apps.subscriptions.enforcement import get_latency_limit_for_team

logger = logging.getLogger("novena_hub")

class TelemetryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.device_id = self.scope["url_route"]["kwargs"]["device_id"]
        self.group_name = f"device_{self.device_id}"
        
        # 1. Verify user is authenticated
        user = self.scope["user"]
        if not user.is_authenticated:
            logger.warning("Unauthenticated connection attempt to telemetry WebSocket.")
            await self.close()
            return

        # 2. Verify team access
        from asgiref.sync import sync_to_async
        try:
            device = await sync_to_async(Device.objects.select_related("team").get)(id=self.device_id)
            has_access = await sync_to_async(user.teams.filter(id=device.team_id).exists)()
            if not has_access:
                logger.warning(f"User {user.email} denied access to device {self.device_id} (team mismatch).")
                await self.close()
                return
            
            # 3. Determine plan latency limit
            self.min_interval = await sync_to_async(get_latency_limit_for_team)(device.team)
        except Device.DoesNotExist:
            logger.warning(f"Device {self.device_id} not found for WebSocket connection.")
            await self.close()
            return
        
        self.last_sent = 0.0
        
        # Join group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        
        # Send back initial subscription tier details
        await self.send_json({
            "type": "connection_established",
            "min_interval": self.min_interval
        })
        logger.info(f"WebSocket connected: user={user.email}, device={self.device_id}, min_interval={self.min_interval}s")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: group={self.group_name}")

    async def telemetry_message(self, event):
        # Enforce rate-limiting / latency gating based on subscription
        current_time = time.time()
        if current_time - self.last_sent >= self.min_interval:
            self.last_sent = current_time
            await self.send_json({
                "type": "telemetry",
                "timestamp": event["timestamp"],
                "values": event["values"]
            })
