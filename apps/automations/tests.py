from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.devices.models import Device, Site
from apps.teams.models import Team

from .engine import evaluate_automations, evaluate_condition
from .models import Automation, AutomationAction, AutomationCondition, AutomationLog


class AutomationsEngineTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Stark Industries", slug="stark")
        self.site = Site.objects.create(team=self.team, name="HQ")
        self.device = Device.objects.create(team=self.team, site=self.site, name="Pump Station")

        self.automation = Automation.objects.create(
            team=self.team,
            name="High Temp Alert",
            trigger_logic="and",
            cooldown_minutes=0,  # Easy for testing
        )

    def test_evaluate_condition_gt(self):
        condition = AutomationCondition.objects.create(
            team=self.team,
            automation=self.automation,
            device=self.device,
            telemetry_key="temp",
            operator="gt",
            threshold="100.0",
        )
        # Should be met
        self.assertTrue(evaluate_condition(condition, 105.0))
        # Should not be met
        self.assertFalse(evaluate_condition(condition, 99.0))

    def test_evaluate_condition_is_true(self):
        condition = AutomationCondition.objects.create(
            team=self.team,
            automation=self.automation,
            device=self.device,
            telemetry_key="motor_fault",
            operator="is_true",
        )
        self.assertTrue(evaluate_condition(condition, True))
        self.assertFalse(evaluate_condition(condition, False))

    @patch("django.core.cache.cache.set")
    @patch("django.core.cache.cache.get")
    def test_evaluate_duration_logic(self, mock_get, mock_set):
        condition = AutomationCondition.objects.create(
            team=self.team,
            automation=self.automation,
            device=self.device,
            telemetry_key="pressure",
            operator="lt",
            threshold="10",
            duration_seconds=60,  # Must be low pressure for 1min
        )

        # Step 1: Initial trigger (not yet duration)
        mock_get.return_value = None
        self.assertFalse(evaluate_condition(condition, 5))
        mock_set.assert_called_once()

        # Step 2: Second trigger, but only 30 secs passed
        mock_set.reset_mock()
        mock_get.return_value = {"is_met": True, "met_since": timezone.now().timestamp() - 30}
        self.assertFalse(evaluate_condition(condition, 5))

        # Step 3: Triggered for 65 secs
        mock_get.return_value = {"is_met": True, "met_since": timezone.now().timestamp() - 65}
        self.assertTrue(evaluate_condition(condition, 5))

    @patch("apps.automations.engine.send_device_command")
    def test_evaluate_automations_full_flow(self, mock_send_rpc):
        # Condition: Temp > 100
        AutomationCondition.objects.create(
            team=self.team,
            automation=self.automation,
            device=self.device,
            telemetry_key="temp",
            operator="gt",
            threshold="100",
            duration_seconds=0,
        )
        # Action: Send command
        AutomationAction.objects.create(
            team=self.team,
            automation=self.automation,
            action_type="send_command",
            target_device=self.device,
            command_key="turn_off",
            command_payload={"value": True},
        )

        # Test 1: Condition not met
        evaluate_automations(self.device, {"temp": 90.0, "humidity": 50.0})
        self.assertEqual(AutomationLog.objects.count(), 0)
        mock_send_rpc.assert_not_called()

        # Test 2: Condition met
        evaluate_automations(self.device, {"temp": 110.0, "humidity": 55.0})
        self.assertEqual(AutomationLog.objects.count(), 1)
        mock_send_rpc.assert_called_once_with(device=self.device, key="turn_off", value=True, user=None)
