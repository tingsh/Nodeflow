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


@login_and_team_required
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
    
    # Recent Alerts
    recent_alerts = Alert.objects.filter(team=request.team, status='active').order_by('-triggered_at')[:5]
    
    # We could calculate total demand across all devices if needed, but for MVP stats counts are good.
    
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
            "recent_alerts": recent_alerts,
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
