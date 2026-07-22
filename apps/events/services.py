import logging
from uuid import uuid4

from anymail.message import AnymailMessage
from django.conf import settings

from .models import ActivityLog, EmailDelivery

logger = logging.getLogger("novena_hub")

DELIVERY_FINAL_STATUSES = {
    EmailDelivery.Status.SENT,
    EmailDelivery.Status.DELIVERED,
    EmailDelivery.Status.BOUNCED,
    EmailDelivery.Status.COMPLAINED,
    EmailDelivery.Status.REJECTED,
}


class TrackedEmailDeliveryError(Exception):
    def __init__(self, deliveries):
        self.deliveries = deliveries
        super().__init__("One or more tracked email deliveries failed.")


def log_event(category, message, team, device=None, site=None, user=None, metadata=None):
    """
    Central utility to log system events.
    """
    return ActivityLog.objects.create(
        category=category, message=message, team=team, device=device, site=site, user=user, metadata=metadata or {}
    )


def _normalize_recipient(email):
    return (email or "").strip().lower()


def _message_id_for_recipient(message, recipient):
    status = getattr(message, "anymail_status", None)
    if not status:
        return ""

    recipient_status = status.recipients.get(recipient) or status.recipients.get(_normalize_recipient(recipient))
    if recipient_status and recipient_status.message_id:
        return str(recipient_status.message_id)

    if isinstance(status.message_id, set):
        return ",".join(sorted(str(message_id) for message_id in status.message_id if message_id))
    return str(status.message_id or "")


def _delivery_lookup(notification_type, recipient, alert=None, invitation=None, maintenance_ticket=None):
    lookup = {"notification_type": notification_type, "recipient": _normalize_recipient(recipient)}
    if alert is not None:
        lookup["alert"] = alert
    if invitation is not None:
        lookup["invitation"] = invitation
    if maintenance_ticket is not None:
        lookup["maintenance_ticket"] = maintenance_ticket
    return lookup


def get_or_create_email_delivery(
    *,
    team,
    notification_type,
    recipient,
    user=None,
    alert=None,
    invitation=None,
    maintenance_ticket=None,
    metadata=None,
):
    normalized_recipient = _normalize_recipient(recipient)
    lookup = _delivery_lookup(
        notification_type,
        normalized_recipient,
        alert=alert,
        invitation=invitation,
        maintenance_ticket=maintenance_ticket,
    )
    defaults = {
        "team": team,
        "user": user,
        "metadata": metadata or {},
        "status": EmailDelivery.Status.PENDING,
    }
    idempotency_key = (metadata or {}).get("idempotency_key")
    if idempotency_key:
        delivery = EmailDelivery.objects.filter(**lookup, metadata__idempotency_key=idempotency_key).first()
        created = delivery is None
        if created:
            delivery = EmailDelivery.objects.create(**lookup, **defaults)
    else:
        delivery, created = EmailDelivery.objects.get_or_create(defaults=defaults, **lookup)
    if not created:
        changed_fields = []
        if team is not None and delivery.team_id != team.id:
            delivery.team = team
            changed_fields.append("team")
        if user is not None and delivery.user_id != user.id:
            delivery.user = user
            changed_fields.append("user")
        if changed_fields:
            delivery.save(update_fields=[*changed_fields, "updated_at"])
    return delivery


def record_no_email_recipients(*, team, notification_type, alert=None, metadata=None):
    metadata = metadata or {}
    idempotency_key = metadata.get("idempotency_key") or f"{notification_type}:none:{getattr(alert, 'id', 'none')}"
    delivery = get_or_create_email_delivery(
        team=team,
        notification_type=notification_type,
        recipient="no-recipient@novena.local",
        alert=alert,
        metadata={**metadata, "idempotency_key": idempotency_key},
    )
    delivery.status = EmailDelivery.Status.NO_RECIPIENT
    delivery.last_error = "No email recipients configured."
    delivery.save(update_fields=["status", "last_error", "updated_at"])
    return delivery


def send_tracked_email(
    *,
    team,
    notification_type,
    subject,
    text_body,
    recipients,
    from_email=None,
    html_body=None,
    alert=None,
    invitation=None,
    maintenance_ticket=None,
    user_by_email=None,
    metadata=None,
    skip_sent=True,
):
    deliveries = []
    failed_deliveries = []
    metadata = metadata or {}
    if not metadata.get("idempotency_key") and not any([alert, invitation, maintenance_ticket]):
        metadata = {**metadata, "idempotency_key": str(uuid4())}
    from_email = from_email or settings.DEFAULT_FROM_EMAIL

    for recipient in recipients:
        normalized_recipient = _normalize_recipient(recipient)
        if not normalized_recipient:
            continue

        user = (user_by_email or {}).get(normalized_recipient)
        delivery = get_or_create_email_delivery(
            team=team,
            notification_type=notification_type,
            recipient=normalized_recipient,
            user=user,
            alert=alert,
            invitation=invitation,
            maintenance_ticket=maintenance_ticket,
            metadata=metadata,
        )
        deliveries.append(delivery)

        if skip_sent and delivery.status in DELIVERY_FINAL_STATUSES:
            logger.info(
                "Skipping email delivery %s because status is already %s.",
                delivery.id,
                delivery.status,
            )
            continue

        delivery.status = EmailDelivery.Status.SENDING
        delivery.attempt_count += 1
        delivery.last_error = ""
        delivery.save(update_fields=["status", "attempt_count", "last_error", "updated_at"])

        message = AnymailMessage(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[normalized_recipient],
            metadata={
                **metadata,
                "email_delivery_id": str(delivery.id),
                "notification_type": notification_type,
            },
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")

        try:
            message.send(fail_silently=False)
        except Exception as exc:
            delivery.status = EmailDelivery.Status.FAILED
            delivery.last_error = str(exc)
            delivery.save(update_fields=["status", "last_error", "updated_at"])
            failed_deliveries.append(delivery)
            logger.warning("Tracked email delivery %s failed: %s", delivery.id, exc)
            continue

        delivery.status = EmailDelivery.Status.SENT
        delivery.provider_message_id = _message_id_for_recipient(message, normalized_recipient)
        delivery.last_error = ""
        delivery.save(update_fields=["status", "provider_message_id", "last_error", "updated_at"])

    if failed_deliveries:
        raise TrackedEmailDeliveryError(failed_deliveries)

    return deliveries
