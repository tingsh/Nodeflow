from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.teams.decorators import login_and_team_required
from apps.teams.mixins import PermissionRequiredMixin

from .forms import MaintenanceTicketForm, PreventiveScheduleForm, TicketCommentForm, TicketTemplateForm
from .models import MaintenanceTicket, PreventiveSchedule, TicketTemplate

# --- Tickets ---


class TicketListView(PermissionRequiredMixin, ListView):
    permission_required = "view_maintenance"
    model = MaintenanceTicket
    template_name = "maintenance/ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        qs = MaintenanceTicket.objects.filter(team=self.request.team)

        status_filter = self.request.GET.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by("-created_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        context["status_filter"] = self.request.GET.get("status", "")
        return context


class TicketDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "view_maintenance"
    model = MaintenanceTicket
    template_name = "maintenance/ticket_detail.html"
    context_object_name = "ticket"

    def get_queryset(self):
        return MaintenanceTicket.objects.filter(team=self.request.team)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        context["comment_form"] = TicketCommentForm()
        return context


class TicketCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_maintenance"
    model = MaintenanceTicket
    form_class = MaintenanceTicketForm
    template_name = "maintenance/ticket_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.request.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.team
        form.instance.reported_by = self.request.user
        messages.success(self.request, "Ticket created successfully.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("web_team:maintenance:ticket_detail", args=[self.request.team.slug, self.object.id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        return context


class TicketUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "manage_maintenance"
    model = MaintenanceTicket
    form_class = MaintenanceTicketForm
    template_name = "maintenance/ticket_form.html"

    def get_queryset(self):
        return MaintenanceTicket.objects.filter(team=self.request.team)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.request.team
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Ticket updated successfully.")
        return reverse("web_team:maintenance:ticket_detail", args=[self.request.team.slug, self.object.id])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        return context


@require_POST
@login_and_team_required
def add_ticket_comment(request, team_slug, pk):
    team = request.team
    ticket = get_object_or_404(MaintenanceTicket, team=team, pk=pk)

    # Needs view permission minimum
    from apps.teams.roles import has_permission

    if not has_permission(request.user, team, "view_maintenance"):
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden()

    form = TicketCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.ticket = ticket
        comment.author = request.user
        comment.save()
        messages.success(request, "Comment added.")
    return redirect("web_team:maintenance:ticket_detail", team_slug=team.slug, pk=ticket.id)


# --- Preventive Schedules ---


class ScheduleListView(PermissionRequiredMixin, ListView):
    permission_required = "view_maintenance"
    model = PreventiveSchedule
    template_name = "maintenance/schedule_list.html"
    context_object_name = "schedules"

    def get_queryset(self):
        return PreventiveSchedule.objects.filter(team=self.request.team).order_by("next_due_at")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        return context


class ScheduleCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_maintenance"
    model = PreventiveSchedule
    form_class = PreventiveScheduleForm
    template_name = "maintenance/schedule_form.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["team"] = self.request.team
        return kwargs

    def form_valid(self, form):
        form.instance.team = self.request.team
        messages.success(self.request, "Preventive Schedule created.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("web_team:maintenance:schedule_list", args=[self.request.team.slug])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        return context


# --- Templates ---


class TemplateListView(PermissionRequiredMixin, ListView):
    permission_required = "view_maintenance"
    model = TicketTemplate
    template_name = "maintenance/template_list.html"
    context_object_name = "templates"

    def get_queryset(self):
        return TicketTemplate.objects.filter(team=self.request.team)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        return context


class TemplateCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_maintenance"
    model = TicketTemplate
    form_class = TicketTemplateForm
    template_name = "maintenance/template_form.html"

    def form_valid(self, form):
        form.instance.team = self.request.team
        messages.success(self.request, "Template created.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("web_team:maintenance:template_list", args=[self.request.team.slug])

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "maintenance"
        return context
