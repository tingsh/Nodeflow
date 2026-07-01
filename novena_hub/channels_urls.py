from apps.chat.routing import websocket_urlpatterns as ai_chat_patterns
from apps.telemetry.routing import websocket_urlpatterns as telemetry_patterns

urlpatterns = [] + ai_chat_patterns + telemetry_patterns
