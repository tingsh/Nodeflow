import base64
import hashlib
import logging
import sys
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from .models import GatewayActivation

logger = logging.getLogger("novena_hub")


def _activation_cipher() -> Fernet:
    key = getattr(settings, "GATEWAY_ACTIVATION_ENCRYPTION_KEY", "")
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)

    if not settings.DEBUG and "test" not in sys.argv:
        raise ImproperlyConfigured("GATEWAY_ACTIVATION_ENCRYPTION_KEY is required outside debug/test.")

    digest = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_activation_secret(secret: str) -> str:
    return _activation_cipher().encrypt(secret.encode()).decode()


def decrypt_activation_secret(encrypted_secret: str) -> str:
    if not encrypted_secret:
        raise ValueError("Activation secret is no longer available.")
    try:
        return _activation_cipher().decrypt(encrypted_secret.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Activation secret cannot be decrypted.") from exc


def activation_ttl() -> timedelta:
    hours = getattr(settings, "GATEWAY_ACTIVATION_TTL_HOURS", 24)
    return timedelta(hours=hours)


def create_gateway_activation(gateway, operational_password: str) -> GatewayActivation:
    expires_at = timezone.now() + activation_ttl()
    return GatewayActivation.objects.create(
        team=gateway.team,
        gateway=gateway,
        expires_at=expires_at,
        encrypted_mqtt_password=encrypt_activation_secret(operational_password),
    )


def retry_delay_for_attempts(attempt_count: int) -> timedelta:
    seconds = min(300, max(60, 60 * (2 ** max(0, attempt_count - 1))))
    return timedelta(seconds=seconds)


def deliver_gateway_activation(activation: GatewayActivation, *, retry: bool = False) -> bool:
    """Publish activation and persist the transport-level delivery attempt."""
    now = timezone.now()
    activation = GatewayActivation.objects.select_related("gateway", "team").get(pk=activation.pk)

    if activation.status == "acknowledged":
        return False
    if activation.expires_at <= now:
        expire_gateway_activation(activation)
        return False

    password = decrypt_activation_secret(activation.encrypted_mqtt_password)

    try:
        from apps.telemetry.mqtt_publisher import publish_gateway_activation

        publish_gateway_activation(activation, password)
    except Exception as exc:
        activation.attempt_count += 1
        activation.last_attempt_at = now
        activation.status = "failed"
        activation.last_error = str(exc)
        activation.save(update_fields=["attempt_count", "last_attempt_at", "status", "last_error", "updated_at"])
        logger.info("Gateway activation delivery failed for %s: %s", activation.gateway.serial_number, exc)
        return False

    activation.attempt_count += 1
    activation.last_attempt_at = now
    activation.delivered_at = now
    activation.status = "retried" if retry or activation.attempt_count > 1 else "delivered"
    activation.last_error = ""
    activation.save(
        update_fields=["attempt_count", "last_attempt_at", "delivered_at", "status", "last_error", "updated_at"]
    )

    gateway = activation.gateway
    if gateway.lifecycle_status in ("claimed", "bootstrap_seen"):
        gateway.lifecycle_status = "activating"
        gateway.save(update_fields=["lifecycle_status"])
    return True


def latest_retryable_activation(gateway):
    now = timezone.now()
    return (
        gateway.activations.filter(
            status__in=GatewayActivation.UNRESOLVED_STATUSES,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )


def retry_activation_for_gateway(gateway) -> bool:
    activation = latest_retryable_activation(gateway)
    if not activation:
        return False
    return deliver_gateway_activation(activation, retry=True)


@transaction.atomic
def acknowledge_gateway_activation(gateway, request_id: str, status: str, error: str = ""):
    activation = GatewayActivation.objects.select_for_update().filter(gateway=gateway, request_id=request_id).first()
    if not activation:
        return None

    if activation.status == "acknowledged":
        return activation

    if status == "success":
        activation.status = "acknowledged"
        activation.acknowledged_at = timezone.now()
        activation.encrypted_mqtt_password = ""
        activation.last_error = ""
        activation.save(
            update_fields=["status", "acknowledged_at", "encrypted_mqtt_password", "last_error", "updated_at"]
        )
    else:
        activation.status = "failed"
        activation.last_error = error or f"Gateway reported activation status: {status}"
        activation.save(update_fields=["status", "last_error", "updated_at"])
    return activation


def expire_gateway_activation(activation: GatewayActivation) -> bool:
    activation = GatewayActivation.objects.get(pk=activation.pk)
    if activation.status in ("acknowledged", "expired"):
        return False
    activation.status = "expired"
    activation.encrypted_mqtt_password = ""
    activation.last_error = activation.last_error or "Activation expired before gateway acknowledgement."
    activation.save(update_fields=["status", "encrypted_mqtt_password", "last_error", "updated_at"])
    return True


def expire_and_retry_gateway_activations() -> dict:
    now = timezone.now()
    expired = 0
    retried = 0

    for activation in GatewayActivation.objects.filter(
        status__in=GatewayActivation.UNRESOLVED_STATUSES,
        expires_at__lte=now,
    ):
        if expire_gateway_activation(activation):
            expired += 1

    retryable = GatewayActivation.objects.select_related("gateway", "team").filter(
        status__in=GatewayActivation.UNRESOLVED_STATUSES,
        expires_at__gt=now,
    )
    for activation in retryable:
        if activation.last_attempt_at:
            next_retry_at = activation.last_attempt_at + retry_delay_for_attempts(activation.attempt_count)
            if next_retry_at > now:
                continue
        if deliver_gateway_activation(activation, retry=activation.attempt_count > 0):
            retried += 1

    return {"expired": expired, "retried": retried}
