import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger("iot_platform")


@shared_task
def check_gateway_heartbeats():
    """
    Safety net: marks gateways as offline if no heartbeat received
    within the timeout window. Handles cases where MQTT LWT doesn't fire
    (e.g. broker restart, network partition).

    Should be scheduled to run every 60 seconds via django-celery-beat.
    """
    from .models import Gateway

    timeout = timedelta(seconds=120)
    cutoff = timezone.now() - timeout

    stale_gateways = Gateway.objects.filter(
        status="online",
        last_seen__lt=cutoff,
    )

    count = stale_gateways.update(status="offline")
    if count:
        logger.info("Marked %d gateway(s) as offline (heartbeat timeout)", count)


@shared_task
def check_rpc_timeouts():
    """
    Marks pending RPC commands as timed out if no response received
    within 60 seconds.
    """
    from .models import RpcCommand

    timeout = timedelta(seconds=60)
    cutoff = timezone.now() - timeout

    timed_out = RpcCommand.objects.filter(
        status="pending",
        sent_at__lt=cutoff,
    )

    count = timed_out.update(status="timeout")
    if count:
        logger.info("Marked %d RPC command(s) as timed out", count)


@shared_task
def generate_template_ai_task(task_id: str, manufacturer: str, model_number: str, doc_url: str = None):
    """
    Background task: AI generates a device template draft.
    Result is cached in Redis keyed by task_id for frontend polling.
    """
    from django.core.cache import cache
    from apps.devices.template_ai import generate_template_from_ai

    logger.info("Starting AI template generation background task: %s (Manufacturer: %s, Model: %s)", task_id, manufacturer, model_number)
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
