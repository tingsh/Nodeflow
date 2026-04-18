import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from apps.devices.models import Device

from .models import TelemetryData
from .services import get_latest_telemetry_for_chart, get_latest_telemetry_value


@login_required
def get_chart_partial(request, team_slug, device_id, key):
    # Security: Ensure device belongs to the team
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)

    chart_data = get_latest_telemetry_for_chart(device, key)

    context = {
        "chart_data": chart_data,
        "device": device,
    }
    return render(request, "telemetry/partials/chart_partial.html", context)


@login_required
def get_kpi_partial(request, team_slug, device_id, key):
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    value = get_latest_telemetry_value(device, key)

    units = {"voltage": "V", "active_power": "W", "frequency": "Hz", "solar_generation": "W"}

    context = {
        "value": value,
        "label": key.replace("_", " "),
        "unit": units.get(key, ""),
    }
    return render(request, "telemetry/partials/kpi_card.html", context)


@login_required
def telemetry_analyzer(request, team_slug, device_id):
    """
    Main view for the historical data analyzer.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)

    context = {"device": device, "team": request.team, "active_tab": "devices", "page_title": f"Analyze: {device.name}"}
    return render(request, "telemetry/analyzer.html", context)


@login_required
def device_metrics_api(request, team_slug, device_id):
    """
    JSON endpoint for Chart.js real-time updates.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    key = request.GET.get("key", "active_power")
    limit = int(request.GET.get("limit", 50))

    data = get_latest_telemetry_for_chart(device, key, limit)
    return JsonResponse(data)


@login_required
def device_telemetry_history_api(request, team_slug, device_id):
    """
    JSON endpoint for historical data tables.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    key = request.GET.get("key", None)

    qs = TelemetryData.objects.filter(device=device).order_by("-timestamp")
    if key:
        qs = qs.filter(key=key)

    data = []
    for point in qs[:100]:
        data.append(
            {
                "timestamp": point.timestamp.isoformat(),
                "key": point.key,
                "value": point.value_numeric
                if point.value_numeric is not None
                else (point.value_string or point.value_bool),
            }
        )

    return JsonResponse({"results": data})


@login_required
def export_telemetry_csv(request, team_slug, device_id):
    """
    Exports device telemetry to CSV.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{device.name}_telemetry.csv"'

    writer = csv.writer(response)
    writer.writerow(["Timestamp", "Key", "Value"])

    qs = TelemetryData.objects.filter(device=device).order_by("-timestamp")
    for point in qs[:5000]:  # Limit export for safety
        val = point.value_numeric if point.value_numeric is not None else (point.value_string or point.value_bool)
        writer.writerow([point.timestamp, point.key, val])

    return response
