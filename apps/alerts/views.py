from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.urls import reverse_lazy
from apps.teams.mixins import LoginAndTeamRequiredMixin
from apps.teams.decorators import login_and_team_required
from apps.devices.models import Device, Site
from .models import Alert, AlertRule

class AlertListView(LoginAndTeamRequiredMixin, ListView):
    model = Alert
    template_name = "alerts/alert_list.html"
    context_object_name = "alerts"

    def get_queryset(self):
        return Alert.objects.filter(team=self.request.team).order_by('-triggered_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "alerts"
        context["rules"] = AlertRule.objects.filter(team=self.request.team)
        return context

# Alert Rule CRUD

class AlertRuleListView(LoginAndTeamRequiredMixin, ListView):
    model = AlertRule
    template_name = "alerts/rule_list.html"
    context_object_name = "rules"

    def get_queryset(self):
        return AlertRule.objects.filter(team=self.request.team)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "alert_rules"
        return context

class AlertRuleCreateView(LoginAndTeamRequiredMixin, CreateView):
    model = AlertRule
    fields = ["name", "device", "site", "telemetry_key", "condition", "threshold", "severity", "is_active", "notify_email", "notify_whatsapp", "cooldown_minutes"]
    template_name = "alerts/rule_form.html"

    def form_valid(self, form):
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:alerts:alert_list", args=[self.request.team.slug])

class AlertRuleUpdateView(LoginAndTeamRequiredMixin, UpdateView):
    model = AlertRule
    fields = ["name", "device", "site", "telemetry_key", "condition", "threshold", "severity", "is_active", "notify_email", "notify_whatsapp", "cooldown_minutes"]
    template_name = "alerts/rule_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:alerts:alert_list", args=[self.request.team.slug])

class AlertRuleDeleteView(LoginAndTeamRequiredMixin, DeleteView):
    model = AlertRule
    template_name = "alerts/rule_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:alerts:alert_list", args=[self.request.team.slug])

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
