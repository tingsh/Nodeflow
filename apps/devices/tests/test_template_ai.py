import tempfile
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.devices.models import DeviceTemplate
from apps.devices.template_ai import (
    _build_generation_prompt,
    _validate_register_map,
    generate_template_from_ai,
    save_approved_template,
)
from apps.teams.models import Team
from apps.users.models import CustomUser


class TemplateAITest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.user = CustomUser.objects.create(email="test@example.com", username="testuser")
        from apps.teams.models import Membership
        from apps.teams.roles import ROLE_ADMIN

        Membership.objects.create(team=self.team, user=self.user, role=ROLE_ADMIN)

    def test_validate_register_map_valid(self):
        valid_map = {
            "voltage": {"address": 3028, "type": "float32", "functionCode": 3, "unit": "V"},
            "frequency": {"address": 100, "type": "uint16", "functionCode": 4},
            "control_speed": {"address": 10, "type": "uint16", "functionCode": 6, "writable": True, "control": "input"},
        }
        is_valid, errors = _validate_register_map(valid_map)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_register_map_invalid(self):
        # Missing address
        invalid_map_1 = {"voltage": {"type": "float32", "functionCode": 3}}
        # Invalid function code
        invalid_map_2 = {"voltage": {"address": 3028, "type": "float32", "functionCode": 99}}
        # Writable but missing control field
        invalid_map_3 = {"control_speed": {"address": 10, "type": "uint16", "functionCode": 6, "writable": True}}

        self.assertFalse(_validate_register_map(invalid_map_1)[0])
        self.assertFalse(_validate_register_map(invalid_map_2)[0])
        self.assertFalse(_validate_register_map(invalid_map_3)[0])

    def test_build_generation_prompt(self):
        prompt_no_url = _build_generation_prompt("Schneider", "PM5350")
        self.assertIn("Schneider", prompt_no_url)
        self.assertIn("PM5350", prompt_no_url)
        self.assertNotIn("IMPORTANT: The user has provided a direct documentation URL", prompt_no_url)

        prompt_with_url = _build_generation_prompt("Schneider", "PM5350", "https://example.com/doc.pdf")
        self.assertIn("https://example.com/doc.pdf", prompt_with_url)

    def test_save_approved_template(self):
        draft = {
            "name": "Schneider PM5350 Test",
            "manufacturer": "Schneider Electric",
            "model_number": "PM5350-T",
            "device_type": "power_meter",
            "protocol": "modbus_tcp",
            "category": "energy",
            "register_map": {"voltage": {"address": 3028, "type": "float32", "functionCode": 3, "unit": "V"}},
            "alert_presets": [
                {
                    "name": "Overvoltage Warning",
                    "key": "voltage",
                    "condition": "gt",
                    "threshold": 250.0,
                    "severity": "warning",
                }
            ],
            "default_polling_interval": 5,
            "source_url": "https://example.com/doc.pdf",
            "ai_confidence": 0.95,
        }

        template = save_approved_template(draft, team=self.team)
        self.assertIsNotNone(template.id)
        self.assertEqual(template.source, "ai_generated")
        self.assertFalse(template.is_verified)
        self.assertEqual(template.created_by_team, self.team)
        self.assertEqual(template.ai_confidence, 0.95)
        self.assertEqual(template.source_url, "https://example.com/doc.pdf")

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_generate_template_from_ai_success(self, mock_configure, mock_model_class):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = """{
            "name": "Schneider PM5350",
            "manufacturer": "Schneider Electric",
            "model_number": "PM5350",
            "device_type": "power_meter",
            "protocol": "modbus_tcp",
            "category": "energy",
            "register_map": {
                "voltage": {"address": 3028, "type": "float32", "functionCode": 3, "unit": "V"}
            },
            "alert_presets": [],
            "default_polling_interval": 5,
            "source_url": "https://example.com/doc",
            "ai_confidence": 0.9
        }"""
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model

        with self.settings(GEMINI_API_KEY="test-key"):
            result = generate_template_from_ai("Schneider Electric", "PM5350")

        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["name"], "Schneider PM5350")
        self.assertEqual(result["ai_confidence"], 0.9)


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
        }
    }
)
class TemplateAIViewTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        self.user = CustomUser.objects.create(email="test@example.com", username="testuser")
        from apps.teams.models import Membership
        from apps.teams.roles import ROLE_ADMIN

        Membership.objects.create(team=self.team, user=self.user, role=ROLE_ADMIN)
        self.client = Client()
        self.client.force_login(self.user)

    @patch("apps.devices.views.generate_template_ai_task.delay")
    def test_ai_template_generate_view_existing(self, mock_task):
        DeviceTemplate.objects.create(
            name="Existing PM5350",
            manufacturer="Schneider Electric",
            model_number="PM5350",
            device_type="power_meter",
            protocol="modbus_tcp",
            register_map={},
        )
        url = reverse("web_team:devices:ai_template_generate", args=[self.team.slug])
        response = self.client.post(url, {"manufacturer": "Schneider Electric", "model_number": "PM5350"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Template Already Exists")
        self.assertFalse(mock_task.called)

    @patch("apps.devices.views.generate_template_ai_task.delay")
    def test_ai_template_generate_view_new(self, mock_task):
        url = reverse("web_team:devices:ai_template_generate", args=[self.team.slug])
        response = self.client.post(url, {"manufacturer": "Schneider Electric", "model_number": "NewModel"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compiling Register Map")
        self.assertTrue(mock_task.called)

    @patch("apps.devices.views.generate_template_ai_task.delay")
    def test_ai_template_generate_accepts_temporary_pdf_evidence(self, mock_task):
        url = reverse("web_team:devices:ai_template_generate", args=[self.team.slug])
        manual = SimpleUploadedFile(
            "manual.pdf",
            b"%PDF-1.4\nminimal-test-document",
            content_type="application/pdf",
        )
        with (
            tempfile.TemporaryDirectory() as media_root,
            self.settings(MEDIA_ROOT=media_root),
        ):
            response = self.client.post(
                url,
                {
                    "manufacturer": "Schneider Electric",
                    "model_number": "PDFModel",
                    "documentation_file": manual,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compiling Register Map")
        self.assertTrue(mock_task.call_args.kwargs["doc_storage_path"].endswith(".pdf"))

    def test_ai_template_status_view_processing(self):
        task_id = "test-task-123"
        cache.set(f"ai_template:{task_id}", {"status": "processing"}, timeout=300)
        url = reverse("web_team:devices:ai_template_status", args=[self.team.slug, task_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compiling Register Map")

    def test_ai_template_status_view_complete(self):
        task_id = "test-task-123"
        draft = {
            "name": "Test Template",
            "manufacturer": "Test Mfg",
            "model_number": "Test Model",
            "device_type": "power_meter",
            "protocol": "modbus_tcp",
            "category": "energy",
            "register_map": {"voltage": {"address": 0, "type": "float32", "functionCode": 3, "unit": "V"}},
            "alert_presets": [],
            "ai_confidence": 90.0,
            "source_url": "https://example.com",
        }
        cache.set(f"ai_template:{task_id}", {"status": "complete", "draft": draft}, timeout=300)
        url = reverse("web_team:devices:ai_template_status", args=[self.team.slug, task_id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Save Private AI Draft")

    def test_ai_template_approve_view(self):
        task_id = "test-task-456"
        draft = {
            "name": "Test Approved Template",
            "manufacturer": "Test Mfg",
            "model_number": "Test Model",
            "device_type": "power_meter",
            "protocol": "modbus_tcp",
            "category": "energy",
            "register_map": {"voltage": {"address": 0, "type": "float32", "functionCode": 3, "unit": "V"}},
            "alert_presets": [],
            "ai_confidence": 0.90,
            "source_url": "https://example.com",
        }
        cache.set(f"ai_template:{task_id}", {"status": "complete", "draft": draft}, timeout=300)
        url = reverse("web_team:devices:ai_template_approve", args=[self.team.slug])
        response = self.client.post(url, {"task_id": task_id})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Template Saved Successfully!")

        self.assertTrue(DeviceTemplate.objects.filter(name="Test Approved Template").exists())
