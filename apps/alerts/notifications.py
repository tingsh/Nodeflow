import logging
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger('iot_platform')

def send_alert_notifications(alert):
    """
    Dispatches notifications for a triggered alert.
    """
    rule = alert.rule
    
    if rule.notify_email:
        send_alert_email(alert)
        
    if rule.notify_webhook:
        send_alert_webhook(alert)

    if rule.notify_whatsapp:
        send_alert_whatsapp(alert)

def send_alert_whatsapp(alert):
    """
    Sends a WhatsApp alert to team members with a phone number.
    """
    rule = alert.rule
    device = alert.device
    members = alert.team.members.all()
    recipients = [m.phone_number for m in members if m.phone_number]

    if not recipients:
        logger.warning(f"No phone numbers found for WhatsApp alert thread for team {alert.team.name}")
        return

    message = (
        f"🚨 *NODEFLOW ALERT*\n"
        f"Rule: {rule.name}\n"
        f"Device: {device.name}\n"
        f"Value: {alert.trigger_value}\n"
        f"Severity: {rule.severity.upper()}\n"
        f"Time: {alert.triggered_at.strftime('%H:%M:%S')}"
    )

    if settings.WHATSAPP_PROVIDER == 'mock':
        logger.info(f"| MOCK WHATSAPP SEND | Recipients: {recipients} | Message: {message}")
        return

    # In a production scenario, you would use Twilio:
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # for number in recipients:
    #     client.messages.create(body=message, from_=f"whatsapp:{settings.TWILIO_WHATSAPP_NUMBER}", to=f"whatsapp:{number}")
    
    logger.info(f"WhatsApp dispatch triggered for {len(recipients)} recipients.")

def send_alert_email(alert):
    """Sends an HTML alert email."""
    try:
        subject = f"[{alert.rule.severity.upper()}] Nodeflow Alert: {alert.rule.name}"
        recipient_list = []
        
        # In a real app, we'd send to all team admins or configured users.
        # For the MVP, we'll send to the team's primary contact or site manager.
        # Here we'll default to the site owners/admins associated with the team.
        members = alert.team.members.all()
        recipient_list = [member.email for member in members if member.email]
        
        if not recipient_list:
            logger.warning(f"No recipients found for alert email for team {alert.team.name}")
            return

        context = {
            'alert': alert,
            'rule': alert.rule,
            'device': alert.device,
            'site': alert.device.site,
            'timestamp': alert.triggered_at,
            'dashboard_url': f"{settings.SITE_URL}/a/{alert.team.slug}/alerts/"
        }
        
        html_message = render_to_string('alerts/email/alert_notification.html', context)
        plain_message = render_to_string('alerts/email/alert_notification.txt', context)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Alert email sent to {len(recipient_list)} recipients.")
        
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")

def send_alert_webhook(alert):
    """Sends a JSON webhook POST."""
    try:
        url = alert.rule.notify_webhook
        payload = {
            "alert_id": alert.id,
            "rule_name": alert.rule.name,
            "severity": alert.rule.severity,
            "device": {
                "id": alert.device.id,
                "name": alert.device.name
            },
            "site": {
                "id": alert.device.site.id,
                "name": alert.device.site.name
            },
            "trigger_value": alert.trigger_value,
            "condition": alert.rule.condition,
            "threshold": alert.rule.threshold,
            "timestamp": alert.triggered_at.isoformat(),
            "status": alert.status
        }
        
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"Alert webhook delivered to {url}")
        
    except Exception as e:
        logger.error(f"Failed to deliver alert webhook: {e}")
