"""Apply subscription polling changes to managed Gateway configurations."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from .models import Gateway, GatewayConfig, GatewayPlanReconciliation
from .remote_control_crypto import payload_checksum

logger = logging.getLogger("novena_hub")


def _schedule_reconciliation(reconciliation_id):
    try:
        from .tasks import reconcile_team_gateway_polling

        reconcile_team_gateway_polling.delay(reconciliation_id)
    except Exception as exc:
        logger.warning("Plan reconciliation %s remains queued: %s", reconciliation_id, exc)


@transaction.atomic
def queue_team_plan_reconciliation(team, previous_interval, new_interval, source_key):
    reconciliation, created = GatewayPlanReconciliation.objects.get_or_create(
        team=team,
        source_key=str(source_key)[:255],
        defaults={
            "previous_interval_seconds": float(previous_interval),
            "new_interval_seconds": float(new_interval),
        },
    )
    if created or reconciliation.status == GatewayPlanReconciliation.Status.QUEUED:
        transaction.on_commit(lambda: _schedule_reconciliation(reconciliation.pk))
    return reconciliation


def reconcile_team_gateway_polling(reconciliation_id):
    stale_before = timezone.now() - timedelta(minutes=5)
    with transaction.atomic():
        reconciliation = (
            GatewayPlanReconciliation.objects.select_for_update().select_related("team").get(pk=reconciliation_id)
        )
        if reconciliation.status in {
            GatewayPlanReconciliation.Status.COMPLETED,
            GatewayPlanReconciliation.Status.NEEDS_ATTENTION,
        }:
            return reconciliation
        if (
            reconciliation.status == GatewayPlanReconciliation.Status.RUNNING
            and reconciliation.updated_at > stale_before
        ):
            return reconciliation
        reconciliation.status = GatewayPlanReconciliation.Status.RUNNING
        reconciliation.last_error = ""
        reconciliation.save(update_fields=["status", "last_error", "updated_at"])

    from .config_generator import generate_connector_config
    from .gateway_config_delivery import gateway_supports_guided_setup, queue_gateway_config

    queued = 0
    skipped = 0
    unsupported = 0
    unsupported_serials = []
    errors = []
    gateways = Gateway.objects.filter(
        team=reconciliation.team,
        lifecycle_status="active",
    ).prefetch_related("devices__template")
    for gateway in gateways:
        if not gateway.devices.exists():
            skipped += 1
            continue
        if not gateway_supports_guided_setup(gateway):
            unsupported += 1
            unsupported_serials.append(gateway.serial_number)
            continue
        connectors = generate_connector_config(gateway)
        if not connectors:
            skipped += 1
            continue
        config_payload = {"connectors": connectors}
        checksum = payload_checksum(config_payload)
        latest = GatewayConfig.objects.filter(gateway=gateway).order_by("-revision").first()
        if latest and latest.checksum == checksum and latest.status != "failed":
            skipped += 1
            continue
        try:
            queue_gateway_config(gateway, "connector_update", config_payload)
            queued += 1
        except Exception as exc:
            logger.exception("Could not reconcile polling for Gateway %s", gateway.serial_number)
            errors.append(f"{gateway.serial_number}: {exc}")

    reconciliation.queued_gateway_count = queued
    reconciliation.skipped_gateway_count = skipped
    reconciliation.unsupported_gateway_count = unsupported
    reconciliation.completed_at = timezone.now()
    reconciliation.status = (
        GatewayPlanReconciliation.Status.NEEDS_ATTENTION
        if errors or unsupported
        else GatewayPlanReconciliation.Status.COMPLETED
    )
    attention = list(errors)
    if unsupported_serials:
        attention.append(f"Gateway update required: {', '.join(sorted(unsupported_serials))}")
    reconciliation.last_error = "; ".join(attention)[:4000]
    reconciliation.save()
    return reconciliation


def dispatch_due_plan_reconciliations(limit=25) -> int:
    """Recover committed queue rows and workers that stopped while running."""
    stale_before = timezone.now() - timedelta(minutes=5)
    ids = list(
        GatewayPlanReconciliation.objects.filter(
            models.Q(status=GatewayPlanReconciliation.Status.QUEUED)
            | models.Q(status=GatewayPlanReconciliation.Status.RUNNING, updated_at__lte=stale_before)
        )
        .order_by("created_at")
        .values_list("pk", flat=True)[:limit]
    )
    for reconciliation_id in ids:
        reconcile_team_gateway_polling(reconciliation_id)
    return len(ids)
