import base64
import hashlib
import json
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

OTA_KEY_ID = "novena-ota-v1"
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-(?:rc|canary)\.\d+)?$")


def canonical_manifest_bytes(manifest: dict) -> bytes:
    return json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def load_private_key(value: str = None) -> Ed25519PrivateKey:
    value = value or getattr(settings, "NOVENA_OTA_SIGNING_PRIVATE_KEY", "")
    if not value:
        raise ValidationError("NOVENA_OTA_SIGNING_PRIVATE_KEY is not configured")
    raw = value.encode("utf-8")
    if "BEGIN" in value:
        key = serialization.load_pem_private_key(raw, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValidationError("OTA signing key must be an Ed25519 private key")
        return key
    try:
        return Ed25519PrivateKey.from_private_bytes(base64.b64decode(value, validate=True))
    except Exception as exc:
        raise ValidationError("NOVENA_OTA_SIGNING_PRIVATE_KEY must be PEM or base64 raw Ed25519 private key") from exc


def public_key_b64(private_key: Ed25519PrivateKey) -> str:
    public_key = private_key.public_key()
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def verify_manifest_signature(manifest: dict, signature_b64: str, public_key_b64_value: str):
    public_key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64_value, validate=True))
    public_key.verify(base64.b64decode(signature_b64, validate=True), canonical_manifest_bytes(manifest))


def validate_release_version(version: str):
    if not VERSION_RE.fullmatch(version or ""):
        raise ValidationError("Firmware version must use MAJOR.MINOR.PATCH with optional -rc.N or -canary.N")


def compute_release_digest(release) -> tuple[str, int]:
    if not release.file:
        raise ValidationError("Firmware release file is required")
    h = hashlib.sha256()
    release.file.open("rb")
    try:
        for chunk in iter(lambda: release.file.read(1024 * 1024), b""):
            h.update(chunk)
    finally:
        release.file.close()
    return h.hexdigest(), release.file.size


def build_release_manifest(release, artifact_url: str, issued_at=None, expires_at=None) -> dict:
    validate_release_version(release.version)
    parsed = urlparse(artifact_url)
    if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        raise ValidationError("OTA artifact URL must use HTTPS outside local test fixtures")

    issued_at = issued_at or timezone.now()
    ttl_days = int(getattr(settings, "NOVENA_OTA_MANIFEST_TTL_DAYS", 14))
    expires_at = expires_at or issued_at + timedelta(days=ttl_days)
    key_id = getattr(settings, "NOVENA_OTA_SIGNING_KEY_ID", OTA_KEY_ID)

    sha256 = release.sha256
    size_bytes = release.size_bytes
    if not sha256 or not size_bytes:
        sha256, size_bytes = compute_release_digest(release)

    return {
        "schema_version": 1,
        "product": "novena-gateway",
        "version": release.version,
        "artifact_url": artifact_url,
        "artifact_sha256": sha256,
        "size_bytes": int(size_bytes),
        "channel": release.channel,
        "issued_at": issued_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "minimum_gateway_version": release.minimum_gateway_version or "0.1.0",
        "maximum_gateway_version": release.maximum_gateway_version or "",
        "key_id": key_id,
    }


def sign_manifest(manifest: dict, private_key: Ed25519PrivateKey = None) -> str:
    private_key = private_key or load_private_key()
    return base64.b64encode(private_key.sign(canonical_manifest_bytes(manifest))).decode("ascii")


def ensure_release_signed(release, artifact_url: str):
    sha256, size_bytes = compute_release_digest(release)
    if (
        release.is_signed
        and release.manifest.get("artifact_url") == artifact_url
        and release.manifest.get("artifact_sha256") == sha256
        and release.manifest.get("size_bytes") == size_bytes
        and release.expires_at
        and release.expires_at > timezone.now()
    ):
        return release

    release.sha256 = sha256
    release.size_bytes = size_bytes
    issued_at = timezone.now()
    manifest = build_release_manifest(release, artifact_url, issued_at=issued_at)
    release.manifest = manifest
    release.signature = sign_manifest(manifest)
    release.key_id = manifest["key_id"]
    release.signed_at = issued_at
    release.expires_at = datetime.fromisoformat(manifest["expires_at"].replace("Z", "+00:00"))
    release.signing_status = "signed"
    release.save(
        update_fields=[
            "sha256",
            "size_bytes",
            "manifest",
            "signature",
            "key_id",
            "signed_at",
            "expires_at",
            "signing_status",
        ]
    )
    return release
