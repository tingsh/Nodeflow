from django.test import SimpleTestCase
from django.urls import resolve, reverse


class NavigationUrlContractTests(SimpleTestCase):
    """Keep the primary navigation URL names stable without live database state."""

    ROUTES = (
        ("web:home", (), "web:home"),
        ("web_team:onboarding:setup_start", ("example-team",), "web_team:onboarding:setup_start"),
        ("web_team:devices:site_list", ("example-team",), "web_team:devices:site_list"),
        ("web_team:devices:device_list", ("example-team",), "web_team:devices:device_list"),
        ("web_team:devices:gateway_list", ("example-team",), "web_team:devices:gateway_list"),
        ("web_team:alerts:alert_list", ("example-team",), "web_team:alerts:alert_list"),
        ("web_team:dashboard_team:list", ("example-team",), "web_team:dashboard_team:list"),
        ("web_team:maintenance:ticket_list", ("example-team",), "web_team:maintenance:ticket_list"),
        ("web_team:automations:list", ("example-team",), "web_team:automations:list"),
    )

    def test_primary_navigation_names_reverse_and_resolve(self):
        for route_name, args, expected_view_name in self.ROUTES:
            with self.subTest(route_name=route_name):
                path = reverse(route_name, args=args)
                self.assertEqual(resolve(path).view_name, expected_view_name)
