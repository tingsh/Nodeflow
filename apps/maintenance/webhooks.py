import json
import logging
from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

from .services import process_incoming_whatsapp

logger = logging.getLogger("novena_hub")


@csrf_exempt
def whatsapp_webhook(request):
    """
    Global webhook to handle incoming events from the Meta WhatsApp Business API.
    """
    if request.method == "GET":
        # Meta verification flow
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        verify_token = getattr(settings, "WHATSAPP_VERIFY_TOKEN", "novena_verify_token")
        if mode == "subscribe" and token == verify_token:
            logger.info("WhatsApp webhook verified successfully.")
            return HttpResponse(challenge)
        logger.warning("WhatsApp webhook verification failed: token mismatch.")
        return HttpResponseForbidden("Verification token mismatch")

    elif request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            for entry in data.get("entry", []):
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    for msg in messages:
                        sender_phone = msg.get("from")  # e.g., "15551234567"
                        text_body = msg.get("text", {}).get("body", "").strip()

                        if sender_phone and text_body:
                            process_incoming_whatsapp(sender_phone, text_body)
        except Exception as e:
            logger.error(f"Error parsing incoming WhatsApp payload: {e}")

        return HttpResponse("EVENT_RECEIVED")
