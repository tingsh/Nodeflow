import contextlib
import json
import logging

from django.db import transaction
from django.contrib.auth.hashers import make_password
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.teams.decorators import require_permission
from apps.teams.mixins import PermissionRequiredMixin

from .models import Device, DeviceTemplate, Gateway, GatewayConfig, GatewayInventory, RpcCommand, Site

logger = logging.getLogger("novena_hub")


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
        context["active_tab"] = "sites"
        from apps.alerts.models import Alert
        from apps.telemetry.anomaly import get_ai_insights
        from apps.telemetry.services import get_site_summary_stats

        context["stats"] = get_site_summary_stats(self.object)

        # Process discovery and conflicts for UI
        for gateway in self.object.gateways.all():
            port_map = {}

            # 1. Map registered devices by their port (interface key)
            for device in gateway.devices.all():
                if device.port:
                    port_map[device.port] = {"status": "registered", "device": device}

            # 2. Layer discovery data — use interface name as port key
            discovery_data = gateway.discovery_data or {}
            discovery_list = discovery_data.get("devices", [])
            interfaces = discovery_data.get("interfaces", [])

            for disc in discovery_list:
                # Use interface as the port key (e.g., "/dev/ttyUSB0", "192.168.1.100:502")
                port_key = disc.get("interface") or disc.get("port")
                if not port_key:
                    continue
                port_key = str(port_key)

                if port_key in port_map:
                    # Check for conflict
                    reg_device = port_map[port_key]["device"]
                    sig = disc.get("signature", "")
                    if sig and sig.lower() not in reg_device.name.lower() and sig.lower() not in reg_device.device_type.lower():
                        port_map[port_key]["status"] = "conflict"
                        port_map[port_key]["discovered"] = disc
                else:
                    port_map[port_key] = {"status": "discovered", "discovered": disc}

            # 3. Add empty slots for interfaces with no devices/discoveries
            for iface in interfaces:
                iface_name = iface.get("name", "")
                if iface_name and iface_name not in port_map:
                    port_map[iface_name] = {"status": "empty", "interface": iface}

            # Attach to the gateway object for use in templates
            gateway.computed_port_map = port_map
            gateway.computed_interfaces = interfaces

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

    def form_valid(self, form):
        confirmation_name = self.request.POST.get("confirmation_name", "").strip()
        expected_name = self.object.name.strip()

        if confirmation_name != expected_name:
            form.add_error(None, "Type the site name exactly to confirm deletion.")
            return self.form_invalid(form)

        return super().form_valid(form)

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from apps.telemetry.models import GatewayLog
        from .models import FirmwareRelease

        gateway = self.object
        context["recent_logs"] = GatewayLog.objects.filter(gateway=gateway)[:20]
        context["recent_rpc"] = RpcCommand.objects.filter(gateway=gateway)[:10]
        context["recent_configs"] = GatewayConfig.objects.filter(gateway=gateway)[:5]

        latest_release = FirmwareRelease.objects.filter(is_active=True).first()
        if latest_release and latest_release.version != gateway.firmware_version:
            context["update_available"] = True
            context["latest_release"] = latest_release

        return context


class GatewayCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_devices"
    model = Gateway
    fields = ["site", "name", "serial_number"]
    template_name = "devices/gateway_form.html"

    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect

        from .services import GatewayClaimError, claim_gateway_for_team

        self.object = None
        form = self.get_form()
        claim_code = request.POST.get("claim_code", "").strip().upper()

        if not claim_code:
            form.add_error(None, "Claim code is required. Check the sticker on your gateway.")
            return self.form_invalid(form)

        if not form.is_valid():
            return self.form_invalid(form)

        site = form.cleaned_data["site"]
        if site.team != request.team:
            form.add_error("site", "Select a site that belongs to the current team.")
            return self.form_invalid(form)

        try:
            self.object = claim_gateway_for_team(
                request.team,
                site,
                form.cleaned_data["name"],
                form.cleaned_data["serial_number"],
                claim_code,
            )
        except GatewayClaimError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)

        return redirect(self.get_success_url())

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_detail", args=[self.request.team.slug, self.object.pk])


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

    def form_valid(self, form):
        confirmation_serial = self.request.POST.get("confirmation_serial", "").strip().upper()
        expected_serial = self.object.serial_number.strip().upper()

        if confirmation_serial != expected_serial:
            form.add_error(None, "Type the gateway serial number exactly to confirm deletion.")
            return self.form_invalid(form)

        success_url = self.get_success_url()

        # Release for self-serve onboarding redo. The Gateway row is preserved so
        # the same serial number + printed claim code can be used again.
        self._deprovision_mqtt_credentials()
        from .services import release_gateway_for_redo

        release_gateway_for_redo(self.object)

        return HttpResponseRedirect(success_url)

    def _deprovision_mqtt_credentials(self):
        try:
            from .mqtt_provisioning import deprovision_gateway_mqtt

            deprovision_gateway_mqtt(self.object)
        except Exception as e:
            logger.warning("Mosquitto deprovisioning failed for gateway %s: %s", self.object.serial_number, e)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:gateway_list", args=[self.request.team.slug])

# ── Gateway Management Views (Cloud ↔ Edge) ────────────────────────────


@require_permission("manage_devices")
@require_POST
def gateway_rotate_password(request, team_slug, pk):
    """Rotate the MQTT password for a gateway."""
    import secrets

    from apps.telemetry.mqtt_publisher import publish_credential_rotation

    from .mqtt_provisioning import rotate_gateway_password

    gateway = Gateway.objects.get(pk=pk, team=request.team)

    if gateway.status != "online":
        return JsonResponse(
            {"error": "Gateway must be online to rotate password."}, status=400
        )

    new_password = secrets.token_urlsafe(32)

    # 1. Update Mosquitto dynsec client password
    rotate_gateway_password(gateway, new_password)

    # 2. Publish new credentials to Edge via provision topic
    publish_credential_rotation(gateway, new_password)

    # 3. Update Cloud DB
    gateway.mqtt_password = make_password(new_password)
    gateway.credential_rotation_status = "pending"
    gateway.save(update_fields=["mqtt_password", "credential_rotation_status"])

    logger.info("Password rotated for gateway %s", gateway.serial_number)

    # Return HTMX-friendly response
    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<div class="flex items-center gap-2 text-sm text-green-600 dark:text-green-400 font-medium">'
            '<i class="fa fa-check-circle"></i> Password rotated successfully. Gateway will reconnect shortly.'
            "</div>"
        )
    return JsonResponse({"status": "rotated", "gateway": gateway.serial_number})


@require_permission("manage_devices")
@require_POST
def gateway_send_rpc(request, team_slug, pk):
    """Send an RPC command to a gateway from the dashboard."""
    from apps.telemetry.mqtt_publisher import publish_rpc_command

    gateway = Gateway.objects.get(pk=pk, team=request.team)
    method = request.POST.get("method")
    params = json.loads(request.POST.get("params", "{}"))

    rpc = publish_rpc_command(gateway, method, params)

    return JsonResponse(
        {"request_id": str(rpc.request_id), "method": method, "status": "sent"}
    )


@require_permission("manage_devices")
@require_POST
def gateway_push_config(request, team_slug, pk):
    """Push a config update to a gateway."""
    from apps.telemetry.mqtt_publisher import publish_config_update

    gateway = Gateway.objects.get(pk=pk, team=request.team)
    action = request.POST.get("action", "full_update")
    config = json.loads(request.POST.get("config"))

    gateway.lifecycle_status = "commissioning"
    gateway.save(update_fields=["lifecycle_status"])

    config_record = publish_config_update(gateway, action, config)

    return JsonResponse(
        {"request_id": str(config_record.request_id), "action": action, "status": "sent"}
    )


@require_permission("view_devices")
def gateway_logs(request, team_slug, pk):
    """View gateway logs with optional level filter."""
    from apps.telemetry.models import GatewayLog

    gateway = Gateway.objects.get(pk=pk, team=request.team)
    level = request.GET.get("level")

    logs = GatewayLog.objects.filter(gateway=gateway)
    if level:
        logs = logs.filter(level=level)
    logs = logs[:200]

    return render(
        request,
        "devices/gateway_logs.html",
        {"gateway": gateway, "logs": logs, "current_level": level},
    )


@require_permission("view_devices")
def gateway_rpc_history(request, team_slug, pk):
    """View RPC command history for a gateway."""
    gateway = Gateway.objects.get(pk=pk, team=request.team)
    commands = RpcCommand.objects.filter(gateway=gateway)[:50]

    return render(
        request,
        "devices/gateway_rpc_history.html",
        {"gateway": gateway, "commands": commands},
    )


@require_permission("manage_devices")
@require_POST
def device_rpc_command(request, team_slug, gateway_pk, device_pk):
    """Send a write/read command to a device via its gateway using RPC."""
    from apps.telemetry.mqtt_publisher import publish_rpc_command

    gateway = Gateway.objects.get(pk=gateway_pk, team=request.team)
    device = Device.objects.get(pk=device_pk, gateway=gateway)

    method = request.POST.get("method")  # 'write_device' or 'read_device'
    params = json.loads(request.POST.get("params", "{}"))
    params["device_name"] = device.name  # Inject the device name

    rpc = publish_rpc_command(gateway, method, params)

    return JsonResponse(
        {
            "request_id": str(rpc.request_id),
            "method": method,
            "device": device.name,
            "status": "sent",
        }
    )


@require_permission("view_devices")
def device_rpc_status(request, team_slug, gateway_pk, device_pk, request_id):
    """Poll the status of an RPC command sent to a device."""
    rpc = RpcCommand.objects.filter(
        gateway__pk=gateway_pk,
        gateway__team=request.team,
        request_id=request_id,
    ).first()

    if not rpc:
        return JsonResponse({"status": "not_found", "result": None, "error": "RPC command not found"}, status=404)

    return JsonResponse(
        {
            "status": rpc.status,
            "result": rpc.result,
            "error": rpc.error_message or None,
        }
    )


@require_permission("view_devices")
def gateway_rpc_status(request, team_slug, gateway_pk, request_id):
    """Poll the status of an RPC command sent to a gateway."""
    rpc = RpcCommand.objects.filter(
        gateway__pk=gateway_pk,
        gateway__team=request.team,
        request_id=request_id,
    ).first()

    if not rpc:
        return JsonResponse({"status": "not_found", "result": None, "error": "RPC command not found"}, status=404)

    return JsonResponse(
        {
            "status": rpc.status,
            "result": rpc.result,
            "error": rpc.error_message or None,
        }
    )



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
        from apps.dashboard.services import build_device_dashboard_context
        from apps.subscriptions.enforcement import get_latency_limit_for_team
        from apps.telemetry.anomaly import get_ai_insights

        dashboard_context = build_device_dashboard_context(self.object)
        context.update(dashboard_context)
        context["ai_insights"] = get_ai_insights(self.object)
        context["recent_commands"] = self.object.commands.all().order_by("-requested_at")[:10]

        latency_limit_seconds = get_latency_limit_for_team(self.object.team)
        context["telemetry_fallback_interval_ms"] = int(max(5.0, latency_limit_seconds) * 1000)

        # Backward compatibility for existing control JavaScript/template code.
        context["writable_keys"] = [
            {"key": reg["key"], "label": reg["label"], "type": reg["config"].get("control", "toggle")}
            for reg in context["writable_registers"]
        ]

        if self.object.gateway_id:
            context["rpc_url"] = reverse_lazy(
                "web_team:devices:device_rpc_command",
                args=[self.request.team.slug, self.object.gateway_id, self.object.pk],
            )
        else:
            context["rpc_url"] = ""

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
        with contextlib.suppress(ValueError):
            value = float(value)

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
    discovery_entry = None
    suggested_templates = []
    if provision == "true" or resolve == "true":
        gateway = Gateway.objects.get(id=gateway_id)
        disc_devices = (gateway.discovery_data or {}).get("devices", [])
        for d in disc_devices:
            # Match by interface key (new format) or legacy port number
            d_key = str(d.get("interface") or d.get("port", ""))
            if d_key == str(port):
                discovery_entry = d
                prefill_data["name"] = d.get("signature", "New Device")
                
                # Check for pre-matched template from discovery
                if d.get("matched_template_id"):
                    first_tpl = DeviceTemplate.objects.filter(id=d["matched_template_id"]).first()
                    if first_tpl:
                        suggested_templates.append(first_tpl)
                
                # Fuzzy matches by signature
                sig = d.get("signature", "").lower()
                if sig and sig != "unknown":
                    from django.db.models import Q
                    other_tpls = DeviceTemplate.objects.filter(
                        Q(name__icontains=sig) | Q(manufacturer__icontains=sig)
                    ).exclude(id__in=[t.id for t in suggested_templates])[:3 - len(suggested_templates)]
                    suggested_templates.extend(other_tpls)
                
                if suggested_templates:
                    prefill_data["template_id"] = suggested_templates[0].id
                break

    if request.method == "POST":
        name = request.POST.get("name")
        template_id = request.POST.get("template_id")

        template = DeviceTemplate.objects.get(id=template_id)

        # If resolving, delete the old device on this port first
        if resolve == "true":
            Device.objects.filter(gateway_id=gateway_id, port=port).delete()

        # Build discovery_meta from the discovery entry
        disc_meta = {}
        if discovery_entry:
            disc_meta = {
                "interface": discovery_entry.get("interface"),
                "connection": discovery_entry.get("connection"),
                "slave_id": discovery_entry.get("slave_id"),
                "baud_rate": discovery_entry.get("baud_rate"),
                "signature": discovery_entry.get("signature"),
                "identification": discovery_entry.get("identification"),
            }

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
            discovery_meta=disc_meta,
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

        # Push updated connector config to the Edge gateway
        try:
            from .config_generator import generate_and_push_config

            gw = Gateway.objects.get(id=gateway_id)
            generate_and_push_config(gw)
        except Exception as e:
            logger.warning("Config push failed after device creation: %s", e)

        # Find first readable register for connection test
        test_register = None
        if template.register_map:
            for key, config in template.register_map.items():
                if isinstance(config, dict) and not config.get("writable"):
                    test_register = {
                        "key": key,
                        "address": config.get("address", 0),
                        "functionCode": config.get("functionCode", 3),
                        "type": config.get("type", "uint16"),
                        "unit": config.get("unit", ""),
                        "objectsCount": config.get("objectsCount", 1),
                    }
                    break

        response = render(request, "devices/partials/device_quick_add_success.html", {
            "device": device,
            "test_register": test_register,
        })
        response["HX-Trigger"] = "infrastructureChanged"
        return response

    templates = DeviceTemplate.objects.all()[:10]
    context = {
        "templates": templates,
        "suggested_templates": suggested_templates,
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
        from .discovery_matching import enrich_discovered_device

        discovered = [enrich_discovered_device(device) for device in discovered]

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


import uuid
from django.core.cache import cache
from django.db.models import Q
from .tasks import generate_template_ai_task
from .template_ai import save_approved_template

@require_permission("manage_devices")
@require_POST
def ai_template_generate(request, team_slug):
    manufacturer = request.POST.get("manufacturer", "").strip()
    model_number = request.POST.get("model_number", "").strip()
    doc_url = request.POST.get("doc_url", "").strip() or None

    if not manufacturer or not model_number:
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "error",
            "error": "Both Manufacturer and Model Number are required."
        })

    # Check for existing template first (case-insensitive)
    existing = DeviceTemplate.objects.filter(
        manufacturer__iexact=manufacturer,
        model_number__iexact=model_number,
    ).first()
    if existing:
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "found_existing",
            "template": existing
        })

    # Kick off async task
    task_id = str(uuid.uuid4())
    # Initialize cache status to processing
    cache.set(f"ai_template:{task_id}", {"status": "processing"}, timeout=300)
    generate_template_ai_task.delay(task_id, manufacturer, model_number, doc_url=doc_url)
    return render(request, "devices/partials/ai_template_loading.html", {"task_id": task_id})


@require_permission("manage_devices")
def ai_template_status(request, team_slug, task_id):
    result = cache.get(f"ai_template:{task_id}")
    if not result or result.get("status") == "processing":
        # HTMX will poll this again
        return render(request, "devices/partials/ai_template_loading.html", {"task_id": task_id})
    elif result.get("status") == "complete":
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "draft",
            "draft": result["draft"],
            "task_id": task_id
        })
    else:
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "error",
            "error": result.get("error", "AI template generation failed or timed out.")
        })


@require_permission("manage_devices")
@require_POST
def ai_template_approve(request, team_slug):
    task_id = request.POST.get("task_id")
    result = cache.get(f"ai_template:{task_id}")
    if not result or result.get("status") != "complete" or "draft" not in result:
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "error",
            "error": "Template draft expired or not found. Please try generating again."
        })

    try:
        # Get team context from request
        team = getattr(request, "team", None)
        template = save_approved_template(result["draft"], team=team)
        
        # Clear cache
        cache.delete(f"ai_template:{task_id}")
        
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "approved",
            "template": template
        })
    except Exception as e:
        logger.exception("Failed to save approved template")
        return render(request, "devices/partials/ai_template_result.html", {
            "status": "error",
            "error": f"Failed to save template: {e}"
        })


class TemplateLibraryView(PermissionRequiredMixin, ListView):
    permission_required = "view_devices"
    model = DeviceTemplate
    template_name = "devices/template_library.html"
    context_object_name = "templates"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        protocol = self.request.GET.get("protocol", "").strip()
        category = self.request.GET.get("category", "").strip()
        verified_only = self.request.GET.get("verified_only", "") == "true"

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(manufacturer__icontains=q) | Q(model_number__icontains=q))
        if protocol:
            qs = qs.filter(protocol=protocol)
        if category:
            qs = qs.filter(category=category)
        if verified_only:
            qs = qs.filter(is_verified=True)

        return qs.order_by("-is_verified", "-usage_count")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["active_tab"] = "templates"
        context["search_query"] = self.request.GET.get("q", "")
        context["selected_protocol"] = self.request.GET.get("protocol", "")
        context["selected_category"] = self.request.GET.get("category", "")
        context["verified_only"] = self.request.GET.get("verified_only", "") == "true"
        context["protocols"] = DeviceTemplate.PROTOCOL_CHOICES
        context["categories"] = DeviceTemplate.VERTICAL_CHOICES
        return context


@require_permission("manage_devices")
@require_POST
def gateway_ota_update(request, team_slug, pk):
    """Trigger an OTA Firmware update on the gateway."""
    from apps.telemetry.mqtt_publisher import publish_rpc_command
    from .models import FirmwareRelease

    gateway = Gateway.objects.get(pk=pk, team=request.team)
    version = request.POST.get("version")

    release = FirmwareRelease.objects.filter(version=version, is_active=True).first()
    if not release:
        return HttpResponse("Firmware release not found.", status=404)

    url = request.build_absolute_uri(release.file.url)
    sha256 = release.sha256
    if not sha256 and release.file:
        import hashlib

        h = hashlib.sha256()
        release.file.open("rb")
        try:
            for chunk in iter(lambda: release.file.read(1024 * 1024), b""):
                h.update(chunk)
        finally:
            release.file.close()
        sha256 = h.hexdigest()
        release.sha256 = sha256
        release.size_bytes = release.file.size
        release.save(update_fields=["sha256", "size_bytes"])

    params = {
        "version": release.version,
        "url": url,
        "sha256": sha256,
        "token": "novena_internal_token_mock",
    }

    rpc = publish_rpc_command(gateway, "update_firmware", params)

    return HttpResponse(
        f'<div class="p-4 bg-blue-50 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 rounded-xl flex items-center gap-3">'
        f'<i class="fa fa-spinner fa-spin"></i>'
        f'<div>'
        f'<p class="font-bold">Update Initiated</p>'
        f'<p class="text-sm opacity-90">Sending v{release.version} to gateway. Do not disconnect power.</p>'
        f'</div>'
        f'</div>'
    )
