"""Reliable Cloud-to-Edge configuration delivery."""

from __future__ import annotations

import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from .models import GatewayConfig, GatewayConfigOutbox
from .remote_control_crypto import payload_checksum, sign_payload

logger = logging.getLogger("novena_hub")

GUIDED_SETUP_CAPABILITY = "guided_setup_v1"
CONFIG_SCHEMA_VERSION = 1


def gateway_supports_guided_setup(gateway) -> bool:
    return GUIDED_SETUP_CAPABILITY in set(gateway.gateway_capabilities or [])


def build_signed_config_envelope(config_record: GatewayConfig) -> dict:
    body = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "request_id": str(config_record.request_id),
        "idempotency_key": str(config_record.idempotency_key),
        "target": {"gateway_serial": config_record.gateway.serial_number},
        "revision": config_record.revision,
        "checksum": config_record.checksum,
        "issued_at": config_record.created_at.isoformat(),
        "expires_at": config_record.expires_at.isoformat(),
        "action": config_record.action,
        "config": config_record.config_json,
    }
    key_id, signature = sign_payload(body)
    return {**body, "signing_key_id": key_id, "signature": signature}


def _schedule_config_dispatch(outbox_id):
    try:
        from .tasks import dispatch_gateway_config_outbox

        dispatch_gateway_config_outbox.delay(outbox_id)
    except Exception as exc:  # Celery may be unavailable in local unit tests.
        logger.warning("Gateway config outbox %s remains queued: %s", outbox_id, exc)


@transaction.atomic
def queue_gateway_config(gateway, action: str, config: dict, *, setup_run=None) -> GatewayConfig:
    """Persist a signed config and its outbox in the same transaction."""
    locked_gateway = gateway.__class__.objects.select_for_update().get(pk=gateway.pk)
    latest_revision = (
        GatewayConfig.objects.filter(gateway=locked_gateway)
        .order_by("-revision")
        .values_list("revision", flat=True)
        .first()
        or 0
    )
    expires_at = timezone.now() + timedelta(seconds=int(getattr(settings, "GATEWAY_CONFIG_ENVELOPE_TTL_SECONDS", 300)))
    config_record = GatewayConfig.objects.create(
        team=locked_gateway.team,
        gateway=locked_gateway,
        setup_run=setup_run,
        config_json=config,
        request_id=uuid.uuid4(),
        action=action,
        revision=latest_revision + 1,
        checksum=payload_checksum(config),
        expires_at=expires_at,
        status="queued",
    )
    config_record.envelope_json = build_signed_config_envelope(config_record)
    config_record.save(update_fields=["envelope_json", "updated_at"])
    outbox = GatewayConfigOutbox.objects.create(
        team=locked_gateway.team,
        config=config_record,
    )
    transaction.on_commit(lambda: _schedule_config_dispatch(outbox.pk))
    return config_record


def dispatch_gateway_config_outbox(outbox_id: int) -> GatewayConfig | None:
    """Claim and deliver one row with bounded retry and dead-letter behavior."""
    now = timezone.now()
    lease_seconds = int(getattr(settings, "GATEWAY_CONFIG_OUTBOX_LEASE_SECONDS", 60))
    max_attempts = int(getattr(settings, "GATEWAY_CONFIG_OUTBOX_MAX_ATTEMPTS", 5))
    with transaction.atomic():
        outbox = GatewayConfigOutbox.objects.select_for_update().filter(pk=outbox_id).first()
        if not outbox:
            return None
        claimable = outbox.status in {
            GatewayConfigOutbox.Status.PENDING,
            GatewayConfigOutbox.Status.RETRY,
        }
        claimable = claimable or (
            outbox.status == GatewayConfigOutbox.Status.CLAIMED
            and outbox.lease_expires_at
            and outbox.lease_expires_at <= now
        )
        if not claimable or outbox.next_attempt_at > now:
            return outbox.config
        config_record = GatewayConfig.objects.select_for_update().select_related("gateway").get(pk=outbox.config_id)
        if config_record.expires_at and config_record.expires_at <= now:
            outbox.status = GatewayConfigOutbox.Status.DEAD_LETTER
            outbox.dead_lettered_at = now
            outbox.last_error = "Configuration envelope expired before delivery."
            config_record.status = "failed"
            config_record.error_code = "config_expired"
            config_record.error_message = outbox.last_error
            outbox.save()
            config_record.save()
            return config_record
        if outbox.attempt_count >= max_attempts:
            outbox.status = GatewayConfigOutbox.Status.DEAD_LETTER
            outbox.dead_lettered_at = now
            outbox.last_error = outbox.last_error or "Configuration delivery attempts were exhausted."
            config_record.status = "failed"
            config_record.error_code = "delivery_attempts_exhausted"
            config_record.error_message = outbox.last_error
            outbox.save()
            config_record.save()
            return config_record
        outbox.status = GatewayConfigOutbox.Status.CLAIMED
        outbox.claimed_at = now
        outbox.lease_expires_at = now + timedelta(seconds=lease_seconds)
        outbox.attempt_count += 1
        outbox.save(
            update_fields=[
                "status",
                "claimed_at",
                "lease_expires_at",
                "attempt_count",
                "updated_at",
            ]
        )

    try:
        from apps.telemetry.mqtt_publisher import publish_config_envelope

        publish_config_envelope(config_record.gateway, config_record.envelope_json)
    except Exception as exc:
        with transaction.atomic():
            outbox = GatewayConfigOutbox.objects.select_for_update().get(pk=outbox_id)
            config_record = GatewayConfig.objects.select_for_update().get(pk=outbox.config_id)
            backoff = min(300, 2 ** max(1, outbox.attempt_count))
            outbox.status = GatewayConfigOutbox.Status.RETRY
            outbox.next_attempt_at = timezone.now() + timedelta(seconds=backoff)
            outbox.lease_expires_at = None
            outbox.last_error = str(exc)
            outbox.save()
            config_record.error_code = "broker_publish_failed"
            config_record.error_message = "Novena could not deliver the setup yet. It will retry automatically."
            config_record.save(update_fields=["error_code", "error_message", "updated_at"])
            return config_record

    with transaction.atomic():
        outbox = GatewayConfigOutbox.objects.select_for_update().get(pk=outbox_id)
        config_record = GatewayConfig.objects.select_for_update().get(pk=outbox.config_id)
        delivered_at = timezone.now()
        outbox.status = GatewayConfigOutbox.Status.DELIVERED
        outbox.delivered_at = delivered_at
        outbox.lease_expires_at = None
        outbox.last_error = ""
        outbox.save()
        if config_record.status == "queued":
            config_record.status = "delivered"
        config_record.delivered_at = delivered_at
        config_record.error_code = ""
        config_record.error_message = ""
        config_record.save()
        return config_record


def dispatch_due_gateway_config_outboxes(limit=100) -> int:
    now = timezone.now()
    ids = list(
        GatewayConfigOutbox.objects.filter(
            status__in=[
                GatewayConfigOutbox.Status.PENDING,
                GatewayConfigOutbox.Status.RETRY,
                GatewayConfigOutbox.Status.CLAIMED,
            ],
            next_attempt_at__lte=now,
        )
        .filter(models.Q(lease_expires_at__isnull=True) | models.Q(lease_expires_at__lte=now))
        .order_by("next_attempt_at")
        .values_list("pk", flat=True)[:limit]
    )
    for outbox_id in ids:
        dispatch_gateway_config_outbox(outbox_id)
    return len(ids)
