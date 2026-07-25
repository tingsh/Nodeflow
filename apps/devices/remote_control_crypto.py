from __future__ import annotations

import base64
import hashlib
import json

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.conf import settings


class CommandSigningUnavailable(RuntimeError):
    pass


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def payload_checksum(payload: dict) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _private_key() -> Ed25519PrivateKey:
    key_id = settings.REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID
    encoded = settings.REMOTE_CONTROL_SIGNING_KEYS.get(
        key_id,
        settings.REMOTE_CONTROL_SIGNING_PRIVATE_KEY,
    )
    if not encoded:
        raise CommandSigningUnavailable("REMOTE_CONTROL_SIGNING_PRIVATE_KEY is not configured")
    try:
        raw = base64.b64decode(encoded, validate=True)
        return Ed25519PrivateKey.from_private_bytes(raw)
    except (ValueError, TypeError) as exc:
        raise CommandSigningUnavailable("Remote-control signing key must be a base64 Ed25519 seed") from exc


def sign_payload(payload: dict) -> tuple[str, str]:
    signature = _private_key().sign(canonical_bytes(payload))
    return settings.REMOTE_CONTROL_ACTIVE_SIGNING_KEY_ID, base64.b64encode(signature).decode()


def build_signed_command_envelope(command, *, request_id=None) -> dict:
    request_id = request_id or command.idempotency_key
    body = {
        "schema_version": command.schema_version,
        "request_id": str(request_id),
        "command_id": str(command.pk),
        "idempotency_key": str(command.idempotency_key),
        "target": {
            "gateway_serial": command.gateway.serial_number,
            "device_id": str(command.device_id) if command.device_id else None,
        },
        "method": command.operation,
        "params": command.request_payload.get("params", {}),
        "risk": command.risk,
        "control_epoch": command.control_epoch,
        "sequence_number": command.sequence_number,
        "revisions": {
            "template": command.template_revision,
            "commissioning": command.commissioning_revision,
            "policy": command.policy_revision,
        },
        "policy_checksum": command.policy_checksum,
        "issued_at": command.created_at.isoformat(),
        "expires_at": command.expires_at.isoformat(),
    }
    key_id, signature = sign_payload(body)
    return {**body, "signing_key_id": key_id, "signature": signature}


def sign_policy_bundle(payload: dict) -> dict:
    key_id, signature = sign_payload(payload)
    return {
        "payload": payload,
        "checksum": payload_checksum(payload),
        "signing_key_id": key_id,
        "signature": signature,
    }
