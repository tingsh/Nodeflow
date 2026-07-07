import csv
import io

from django.core.management import call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

import pytest

from apps.alerts.models import Alert
from apps.devices.management.commands.pilot_readiness_audit import AUDIT_USER_EMAIL, SCENARIOS
from apps.devices.models import Device, Gateway, GatewayInventory, Site
from apps.maintenance.models import MaintenanceTicket, PreventiveSchedule, SharedTicketLink
from apps.teams.models import Team
from apps.telemetry.models import TelemetryData
from apps.users.models import CustomUser


@pytest.mark.django_db
def test_pilot_readiness_prepare_creates_audit_tenants_and_inventory():
    call_command("pilot_readiness_audit", "prepare")

    assert CustomUser.objects.filter(email=AUDIT_USER_EMAIL).exists()
    for scenario in SCENARIOS:
        assert Team.objects.filter(slug=scenario.team_slug).exists()
        assert GatewayInventory.objects.filter(serial_number=scenario.sim_serial).exists()
        assert GatewayInventory.objects.filter(serial_number=scenario.replay_serial).exists()


@pytest.mark.django_db
def test_pilot_readiness_simulate_creates_live_customer_journey_data():
    call_command("pilot_readiness_audit", "simulate")

    for scenario in SCENARIOS:
        team = Team.objects.get(slug=scenario.team_slug)
        assert Site.objects.filter(team=team).exists()
        assert Gateway.objects.filter(team=team, status="online").exists()
        assert Device.objects.filter(team=team, status="online").exists()
        assert TelemetryData.objects.filter(device__team=team).exists()
        assert Alert.objects.filter(team=team).exists()
        assert MaintenanceTicket.objects.filter(team=team).exists()
        assert SharedTicketLink.objects.filter(team=team).exists()

    facilities = Team.objects.get(slug="pilot-facilities")
    assert Site.objects.filter(team=facilities).count() >= 2
    assert PreventiveSchedule.objects.filter(team=facilities, is_active=True).exists()


@pytest.mark.django_db
def test_pilot_readiness_keepalive_refreshes_only_simulation_freshness_without_duplicates():
    call_command("pilot_readiness_audit", "simulate")

    ticket_count = MaintenanceTicket.objects.count()
    alert_count = Alert.objects.count()
    shared_link_count = SharedTicketLink.objects.count()
    old_timestamp = timezone.now() - timezone.timedelta(minutes=10)

    Gateway.objects.filter(serial_number__in=[scenario.sim_serial for scenario in SCENARIOS]).update(
        status="offline",
        last_seen=old_timestamp,
    )
    Device.objects.filter(team__slug__in=[scenario.team_slug for scenario in SCENARIOS]).update(
        status="offline",
        last_telemetry_at=old_timestamp,
    )

    call_command("pilot_readiness_audit", "keepalive", "--once")

    for scenario in SCENARIOS:
        gateway = Gateway.objects.get(serial_number=scenario.sim_serial)
        assert gateway.status == "online"
        assert gateway.freshness.status == "live"
        for device in Device.objects.filter(team__slug=scenario.team_slug):
            assert device.status == "online"
            assert device.freshness.status == "live"

    assert MaintenanceTicket.objects.count() == ticket_count
    assert Alert.objects.count() == alert_count
    assert SharedTicketLink.objects.count() == shared_link_count


@pytest.mark.django_db
def test_pilot_readiness_snapshot_prints_freshness_labels():
    call_command("pilot_readiness_audit", "simulate")

    output = io.StringIO()
    call_command("pilot_readiness_audit", "snapshot", stdout=output)

    text = output.getvalue()
    assert "Gateway NOV-AUDIT-COLD-SIM:" in text
    assert "Device Cold Room Temperature Sensor:" in text


@pytest.mark.django_db
def test_existing_team_onboarding_start_redirects_to_setup_flow():
    call_command("pilot_readiness_audit", "simulate")
    user = CustomUser.objects.get(email=AUDIT_USER_EMAIL)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("web_team:onboarding:start", args=["pilot-cold-room"]))

    assert response.status_code == 302
    assert response.url == reverse("web_team:onboarding:setup_start", args=["pilot-cold-room"])


@pytest.mark.django_db
def test_alert_list_includes_threshold_unit_ticket_and_next_action():
    call_command("pilot_readiness_audit", "simulate")
    user = CustomUser.objects.get(email=AUDIT_USER_EMAIL)
    client = Client()
    client.force_login(user)

    response = client.get(reverse("web_team:alerts:alert_list", args=["pilot-cold-room"]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Rule: Temperature above 4" in content
    assert "8.6 degC" in content
    assert "Open TKT-" in content
    assert "confirm the device reading" in content


@pytest.mark.django_db
def test_factory_telemetry_csv_export_includes_labels_units_and_raw_keys():
    call_command("pilot_readiness_audit", "simulate")
    user = CustomUser.objects.get(email=AUDIT_USER_EMAIL)
    device = Device.objects.get(team__slug="pilot-factory-energy", name="Main Incomer Power Meter")
    client = Client()
    client.force_login(user)

    response = client.get(reverse("web_team:telemetry:export_telemetry_csv", args=["pilot-factory-energy", device.id]))

    rows = list(csv.reader(io.StringIO(response.content.decode())))
    assert response.status_code == 200
    assert rows[0] == ["Timestamp", "Metric", "Key", "Value", "Unit"]
    assert any(row[1:] == ["Active Power", "active_power", "820.0", "W"] for row in rows[1:])


@pytest.mark.django_db
def test_public_contractor_link_is_ticket_scoped_without_marketing_navigation():
    call_command("pilot_readiness_audit", "simulate")
    link = SharedTicketLink.objects.get(team__slug="pilot-facilities")
    client = Client()

    response = client.get(reverse("maintenance_public:public_ticket_view", args=[str(link.token)]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Guest Compliance Portal" in content
    assert "Submit Activity Log" in content
    assert "Sign In" not in content
    assert "Get Started" not in content
    assert "/None" not in content


@pytest.mark.django_db
def test_gateway_command_history_avoids_visible_software_rpc_term():
    call_command("pilot_readiness_audit", "simulate")
    user = CustomUser.objects.get(email=AUDIT_USER_EMAIL)
    gateway = Gateway.objects.get(serial_number="NOV-AUDIT-FACTORY-SIM")
    client = Client()
    client.force_login(user)

    response = client.get(reverse("web_team:devices:gateway_rpc_history", args=["pilot-factory-energy", gateway.id]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Remote Command History" in content
    assert "Settings" in content
    assert "RPC" not in content
