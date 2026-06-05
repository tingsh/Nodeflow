from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/device/<int:device_id>/", consumers.TelemetryConsumer.as_asgi()),
]
