from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.devices.models import Device
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
    
    units = {
        'voltage': 'V',
        'active_power': 'W',
        'frequency': 'Hz',
        'solar_generation': 'W'
    }
    
    context = {
        "value": value,
        "label": key.replace('_', ' '),
        "unit": units.get(key, ''),
    }
    return render(request, "telemetry/partials/kpi_card.html", context)
