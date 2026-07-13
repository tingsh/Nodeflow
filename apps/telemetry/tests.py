import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from django.http import Http404
from django.test import RequestFactory
from django.utils import timezone

from apps.devices.models import Device, DeviceTemplate, Gateway, GatewayConfig, Site
from apps.teams.models import Team
from apps.telemetry.management.commands.mqtt_consumer import Command as MqttConsumerCommand
from apps.telemetry.models import TelemetryData
from apps.telemetry.tasks import flush_telemetry_buffer_task
from apps.users.models import CustomUser


@pytest.mark.django_db
def test_gateway_attribute_ingest_persists_edge_diagnostics():
    team = Team.objects.create(name="Gateway Diagnostics", slug="gateway-diagnostics")
    site = Site.objects.create(team=team, name="Factory")
    gateway = Gateway.objects.create(
        team=team,
        site=site,
        name="GW-DIAG",
        serial_number="GW-DIAG-001",
        access_token="diag-token",
    )
    config_record = GatewayConfig.objects.create(
        team=team,
        gateway=gateway,
        config_json={"connectors": []},
        request_id="11111111-1111-1111-1111-111111111111",
    )

    command = MqttConsumerCommand()
    command._handle_attributes({
        "serial_number": "GW-DIAG-001",
        "attributes": {
            "status": "online",
            "internet_reachable": False,
            "dns_ok": True,
            "broker_tcp_ok": False,
            "broker_tcp_error": "timed out",
            "tls_ok": False,
            "mqtt_connected": False,
            "mqtt_last_error": "unexpected_disconnect_rc_7",
            "device_health": {"Power Meter 1": {"poll_status": "degraded"}},
            "ota_status": "rolled_back",
            "ota_version": "1.2.0",
            "ota_error": "health check failed",
            "ota_rollback_performed": True,
            "config_update_request_id": str(config_record.request_id),
            "config_update_status": "rolled_back",
            "config_update_error": "Broken Modbus",
            "rollback_performed": True,
            "connector_results": [{"name": "Broken Modbus", "status": "error"}],
        },
    })

    gateway.refresh_from_db()
    config_record.refresh_from_db()

    assert gateway.internet_reachable is False
    assert gateway.dns_ok is True
    assert gateway.broker_tcp_ok is False
    assert gateway.broker_tcp_error == "timed out"
    assert gateway.device_health["Power Meter 1"]["poll_status"] == "degraded"
    assert gateway.ota_status == "rolled_back"
    assert gateway.ota_rollback_performed is True
    assert config_record.status == "rolled_back"
    assert config_record.rollback_performed is True
    assert config_record.connector_results[0]["name"] == "Broken Modbus"


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
        flush_telemetry_buffer_task()

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



def _sample_request(user, limit="20"):
    request = RequestFactory().get(f"/telemetry/samples/?limit={limit}")
    request.user = user
    return request


@pytest.mark.django_db
def test_device_telemetry_samples_api_groups_template_columns():
    from apps.telemetry.views import device_telemetry_samples_api

    user = CustomUser.objects.create_user(
        username="samples_user",
        email="samples@example.com",
        password="password123",
    )
    team = Team.objects.create(name="Samples Team", slug="samples-team")
    site = Site.objects.create(team=team, name="Samples Site")
    template = DeviceTemplate.objects.create(
        name="Power Meter Template",
        device_type="power_meter",
        protocol="modbus_tcp",
        register_map={
            "current": {"label": "Current", "unit": "A"},
            "voltage": {"label": "Voltage", "unit": "V"},
            "active_power": {"label": "Active Power", "unit": "W"},
            "run_command": {"label": "Run Command", "unit": "", "writable": True},
        },
    )
    device = Device.objects.create(
        team=team,
        site=site,
        template=template,
        name="Power Meter 1",
        device_type="power_meter",
        protocol="modbus_tcp",
        status="online",
    )

    older = timezone.now() - timezone.timedelta(seconds=5)
    newer = timezone.now()
    TelemetryData.objects.bulk_create([
        TelemetryData(device=device, timestamp=older, key="current", value_numeric=1.5),
        TelemetryData(device=device, timestamp=older, key="voltage", value_numeric=240.0),
        TelemetryData(device=device, timestamp=older, key="active_power", value_numeric=300.0),
        TelemetryData(device=device, timestamp=newer, key="current", value_numeric=2.2),
        TelemetryData(device=device, timestamp=newer, key="voltage", value_numeric=235.0),
        TelemetryData(device=device, timestamp=newer, key="active_power", value_numeric=295.0),
        TelemetryData(device=device, timestamp=newer, key="run_command", value_numeric=1.0),
    ])

    response = device_telemetry_samples_api(_sample_request(user), team.slug, device.id)
    data = json.loads(response.content)

    assert response.status_code == 200
    assert data["limit"] == 20
    assert data["columns"] == [
        {"key": "current", "label": "Current", "unit": "A"},
        {"key": "voltage", "label": "Voltage", "unit": "V"},
        {"key": "active_power", "label": "Active Power", "unit": "W"},
    ]
    assert len(data["rows"]) == 2
    assert data["rows"][0]["timestamp"] == newer.isoformat()
    assert data["rows"][0]["timestamp_local"]
    assert data["timezone"] == "Asia/Singapore"
    assert data["rows"][0]["values"] == {"current": 2.2, "voltage": 235.0, "active_power": 295.0}
    assert "run_command" not in data["rows"][0]["values"]


@pytest.mark.django_db
def test_device_telemetry_samples_api_discovers_keys_and_clamps_limit():
    from apps.telemetry.views import device_telemetry_samples_api

    user = CustomUser.objects.create_user(
        username="manual_samples_user",
        email="manual-samples@example.com",
        password="password123",
    )
    team = Team.objects.create(name="Manual Samples Team", slug="manual-samples-team")
    site = Site.objects.create(team=team, name="Manual Site")
    device = Device.objects.create(
        team=team,
        site=site,
        name="Manual Meter",
        device_type="power_meter",
        protocol="modbus_tcp",
        status="online",
    )
    timestamp = timezone.now()
    TelemetryData.objects.bulk_create([
        TelemetryData(device=device, timestamp=timestamp, key="temperature", value_numeric=28.0),
        TelemetryData(device=device, timestamp=timestamp, key="humidity", value_numeric=70.0),
    ])

    response = device_telemetry_samples_api(_sample_request(user, limit="999"), team.slug, device.id)
    data = json.loads(response.content)

    assert response.status_code == 200
    assert data["limit"] == 50
    assert data["columns"] == [
        {"key": "humidity", "label": "Humidity", "unit": ""},
        {"key": "temperature", "label": "Temperature", "unit": ""},
    ]
    assert data["rows"][0]["values"] == {"humidity": 70.0, "temperature": 28.0}


@pytest.mark.django_db
def test_device_telemetry_samples_api_rejects_wrong_team_slug():
    from apps.telemetry.views import device_telemetry_samples_api

    user = CustomUser.objects.create_user(
        username="wrong_team_samples_user",
        email="wrong-team-samples@example.com",
        password="password123",
    )
    team = Team.objects.create(name="Right Team", slug="right-team")
    other_team = Team.objects.create(name="Other Team", slug="other-team")
    site = Site.objects.create(team=team, name="Right Site")
    device = Device.objects.create(
        team=team,
        site=site,
        name="Protected Meter",
        device_type="power_meter",
        protocol="modbus_tcp",
    )

    with pytest.raises(Http404):
        device_telemetry_samples_api(_sample_request(user), other_team.slug, device.id)


@pytest.mark.django_db
def test_telemetry_history_api_returns_utc_and_site_local_labels():
    from apps.telemetry.views import device_telemetry_history_api

    user = CustomUser.objects.create_user(
        username="history_tz_user",
        email="history-tz@example.com",
        password="password123",
    )
    team = Team.objects.create(name="History TZ Team", slug="history-tz-team")
    site = Site.objects.create(team=team, name="Jakarta Site", timezone="Asia/Jakarta")
    device = Device.objects.create(
        team=team,
        site=site,
        name="Jakarta Meter",
        device_type="power_meter",
        protocol="modbus_tcp",
        status="online",
    )
    timestamp = datetime(2026, 7, 13, 2, 42, 25, tzinfo=UTC)
    TelemetryData.objects.create(device=device, timestamp=timestamp, key="temperature", value_numeric=28.0)

    request = RequestFactory().get(f"/a/{team.slug}/telemetry/api/history/{device.id}/?key=temperature&hours=24")
    request.user = user
    request.team = team
    response = device_telemetry_history_api(request, team.slug, device.id)
    data = json.loads(response.content)

    assert response.status_code == 200
    assert data["labels"] == [timestamp.isoformat()]
    assert data["labels_local"] == ["09:42:25"]
    assert data["timezone"] == "Asia/Jakarta"


@pytest.mark.django_db
def test_telemetry_csv_export_uses_site_local_timestamp():
    from apps.telemetry.views import export_telemetry_csv

    user = CustomUser.objects.create_user(
        username="csv_tz_user",
        email="csv-tz@example.com",
        password="password123",
    )
    team = Team.objects.create(name="CSV TZ Team", slug="csv-tz-team")
    site = Site.objects.create(team=team, name="Tokyo Site", timezone="Asia/Tokyo")
    device = Device.objects.create(
        team=team,
        site=site,
        name="Tokyo Meter",
        device_type="power_meter",
        protocol="modbus_tcp",
        status="online",
    )
    TelemetryData.objects.create(
        device=device,
        timestamp=datetime(2026, 7, 13, 2, 42, 25, tzinfo=UTC),
        key="temperature",
        value_numeric=28.0,
    )

    request = RequestFactory().get(f"/a/{team.slug}/telemetry/api/export/{device.id}/?days=7")
    request.user = user
    request.team = team
    response = export_telemetry_csv(request, team.slug, device.id)

    assert response.status_code == 200
    assert "2026-07-13 11:42:25 JST" in response.content.decode()


@pytest.mark.django_db
def test_same_utc_telemetry_displays_different_site_local_times():
    from apps.telemetry.views import device_telemetry_history_api

    user = CustomUser.objects.create_user(
        username="multi_site_tz_user",
        email="multi-site-tz@example.com",
        password="password123",
    )
    team = Team.objects.create(name="Multi Site TZ Team", slug="multi-site-tz-team")
    singapore_site = Site.objects.create(team=team, name="Singapore Site", timezone="Asia/Singapore")
    auckland_site = Site.objects.create(team=team, name="Auckland Site", timezone="Pacific/Auckland")
    instant = datetime(2026, 7, 13, 2, 42, 25, tzinfo=UTC)
    devices = [
        Device.objects.create(
            team=team,
            site=singapore_site,
            name="Singapore Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
            status="online",
        ),
        Device.objects.create(
            team=team,
            site=auckland_site,
            name="Auckland Meter",
            device_type="power_meter",
            protocol="modbus_tcp",
            status="online",
        ),
    ]
    for device in devices:
        TelemetryData.objects.create(device=device, timestamp=instant, key="temperature", value_numeric=28.0)

    local_labels = []
    for device in devices:
        request = RequestFactory().get(f"/a/{team.slug}/telemetry/api/history/{device.id}/?key=temperature&hours=24")
        request.user = user
        request.team = team
        response = device_telemetry_history_api(request, team.slug, device.id)
        local_labels.append(json.loads(response.content)["labels_local"][0])

    assert local_labels == ["10:42:25", "14:42:25"]


@pytest.mark.django_db
def test_flush_telemetry_matches_device_id_before_name():
    team = Team.objects.create(name='Match Team', slug='match-team')
    site = Site.objects.create(team=team, name='Match Site')
    gateway = Gateway.objects.create(
        team=team,
        site=site,
        name='Match Gateway',
        serial_number='GW-MATCH-001',
        access_token='tok_match_001',
    )
    device_by_id = Device.objects.create(
        team=team,
        site=site,
        gateway=gateway,
        name='ID Device',
        device_type='power_meter',
        protocol='modbus_tcp',
        status='offline',
    )
    device_by_name = Device.objects.create(
        team=team,
        site=site,
        gateway=gateway,
        name='Name Device',
        device_type='power_meter',
        protocol='modbus_tcp',
        status='offline',
    )
    payload = {
        'serial_number': gateway.serial_number,
        'device_id': device_by_id.id,
        'device_name': device_by_name.name,
        'values': {'active_power': 111.0},
    }
    raw_payload = json.dumps(payload).encode('utf-8')
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value.__enter__.return_value = mock_pipeline
    mock_pipeline.execute.return_value = [[raw_payload], 1]

    with patch('redis.Redis.from_url', return_value=mock_redis):
        flush_telemetry_buffer_task()

    assert TelemetryData.objects.filter(device=device_by_id, key='active_power').exists()
    assert not TelemetryData.objects.filter(device=device_by_name, key='active_power').exists()
    device_by_id.refresh_from_db()
    assert device_by_id.status == 'online'


@pytest.mark.django_db
def test_flush_telemetry_logs_legacy_first_device_fallback(caplog):
    team = Team.objects.create(name='Fallback Team', slug='fallback-team')
    site = Site.objects.create(team=team, name='Fallback Site')
    gateway = Gateway.objects.create(
        team=team,
        site=site,
        name='Fallback Gateway',
        serial_number='GW-FALLBACK-001',
        access_token='tok_fallback_001',
    )
    device = Device.objects.create(
        team=team,
        site=site,
        gateway=gateway,
        name='Only Device',
        device_type='power_meter',
        protocol='modbus_tcp',
        status='offline',
    )
    payload = {
        'serial_number': gateway.serial_number,
        'values': {'active_power': 222.0},
    }
    raw_payload = json.dumps(payload).encode('utf-8')
    mock_redis = MagicMock()
    mock_pipeline = MagicMock()
    mock_redis.pipeline.return_value.__enter__.return_value = mock_pipeline
    mock_pipeline.execute.return_value = [[raw_payload], 1]

    with patch('redis.Redis.from_url', return_value=mock_redis), caplog.at_level('WARNING', logger='novena_hub'):
        flush_telemetry_buffer_task()

    assert TelemetryData.objects.filter(device=device, key='active_power').exists()
    assert 'legacy first-device telemetry fallback' in caplog.text
