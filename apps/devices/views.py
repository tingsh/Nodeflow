from django.urls import reverse_lazy
from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from apps.teams.mixins import LoginAndTeamRequiredMixin
from .models import Site, Gateway, Device, DeviceTemplate

class SiteListView(LoginAndTeamRequiredMixin, ListView):
    model = Site
    template_name = "devices/site_list.html"
    context_object_name = "sites"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "sites"
        return context

class SiteDetailView(LoginAndTeamRequiredMixin, DetailView):
    model = Site
    template_name = "devices/site_detail.html"
    context_object_name = "site"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.telemetry.services import get_site_summary_stats
        from apps.telemetry.anomaly import get_ai_insights
        from apps.alerts.models import Alert
        
        context["stats"] = get_site_summary_stats(self.object)
        
        # Aggregate insights for all devices in the site
        site_insights = []
        for device in self.object.devices.all():
            site_insights.extend(get_ai_insights(device))
        context["ai_insights"] = site_insights[:3] # Show top 3

        context["recent_alerts"] = Alert.objects.filter(
            device__site=self.object,
            status='active'
        ).order_by('-triggered_at')[:5]
        return context

class SiteCreateView(LoginAndTeamRequiredMixin, CreateView):
    model = Site
    fields = ["name", "address", "latitude", "longitude", "timezone"]
    template_name = "devices/site_form.html"

    def form_valid(self, form):
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])

class SiteUpdateView(LoginAndTeamRequiredMixin, UpdateView):
    model = Site
    fields = ["name", "address", "latitude", "longitude", "timezone"]
    template_name = "devices/site_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])

class SiteDeleteView(LoginAndTeamRequiredMixin, DeleteView):
    model = Site
    template_name = "devices/site_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])


class GatewayListView(LoginAndTeamRequiredMixin, ListView):
    model = Gateway
    template_name = "devices/gateway_list.html"
    context_object_name = "gateways"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "gateways"
        return context

class GatewayDetailView(LoginAndTeamRequiredMixin, DetailView):
    model = Gateway
    template_name = "devices/gateway_detail.html"
    context_object_name = "gateway"

class GatewayCreateView(LoginAndTeamRequiredMixin, CreateView):
    model = Gateway
    fields = ["site", "name", "serial_number"]
    template_name = "devices/gateway_form.html"

    def form_valid(self, form):
        form.instance.team = self.request.team
        # For MVP, auto-generate a token if not present
        import secrets
        form.instance.access_token = secrets.token_hex(20)
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_list", args=[self.request.team.slug])

class GatewayUpdateView(LoginAndTeamRequiredMixin, UpdateView):
    model = Gateway
    fields = ["site", "name", "serial_number", "status"]
    template_name = "devices/gateway_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_list", args=[self.request.team.slug])

class GatewayDeleteView(LoginAndTeamRequiredMixin, DeleteView):
    model = Gateway
    template_name = "devices/gateway_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_list", args=[self.request.team.slug])


class DeviceListView(LoginAndTeamRequiredMixin, ListView):
    model = Device
    template_name = "devices/device_list.html"
    context_object_name = "devices"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "devices"
        return context

class DeviceDetailView(LoginAndTeamRequiredMixin, DetailView):
    model = Device
    template_name = "devices/device_detail.html"
    context_object_name = "device"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.telemetry.anomaly import get_ai_insights
        context["ai_insights"] = get_ai_insights(self.object)
        return context

class DeviceCreateView(LoginAndTeamRequiredMixin, CreateView):
    model = Device
    fields = ["gateway", "site", "template", "name", "device_type", "protocol", "energy_category", "connection_config"]
    template_name = "devices/device_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Enforce device limits
        from apps.subscriptions.enforcement import can_add_device, get_device_limit_for_team
        if not can_add_device(request.team):
            limit = get_device_limit_for_team(request.team)
            count = Device.objects.filter(team=request.team).count()
            return render(request, "devices/upgrade_required.html", {
                "limit": limit,
                "count": count,
            })
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:device_list", args=[self.request.team.slug])

class DeviceUpdateView(LoginAndTeamRequiredMixin, UpdateView):
    model = Device
    fields = ["name", "device_type", "protocol", "energy_category", "connection_config", "status"]
    template_name = "devices/device_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:device_list", args=[self.request.team.slug])

class DeviceDeleteView(LoginAndTeamRequiredMixin, DeleteView):
    model = Device
    template_name = "devices/device_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:device_list", args=[self.request.team.slug])
