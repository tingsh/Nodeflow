from __future__ import annotations

import json
import re
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import paho.mqtt.client as mqtt
import redis
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.test import RequestFactory
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.dashboard.models import Dashboard, Widget
from apps.dashboard.services import build_device_dashboard_context, build_team_operations_dashboard
from apps.teams.helpers import create_default_team_for_user
from apps.teams.models import Team
from apps.telemetry.models import GatewayLog, TelemetryData
from apps.telemetry.views import device_telemetry_samples_api
from apps.users.models import CustomUser

from .models import Device, DeviceTemplate, Gateway, GatewayConfig, GatewayInventory, Site
from .services import current_claimed_gateway

CREATED_BY = "automated_first_customer_journey_test"
ALLOWED_DEPLOYMENT_MODES = frozenset({"local", "dev", "development", "test", "staging"})
RUN_ID_PATTERN = re.compile(r"^fcj_\d{8}T\d{6}Z_[0-9a-f]{6}$")
FAILURE_RETENTION = timedelta(hours=24)
DEFAULT_SAMPLE_COUNT = 10
MIN_SAMPLE_COUNT = 10
MAX_SAMPLE_COUNT = 100
DEFAULT_TIMEOUT_SECONDS = 45.0
TELEMETRY_KEYS = ("temperature", "humidity")


class FirstCustomerJourneyError(RuntimeError):
    def __init__(self, message: str, *, test_run_id: str, stage: str, preserved: bool = False):
        super().__init__(message)
        self.test_run_id = test_run_id
        self.stage = stage
        self.preserved = preserved


@dataclass(frozen=True)
class JourneyNames:
    test_run_id: str
    display_prefix: str
    user_email: str
    team_name: str
    site_name: str
    template_name: str
    gateway_name: str
    gateway_serial: str
    device_name: str


@dataclass(frozen=True)
class JourneyResources:
    test_run_id: str
    expires_at: datetime
    user_id: int
    team_id: int
    site_id: int
    template_id: int
    gateway_id: int
    inventory_id: int
    device_id: int


def generate_test_run_id(now: datetime | None = None) -> str:
    now = now or timezone.now()
    return f"fcj_{now.astimezone(UTC):%Y%m%dT%H%M%SZ}_{secrets.token_hex(3)}"


def validate_test_run_id(test_run_id: str) -> str:
    normalized = str(test_run_id or "").strip()
    if not RUN_ID_PATTERN.fullmatch(normalized):
        raise ValueError("test_run_id must match fcj_YYYYMMDDTHHMMSSZ_<6 lowercase hex characters>.")
    return normalized


def validate_sample_count(sample_count: int) -> int:
    try:
        sample_count = int(sample_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("sample_count must be an integer.") from exc
    if not MIN_SAMPLE_COUNT <= sample_count <= MAX_SAMPLE_COUNT:
        raise ValueError(f"sample_count must be between {MIN_SAMPLE_COUNT} and {MAX_SAMPLE_COUNT}.")
    return sample_count


def assert_safe_deployment_mode() -> str:
    mode = str(getattr(settings, "NOVENA_DEPLOYMENT_MODE", "") or "").strip().lower()
    if mode not in ALLOWED_DEPLOYMENT_MODES:
        allowed = ", ".join(sorted(ALLOWED_DEPLOYMENT_MODES))
        raise RuntimeError(
            f"First-customer journey actions are disabled for NOVENA_DEPLOYMENT_MODE={mode or 'unset'!r}. "
            f"Allowed non-production modes: {allowed}."
        )
    return mode


def journey_names(test_run_id: str) -> JourneyNames:
    test_run_id = validate_test_run_id(test_run_id)
    prefix = f"FCJ Test {test_run_id}"
    serial = test_run_id.upper().replace("_", "-")
    return JourneyNames(
        test_run_id=test_run_id,
        display_prefix=prefix,
        user_email=f"{test_run_id}@automated-fcj.invalid",
        team_name=f"{prefix} Customer",
        site_name=f"{prefix} Site",
        template_name=f"{prefix} Temperature Sensor",
        gateway_name=f"{prefix} Gateway",
        gateway_serial=serial,
        device_name=f"{prefix} Device",
    )


def ownership_marker(test_run_id: str, expires_at: datetime, **extra) -> dict:
    return {
        "test_run_id": validate_test_run_id(test_run_id),
        "created_by": CREATED_BY,
        "expires_at": expires_at.astimezone(UTC).isoformat(),
        **extra,
    }


def _metadata_owned_by_run(metadata, test_run_id: str) -> bool:
    return bool(
        isinstance(metadata, dict)
        and metadata.get("test_run_id") == test_run_id
        and metadata.get("created_by") == CREATED_BY
    )


def _parse_inventory_notes(notes: str) -> dict:
    try:
        parsed = json.loads(notes or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _owned_inventory_ids(test_run_id: str) -> list[int]:
    owned_ids = []
    inventories = GatewayInventory.objects.filter(
        serial_number=journey_names(test_run_id).gateway_serial,
        batch=CREATED_BY,
    ).values_list("id", "notes")
    for inventory_id, notes in inventories:
        marker = _parse_inventory_notes(notes)
        if _metadata_owned_by_run(marker, test_run_id):
            owned_ids.append(inventory_id)
    return owned_ids


def _expires_at(value) -> datetime | None:
    parsed = value if isinstance(value, datetime) else parse_datetime(str(value or ""))
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, UTC)
    return parsed


class FirstCustomerJourneyRunner:
    def __init__(
        self,
        *,
        test_run_id: str | None = None,
        ingestion_mode: str = "mqtt",
        sample_count: int = DEFAULT_SAMPLE_COUNT,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        cleanup_on_failure: bool = False,
        progress: Callable[[str], None] | None = None,
    ):
        self.test_run_id = validate_test_run_id(test_run_id or generate_test_run_id())
        self.names = journey_names(self.test_run_id)
        if ingestion_mode not in {"mqtt", "service"}:
            raise ValueError("ingestion_mode must be 'mqtt' or 'service'.")
        self.ingestion_mode = ingestion_mode
        self.sample_count = validate_sample_count(sample_count)
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self.cleanup_on_failure = bool(cleanup_on_failure)
        self.progress = progress or (lambda _message: None)
        self.resources: JourneyResources | None = None
        self._mqtt_client = None
        self._redis_client = None
        self._stage = "preflight"

    def run(self) -> dict:
        assert_safe_deployment_mode()
        started_at = timezone.now()
        expected_samples = []
        try:
            self._preflight()
            self._stage = "setup"
            self.resources = self._setup()
            self._stage = "ingestion"
            expected_samples = self._send_samples()
            self._stage = "persistence"
            self._wait_for_persistence(expected_samples)
            self._stage = "customer_visible_assertions"
            assertions = self._assert_customer_visible_state(expected_samples)
            self._stage = "success_cleanup"
            cleanup_result = cleanup_test_run(
                self.test_run_id,
                redis_client=self._redis_client,
            )
            remaining = count_test_run_records(self.test_run_id)
            if any(remaining.values()):
                raise RuntimeError(f"Success cleanup left owned records behind: {remaining}")
            return {
                "status": "passed",
                "test_run_id": self.test_run_id,
                "ingestion_mode": self.ingestion_mode,
                "samples": self.sample_count,
                "telemetry_points": self.sample_count * len(TELEMETRY_KEYS),
                "assertions": assertions,
                "cleanup": cleanup_result,
                "duration_seconds": round((timezone.now() - started_at).total_seconds(), 3),
            }
        except FirstCustomerJourneyError:
            raise
        except Exception as exc:
            preserved = bool(self.resources and self._stage not in {"setup", "success_cleanup"})
            if self.resources and (self.cleanup_on_failure or not preserved):
                cleanup_test_run(self.test_run_id, redis_client=self._redis_client)
                preserved = False
            elif self.resources and preserved:
                self._mark_failure(self._stage)
            raise FirstCustomerJourneyError(
                str(exc),
                test_run_id=self.test_run_id,
                stage=self._stage,
                preserved=preserved,
            ) from exc
        finally:
            self._disconnect_mqtt()

    def _preflight(self):
        self.progress(f"[{self.test_run_id}] preflight ({self.ingestion_mode})")
        if self.ingestion_mode != "mqtt":
            return
        self._redis_client = redis.Redis.from_url(settings.REDIS_URL)
        if not self._redis_client.ping():
            raise RuntimeError("Redis preflight did not return PONG.")
        self._mqtt_client = self._connect_mqtt()

    def _connect_mqtt(self):
        connected = threading.Event()
        connection_error = {}
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"novena-fcj-{self.test_run_id[-6:]}",
            protocol=mqtt.MQTTv311,
        )

        def on_connect(inner_client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                connected.set()
            else:
                connection_error["reason"] = str(reason_code)
                connected.set()

        client.on_connect = on_connect
        client.connect(settings.MQTT_BROKER_HOST, settings.MQTT_BROKER_PORT, keepalive=30)
        client.loop_start()
        if not connected.wait(min(10.0, self.timeout_seconds)):
            client.loop_stop()
            client.disconnect()
            raise RuntimeError("Timed out connecting to the configured MQTT broker.")
        if connection_error:
            client.loop_stop()
            client.disconnect()
            raise RuntimeError(f"MQTT broker rejected the FCJ client: {connection_error['reason']}")
        return client

    @transaction.atomic
    def _setup(self) -> JourneyResources:
        expires_at = timezone.now() + FAILURE_RETENTION
        marker = ownership_marker(self.test_run_id, expires_at)
        user = CustomUser.objects.create_user(
            username=self.names.user_email,
            email=self.names.user_email,
            password=secrets.token_urlsafe(24),
            first_name="Automated FCJ",
        )
        team = create_default_team_for_user(user, self.names.team_name)
        site = Site.objects.create(
            team=team,
            name=self.names.site_name,
            address="Automated first-customer journey; not a physical customer site.",
            timezone="Asia/Singapore",
            solution_profile="general_iot",
            metadata=ownership_marker(self.test_run_id, expires_at, simulated=True),
        )
        template = DeviceTemplate.objects.create(
            name=self.names.template_name,
            manufacturer="Novena FCJ Simulator",
            model_number=self.test_run_id,
            device_type="temp_sensor",
            protocol="mqtt",
            register_map={
                "temperature": {
                    "label": "Temperature",
                    "unit": "degC",
                    "type": "float32",
                    "dashboard_role": "trend",
                    "priority": 1,
                },
                "humidity": {
                    "label": "Humidity",
                    "unit": "%",
                    "type": "float32",
                    "dashboard_role": "secondary",
                    "priority": 2,
                },
            },
            default_polling_interval=5,
            category="cold_chain",
            source="user_created",
            created_by_team=team,
        )
        gateway = Gateway.objects.create(
            team=team,
            site=site,
            name=self.names.gateway_name,
            serial_number=self.names.gateway_serial,
            access_token=secrets.token_hex(20),
            status="offline",
            lifecycle_status="active",
            mqtt_username=self.names.gateway_serial,
            tls_mode="none",
            firmware_version="fcj-simulator",
        )
        inventory = GatewayInventory.objects.create(
            serial_number=self.names.gateway_serial,
            status="claimed",
            batch=CREATED_BY,
            gateway=gateway,
            claimed_by_team=team,
            claimed_at=timezone.now(),
            notes=json.dumps({**marker, "simulated": True}, sort_keys=True),
        )
        device = Device.objects.create(
            team=team,
            site=site,
            gateway=gateway,
            template=template,
            name=self.names.device_name,
            device_type=template.device_type,
            protocol=template.protocol,
            port=f"simulated:{self.test_run_id}",
            connection_config={"simulated": True, "source": CREATED_BY},
            metadata=ownership_marker(self.test_run_id, expires_at, simulated=True),
        )
        self.progress(f"[{self.test_run_id}] created isolated customer/site/gateway/device")
        return JourneyResources(
            test_run_id=self.test_run_id,
            expires_at=expires_at,
            user_id=user.pk,
            team_id=team.pk,
            site_id=site.pk,
            template_id=template.pk,
            gateway_id=gateway.pk,
            inventory_id=inventory.pk,
            device_id=device.pk,
        )

    def _sample_payloads(self) -> list[tuple[datetime, dict]]:
        device = Device.objects.get(pk=self.resources.device_id)
        base_ms = int((timezone.now() - timedelta(seconds=self.sample_count - 1)).timestamp() * 1000)
        samples = []
        for index in range(self.sample_count):
            timestamp_ms = base_ms + index * 1000
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=UTC)
            values = {
                "device_name": device.name,
                "temperature": round(22.0 + index * 0.1, 2),
                "humidity": round(55.0 + index * 0.2, 2),
            }
            samples.append(
                (
                    timestamp,
                    {
                        "serial_number": self.names.gateway_serial,
                        "ts": timestamp_ms,
                        "device_id": str(device.pk),
                        "device_name": device.name,
                        "values": values,
                    },
                )
            )
        return samples

    def _heartbeat_payload(self) -> dict:
        return {
            "serial_number": self.names.gateway_serial,
            "ts": int(timezone.now().timestamp() * 1000),
            "attributes": {
                "status": "online",
                "firmware_version": "fcj-simulator",
                "connected_devices": [self.names.device_name],
                "active_connectors": [{"name": "fcj-simulator", "status": "running"}],
            },
        }

    def _send_samples(self) -> list[tuple[datetime, dict]]:
        samples = self._sample_payloads()
        gateway = Gateway.objects.get(pk=self.resources.gateway_id)
        if self.ingestion_mode == "mqtt":
            self._publish_qos1(
                f"v1/gateway/{gateway.serial_number}/attributes",
                self._heartbeat_payload(),
            )
            topic = f"v1/gateway/{gateway.serial_number}/telemetry"
            for _timestamp, payload in samples:
                self._publish_qos1(topic, payload)
        else:
            from apps.telemetry.management.commands.mqtt_consumer import Command as MqttConsumerCommand
            from apps.telemetry.services import ingest_telemetry_data

            MqttConsumerCommand()._handle_attributes(self._heartbeat_payload(), gateway=gateway)
            for timestamp, payload in samples:
                ingest_telemetry_data(
                    gateway.serial_number,
                    payload["values"],
                    timestamp=timestamp,
                    device_id=payload["device_id"],
                )
        self.progress(f"[{self.test_run_id}] sent {self.sample_count} Gateway-shaped samples")
        return samples

    def _publish_qos1(self, topic: str, payload: dict):
        result = self._mqtt_client.publish(topic, json.dumps(payload), qos=1)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"MQTT publish to {topic} was rejected locally (rc={result.rc}).")
        result.wait_for_publish(timeout=min(10.0, self.timeout_seconds))
        if not result.is_published():
            raise RuntimeError(f"MQTT broker acknowledgement timed out for {topic}.")

    def _wait_for_persistence(self, expected_samples: list[tuple[datetime, dict]]):
        expected_timestamps = {timestamp for timestamp, _payload in expected_samples}
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            timestamps = set(
                TelemetryData.objects.filter(device_id=self.resources.device_id, key__in=TELEMETRY_KEYS).values_list(
                    "timestamp", flat=True
                )
            )
            gateway = Gateway.objects.get(pk=self.resources.gateway_id)
            if expected_timestamps.issubset(timestamps) and gateway.status == "online" and gateway.last_seen:
                return
            time.sleep(0.25)
        raise RuntimeError(
            "Timed out waiting for MQTT consumer/Celery persistence. "
            "Ensure mqtt_consumer, Redis, and Celery Beat are running."
        )

    def _assert_customer_visible_state(self, expected_samples: list[tuple[datetime, dict]]) -> list[str]:
        user = CustomUser.objects.get(pk=self.resources.user_id)
        team = Team.objects.get(pk=self.resources.team_id)
        gateway = Gateway.objects.get(pk=self.resources.gateway_id)
        device = Device.objects.select_related("site", "gateway", "template").get(pk=self.resources.device_id)

        claimed = current_claimed_gateway(gateway.serial_number)
        if not claimed or claimed.pk != gateway.pk:
            raise AssertionError("The test Gateway does not resolve as the current claimed Gateway.")

        expected_timestamps = {timestamp for timestamp, _payload in expected_samples}
        points = list(TelemetryData.objects.filter(device=device).order_by("timestamp", "key"))
        if len(points) != self.sample_count * len(TELEMETRY_KEYS):
            raise AssertionError(
                f"Expected {self.sample_count * len(TELEMETRY_KEYS)} telemetry points, found {len(points)}."
            )
        if {point.key for point in points} != set(TELEMETRY_KEYS):
            raise AssertionError("Persisted telemetry keys do not match the expected FCJ metrics.")
        if {point.timestamp for point in points} != expected_timestamps:
            raise AssertionError("Persisted telemetry timestamps do not match the sent FCJ samples.")

        gateway_state = gateway.freshness
        device_state = device.freshness
        if gateway_state.status != "live" or device_state.status != "live":
            raise AssertionError(
                f"Expected live Gateway/device state, got gateway={gateway_state.status} device={device_state.status}."
            )

        request = RequestFactory().get(
            f"/a/{team.slug}/telemetry/api/samples/{device.pk}/",
            {"limit": 50},
        )
        request.user = user
        request.team = team
        response = device_telemetry_samples_api(request, team.slug, device.pk)
        if response.status_code != 200:
            raise AssertionError(f"Telemetry samples API returned HTTP {response.status_code}.")
        samples_data = json.loads(response.content)
        expected_api_rows = min(self.sample_count, 50)
        if len(samples_data["rows"]) != expected_api_rows:
            raise AssertionError(
                f"Expected {expected_api_rows} customer-visible sample rows, found {len(samples_data['rows'])}."
            )
        if {column["key"] for column in samples_data["columns"]} != set(TELEMETRY_KEYS):
            raise AssertionError("Telemetry samples API columns do not match the expected FCJ metrics.")
        latest_values = samples_data["rows"][0]["values"]
        expected_latest = expected_samples[-1][1]["values"]
        for key in TELEMETRY_KEYS:
            if latest_values.get(key) != expected_latest[key]:
                raise AssertionError(f"Latest customer-visible {key} value is incorrect.")

        device_dashboard = build_device_dashboard_context(device)
        widget_keys = {widget.telemetry_key for widget in device_dashboard["widgets"]}
        if not device_dashboard["dashboard"] or widget_keys != set(TELEMETRY_KEYS):
            raise AssertionError("The generated device dashboard does not expose both FCJ metrics.")

        cache.delete(f"dashboard_{team.id}_operations_trend")
        command_center = build_team_operations_dashboard(team)
        if (
            command_center["sites_count"] != 1
            or command_center["gateways_count"] != 1
            or command_center["devices_count"] != 1
            or command_center["gateways_online"] != 1
            or command_center["devices_live"] != 1
        ):
            raise AssertionError("Command Center fleet counts do not reflect the FCJ customer state.")
        latest_reading = command_center["top_devices"][0]["latest_reading"]
        if not latest_reading or latest_reading["key"] not in TELEMETRY_KEYS:
            raise AssertionError("Command Center does not expose a latest FCJ device reading.")

        self.progress(f"[{self.test_run_id}] customer-visible Hub assertions passed")
        return [
            "claimed_gateway_identity",
            "gateway_and_device_live",
            "telemetry_persisted",
            "samples_api_readback",
            "device_dashboard_widgets",
            "command_center_summary",
        ]

    def _mark_failure(self, stage: str):
        failed_at = timezone.now().astimezone(UTC).isoformat()
        for model, pk in ((Site, self.resources.site_id), (Device, self.resources.device_id)):
            record = model.objects.filter(pk=pk).first()
            if not record or not _metadata_owned_by_run(record.metadata, self.test_run_id):
                continue
            record.metadata = {
                **record.metadata,
                "status": "failed",
                "failure_stage": stage,
                "failed_at": failed_at,
            }
            record.save(update_fields=["metadata", "updated_at"])

    def _disconnect_mqtt(self):
        if not self._mqtt_client:
            return
        try:
            self._mqtt_client.disconnect()
            self._mqtt_client.loop_stop()
        finally:
            self._mqtt_client = None


def _remove_queued_run_payloads(test_run_id: str, redis_client=None) -> int:
    names = journey_names(test_run_id)
    try:
        redis_client = redis_client or redis.Redis.from_url(settings.REDIS_URL)
        removed = 0
        for queue_key in ("telemetry_ingest_queue", "logs_ingest_queue"):
            for raw in redis_client.lrange(queue_key, 0, -1):
                try:
                    payload = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
                    continue
                matches_serial = (
                    payload.get("serial_number") == names.gateway_serial
                    or payload.get("_topic_gateway_sn") == names.gateway_serial
                )
                if matches_serial:
                    removed += int(redis_client.lrem(queue_key, 0, raw) or 0)
        return removed
    except Exception:
        return 0


def count_test_run_records(test_run_id: str) -> dict[str, int]:
    names = journey_names(test_run_id)
    devices = Device.objects.filter(metadata__test_run_id=test_run_id, metadata__created_by=CREATED_BY)
    sites = Site.objects.filter(metadata__test_run_id=test_run_id, metadata__created_by=CREATED_BY)
    inventory_ids = _owned_inventory_ids(test_run_id)
    team_ids = set(sites.values_list("team_id", flat=True)) | set(devices.values_list("team_id", flat=True))
    inventory = GatewayInventory.objects.filter(id__in=inventory_ids)
    team_ids.update(inventory.values_list("claimed_by_team_id", flat=True))
    gateway_ids = set(inventory.exclude(gateway_id=None).values_list("gateway_id", flat=True))
    return {
        "telemetry": TelemetryData.objects.filter(device__in=devices).count(),
        "devices": devices.count(),
        "gateways": Gateway.objects.filter(
            id__in=gateway_ids,
            serial_number=names.gateway_serial,
            name=names.gateway_name,
        ).count(),
        "inventory": inventory.count(),
        "sites": sites.count(),
        "templates": DeviceTemplate.objects.filter(
            name=names.template_name,
            created_by_team_id__in=team_ids,
        ).count(),
        "teams": Team.objects.filter(id__in=team_ids, name=names.team_name).count(),
        "users": CustomUser.objects.filter(email=names.user_email, username=names.user_email).count(),
    }


@transaction.atomic
def cleanup_test_run(test_run_id: str, *, redis_client=None) -> dict[str, int]:
    test_run_id = validate_test_run_id(test_run_id)
    names = journey_names(test_run_id)
    devices = Device.objects.filter(metadata__test_run_id=test_run_id, metadata__created_by=CREATED_BY)
    sites = Site.objects.filter(metadata__test_run_id=test_run_id, metadata__created_by=CREATED_BY)
    team_ids = set(sites.values_list("team_id", flat=True)) | set(devices.values_list("team_id", flat=True))
    inventory_ids = _owned_inventory_ids(test_run_id)
    inventories = GatewayInventory.objects.filter(id__in=inventory_ids)
    team_ids.update(inventories.values_list("claimed_by_team_id", flat=True))
    device_ids = list(devices.values_list("id", flat=True))
    inventory_gateway_ids = set(inventories.exclude(gateway_id=None).values_list("gateway_id", flat=True))
    gateway_ids = set(
        Gateway.objects.filter(
            serial_number=names.gateway_serial,
            name=names.gateway_name,
            team_id__in=team_ids,
        ).values_list("id", flat=True)
    )
    gateway_ids.update(inventory_gateway_ids)

    result = {
        "telemetry": TelemetryData.objects.filter(device_id__in=device_ids).count(),
        "widgets": Widget.objects.filter(device_id__in=device_ids).count(),
        "dashboards": Dashboard.objects.filter(device_id__in=device_ids).count(),
        "devices": len(device_ids),
        "gateway_logs": GatewayLog.objects.filter(gateway_id__in=gateway_ids).count(),
        "gateway_configs": GatewayConfig.objects.filter(gateway_id__in=gateway_ids).count(),
        "inventory": len(inventory_ids),
        "gateways": len(gateway_ids),
        "sites": sites.count(),
        "templates": DeviceTemplate.objects.filter(name=names.template_name, created_by_team_id__in=team_ids).count(),
        "teams": Team.objects.filter(id__in=team_ids, name=names.team_name).count(),
        "users": CustomUser.objects.filter(email=names.user_email, username=names.user_email).count(),
        "redis_messages": 0,
    }

    TelemetryData.objects.filter(device_id__in=device_ids).delete()
    Widget.objects.filter(device_id__in=device_ids).delete()
    Dashboard.objects.filter(device_id__in=device_ids).delete()
    devices.delete()
    GatewayLog.objects.filter(gateway_id__in=gateway_ids).delete()
    GatewayConfig.objects.filter(gateway_id__in=gateway_ids).delete()
    inventories.delete()
    Gateway.objects.filter(id__in=gateway_ids).delete()
    sites.delete()
    DeviceTemplate.objects.filter(name=names.template_name, created_by_team_id__in=team_ids).delete()
    for team_id in team_ids:
        cache.delete(f"dashboard_{team_id}_operations_trend")
    Team.objects.filter(id__in=team_ids, name=names.team_name).delete()
    CustomUser.objects.filter(email=names.user_email, username=names.user_email).delete()
    result["redis_messages"] = _remove_queued_run_payloads(test_run_id, redis_client=redis_client)
    return result


def discover_owned_run_ids(
    *,
    created_by: str,
    include_unexpired: bool = False,
    now: datetime | None = None,
) -> list[str]:
    if created_by != CREATED_BY:
        raise ValueError(f"created_by must be exactly {CREATED_BY!r}.")
    now = now or timezone.now()
    candidates: dict[str, list[datetime | None]] = {}

    for metadata in Site.objects.filter(metadata__created_by=CREATED_BY).values_list("metadata", flat=True):
        run_id = metadata.get("test_run_id") if isinstance(metadata, dict) else None
        if run_id and RUN_ID_PATTERN.fullmatch(run_id):
            candidates.setdefault(run_id, []).append(_expires_at(metadata.get("expires_at")))
    for metadata in Device.objects.filter(metadata__created_by=CREATED_BY).values_list("metadata", flat=True):
        run_id = metadata.get("test_run_id") if isinstance(metadata, dict) else None
        if run_id and RUN_ID_PATTERN.fullmatch(run_id):
            candidates.setdefault(run_id, []).append(_expires_at(metadata.get("expires_at")))
    for notes in GatewayInventory.objects.filter(batch=CREATED_BY).values_list("notes", flat=True):
        marker = _parse_inventory_notes(notes)
        run_id = marker.get("test_run_id")
        if marker.get("created_by") == CREATED_BY and run_id and RUN_ID_PATTERN.fullmatch(run_id):
            candidates.setdefault(run_id, []).append(_expires_at(marker.get("expires_at")))

    prefix = "FCJ Test "
    suffix = " Customer"
    stale_cutoff = now - FAILURE_RETENTION
    for name, created_at in Team.objects.filter(name__startswith=prefix).values_list("name", "created_at"):
        run_id = name[len(prefix) : -len(suffix)] if name.endswith(suffix) else ""
        if RUN_ID_PATTERN.fullmatch(run_id):
            candidates.setdefault(run_id, []).append(created_at + FAILURE_RETENTION if created_at else stale_cutoff)
    for email, date_joined in CustomUser.objects.filter(email__endswith="@automated-fcj.invalid").values_list(
        "email", "date_joined"
    ):
        run_id = email.removesuffix("@automated-fcj.invalid")
        if RUN_ID_PATTERN.fullmatch(run_id):
            candidates.setdefault(run_id, []).append(date_joined + FAILURE_RETENTION if date_joined else stale_cutoff)

    if include_unexpired:
        return sorted(candidates)
    return sorted(
        run_id
        for run_id, expirations in candidates.items()
        if expirations and all(expiration is not None and expiration <= now for expiration in expirations)
    )


def cleanup_owned_runs(*, created_by: str, include_unexpired: bool = False) -> dict:
    run_ids = discover_owned_run_ids(created_by=created_by, include_unexpired=include_unexpired)
    return {
        "created_by": created_by,
        "include_unexpired": include_unexpired,
        "run_ids": run_ids,
        "runs": {run_id: cleanup_test_run(run_id) for run_id in run_ids},
    }
