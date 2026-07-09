import csv
from datetime import timedelta

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.devices.models import Device
from apps.teams.decorators import login_and_team_required
from apps.telemetry.models import TelemetryData


@login_and_team_required
def device_metrics_api(request, team_slug, device_id):
    """
    Returns a list of unique telemetry keys that this device has reported
    in the last 7 days.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)

    # Get unique keys from the database for this device
    # In a high-scale production env, we might cache this or store it in the Device model
    lookback = timezone.now() - timedelta(days=7)
    metrics = (
        TelemetryData.objects.filter(device=device, timestamp__gte=lookback).values_list("key", flat=True).distinct()
    )

    # Map keys to human-readable labels and units
    # This could eventually come from the DeviceTemplate
    unit_map = {
        "voltage": "V",
        "active_power": "W",
        "current": "A",
        "frequency": "Hz",
        "energy": "kWh",
        "temperature": "°C",
        "humidity": "%",
        "solar_generation": "W",
    }

    result = []
    for key in metrics:
        result.append({"key": key, "label": key.replace("_", " ").title(), "unit": unit_map.get(key, "")})

    return JsonResponse({"metrics": result})


def get_retention_limit_days(team) -> int:
    from apps.subscriptions.enforcement import get_retention_limit_days_for_team

    return get_retention_limit_days_for_team(team)


@login_and_team_required
def device_telemetry_history_api(request, team_slug, device_id):
    """
    Returns time-series data for a specific metric key.
    Usage: ?key=active_power&hours=24
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    key = request.GET.get("key")
    hours = int(request.GET.get("hours", 24))

    plan_days = get_retention_limit_days(request.team)
    max_hours = plan_days * 24

    # Safety cap: don't allow querying beyond the plan's limit
    if hours > max_hours:
        hours = max_hours

    if not key:
        return JsonResponse({"error": "Metric key is required"}, status=400)

    start_time = timezone.now() - timedelta(hours=hours)

    # Fetch data points
    data_points = TelemetryData.objects.filter(device=device, key=key, timestamp__gte=start_time).order_by("timestamp")

    # Format for Chart.js
    labels = []
    values = []
    for dp in data_points:
        labels.append(dp.timestamp.isoformat())
        values.append(dp.value_numeric)

    return JsonResponse({"key": key, "labels": labels, "values": values})


class Echo:
    def write(self, value):
        return value


@login_and_team_required
def export_telemetry_csv(request, team_slug, device_id):
    """
    Streams a CSV export of telemetry data for a device.
    Caps based on plan.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    days = int(request.GET.get("days", 7))
    
    plan_days = get_retention_limit_days(request.team)
    if days > plan_days:
        days = plan_days

    start_time = timezone.now() - timedelta(days=days)
    queryset = TelemetryData.objects.filter(device=device, timestamp__gte=start_time).order_by("-timestamp")

    metric_meta = {}
    if device.template and device.template.register_map:
        for key, config in device.template.register_map.items():
            if not isinstance(config, dict) or config.get("writable"):
                continue
            metric_meta[key] = {
                "label": config.get("label") or key.replace("_", " ").title(),
                "unit": config.get("unit", ""),
            }

    def row_generator():
        yield ["Timestamp", "Metric", "Key", "Value", "Unit"]
        for point in queryset.iterator(chunk_size=1000):
            meta = metric_meta.get(point.key, {"label": point.key.replace("_", " ").title(), "unit": ""})
            if point.value_numeric is not None:
                value = point.value_numeric
            elif point.value_bool is not None:
                value = point.value_bool
            else:
                value = point.value_string
            yield [point.timestamp, meta["label"], point.key, value, meta["unit"]]

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in row_generator()),
        content_type="text/csv",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="telemetry_{device.id}_{timezone.now().strftime("%Y%m%d")}.csv"'
    )
    return response
