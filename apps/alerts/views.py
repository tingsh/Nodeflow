from django.views.generic import ListView
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.teams.mixins import LoginAndTeamRequiredMixin
from apps.teams.decorators import login_and_team_required
from .models import Alert

class AlertListView(LoginAndTeamRequiredMixin, ListView):
    model = Alert
    template_name = "alerts/alert_list.html"
    context_object_name = "alerts"

    def get_queryset(self):
        return Alert.objects.filter(team=self.request.team).order_by('-triggered_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "alerts"
        return context

@login_and_team_required
@require_POST
def acknowledge_alert(request, team_slug, alert_id):
    """
    HTMX view to acknowledge an alert.
    Returns the updated alert partial or a success indicator.
    """
    alert = get_object_or_404(Alert, id=alert_id, team=request.team)
    if alert.status == 'active':
        alert.status = 'acknowledged'
        alert.acknowledged_at = timezone.now()
        alert.acknowledged_by = request.user
        alert.save(update_fields=['status', 'acknowledged_at', 'acknowledged_by'])
    
    # Return a partial or just the updated row
    return render(request, "alerts/partials/alert_row.html", {"alert": alert})
