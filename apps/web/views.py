from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from health_check.views import MainView

from apps.teams.decorators import login_and_team_required
from apps.teams.helpers import get_open_invitations_for_user


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
        return render(request, "web/landing_page.html")


from apps.teams.decorators import login_and_team_required, require_permission


@require_permission("view_dashboard")
def team_home(request, team_slug):
    assert request.team.slug == team_slug
    
    from apps.devices.models import Site, Gateway, Device
    from apps.alerts.models import Alert
    from django.db.models import Sum
    
    # IoT Stats
    sites_count = Site.objects.filter(team=request.team).count()
    if sites_count == 0:
        return HttpResponseRedirect(reverse("web_team:onboarding:start", args=[team_slug]))
        
    gateways_count = Gateway.objects.filter(team=request.team).count()
    devices_count = Device.objects.filter(team=request.team).count()
    
    # Energy Aggregates (24h)
    from apps.telemetry.models import TelemetryData
    from django.utils import timezone
    from datetime import timedelta
    yesterday = timezone.now() - timedelta(days=1)
    
    # Sum unique energy values (assuming kWh key)
    total_energy = TelemetryData.objects.filter(
        device__team=request.team,
        key='energy',
        timestamp__gte=yesterday
    ).aggregate(Sum('value_numeric'))['value_numeric__sum'] or 0
    
    # Activity Logs
    from apps.events.models import ActivityLog
    logs = ActivityLog.objects.filter(team=request.team).order_by('-timestamp')[:20]
    
    # Maintenance Stats
    from apps.maintenance.models import MaintenanceTicket, PreventiveSchedule
    open_tickets = MaintenanceTicket.objects.filter(
        team=request.team, 
        status__in=['open', 'in_progress', 'waiting']
    ).count()
    overdue_pms = PreventiveSchedule.objects.filter(
        team=request.team,
        is_active=True,
        next_due_at__lt=timezone.now()
    ).count()

    return render(
        request,
        "web/app_home.html",
        context={
            "team": request.team,
            "active_tab": "dashboard",
            "page_title": _("{team} Dashboard").format(team=request.team),
            "sites_count": sites_count,
            "gateways_count": gateways_count,
            "devices_count": devices_count,
            "total_energy": round(total_energy, 1),
            "logs": logs,
            "open_tickets": open_tickets,
            "overdue_pms": overdue_pms,
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
