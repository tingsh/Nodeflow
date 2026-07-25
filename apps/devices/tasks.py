import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger("novena_hub")


@shared_task(
    bind=True,
    autoretry_for=(),
    name="apps.devices.tasks.dispatch_remote_command_outbox",
)
def dispatch_remote_command_outbox(self, outbox_id):
    """Dispatch one durable outbox row; writes are never blindly autoretried."""
    from .remote_control import dispatch_outbox

    command = dispatch_outbox(outbox_id)
    return str(command.pk) if command else None


@shared_task
def check_device_heartbeats():
    """Persist devices as offline when telemetry freshness exceeds the offline timeout."""
    from .freshness import device_offline_cutoff
    from .models import Device

    now = timezone.now()
    stale_ids = []

    devices = Device.objects.select_related("template").filter(status="online")
    for device in devices:
        if not device.last_telemetry_at or device.last_telemetry_at < device_offline_cutoff(device, now):
            stale_ids.append(device.id)

    count = 0
    if stale_ids:
        count = Device.objects.filter(id__in=stale_ids).exclude(status="alarm").update(status="offline")
        logger.info("Marked %d device(s) as offline (telemetry timeout)", count)

    return count


@shared_task
def check_gateway_heartbeats():
    """Mark gateways offline when the edge heartbeat exceeds the configured timeout."""
    from .models import Gateway

    timeout = timedelta(seconds=getattr(settings, "GATEWAY_OFFLINE_SECONDS", 120))
    cutoff = timezone.now() - timeout

    stale_gateways = Gateway.objects.filter(
        status="online",
        last_seen__lt=cutoff,
    )

    count = stale_gateways.update(status="offline")
    if count:
        logger.info("Marked %d gateway(s) as offline (heartbeat timeout)", count)

    return count


@shared_task
def check_rpc_timeouts():
    """Marks pending RPC commands as timed out if no response received within 60 seconds."""
    from .models import RpcCommand
    from .services import sync_device_command_from_rpc

    timeout = timedelta(seconds=60)
    cutoff = timezone.now() - timeout

    timed_out = list(
        RpcCommand.objects.filter(
            status="pending",
            sent_at__lt=cutoff,
        )
    )

    count = 0
    for rpc in timed_out:
        rpc.status = "timeout"
        rpc.error_message = rpc.error_message or "Timed out waiting for gateway response."
        rpc.save(update_fields=["status", "error_message", "updated_at"])
        sync_device_command_from_rpc(rpc)
        count += 1
    if count:
        logger.info("Marked %d RPC command(s) as timed out", count)

    return count


@shared_task
def expire_and_retry_gateway_activations():
    """Expire stale activation escrow and retry unresolved gateway activations."""
    from .activation import expire_and_retry_gateway_activations as run_activation_maintenance

    result = run_activation_maintenance()
    if result["expired"] or result["retried"]:
        logger.info(
            "Gateway activation maintenance completed: expired=%d retried=%d",
            result["expired"],
            result["retried"],
        )
    return result


@shared_task
def expire_control_activations():
    """Require annual recommissioning and suspend the exact expired keys."""
    from .models import (
        ControlActivation,
        ControlReadinessAssessment,
        RemoteControlScope,
    )

    expired = list(
        ControlActivation.objects.filter(
            status=ControlActivation.Status.ACTIVE,
            expires_at__lte=timezone.now(),
        ).select_related("device")
    )
    for activation in expired:
        activation.status = ControlActivation.Status.EXPIRED
        activation.suspended_reason = "Annual recommissioning is due"
        activation.save(update_fields=["status", "suspended_reason", "updated_at"])
        RemoteControlScope.objects.filter(
            team=activation.team,
            device=activation.device,
            command_key=activation.command_key,
        ).update(
            mode=RemoteControlScope.Mode.SUSPENDED,
            reason="Annual recommissioning is due",
        )
        ControlReadinessAssessment.objects.filter(
            pk=activation.readiness_assessment_id
        ).update(state=ControlReadinessAssessment.State.RECOMMISSIONING_REQUIRED)
    return len(expired)


@shared_task
def generate_template_ai_task(task_id: str, manufacturer: str, model_number: str, doc_url: str = None):
    """Background task: AI generates a device template draft."""
    from django.core.cache import cache

    from apps.devices.template_ai import generate_template_from_ai

    logger.info(
        "Starting AI template generation background task: %s (Manufacturer: %s, Model: %s)",
        task_id,
        manufacturer,
        model_number,
    )
    try:
        cache.set(f"ai_template:{task_id}", {"status": "processing"}, timeout=300)
        draft = generate_template_from_ai(manufacturer, model_number, doc_url=doc_url)
        if draft.get("status") == "error":
            cache.set(f"ai_template:{task_id}", {"status": "error", "error": draft.get("error")}, timeout=300)
        else:
            cache.set(f"ai_template:{task_id}", {"status": "complete", "draft": draft}, timeout=300)
    except Exception as e:
        cache.set(f"ai_template:{task_id}", {"status": "error", "error": str(e)}, timeout=300)
        logger.exception("AI template generation background task failed for task_id %s", task_id)
