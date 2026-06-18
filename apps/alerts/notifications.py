import logging

from django.conf import settings

logger = logging.getLogger("iot_platform")


from .tasks import (
    dispatch_alert_email_task,
    dispatch_alert_whatsapp_task,
    dispatch_alert_webhook_task,
)


def send_alert_notifications(alert):
    """
    Dispatches notifications for a triggered alert asynchronously.
    """
    rule = alert.rule

    if rule.notify_email:
        dispatch_alert_email_task.delay(alert.id, is_resolved=False)

    if rule.notify_webhook:
        dispatch_alert_webhook_task.delay(alert.id, is_resolved=False)

    if rule.notify_whatsapp:
        dispatch_alert_whatsapp_task.delay(alert.id, is_resolved=False)


def send_alert_resolution_notifications(alert):
    """
    Dispatches notifications for a resolved alert asynchronously.
    """
    rule = alert.rule

    if rule.notify_email:
        dispatch_alert_email_task.delay(alert.id, is_resolved=True)

    if rule.notify_webhook:
        dispatch_alert_webhook_task.delay(alert.id, is_resolved=True)

    if rule.notify_whatsapp:
        dispatch_alert_whatsapp_task.delay(alert.id, is_resolved=True)
