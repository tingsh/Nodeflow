import pytest
from anymail.signals import AnymailTrackingEvent, EventType, tracking
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from apps.events.models import EmailDelivery
from apps.events.services import send_tracked_email
from apps.teams.models import Team


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_send_tracked_email_creates_delivery_and_skips_already_sent():
    team = Team.objects.create(name="Audit Team", slug="audit-team")

    deliveries = send_tracked_email(
        team=team,
        notification_type=EmailDelivery.NotificationType.SUPPORT_REQUEST,
        subject="Tracked",
        text_body="Body",
        recipients=["ops@example.com"],
        metadata={"idempotency_key": "support-1"},
    )

    assert len(deliveries) == 1
    delivery = deliveries[0]
    delivery.refresh_from_db()
    assert delivery.status == EmailDelivery.Status.SENT
    assert delivery.attempt_count == 1
    assert len(mail.outbox) == 1

    send_tracked_email(
        team=team,
        notification_type=EmailDelivery.NotificationType.SUPPORT_REQUEST,
        subject="Tracked",
        text_body="Body",
        recipients=["ops@example.com"],
        metadata={"idempotency_key": "support-1"},
    )

    delivery.refresh_from_db()
    assert delivery.attempt_count == 1
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_anymail_tracking_updates_delivery_statuses_idempotently():
    team = Team.objects.create(name="Tracking Team", slug="tracking-team")
    event_types = [
        (EventType.DELIVERED, EmailDelivery.Status.DELIVERED),
        (EventType.BOUNCED, EmailDelivery.Status.BOUNCED),
        (EventType.COMPLAINED, EmailDelivery.Status.COMPLAINED),
        (EventType.REJECTED, EmailDelivery.Status.REJECTED),
        (EventType.DEFERRED, EmailDelivery.Status.DEFERRED),
    ]

    for index, (event_type, expected_status) in enumerate(event_types):
        delivery = EmailDelivery.objects.create(
            team=team,
            notification_type=EmailDelivery.NotificationType.ALERT_TRIGGERED,
            recipient=f"user{index}@example.com",
            provider_message_id=f"ses-{index}",
            status=EmailDelivery.Status.SENT,
        )
        event = AnymailTrackingEvent(
            event_type=event_type,
            event_id=f"event-{index}",
            message_id=f"ses-{index}",
            recipient=f"user{index}@example.com",
            timestamp=timezone.now(),
            description="event description",
        )

        tracking.send(sender=object(), event=event, esp_name="Amazon SES")
        tracking.send(sender=object(), event=event, esp_name="Amazon SES")

        delivery.refresh_from_db()
        assert delivery.status == expected_status
        assert delivery.last_event_id == f"event-{index}"
        if expected_status == EmailDelivery.Status.DELIVERED:
            assert delivery.delivered_at is not None


@pytest.mark.django_db
def test_anymail_tracking_creates_unmatched_audit_row():
    event = AnymailTrackingEvent(
        event_type=EventType.BOUNCED,
        event_id="unmatched-event",
        message_id="unknown-ses-id",
        recipient="missing@example.com",
        description="Permanent bounce",
    )

    tracking.send(sender=object(), event=event, esp_name="Amazon SES")

    delivery = EmailDelivery.objects.get(provider_message_id="unknown-ses-id")
    assert delivery.status == EmailDelivery.Status.BOUNCED
    assert delivery.recipient == "missing@example.com"
    assert delivery.metadata["unmatched_tracking_event"] is True
