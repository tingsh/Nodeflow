import base64
import shutil
import tempfile
from unittest.mock import patch

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.devices.models import FirmwareRelease, Gateway, Site
from apps.devices.ota_signing import ensure_release_signed, public_key_b64, verify_manifest_signature
from apps.teams.models import Team
from apps.teams.roles import ROLE_OWNER
from apps.users.models import CustomUser


class OtaSigningTest(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.private_key = Ed25519PrivateKey.generate()
        raw_private = self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        self.override = override_settings(
            MEDIA_ROOT=self.media_root,
            NOVENA_OTA_SIGNING_PRIVATE_KEY=base64.b64encode(raw_private).decode("ascii"),
            NOVENA_OTA_SIGNING_KEY_ID="novena-ota-v1",
            NOVENA_OTA_MANIFEST_TTL_DAYS=14,
            ALLOWED_HOSTS=["testserver"],
        )
        self.override.enable()

        self.user = CustomUser.objects.create_user(email="owner@example.com", username="owner", password="pw")
        self.team = Team.objects.create(name="OTA Team", slug="ota-team")
        self.team.members.add(self.user, through_defaults={"role": ROLE_OWNER})
        self.site = Site.objects.create(team=self.team, name="Factory")
        self.gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="GW-OTA",
            serial_number="NF-OTA-001",
            access_token="ota-token",
            firmware_version="1.1.0",
        )
        self.release = FirmwareRelease.objects.create(
            version="1.2.0",
            file=SimpleUploadedFile("novena-gateway-1.2.0.tar.gz", b"signed firmware bytes"),
            is_active=True,
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root)

    def test_release_signing_creates_verifiable_manifest(self):
        ensure_release_signed(self.release, "https://testserver/media/firmware/novena-gateway-1.2.0.tar.gz")
        self.release.refresh_from_db()

        self.assertTrue(self.release.is_signed)
        self.assertEqual(self.release.key_id, "novena-ota-v1")
        self.assertEqual(self.release.manifest["version"], "1.2.0")
        verify_manifest_signature(self.release.manifest, self.release.signature, public_key_b64(self.private_key))

        tampered = dict(self.release.manifest)
        tampered["version"] = "9.9.9"
        with self.assertRaises(InvalidSignature):
            verify_manifest_signature(tampered, self.release.signature, public_key_b64(self.private_key))

    @patch("apps.telemetry.mqtt_publisher.publish_rpc_command")
    def test_ota_endpoint_is_monitoring_only_by_default(self, mock_publish):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("web_team:devices:gateway_ota_update", args=[self.team.slug, self.gateway.pk]),
            {"version": self.release.version},
            secure=True,
        )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertIn("disabled", payload["error"])
        mock_publish.assert_not_called()

    @patch("apps.telemetry.mqtt_publisher.publish_rpc_command")
    def test_generic_rpc_rejects_update_firmware(self, mock_publish):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("web_team:devices:gateway_send_rpc", args=[self.team.slug, self.gateway.pk]),
            {"method": "update_firmware", "params": "{}"},
        )

        self.assertEqual(response.status_code, 400)
        mock_publish.assert_not_called()
