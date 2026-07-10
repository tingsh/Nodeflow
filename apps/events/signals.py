import logging

from anymail.signals import EventType, tracking
from django.dispatch import receiver
from django.utils import timezone

from .models import EmailDelivery

logger = logging.getLogger("novena_hub")

EVENT_STATUS_MAP = {
    EventType.SENT: EmailDelivery.Status.SENT,
    EventType.DELIVERED: EmailDelivery.Status.DELIVERED,
    EventType.BOUNCED: EmailDelivery.Status.BOUNCED,
    EventType.COMPLAINED: EmailDelivery.Status.COMPLAINED,
    EventType.REJECTED: EmailDelivery.Status.REJECTED,
    EventType.FAILED: EmailDelivery.Status.FAILED,
    EventType.DEFERRED: EmailDelivery.Status.DEFERRED,
    EventType.UNKNOWN: EmailDelivery.Status.UNKNOWN,
}


@receiver(tracking)
def update_email_delivery_from_tracking(sender, event, esp_name, **kwargs):
    status = EVENT_STATUS_MAP.get(event.event_type)
    if not status:
        return

    metadata_delivery_id = (event.metadata or {}).get("email_delivery_id")
    delivery = None
    if metadata_delivery_id:
        delivery = EmailDelivery.objects.filter(id=metadata_delivery_id).first()

    if delivery is None and event.message_id and event.recipient:
        delivery = (
            EmailDelivery.objects.filter(
                provider_message_id=event.message_id,
                recipient__iexact=event.recipient,
            )
            .order_by("-created_at")
            .first()
        )

    if delivery and event.event_id and delivery.last_event_id == event.event_id:
        return

    if delivery is None:
        delivery = EmailDelivery.objects.create(
            notification_type=EmailDelivery.NotificationType.UNKNOWN,
            recipient=event.recipient or "unknown@novena.local",
            provider_message_id=event.message_id or "",
            status=status,
            last_event_id=event.event_id or "",
            last_error=event.description or event.mta_response or "",
            metadata={
                "esp_name": esp_name,
                "event_type": event.event_type,
                "unmatched_tracking_event": True,
            },
        )
        logger.warning("Created unmatched email delivery audit row for %s event %s.", esp_name, event.event_id)
        return

    delivery.status = status
    if event.message_id and not delivery.provider_message_id:
        delivery.provider_message_id = event.message_id
    delivery.last_event_id = event.event_id or delivery.last_event_id
    delivery.last_error = event.description or event.mta_response or ""
    delivery.metadata = {
        **(delivery.metadata or {}),
        "last_tracking_event_type": event.event_type,
        "last_tracking_esp": esp_name,
    }
    if status == EmailDelivery.Status.DELIVERED:
        delivery.delivered_at = event.timestamp or timezone.now()
    delivery.save(
        update_fields=[
            "status",
            "provider_message_id",
            "last_event_id",
            "last_error",
            "metadata",
            "delivered_at",
            "updated_at",
        ]
    )
