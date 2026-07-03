from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Sum
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from health_check.views import MainView

from apps.alerts.models import Alert
from apps.automations.models import Automation
from apps.devices.models import Device, Gateway, Site
from apps.events.models import ActivityLog
from apps.maintenance.models import MaintenanceTicket, PreventiveSchedule
from apps.teams.decorators import require_permission
from apps.teams.helpers import get_open_invitations_for_user
from apps.telemetry.models import TelemetryData


def home(request):
    if request.user.is_authenticated:
        team = request.team
        if team:
            return HttpResponseRedirect(reverse("web_team:home", args=[team.slug]))
        else:
            if (open_invitations := get_open_invitations_for_user(request.user)) and len(open_invitations) > 1:
                invitation = open_invitations[0]
                return HttpResponseRedirect(reverse("teams:accept_invitation", args=[invitation["id"]]))

            messages.info(
                request,
                _("Teams are enabled but you have no teams. Create a team below to access the rest of the dashboard."),
            )
            return HttpResponseRedirect(reverse("teams:manage_teams"))
    else:
        from wagtail.views import serve
        return serve(request, request.path)


@require_permission("view_dashboard")
def team_home(request, team_slug):
    assert request.team.slug == team_slug

    team = request.team

    # IoT Stats
    sites_count = Site.objects.filter(team=team).count()
    if sites_count == 0:
        return HttpResponseRedirect(reverse("web_team:onboarding:start", args=[team_slug]))

    # --- Cache key prefix ---
    cache_prefix = f"dashboard_{team.id}_"

    # --- Device & Gateway Counts ---
    devices = Device.objects.filter(team=team)
    devices_count = devices.count()
    gateways_count = Gateway.objects.filter(team=team).count()

    now = timezone.now()

    devices_online = devices.filter(status="online").count()
    devices_offline = devices_count - devices_online

    gateways_online = Gateway.objects.filter(team=team, status="online").count()
    gateways_offline = gateways_count - gateways_online

    # --- Energy Aggregates (24h) ---
    yesterday = now - timedelta(days=1)
    total_energy = (
        TelemetryData.objects.filter(device__team=team, key="energy", timestamp__gte=yesterday).aggregate(
            Sum("value_numeric")
        )["value_numeric__sum"]
        or 0
    )

    # --- Hourly energy data for fleet chart (real data) ---
    cache_key_chart = cache_prefix + "hourly_energy"
    hourly_energy = cache.get(cache_key_chart)
    if hourly_energy is None:
        hourly_energy = {"labels": [], "values": []}
        for i in range(23, -1, -1):
            hour_start = now - timedelta(hours=i + 1)
            hour_end = now - timedelta(hours=i)
            hour_kwh = (
                TelemetryData.objects.filter(
                    device__team=team,
                    key__in=["energy", "active_power"],
                    timestamp__gte=hour_start,
                    timestamp__lt=hour_end,
                ).aggregate(Sum("value_numeric"))["value_numeric__sum"]
                or 0
            )
            hourly_energy["labels"].append(hour_end.strftime("%H:%M"))
            hourly_energy["values"].append(round(float(hour_kwh), 2))
        cache.set(cache_key_chart, hourly_energy, 60)  # 60s TTL

    # --- Active Alerts ---
    active_alerts_count = Alert.objects.filter(device__team=team, status="active").count()

    recent_alerts = (
        Alert.objects.filter(device__team=team).select_related("device", "rule").order_by("-triggered_at")[:5]
    )

    # --- Maintenance Stats ---
    open_tickets = MaintenanceTicket.objects.filter(team=team, status__in=["open", "in_progress", "waiting"]).count()
    overdue_pms = PreventiveSchedule.objects.filter(team=team, is_active=True, next_due_at__lt=now).count()

    # --- Automations ---
    active_automations = Automation.objects.filter(team=team, is_active=True).count()
    total_automations = Automation.objects.filter(team=team).count()

    # --- Top Devices for Fleet Grid ---
    top_devices = devices.select_related("site").order_by("-last_telemetry_at")[:8]

    # Get latest readings for top devices
    device_readings = {}
    for device in top_devices:
        latest = TelemetryData.objects.filter(device=device).order_by("-timestamp").first()
        if latest:
            device_readings[device.id] = {
                "key": latest.key,
                "value": latest.value_numeric if latest.value_numeric is not None else latest.value_string,
                "timestamp": latest.timestamp,
            }

    # --- Activity Logs ---
    logs = ActivityLog.objects.filter(team=team).order_by("-timestamp")[:15]

    return render(
        request,
        "web/app_home.html",
        context={
            "team": team,
            "active_tab": "dashboard",
            "page_title": _("{team} Dashboard").format(team=team),
            # KPI strip
            "sites_count": sites_count,
            "gateways_count": gateways_count,
            "devices_count": devices_count,
            "devices_online": devices_online,
            "devices_offline": devices_offline,
            "gateways_online": gateways_online,
            "gateways_offline": gateways_offline,
            "total_energy": round(total_energy, 1),
            "active_alerts_count": active_alerts_count,
            "open_tickets": open_tickets,
            "overdue_pms": overdue_pms,
            "active_automations": active_automations,
            "total_automations": total_automations,
            # Charts
            "hourly_energy": hourly_energy,
            # Feeds
            "recent_alerts": recent_alerts,
            "top_devices": top_devices,
            "device_readings": device_readings,
            "logs": logs,
        },
    )


def simulate_error(request):
    raise Exception("This is a simulated error.")


class HealthCheck(MainView):
    def get(self, request, *args, **kwargs):
        tokens = settings.HEALTH_CHECK_TOKENS
        if tokens and request.GET.get("token") not in tokens:
            raise Http404
        return super().get(request, *args, **kwargs)
