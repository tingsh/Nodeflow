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
    JSON endpoint returning available telemetry metrics (keys, labels, units) for a device.
    """
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    
    metrics = []
    if device.template and device.template.register_map:
        for key, val in device.template.register_map.items():
            if isinstance(val, dict):
                if not val.get("writable"):
                    metrics.append({
                        "key": key,
                        "label": val.get("label", key.replace("_", " ").title()),
                        "unit": val.get("unit", "")
                    })
    
    if not metrics:
        # Fallback to distinct keys recorded in TelemetryData
        keys = TelemetryData.objects.filter(device=device).order_by().values_list("key", flat=True).distinct()
        for key in keys:
            metrics.append({
                "key": key,
                "label": key.replace("_", " ").title(),
                "unit": ""
            })
            
    return JsonResponse({"metrics": metrics})


def get_retention_limit_days(team) -> int:
    if not team or not team.has_active_subscription():
        return 7  # Default to Starter tier for unsubscribed teams

    try:
        from apps.subscriptions.metadata import get_product_with_metadata
        subscription = team.active_stripe_subscription
        for item in subscription.items.select_related("price__product"):
            product_metadata = get_product_with_metadata(item.price.product).metadata
            if product_metadata.slug == "starter":
                return 7
            elif product_metadata.slug == "professional":
                return 30
            elif product_metadata.slug == "business":
                return 90
    except Exception:
        pass
    return 7


@login_required
def device_telemetry_history_api(request, team_slug, device_id):
    """
    JSON endpoint for historical and real-time Chart.js updates.
    """
    from django.utils import timezone
    
    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    key = request.GET.get("key", "active_power")
    hours = int(request.GET.get("hours", 24))

    plan_days = get_retention_limit_days(request.team)
    max_hours = plan_days * 24

    if hours > max_hours:
        hours = max_hours

    qs = TelemetryData.objects.filter(device=device)
    if key:
        qs = qs.filter(key=key)
        
    cutoff = timezone.now() - timezone.timedelta(hours=hours)
    qs = qs.filter(timestamp__gte=cutoff).order_by("-timestamp")[:1000]

    # Reverse to keep chronological order
    points = list(reversed(list(qs)))
    
    labels = []
    values = []
    for point in points:
        labels.append(point.timestamp.isoformat())
        values.append(point.value_numeric or 0.0)

    return JsonResponse({"labels": labels, "values": values, "key": key})


@login_required
def export_telemetry_csv(request, team_slug, device_id):
    """
    Exports device telemetry to CSV.
    """
    from django.utils import timezone

    device = get_object_or_404(Device, id=device_id, team__slug=team_slug)
    days = int(request.GET.get("days", 7))

    plan_days = get_retention_limit_days(request.team)
    if days > plan_days:
        days = plan_days

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{device.name}_telemetry.csv"'

    writer = csv.writer(response)
    writer.writerow(["Timestamp", "Key", "Value"])

    cutoff = timezone.now() - timezone.timedelta(days=days)
    qs = TelemetryData.objects.filter(device=device, timestamp__gte=cutoff).order_by("-timestamp")
    for point in qs[:5000]:  # Limit export for safety
        val = point.value_numeric if point.value_numeric is not None else (point.value_string or point.value_bool)
        writer.writerow([point.timestamp, point.key, val])

    return response
