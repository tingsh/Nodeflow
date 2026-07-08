from unittest.mock import patch

from django.test import TestCase

from apps.devices.models import Device, Gateway, GatewayInventory, Site
from apps.devices.services import GatewayClaimError, claim_gateway_for_team, compute_claim_code
from apps.subscriptions.enforcement import (
    can_add_device,
    can_add_gateway,
    get_device_limit_for_team,
    get_gateway_limit_for_team,
    get_latency_limit_for_team,
    get_retention_limit_days_for_team,
)
from apps.subscriptions.metadata import ACTIVE_PRODUCTS
from apps.subscriptions.tests.utils import create_subscription_for_team
from apps.teams.models import Team


class SubscriptionEnforcementTests(TestCase):
    def setUp(self):
        self.team = Team.objects.create(name="Acme", slug="acme")
        self.site = Site.objects.create(team=self.team, name="Factory")

    def test_unsubscribed_team_uses_default_limits(self):
        self.assertEqual(get_device_limit_for_team(self.team), 3)
        self.assertEqual(get_gateway_limit_for_team(self.team), 1)
        self.assertEqual(get_retention_limit_days_for_team(self.team), 7)
        self.assertEqual(get_latency_limit_for_team(self.team), 10.0)

    def test_business_limits_come_from_product_metadata(self):
        business = next(product for product in ACTIVE_PRODUCTS if product.slug == "business")
        create_subscription_for_team(self.team, business)

        self.assertEqual(get_device_limit_for_team(self.team), business.device_limit)
        self.assertEqual(get_gateway_limit_for_team(self.team), business.gateway_limit)
        self.assertEqual(get_retention_limit_days_for_team(self.team), business.retention_days)
        self.assertEqual(get_latency_limit_for_team(self.team), business.telemetry_interval_seconds)

    def test_device_and_gateway_capacity_checks_use_metadata_limits(self):
        starter = next(product for product in ACTIVE_PRODUCTS if product.slug == "starter")
        create_subscription_for_team(self.team, starter)

        gateway = Gateway.objects.create(
            team=self.team,
            site=self.site,
            name="Gateway 1",
            serial_number="GW-001",
            access_token="token-001",
        )
        self.assertFalse(can_add_gateway(self.team))

        for index in range(starter.device_limit):
            Device.objects.create(
                team=self.team,
                site=self.site,
                gateway=gateway,
                name=f"Device {index + 1}",
                device_type="power_meter",
                protocol="modbus_tcp",
            )

        self.assertFalse(can_add_device(self.team))

    @patch("apps.devices.mqtt_provisioning.provision_gateway_mqtt")
    def test_gateway_claim_blocks_when_plan_limit_is_reached(self, mock_provision):
        starter = next(product for product in ACTIVE_PRODUCTS if product.slug == "starter")
        create_subscription_for_team(self.team, starter)
        serial_one = "GW-CLAIM-001"
        serial_two = "GW-CLAIM-002"
        GatewayInventory.objects.create(serial_number=serial_one)
        GatewayInventory.objects.create(serial_number=serial_two)

        claim_gateway_for_team(
            self.team,
            self.site,
            "Gateway 1",
            serial_one,
            compute_claim_code(serial_one),
        )

        with self.assertRaisesMessage(GatewayClaimError, "current plan supports up to 1 gateway"):
            claim_gateway_for_team(
                self.team,
                self.site,
                "Gateway 2",
                serial_two,
                compute_claim_code(serial_two),
            )
