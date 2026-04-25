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
