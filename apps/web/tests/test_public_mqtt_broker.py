from django.test import TestCase, override_settings
from django.urls import reverse

from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_ADMIN
from apps.users.models import CustomUser


class PublicMqttBrokerCopyTest(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Broker Copy", slug="broker-copy")
        self.user = CustomUser.objects.create_user(
            email="broker-copy@example.com",
            username="broker-copy@example.com",
            password="testpass123",
        )
        Membership.objects.create(team=self.team, user=self.user, role=ROLE_ADMIN)
        self.client.force_login(self.user)

    @override_settings(
        PUBLIC_MQTT_BROKER_SCHEME="mqtts",
        PUBLIC_MQTT_BROKER_HOST="mqtt.novenaplatform.com",
        PUBLIC_MQTT_BROKER_PORT=8883,
        ALLOWED_HOSTS=["app.novenaplatform.com", "testserver"],
    )
    def test_onboarding_complete_uses_public_mqtt_broker_not_request_host(self):
        response = self.client.get(
            reverse("web_team:onboarding:complete", args=[self.team.slug]),
            HTTP_HOST="app.novenaplatform.com",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "mqtts://mqtt.novenaplatform.com:8883")
        self.assertNotContains(response, "mqtt://app.novenaplatform.com")
