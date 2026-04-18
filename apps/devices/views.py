from django.http import HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.teams.decorators import require_permission
from apps.teams.mixins import PermissionRequiredMixin

from .models import Device, DeviceTemplate, Gateway, Site


class SiteListView(PermissionRequiredMixin, ListView):
    permission_required = "view_devices"
    model = Site
    template_name = "devices/site_list.html"
    context_object_name = "sites"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "sites"
        return context


class SiteDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "view_devices"
    model = Site
    template_name = "devices/site_detail.html"
    context_object_name = "site"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.alerts.models import Alert
        from apps.telemetry.anomaly import get_ai_insights
        from apps.telemetry.services import get_site_summary_stats

        context["stats"] = get_site_summary_stats(self.object)

        # Process discovery and conflicts for UI
        for gateway in self.object.gateways.all():
            gateway.port_range = range(1, gateway.capacity + 1)
            port_map = {}
            # 1. Map registered devices
            for device in gateway.devices.all():
                if device.port:
                    port_map[device.port] = {"status": "registered", "device": device}

            # 2. Layer discovery data
            discovery_list = gateway.discovery_data.get("devices", [])
            for disc in discovery_list:
                port = disc.get("port")
                if not port:
                    continue

                if port in port_map:
                    # Check for conflict
                    reg_device = port_map[port]["device"]
                    # Simplified signature check
                    if (
                        disc.get("signature") not in reg_device.name
                        and disc.get("signature") not in reg_device.device_type
                    ):
                        port_map[port]["status"] = "conflict"
                        port_map[port]["discovered"] = disc
                else:
                    # New device discovered
                    port_map[port] = {"status": "discovered", "discovered": disc}

            # Attach to the gateway object for use in templates
            gateway.computed_port_map = port_map

        # Aggregate insights for all devices in the site
        site_insights = []
        for device in self.object.devices.all():
            site_insights.extend(get_ai_insights(device))
        context["ai_insights"] = site_insights[:3]  # Show top 3

        context["recent_alerts"] = Alert.objects.filter(device__site=self.object, status="active").order_by(
            "-triggered_at"
        )[:5]
        return context


class SiteCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_devices"
    model = Site
    fields = ["name", "address", "latitude", "longitude", "timezone"]
    template_name = "devices/site_form.html"

    def form_valid(self, form):
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])


class SiteUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "manage_devices"
    model = Site
    fields = ["name", "address", "latitude", "longitude", "timezone"]
    template_name = "devices/site_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])


class SiteDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = "manage_devices"
    model = Site
    template_name = "devices/site_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])


class GatewayListView(PermissionRequiredMixin, ListView):
    permission_required = "view_devices"
    model = Gateway
    template_name = "devices/gateway_list.html"
    context_object_name = "gateways"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "gateways"
        return context


class GatewayDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "view_devices"
    model = Gateway
    template_name = "devices/gateway_detail.html"
    context_object_name = "gateway"


class GatewayCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_devices"
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


class GatewayUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "manage_devices"
    model = Gateway
    fields = ["site", "name", "serial_number", "status"]
    template_name = "devices/gateway_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_list", args=[self.request.team.slug])


class GatewayDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = "manage_devices"
    model = Gateway
    template_name = "devices/gateway_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_list", args=[self.request.team.slug])


class DeviceListView(PermissionRequiredMixin, ListView):
    permission_required = "view_devices"
    model = Device
    template_name = "devices/device_list.html"
    context_object_name = "devices"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "devices"
        return context


class DeviceDetailView(PermissionRequiredMixin, DetailView):
    permission_required = "view_devices"
    model = Device
    template_name = "devices/device_detail.html"
    context_object_name = "device"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.telemetry.anomaly import get_ai_insights

        context["ai_insights"] = get_ai_insights(self.object)
        context["recent_commands"] = self.object.commands.all().order_by("-requested_at")[:10]

        # Check for writable keys in template
        writable_keys = []
        if self.object.template and self.object.template.register_map:
            for key, config in self.object.template.register_map.items():
                if isinstance(config, dict) and config.get("writable"):
                    writable_keys.append(
                        {
                            "key": key,
                            "label": key.replace("_", " ").title(),
                            "type": config.get("type", "toggle"),  # toggle or slider
                        }
                    )
        context["writable_keys"] = writable_keys
        return context


# ... existing views ...


@require_permission("manage_devices")
def device_send_command(request, team_slug, pk):
    from django.shortcuts import get_object_or_404

    device = get_object_or_404(Device, pk=pk, team=request.team)
    key = request.POST.get("key")
    value = request.POST.get("value")

    # Handle value types
    if value.lower() == "true":
        value = True
    elif value.lower() == "false":
        value = False
    else:
        try:
            value = float(value)
        except ValueError:
            pass  # Keep as string

    try:
        from .services import send_device_command

        command = send_device_command(device, request.user, key, value)
        return render(request, "devices/partials/command_status_badge.html", {"command": command})
    except Exception as e:
        return HttpResponse(f'<span class="text-error text-xs font-bold">{str(e)}</span>', status=400)


@require_permission("view_devices")
def device_command_status(request, team_slug, pk, tx_id):
    from django.shortcuts import get_object_or_404

    from .models import DeviceCommand

    command = get_object_or_404(DeviceCommand, transaction_id=tx_id, team=request.team)
    return render(request, "devices/partials/command_status_badge.html", {"command": command})


class DeviceCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_devices"
    model = Device
    fields = ["gateway", "site", "template", "name", "device_type", "protocol", "energy_category", "connection_config"]
    template_name = "devices/device_form.html"

    def dispatch(self, request, *args, **kwargs):
        # Enforce device limits
        from apps.subscriptions.enforcement import can_add_device, get_device_limit_for_team

        if not can_add_device(request.team):
            limit = get_device_limit_for_team(request.team)
            count = Device.objects.filter(team=request.team).count()
            return render(
                request,
                "devices/upgrade_required.html",
                {
                    "limit": limit,
                    "count": count,
                },
            )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:device_list", args=[self.request.team.slug])


class DeviceUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "manage_devices"
    model = Device
    fields = ["name", "device_type", "protocol", "energy_category", "connection_config", "status"]
    template_name = "devices/device_form.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:device_list", args=[self.request.team.slug])


class DeviceDeleteView(PermissionRequiredMixin, DeleteView):
    permission_required = "manage_devices"
    model = Device
    template_name = "devices/device_confirm_delete.html"

    def get_success_url(self):
        return reverse_lazy("web_team:devices:device_list", args=[self.request.team.slug])


# HTMX Views


@require_permission("manage_devices")
def htmx_device_create(request, team_slug):
    gateway_id = request.GET.get("gateway_id")
    site_id = request.GET.get("site_id")
    port = request.GET.get("port")
    provision = request.GET.get("provision")
    resolve = request.GET.get("resolve")

    prefill_data = {}
    if provision == "true" or resolve == "true":
        gateway = Gateway.objects.get(id=gateway_id)
        # Find discovery info for this port
        disc_devices = gateway.discovery_data.get("devices", [])
        for d in disc_devices:
            if str(d.get("port")) == str(port):
                prefill_data["name"] = d.get("signature", "New Device")
                # Try to find a matching template
                sig = d.get("signature", "").lower()
                tpl = DeviceTemplate.objects.filter(name__icontains=sig).first()
                if tpl:
                    prefill_data["template_id"] = tpl.id
                break

    if request.method == "POST":
        name = request.POST.get("name")
        template_id = request.POST.get("template_id")

        template = DeviceTemplate.objects.get(id=template_id)

        # If resolving, delete the old device on this port first
        if resolve == "true":
            Device.objects.filter(gateway_id=gateway_id, port=port).delete()

        device = Device.objects.create(
            team=request.team,
            site_id=site_id,
            gateway_id=gateway_id,
            port=port,
            name=name,
            template=template,
            device_type=template.device_type,
            protocol=template.protocol,
            connection_config=template.register_map,
        )

        from apps.events.services import log_event

        log_event(
            category="audit",
            message=f"Created device {device.name} via Intelligent Port Grid.",
            team=request.team,
            device=device,
            site=device.site,
            user=request.user,
        )

        # Return the updated gateway section (Re-calculate the port map first)
        gateway = Gateway.objects.get(id=gateway_id)
        # We need to re-run the logic from SiteDetailView or extract it.
        # For simplicity in this fragment render, we'll just re-map the specific gateway.
        # (This logic is already in SiteDetailView, so a full page refresh via HX-Trigger might be cleaner,
        # but let's try to return the fragment).

        # ... Re-map logic here or just rely on the next SiteDetailView call ...
        # Actually, let's use HX-Trigger to refresh the whole section or return the partial with mapped data.
        return HttpResponse(status=204, headers={"HX-Trigger": "infrastructureChanged"})

    templates = DeviceTemplate.objects.all()[:10]
    context = {
        "templates": templates,
        "gateway_id": gateway_id,
        "site_id": site_id,
        "port": port,
        "prefill": prefill_data,
        "resolve": resolve,
    }
    return render(request, "devices/partials/device_quick_add_form.html", context)


@require_permission("view_devices")
def template_library_search(request, team_slug):
    query = request.GET.get("q", "")
    templates = DeviceTemplate.objects.filter(name__icontains=query) | DeviceTemplate.objects.filter(
        manufacturer__icontains=query
    )
    return render(request, "devices/partials/template_search_results.html", {"templates": templates[:10]})


import json

from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def gateway_discovery_api(request, team_slug):
    """
    API for the Edge Gateway to report discovered devices.
    Expected payload:
    {
        "serial_number": "NF-xxx",
        "discovered_devices": [
            {"port": 1, "protocol": "modbus", "slave_id": 5, "signature": "Eastron-SDM630"},
            ...
        ]
    }
    """
    if request.method != "POST":
        return HttpResponse("Method not allowed", status=405)

    try:
        data = json.loads(request.body)
        serial = data.get("serial_number")
        discovered = data.get("discovered_devices", [])

        gateway = Gateway.objects.get(serial_number=serial)

        # Store for the UI to display
        gateway.discovery_data = {"last_discovered_at": str(timezone.now()), "devices": discovered}
        gateway.save()

        from apps.events.services import log_event

        log_event(
            category="infrastructure",
            message=f"Gateway {gateway.serial_number} discovered {len(discovered)} new devices.",
            team=gateway.team,
            site=gateway.site,
            metadata={"discovered_count": len(discovered), "serial": serial},
        )

        return HttpResponse(
            json.dumps({"status": "ok", "message": "Discovery report received"}), content_type="application/json"
        )
    except Gateway.DoesNotExist:
        return HttpResponse("Gateway not found", status=404)
    except Exception as e:
        return HttpResponse(str(e), status=400)
