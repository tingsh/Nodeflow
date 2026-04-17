import uuid
from django.test import TestCase
from django.utils import timezone
from apps.teams.models import Team, Membership
from apps.users.models import CustomUser
from apps.devices.models import Site, Device, DeviceTemplate
from apps.telemetry.models import TelemetryData
from apps.chat.models import Chat, ChatMessage, ChatUsage
from apps.chat.tool_executor import NodeflowToolExecutor
from apps.chat.system_prompt import get_system_prompt

class ChatAIFeatureTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create(email="test@example.com", username="testuser")
        self.team = Team.objects.create(name="Test Team", slug="test-team")
        Membership.objects.create(team=self.team, user=self.user, role="owner")
        
        self.site = Site.objects.create(team=self.team, name="Main Plant")
        self.device = Device.objects.create(
            team=self.team, 
            site=self.site, 
            name="Power Meter 1",
            device_type="power_meter",
            energy_category="utility"
        )
        
        # Add some telemetry
        now = timezone.now()
        TelemetryData.objects.create(
            device=self.device,
            timestamp=now - timezone.timedelta(minutes=5),
            key="active_power",
            value_numeric=150.5
        )
        TelemetryData.objects.create(
            device=self.device,
            timestamp=now - timezone.timedelta(minutes=10),
            key="active_power",
            value_numeric=140.0
        )

    def test_usage_tracking(self):
        count1 = ChatUsage.get_count_for_team(self.team)
        self.assertEqual(count1, 0)
        
        ChatUsage.increment_count_for_team(self.team)
        count2 = ChatUsage.get_count_for_team(self.team)
        self.assertEqual(count2, 1)

    def test_tool_executor_status(self):
        executor = NodeflowToolExecutor(self.team)
        status = executor.get_device_status([self.device.id])
        
        self.assertEqual(len(status), 1)
        self.assertEqual(status[0]['name'], "Power Meter 1")
        self.assertTrue(any(r['key'] == 'active_power' and r['value'] == 150.5 for r in status[0]['readings']))

    def test_tool_executor_energy_aggregation(self):
        executor = NodeflowToolExecutor(self.team)
        now = timezone.now()
        start = (now - timezone.timedelta(days=1)).isoformat()
        end = (now + timezone.timedelta(days=1)).isoformat()
        
        data = executor.get_energy_data(
            device_ids=[self.device.id],
            keys=["active_power"],
            start_date=start,
            end_date=end,
            aggregation="hour"
        )
        
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]['device'], "Power Meter 1")
        # Avg of 150.5 and 140.0 is 145.25
        self.assertEqual(data[0]['avg'], 145.25)

    def test_system_prompt_generation(self):
        prompt = get_system_prompt(self.team, self.user)
        self.assertIn("Test Team", prompt)
        self.assertIn("Main Plant", prompt)
        self.assertIn("Power Meter 1", prompt)
        self.assertIn("Antigravity AI", prompt)
