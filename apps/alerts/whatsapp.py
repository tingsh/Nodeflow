import logging

import requests
from django.conf import settings

logger = logging.getLogger("novena_hub")


def normalize_whatsapp_number(phone_number):
    """
    Convert a stored phone number into WhatsApp Cloud API format.
    Meta expects country code + number without symbols, for example 6591234567.
    """
    return "".join(filter(str.isdigit, phone_number or ""))


def get_whatsapp_messages_url():
    version = getattr(settings, "WHATSAPP_GRAPH_API_VERSION", "v21.0")
    phone_number_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    return f"https://graph.facebook.com/{version}/{phone_number_id}/messages"


def send_whatsapp_meta_payload(phone_number, payload, log_label="message"):
    provider = getattr(settings, "WHATSAPP_PROVIDER", "mock")
    recipient = normalize_whatsapp_number(phone_number)

    if not recipient:
        logger.warning("WhatsApp %s skipped because recipient phone number is blank.", log_label)
        return False

    if provider == "mock":
        logger.info("| MOCK WHATSAPP SEND | Recipient: %s | Payload: %s", recipient, payload)
        return True

    if provider != "meta":
        logger.warning("Unsupported WHATSAPP_PROVIDER '%s'. Use 'mock' or 'meta'.", provider)
        return False

    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    if not phone_id or not access_token:
        logger.warning("WhatsApp Meta API configuration missing (phone_id/access_token).")
        return False

    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": recipient, **payload}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(get_whatsapp_messages_url(), headers=headers, json=payload, timeout=5)
        response.raise_for_status()
        logger.info("WhatsApp %s accepted by Meta for %s: %s", log_label, recipient, response.text)
        return True
    except requests.RequestException as exc:
        response_text = getattr(getattr(exc, "response", None), "text", "")
        logger.error("WhatsApp Meta API failed for %s: %s %s", recipient, exc, response_text)
        return False


def send_whatsapp_text_message(phone_number, message_text):
    """
    Send a WhatsApp text message through Meta Cloud API, or log it in mock mode.
    """
    return send_whatsapp_meta_payload(
        phone_number,
        {
            "type": "text",
            "text": {"body": message_text},
        },
        log_label="text message",
    )


def text_parameter(value):
    return {
        "type": "text",
        "text": str(value),
    }


def send_whatsapp_template_message(phone_number, template_name, language_code="en_US", body_parameters=None):
    """
    Send a WhatsApp template message.
    Template messages are required when Novena starts a business-initiated conversation.
    """
    template = {
        "name": template_name,
        "language": {"code": language_code},
    }
    if body_parameters:
        template["components"] = [
            {
                "type": "body",
                "parameters": [text_parameter(value) for value in body_parameters],
            }
        ]

    return send_whatsapp_meta_payload(
        phone_number,
        {
            "type": "template",
            "template": template,
        },
        log_label=f"template message '{template_name}'",
    )
