import io
import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

from apps.devices.first_customer_journey import (
    CREATED_BY,
    FAILURE_RETENTION,
    FirstCustomerJourneyError,
    FirstCustomerJourneyRunner,
    cleanup_owned_runs,
    cleanup_test_run,
    count_test_run_records,
    discover_owned_run_ids,
    validate_sample_count,
)
from apps.devices.models import Device, GatewayInventory, Site
from apps.teams.helpers import create_default_team_for_user
from apps.teams.models import Team
from apps.users.models import CustomUser

RUN_ID = "fcj_20260818T010203Z_a1b2c3"


@pytest.mark.django_db
@override_settings(NOVENA_DEPLOYMENT_MODE="test")
def test_service_journey_proves_customer_state_then_removes_success_data():
    runner = FirstCustomerJourneyRunner(
        test_run_id=RUN_ID,
        ingestion_mode="service",
        sample_count=10,
        timeout_seconds=5,
    )

    with patch("apps.devices.first_customer_journey._remove_queued_run_payloads", return_value=0):
        result = runner.run()

    assert result["status"] == "passed"
    assert result["samples"] == 10
    assert result["telemetry_points"] == 20
    assert result["assertions"] == [
        "claimed_gateway_identity",
        "gateway_and_device_live",
        "telemetry_persisted",
        "samples_api_readback",
        "device_dashboard_widgets",
        "command_center_summary",
    ]
    assert result["cleanup"]["telemetry"] == 20
    assert not any(count_test_run_records(RUN_ID).values())


@pytest.mark.django_db
def test_setup_marks_owned_records_and_mqtt_uses_gateway_topics_and_payload_contract():
    runner = FirstCustomerJourneyRunner(test_run_id=RUN_ID, ingestion_mode="mqtt", sample_count=10)
    runner.resources = runner._setup()
    published = []

    class PublishResult:
        rc = 0

        def wait_for_publish(self, timeout):
            assert timeout > 0

        def is_published(self):
            return True

    class MqttClient:
        def publish(self, topic, payload, qos):
            published.append((topic, json.loads(payload), qos))
            return PublishResult()

    runner._mqtt_client = MqttClient()
    try:
        samples = runner._send_samples()

        site = Site.objects.get(pk=runner.resources.site_id)
        device = Device.objects.get(pk=runner.resources.device_id)
        inventory = GatewayInventory.objects.get(pk=runner.resources.inventory_id)
        inventory_marker = json.loads(inventory.notes)
        for marker in (site.metadata, device.metadata, inventory_marker):
            assert marker["test_run_id"] == RUN_ID
            assert marker["created_by"] == CREATED_BY
            assert marker["expires_at"]

        assert len(published) == 11
        attributes_topic, heartbeat, attributes_qos = published[0]
        assert attributes_topic == f"v1/gateway/{runner.names.gateway_serial}/attributes"
        assert heartbeat["serial_number"] == runner.names.gateway_serial
        assert attributes_qos == 1

        for topic, payload, qos in published[1:]:
            assert topic == f"v1/gateway/{runner.names.gateway_serial}/telemetry"
            assert qos == 1
            assert payload["serial_number"] == runner.names.gateway_serial
            assert payload["device_id"] == str(runner.resources.device_id)
            assert set(payload["values"]) == {"device_name", "temperature", "humidity"}
        assert len({payload["ts"] for _topic, payload, _qos in published[1:]}) == 10
        assert len(samples) == 10
    finally:
        runner._mqtt_client = None
        with patch("apps.devices.first_customer_journey._remove_queued_run_payloads", return_value=0):
            cleanup_test_run(RUN_ID)


@pytest.mark.django_db
@override_settings(NOVENA_DEPLOYMENT_MODE="test")
def test_failed_assertion_retains_marked_data_for_debugging_and_cleanup_is_idempotent():
    runner = FirstCustomerJourneyRunner(
        test_run_id=RUN_ID,
        ingestion_mode="service",
        sample_count=10,
        timeout_seconds=5,
    )

    with (
        patch.object(runner, "_assert_customer_visible_state", side_effect=AssertionError("forced failure")),
        pytest.raises(FirstCustomerJourneyError) as exc_info,
    ):
        runner.run()

    error = exc_info.value
    assert error.test_run_id == RUN_ID
    assert error.stage == "customer_visible_assertions"
    assert error.preserved is True
    site = Site.objects.get(metadata__test_run_id=RUN_ID)
    device = Device.objects.get(metadata__test_run_id=RUN_ID)
    for metadata in (site.metadata, device.metadata):
        assert metadata["created_by"] == CREATED_BY
        assert metadata["status"] == "failed"
        assert metadata["failure_stage"] == "customer_visible_assertions"
        assert timezone.datetime.fromisoformat(metadata["expires_at"]) > timezone.now()

    with patch("apps.devices.first_customer_journey._remove_queued_run_payloads", return_value=0):
        first_cleanup = cleanup_test_run(RUN_ID)
        second_cleanup = cleanup_test_run(RUN_ID)

    assert first_cleanup["telemetry"] == 20
    assert not any(second_cleanup.values())
    assert not any(count_test_run_records(RUN_ID).values())


@pytest.mark.django_db
def test_created_by_cleanup_is_exact_scoped_and_skips_unexpired_runs_by_default():
    unrelated_user = CustomUser.objects.create_user(
        username="ordinary@example.com",
        email="ordinary@example.com",
        password="not-used",
    )
    unrelated_team = create_default_team_for_user(unrelated_user, "Ordinary Customer")
    runner = FirstCustomerJourneyRunner(test_run_id=RUN_ID, ingestion_mode="service")
    runner.resources = runner._setup()

    try:
        assert discover_owned_run_ids(created_by=CREATED_BY) == []
        assert discover_owned_run_ids(created_by=CREATED_BY, include_unexpired=True) == [RUN_ID]
        with pytest.raises(ValueError, match="created_by must be exactly"):
            cleanup_owned_runs(created_by="test", include_unexpired=True)

        expired_at = timezone.now() - timedelta(seconds=1)
        for model, record_id in (
            (Site, runner.resources.site_id),
            (Device, runner.resources.device_id),
        ):
            record = model.objects.get(pk=record_id)
            record.metadata = {**record.metadata, "expires_at": expired_at.isoformat()}
            record.save(update_fields=["metadata", "updated_at"])
        inventory = GatewayInventory.objects.get(pk=runner.resources.inventory_id)
        inventory_marker = json.loads(inventory.notes)
        inventory.notes = json.dumps({**inventory_marker, "expires_at": expired_at.isoformat()}, sort_keys=True)
        inventory.save(update_fields=["notes"])
        ownership_created_at = expired_at - FAILURE_RETENTION
        Team.objects.filter(pk=runner.resources.team_id).update(created_at=ownership_created_at)
        CustomUser.objects.filter(pk=runner.resources.user_id).update(date_joined=ownership_created_at)
        assert discover_owned_run_ids(created_by=CREATED_BY) == [RUN_ID]

        with patch("apps.devices.first_customer_journey._remove_queued_run_payloads", return_value=0):
            result = cleanup_owned_runs(created_by=CREATED_BY)

        assert result["run_ids"] == [RUN_ID]
        assert Team.objects.filter(pk=unrelated_team.pk).exists()
        assert CustomUser.objects.filter(pk=unrelated_user.pk).exists()
        assert not any(count_test_run_records(RUN_ID).values())
    finally:
        with patch("apps.devices.first_customer_journey._remove_queued_run_payloads", return_value=0):
            cleanup_test_run(RUN_ID)


@pytest.mark.parametrize("sample_count", [9, 101])
def test_sample_count_is_bounded(sample_count):
    with pytest.raises(ValueError, match="between 10 and 100"):
        validate_sample_count(sample_count)


@pytest.mark.django_db
@override_settings(NOVENA_DEPLOYMENT_MODE="production")
def test_command_refuses_production_run_and_cleanup():
    for arguments in (
        ("run", "--ingestion-mode", "service"),
        ("cleanup", "--test-run-id", RUN_ID),
    ):
        with pytest.raises(CommandError, match="disabled for NOVENA_DEPLOYMENT_MODE='production'"):
            call_command("first_customer_journey", *arguments, stdout=io.StringIO(), stderr=io.StringIO())
