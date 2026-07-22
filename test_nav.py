import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "novena_hub.settings")
django.setup()

from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402

from apps.teams.models import Team  # noqa: E402
from apps.users.models import CustomUser  # noqa: E402


def run_tests():
    try:
        user = CustomUser.objects.first()
        if not user:
            print("No users found.")
            return

        team = Team.objects.first()
        if not team:
            print("No teams found.")
            return

        print(f"Testing as User: {user.email}, Team: {team.name} ({team.slug})")

        client = Client()
        client.force_login(user)

        urls_to_test = [
            ("Dashboard", reverse("web:home")),
            ("Setup", reverse("web_team:onboarding:setup_start", args=[team.slug])),
            ("Sites", reverse("web_team:devices:site_list", args=[team.slug])),
            ("Devices", reverse("web_team:devices:device_list", args=[team.slug])),
            ("Gateways", reverse("web_team:devices:gateway_list", args=[team.slug])),
            ("Alerts", reverse("web_team:alerts:alert_list", args=[team.slug])),
            ("Shared Links", reverse("web_team:dashboard_team:list", args=[team.slug])),
            ("Maintenance", reverse("web_team:maintenance:ticket_list", args=[team.slug])),
            ("Automations", reverse("web_team:automations:list", args=[team.slug])),
        ]

        success = True
        for name, url in urls_to_test:
            print(f"Testing {name} ({url}) ...", end=" ")
            try:
                response = client.get(url)
                if response.status_code == 200:
                    print("OK (200)")
                elif response.status_code in [301, 302]:
                    print(f"REDIRECT ({response.status_code}) to {response.url}")
                else:
                    print(f"FAIL ({response.status_code})")
                    success = False
            except Exception as e:
                print(f"ERROR: {e}")
                success = False

        if success:
            print("\nAll endpoints returned 200 OK or valid redirects!")
        else:
            print("\nSome endpoints failed.")

    except Exception as e:
        print(f"Test script error: {e}")


if __name__ == "__main__":
    run_tests()
