from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.teams.decorators import require_permission
from apps.teams.mixins import PermissionRequiredMixin

from .forms import AlertRuleForm
from .models import Alert, AlertRule


class AlertListView(PermissionRequiredMixin, ListView):
    permission_required = "view_dashboard"
    model = Alert
    template_name = "alerts/alert_list.html"
    context_object_name = "alerts"

    def get_queryset(self):
        return Alert.objects.filter(team=self.request.team).order_by("-triggered_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "alerts"
        context["rules"] = AlertRule.objects.filter(team=self.request.team)
        return context


# Alert Rule CRUD


class AlertRuleListView(PermissionRequiredMixin, ListView):
    permission_required = "view_dashboard"
    model = AlertRule
    template_name = "alerts/rule_list.html"
    context_object_name = "rules"

    def get_queryset(self):
        return AlertRule.objects.filter(team=self.request.team)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "alert_rules"
        return context


class AlertRuleCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_alerts"
    model = AlertRule
    form_class = AlertRuleForm
    template_name = "alerts/rule_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.request.team
        return kwargs

    def form_valid(self, form):
        if (form.cleaned_data.get("notify_email") or form.cleaned_data.get("notify_whatsapp")) \
           and not form.cleaned_data.get("recipients"):
            form.add_error("recipients", "You must select at least one recipient if notifications are enabled.")
            return self.form_invalid(form)
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:alerts:alert_list", args=[self.request.team.slug])


class AlertRuleUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "manage_alerts"
    model = AlertRule
    form_class = AlertRuleForm
    template_name = "alerts/rule_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.request.team
        return kwargs

    def form_valid(self, form):
        if (form.cleaned_data.get("notify_email") or form.cleaned_data.get("notify_whatsapp")) \
           and not form.cleaned_data.get("recipients"):
            form.add_error("recipients", "You must select at least one recipient if notifications are enabled.")
            return self.form_invalid(form)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:alerts:alert_list", args=[self.request.team.slug])


class AlertRuleDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = "manage_alerts"
    model = AlertRule
    template_name = "alerts/rule_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:alerts:alert_list", args=[self.request.team.slug])


@require_permission("acknowledge_alerts")
@require_POST
def acknowledge_alert(request, team_slug, alert_id):
    """
    HTMX view to acknowledge an alert.
    Returns the updated alert partial or a success indicator.
    """
    alert = get_object_or_404(Alert, id=alert_id, team=request.team)
    if alert.status == "active":
        alert.status = "acknowledged"
        alert.acknowledged_at = timezone.now()
        alert.acknowledged_by = request.user
        alert.save(update_fields=["status", "acknowledged_at", "acknowledged_by"])

    # Return a partial or just the updated row
    return render(request, "alerts/partials/alert_row.html", {"alert": alert})


@require_permission("manage_alerts")
def search_team_members(request, team_slug):
    q = request.GET.get("q", "").strip()
    if not q:
        return render(request, "alerts/partials/user_search_results.html", {"users": []})

    users = request.team.members.filter(
        Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q) | Q(username__icontains=q)
    )[:10]

    return render(request, "alerts/partials/user_search_results.html", {"users": users})


@require_permission("manage_maintenance")
@require_POST
def escalate_alert_to_ticket(request, team_slug, alert_id):
    """
    HTMX POST view to manually escalate an alert into a reactive maintenance ticket.
    Uses the auto_create_ticket service with force=True.
    """
    from apps.alerts.models import Alert
    from apps.maintenance.services import auto_create_ticket

    alert = get_object_or_404(Alert, id=alert_id, team=request.team)
    
    ticket = alert.ticket
    if not ticket:
        auto_create_ticket(alert, force=True)

    return render(request, "alerts/partials/alert_row.html", {"alert": alert})

