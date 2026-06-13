import pytest
from unittest.mock import patch, MagicMock
import json
from apps.teams.models import Team
from apps.devices.models import Site, Gateway, Device
from apps.telemetry.models import TelemetryData
from apps.telemetry.tasks import flush_telemetry_buffer_task


@pytest.mark.django_db
def test_flush_telemetry_buffer_task():
    # 1. Create a Team, Site, Gateway, Device
    team = Team.objects.create(name="Telemetry Team", slug="telemetry-team")
    site = Site.objects.create(team=team, name="Telemetry Site")
    gateway = Gateway.objects.create(
        team=team,
        site=site,
        name="Telemetry Gateway",
        serial_number="GW-001",
        access_token="tok_123"
    )
    device = Device.objects.create(
        team=team,
        site=site,
        gateway=gateway,
        name="Test Device",
        device_type="plc",
        protocol="modbus_tcp",
        status="online"
    )

    # 2. Prepare mock raw MQTT payload in Format A
    payload = {
        "serial_number": "GW-001",
        "values": {
            "device_name": "Test Device",
            "active_power": 123.4
        }
    }
    raw_payload = json.dumps(payload).encode("utf-8")

    # Mock Redis client and its pipeline
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value.__enter__.return_value = mock_pipeline

    # pipe.execute() returns [ [list_of_payloads], delete_result ]
    mock_pipeline.execute.return_value = [[raw_payload], 1]

    with patch("redis.Redis.from_url", return_value=mock_redis):
        # 3. Call task
        result = flush_telemetry_buffer_task()

    # 4. Asserts
    assert TelemetryData.objects.filter(device=device, key="active_power").exists()
    data = TelemetryData.objects.get(device=device, key="active_power")
    assert data.value_numeric == 123.4


@pytest.mark.django_db
def test_device_telemetry_history_api_retention_limit():
    from django.test import RequestFactory
    from apps.telemetry.views import device_telemetry_history_api, get_retention_limit_days

    # 1. Create a Team (unsubscribed)
    team = Team.objects.create(name="Telemetry Team", slug="telemetry-team")
    site = Site.objects.create(team=team, name="Telemetry Site")
    device = Device.objects.create(
        team=team,
        site=site,
        name="Test Device",
        device_type="plc",
        protocol="modbus_tcp",
        status="online"
    )

    # Unsubscribed team gets 7 days retention limit by default
    assert get_retention_limit_days(team) == 7

    # 2. Test dynamic cap
    from apps.users.models import CustomUser
    user = CustomUser.objects.create_user(
        username="test_telemetry_user",
        email="test@telemetry.com",
        password="password123"
    )

    factory = RequestFactory()
    # Request 30 days (720 hours) which exceeds the Starter 7-day limit (168 hours)
    request = factory.get(f"/a/{team.slug}/telemetry/api/history/{device.id}/?key=active_power&hours=720")
    request.team = team
    request.user = user

    # Call view
    response = device_telemetry_history_api(request, team_slug=team.slug, device_id=device.id)
    assert response.status_code == 200

