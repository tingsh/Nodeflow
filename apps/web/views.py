from django.conf import settings
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from health_check.views import MainView
from waffle import flag_is_active

from apps.devices.models import Site
from apps.teams.decorators import require_permission
from apps.teams.helpers import get_open_invitations_for_user
from apps.teams.roles import has_permission


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
    if not Site.objects.filter(team=team).exists():
        return HttpResponseRedirect(reverse("web_team:onboarding:start", args=[team_slug]))

    from apps.dashboard.services import build_team_operations_dashboard

    dashboard_context = build_team_operations_dashboard(
        team,
        include_impact=bool(flag_is_active(request, "business_impact_roi")),
        impact_site_ids=[
            site.id
            for site in Site.objects.filter(team=team).only("id")
            if has_permission(request.user, team, "view_business_impact", site=site)
        ],
    )
    context = {
        "team": team,
        "active_tab": "dashboard",
        "page_title": _("{team} Dashboard").format(team=team),
        **dashboard_context,
    }
    return render(request, "web/app_home.html", context=context)


def simulate_error(request):
    raise Exception("This is a simulated error.")


class HealthCheck(MainView):
    def get(self, request, *args, **kwargs):
        tokens = settings.HEALTH_CHECK_TOKENS
        if tokens and request.GET.get("token") not in tokens:
            raise Http404
        return super().get(request, *args, **kwargs)
