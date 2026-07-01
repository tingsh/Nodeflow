import logging
import requests
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from .models import Alert

logger = logging.getLogger("novena_hub")


@shared_task
def dispatch_alert_email_task(alert_id, is_resolved=False):
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found for email dispatch.")
        return

    recipient_list = [member.email for member in alert.rule.recipients.all() if member.email]
    if not recipient_list:
        logger.warning(f"No email recipients configured for alert {alert.id}")
        return

    if is_resolved:
        subject = f"[RESOLVED] Novena Alert: {alert.rule.name}"
    else:
        subject = f"[{alert.rule.severity.upper()}] Novena Alert: {alert.rule.name}"

    context = {
        "alert": alert,
        "rule": alert.rule,
        "device": alert.device,
        "site": alert.device.site,
        "timestamp": timezone.now() if is_resolved else alert.triggered_at,
        "dashboard_url": f"{settings.PROJECT_METADATA['URL']}/a/{alert.team.slug}/alerts/",
        "is_resolved": is_resolved,
    }

    html_message = render_to_string("alerts/email/alert_notification.html", context)
    plain_message = render_to_string("alerts/email/alert_notification.txt", context)

    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Alert email sent asynchronously to {len(recipient_list)} recipients (is_resolved={is_resolved}).")
    except Exception as e:
        logger.error(f"Failed to send alert email for alert {alert.id}: {e}")


@shared_task
def dispatch_alert_whatsapp_task(alert_id, is_resolved=False):
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found for WhatsApp dispatch.")
        return

    phone_numbers = [m.phone_number for m in alert.rule.recipients.all() if m.phone_number]
    if not phone_numbers:
        logger.warning(f"No WhatsApp recipients configured for alert {alert.id}")
        return

    status_text = "RESOLVED" if is_resolved else alert.rule.severity.upper()
    emoji = "✅" if is_resolved else "🚨"
    message_text = (
        f"{emoji} *NOVENA ALERT {status_text}*\n"
        f"Rule: {alert.rule.name}\n"
        f"Device: {alert.device.name}\n"
        f"Value: {alert.trigger_value}\n"
        f"Severity: {alert.rule.severity.upper()}\n"
        f"Time: {alert.triggered_at.strftime('%H:%M:%S')}"
    )

    if getattr(settings, "WHATSAPP_PROVIDER", "mock") == "mock":
        logger.info(f"| MOCK WHATSAPP SEND | Recipients: {phone_numbers} | Message: {message_text}")
        return

    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_TOKEN
    if not phone_id or not access_token:
        logger.warning("WhatsApp Meta API configuration missing (phone_id/access_token).")
        return

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    for number in phone_numbers:
        clean_number = "".join(filter(str.isdigit, number))
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": clean_number,
            "type": "text",
            "text": {"body": message_text},
        }
        try:
            requests.post(url, headers=headers, json=payload, timeout=5).raise_for_status()
            logger.info(f"WhatsApp alert successfully dispatched to {clean_number} (is_resolved={is_resolved})")
        except Exception as e:
            logger.error(f"WhatsApp Meta API failed for {number}: {e}")


@shared_task
def dispatch_alert_webhook_task(alert_id, is_resolved=False):
    try:
        alert = Alert.objects.get(id=alert_id)
    except Alert.DoesNotExist:
        logger.error(f"Alert {alert_id} not found for Webhook dispatch.")
        return

    url = alert.rule.notify_webhook
    if not url:
        logger.warning(f"No Webhook URL configured for alert {alert.id}")
        return

    payload = {
        "alert_id": alert.id,
        "rule_name": alert.rule.name,
        "severity": alert.rule.severity,
        "device": {"id": alert.device.id, "name": alert.device.name},
        "site": {"id": alert.device.site.id, "name": alert.device.site.name},
        "trigger_value": alert.trigger_value,
        "condition": alert.rule.condition,
        "threshold": alert.rule.threshold,
        "timestamp": alert.triggered_at.isoformat(),
        "status": "resolved" if is_resolved else alert.status,
    }

    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Alert Webhook successfully dispatched to {url} (is_resolved={is_resolved})")
    except Exception as e:
        logger.error(f"Alert Webhook dispatch failed for alert {alert.id}: {e}")


@shared_task
def send_whatsapp_message_task(phone_number, message_text):
    """
    Sends a general WhatsApp text message using Meta API or mock logs.
    """
    if getattr(settings, "WHATSAPP_PROVIDER", "mock") == "mock":
        logger.info(f"| MOCK WHATSAPP SEND | Recipient: {phone_number} | Message: {message_text}")
        return

    phone_id = getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", None)
    access_token = getattr(settings, "WHATSAPP_ACCESS_TOKEN", None)
    if not phone_id or not access_token:
        logger.warning("WhatsApp Meta API configuration missing (phone_id/access_token).")
        return

    url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    clean_number = "".join(filter(str.isdigit, phone_number))
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": clean_number,
        "type": "text",
        "text": {"body": message_text},
    }
    try:
        requests.post(url, headers=headers, json=payload, timeout=5).raise_for_status()
        logger.info(f"WhatsApp message successfully sent to {clean_number}")
    except Exception as e:
        logger.error(f"WhatsApp Meta API failed for {phone_number}: {e}")
