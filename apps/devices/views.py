import json
import logging
import uuid
import csv
from datetime import datetime

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.teams.decorators import require_permission
from apps.teams.mixins import PermissionRequiredMixin

from .models import (
    ControlActivation,
    ControlReadinessAssessment,
    Device,
    DeviceTemplate,
    Gateway,
    GatewayConfig,
    RemoteCommand,
    RemoteCommandApproval,
    RpcCommand,
    Site,
)
from .services import gateways_for_team, sites_for_team, visible_templates_for_team
from .tasks import generate_template_ai_task
from .template_ai import save_approved_template

logger = logging.getLogger("novena_hub")


@require_permission("view_command_audit")
def gateway_control_center(request, pk):
    gateway = get_object_or_404(Gateway, pk=pk, team=request.team)
    return render(
        request,
        "devices/control_center.html",
        {
            "gateway": gateway,
            "assessment": gateway.control_readiness_assessments.order_by("-assessed_at").first(),
            "activations": ControlActivation.objects.filter(
                team=request.team,
                device__gateway=gateway,
            ).select_related("device"),
            "approvals": RemoteCommandApproval.objects.filter(
                command__team=request.team,
                command__gateway=gateway,
                status=RemoteCommandApproval.Status.PENDING,
            ).select_related("command", "command__device"),
            "commands": RemoteCommand.objects.filter(
                team=request.team,
                gateway=gateway,
            ).prefetch_related("events")[:100],
        },
    )


@require_POST
@require_permission("toggle_remote_control")
def gateway_emergency_disable(request, pk):
    gateway = get_object_or_404(Gateway, pk=pk, team=request.team)
    from .control_readiness import emergency_disable

    epoch = emergency_disable(
        team=request.team,
        actor=request.user,
        reason=request.POST.get("reason", "Emergency disable from control center"),
        gateway=gateway,
    )
    return JsonResponse(
        {
            "status": "disabled_at_hub",
            "control_epoch": epoch,
            "gateway_acknowledged": False,
            "message": "Hub dispatch is blocked immediately. Gateway acknowledgement is pending.",
        }
    )


@require_POST
@require_permission("approve_high_risk_commands")
def remote_command_approve(request, command_id):
    command = get_object_or_404(RemoteCommand, pk=command_id, team=request.team)
    recent_value = request.session.get("remote_control_recent_auth_at")
    recent_auth_at = datetime.fromisoformat(recent_value) if recent_value else None
    mfa_value = request.session.get("remote_control_mfa_verified_at")
    mfa_verified = bool(mfa_value)
    from .control_readiness import ReadinessDenied, approve_command

    try:
        approve_command(
            command=command,
            approver=request.user,
            mfa_verified=mfa_verified,
            recent_auth_at=recent_auth_at,
            reason=request.POST.get("reason", ""),
        )
    except ReadinessDenied as exc:
        return JsonResponse({"error": str(exc), "code": exc.code}, status=409)
    return JsonResponse({"status": "queued_for_dispatch", "command_id": str(command.pk)})


@require_permission("export_command_audit")
def command_audit_export(request, format):
    commands = RemoteCommand.objects.filter(team=request.team).select_related(
        "gateway",
        "device",
        "requested_by",
    )
    records = [
        {
            "command_id": str(command.pk),
            "requested_at": command.created_at.isoformat(),
            "requester": command.actor_snapshot.get("email", ""),
            "gateway": command.gateway.serial_number,
            "device": command.device.name if command.device_id else "",
            "operation": command.operation,
            "command_key": command.command_key,
            "requested_value": command.requested_value,
            "status": command.status,
            "error_code": command.error_code,
            "error_message": command.error_message,
        }
        for command in commands
    ]
    if format == "json":
        return JsonResponse({"commands": records})
    if format != "csv":
        raise Http404
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="remote-command-audit.csv"'
    fields = list(records[0]) if records else [
        "command_id",
        "requested_at",
        "requester",
        "gateway",
        "device",
        "operation",
        "command_key",
        "requested_value",
        "status",
        "error_code",
        "error_message",
    ]
    writer = csv.DictWriter(response, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)
    return response


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
                    if (
                        sig
                        and sig.lower() not in reg_device.name.lower()
                        and sig.lower() not in reg_device.device_type.lower()
                    ):
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
    fields = ["name", "solution_profile", "site_type", "address", "latitude", "longitude", "timezone"]
    template_name = "devices/site_form.html"

    def form_valid(self, form):
        form.instance.team = self.request.team
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("web_team:devices:site_list", args=[self.request.team.slug])


class SiteUpdateView(PermissionRequiredMixin, UpdateView):
    permission_required = "manage_devices"
    model = Site
    fields = ["name", "solution_profile", "site_type", "address", "latitude", "longitude", "timezone"]
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
            context["ota_signing_ready"] = latest_release.is_signed or bool(
                getattr(settings, "NOVENA_OTA_SIGNING_PRIVATE_KEY", "")
            )

        return context


class GatewayCreateView(PermissionRequiredMixin, CreateView):
    permission_required = "manage_devices"
    model = Gateway
    fields = ["site", "name", "serial_number"]
    template_name = "devices/gateway_form.html"

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["site"].queryset = sites_for_team(self.request.team)
        return form

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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["site"].queryset = sites_for_team(self.request.team)
        return form

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
        return JsonResponse({"error": "Gateway must be online to rotate password."}, status=400)

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


@require_permission("request_low_risk_commands")
@require_POST
def gateway_send_rpc(request, team_slug, pk):
    """Send an RPC command to a gateway from the dashboard."""
    from .remote_control import CommandDenied, request_remote_command

    gateway = Gateway.objects.get(pk=pk, team=request.team)
    method = request.POST.get("method")
    if method == "update_firmware":
        return JsonResponse(
            {"error": "Firmware updates must use the signed OTA release endpoint."},
            status=400,
        )
    try:
        params = json.loads(request.POST.get("params", "{}"))
        command = request_remote_command(
            gateway=gateway,
            operation=method,
            requested_by=request.user,
            params=params,
            reason=request.POST.get("reason", ""),
        )
    except (CommandDenied, json.JSONDecodeError) as exc:
        return JsonResponse(
            {"error": str(exc), "code": getattr(exc, "code", "invalid_request")},
            status=403 if getattr(exc, "code", "") == "permission_denied" else 400,
        )

    return JsonResponse({"command_id": str(command.pk), "method": method, "status": command.status})


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

    return JsonResponse({"request_id": str(config_record.request_id), "action": action, "status": "sent"})


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


@require_permission("request_low_risk_commands")
@require_POST
def device_rpc_command(request, team_slug, gateway_pk, device_pk):
    """Compatibility endpoint: routes customer device RPC through DeviceCommand audit."""
    from .services import send_device_command

    gateway = Gateway.objects.get(pk=gateway_pk, team=request.team)
    device = Device.objects.get(pk=device_pk, gateway=gateway)

    method = request.POST.get("method")  # 'write_device' or 'read_device'
    params = json.loads(request.POST.get("params", "{}"))
    command_type = "read" if method == "read_device" else "write"
    key = params.pop("command_key", f"manual_{command_type}")
    value = params.get("value")
    command = send_device_command(device, request.user, key, value, command_type=command_type)

    return JsonResponse(
        {
            "request_id": str(command.rpc_command.request_id) if command.rpc_command else None,
            "transaction_id": str(command.transaction_id),
            "method": method,
            "device": device.name,
            "status": command.status,
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
        context["remote_control_enabled"] = (
            self.request.team.remote_control_mode == self.request.team.RemoteControlMode.CONTROLLED
        )

        latency_limit_seconds = get_latency_limit_for_team(self.object.team)
        context["telemetry_fallback_interval_ms"] = int(max(5.0, latency_limit_seconds) * 1000)

        # Backward compatibility for existing control JavaScript/template code.
        context["writable_keys"] = [
            {"key": reg["key"], "label": reg["label"], "type": reg["config"].get("control", "toggle")}
            for reg in context["writable_registers"]
        ]

        if self.object.gateway_id:
            context["command_url"] = reverse_lazy(
                "web_team:devices:device_send_command",
                args=[self.request.team.slug, self.object.pk],
            )
            context["rpc_url"] = reverse_lazy(
                "web_team:devices:device_rpc_command",
                args=[self.request.team.slug, self.object.gateway_id, self.object.pk],
            )
        else:
            context["command_url"] = ""
            context["rpc_url"] = ""

        return context


# ... existing views ...


@require_permission("request_low_risk_commands")
def device_send_command(request, team_slug, pk):
    from django.shortcuts import get_object_or_404

    device = get_object_or_404(Device, pk=pk, team=request.team)
    command_type = request.POST.get("command_type") or request.POST.get("type") or "write"
    method = request.POST.get("method", "")
    if method == "read_device":
        command_type = "read"
    elif method == "write_device":
        command_type = "write"
    key = request.POST.get("key") or request.POST.get("command_key") or f"manual_{command_type}"
    raw_value = request.POST.get("value")
    if request.POST.get("params"):
        submitted = json.loads(request.POST.get("params", "{}"))
        key = submitted.get("command_key", key)

    try:
        from .services import send_device_command

        command = send_device_command(
            device,
            request.user,
            key,
            raw_value,
            command_type=command_type,
        )
        if request.headers.get("HX-Request"):
            return render(request, "devices/partials/command_status_badge.html", {"command": command})
        return JsonResponse(
            {
                "transaction_id": str(command.transaction_id),
                "status": command.status,
                "command_type": command.command_type,
                "command_key": command.command_key,
                "rpc_request_id": str(command.rpc_command.request_id) if command.rpc_command else None,
            }
        )
    except Exception as e:
        if request.headers.get("HX-Request"):
            return HttpResponse(f'<span class="text-error text-xs font-bold">{str(e)}</span>', status=400)
        return JsonResponse({"error": str(e)}, status=400)


@require_permission("view_devices")
def device_command_status(request, team_slug, pk, tx_id):
    from django.shortcuts import get_object_or_404

    from .models import DeviceCommand

    command = get_object_or_404(DeviceCommand, transaction_id=tx_id, team=request.team)
    if request.GET.get("format") == "json" or "application/json" in request.headers.get("Accept", ""):
        result = command.response_payload.get("result") if isinstance(command.response_payload, dict) else None
        return JsonResponse(
            {
                "transaction_id": str(command.transaction_id),
                "status": command.status,
                "command_type": command.command_type,
                "command_key": command.command_key,
                "result": result,
                "response_payload": command.response_payload,
                "error": command.error_message or None,
            }
        )
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

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["gateway"].queryset = gateways_for_team(self.request.team)
        form.fields["site"].queryset = sites_for_team(self.request.team)
        form.fields["template"].queryset = visible_templates_for_team(self.request.team)
        return form

    def form_valid(self, form):
        gateway = form.cleaned_data.get("gateway")
        site = form.cleaned_data.get("site")
        if gateway and site and gateway.site_id != site.id:
            form.add_error("gateway", "Select a gateway that belongs to the selected site.")
            return self.form_invalid(form)
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


def _resolve_quick_add_gateway_and_site(team, gateway_id, site_id=None, lock_gateway=False):
    gateway_qs = gateways_for_team(team).select_related("site")
    if lock_gateway:
        gateway_qs = gateway_qs.select_for_update()

    gateway = get_object_or_404(gateway_qs, id=gateway_id)
    if site_id:
        site = get_object_or_404(sites_for_team(team), id=site_id)
        if gateway.site_id != site.id:
            raise Http404("Gateway does not belong to the selected site.")
        return gateway, site
    return gateway, gateway.site


def _discovery_entry_for_port(gateway, port):
    for discovered in (gateway.discovery_data or {}).get("devices", []):
        discovered_key = str(discovered.get("interface") or discovered.get("port", ""))
        if discovered_key == str(port):
            return discovered
    return None


def _first_readable_register(template):
    if not template.register_map:
        return None
    for key, config in template.register_map.items():
        if isinstance(config, dict) and not config.get("writable"):
            return {
                "key": key,
                "address": config.get("address", 0),
                "functionCode": config.get("functionCode", 3),
                "type": config.get("type", "uint16"),
                "unit": config.get("unit", ""),
                "objectsCount": config.get("objectsCount", 1),
            }
    return None


def _push_gateway_config_after_commit(gateway_id, team_id):
    try:
        from .config_generator import generate_and_push_config

        gateway = Gateway.objects.get(id=gateway_id, team_id=team_id)
        generate_and_push_config(gateway)
    except Exception as e:
        logger.warning("Config push failed after device creation: %s", e)


@require_permission("manage_devices")
def htmx_device_create(request, team_slug):
    gateway_id = request.GET.get("gateway_id")
    site_id = request.GET.get("site_id")
    port = request.GET.get("port")
    provision = request.GET.get("provision")
    resolve = request.GET.get("resolve")

    gateway, site = _resolve_quick_add_gateway_and_site(request.team, gateway_id, site_id)
    template_qs = visible_templates_for_team(request.team)

    prefill_data = {}
    discovery_entry = None
    suggested_templates = []
    if provision == "true" or resolve == "true":
        discovery_entry = _discovery_entry_for_port(gateway, port)
        if discovery_entry:
            prefill_data["name"] = discovery_entry.get("signature", "New Device")

            if discovery_entry.get("matched_template_id"):
                first_tpl = template_qs.filter(id=discovery_entry["matched_template_id"]).first()
                if first_tpl:
                    suggested_templates.append(first_tpl)

            sig = discovery_entry.get("signature", "").lower()
            if sig and sig != "unknown":
                other_tpls = template_qs.filter(Q(name__icontains=sig) | Q(manufacturer__icontains=sig)).exclude(
                    id__in=[template.id for template in suggested_templates]
                )[: 3 - len(suggested_templates)]
                suggested_templates.extend(other_tpls)

            if suggested_templates:
                prefill_data["template_id"] = suggested_templates[0].id

    if request.method == "POST":
        name = request.POST.get("name")
        template_id = request.POST.get("template_id")

        with transaction.atomic():
            gateway, site = _resolve_quick_add_gateway_and_site(request.team, gateway_id, site_id, lock_gateway=True)
            if provision == "true" or resolve == "true":
                discovery_entry = _discovery_entry_for_port(gateway, port)
            template = get_object_or_404(visible_templates_for_team(request.team), id=template_id)

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

            if resolve == "true":
                Device.objects.filter(team=request.team, site=site, gateway=gateway, port=port).delete()

            device = Device.objects.create(
                team=request.team,
                site=site,
                gateway=gateway,
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
            transaction.on_commit(lambda: _push_gateway_config_after_commit(gateway.id, request.team.id))

        test_register = _first_readable_register(template)

        response = render(
            request,
            "devices/partials/device_quick_add_success.html",
            {
                "device": device,
                "test_register": test_register,
            },
        )
        response["HX-Trigger"] = "infrastructureChanged"
        return response

    templates = template_qs.order_by("-is_verified", "-usage_count")[:10]
    context = {
        "templates": templates,
        "suggested_templates": suggested_templates,
        "gateway": gateway,
        "gateway_id": gateway.id,
        "site_id": site.id,
        "port": port,
        "prefill": prefill_data,
        "resolve": resolve,
    }
    return render(request, "devices/partials/device_quick_add_form.html", context)


@require_permission("view_devices")
def template_library_search(request, team_slug):
    query = request.GET.get("q", "")
    templates = visible_templates_for_team(request.team).filter(
        Q(name__icontains=query) | Q(manufacturer__icontains=query)
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


@require_permission("manage_devices")
@require_POST
def ai_template_generate(request, team_slug):
    manufacturer = request.POST.get("manufacturer", "").strip()
    model_number = request.POST.get("model_number", "").strip()
    doc_url = request.POST.get("doc_url", "").strip() or None

    if not manufacturer or not model_number:
        return render(
            request,
            "devices/partials/ai_template_result.html",
            {"status": "error", "error": "Both Manufacturer and Model Number are required."},
        )

    # Check for existing template first (case-insensitive)
    existing = DeviceTemplate.objects.filter(
        manufacturer__iexact=manufacturer,
        model_number__iexact=model_number,
    ).first()
    if existing:
        return render(
            request, "devices/partials/ai_template_result.html", {"status": "found_existing", "template": existing}
        )

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
        return render(
            request,
            "devices/partials/ai_template_result.html",
            {"status": "draft", "draft": result["draft"], "task_id": task_id},
        )
    else:
        return render(
            request,
            "devices/partials/ai_template_result.html",
            {"status": "error", "error": result.get("error", "AI template generation failed or timed out.")},
        )


@require_permission("manage_devices")
@require_POST
def ai_template_approve(request, team_slug):
    task_id = request.POST.get("task_id")
    result = cache.get(f"ai_template:{task_id}")
    if not result or result.get("status") != "complete" or "draft" not in result:
        return render(
            request,
            "devices/partials/ai_template_result.html",
            {"status": "error", "error": "Template draft expired or not found. Please try generating again."},
        )

    try:
        # Get team context from request
        team = getattr(request, "team", None)
        template = save_approved_template(result["draft"], team=team)

        # Clear cache
        cache.delete(f"ai_template:{task_id}")

        return render(request, "devices/partials/ai_template_result.html", {"status": "approved", "template": template})
    except Exception as e:
        logger.exception("Failed to save approved template")
        return render(
            request,
            "devices/partials/ai_template_result.html",
            {"status": "error", "error": f"Failed to save template: {e}"},
        )


class TemplateLibraryView(PermissionRequiredMixin, ListView):
    permission_required = "view_devices"
    model = DeviceTemplate
    template_name = "devices/template_library.html"
    context_object_name = "templates"

    def get_queryset(self):
        from apps.devices.solution_profiles import get_profile, rank_templates_for_profile

        qs = visible_templates_for_team(self.request.team)
        q = self.request.GET.get("q", "").strip()
        protocol = self.request.GET.get("protocol", "").strip()
        category = self.request.GET.get("category", "").strip()
        profile_key = self.request.GET.get("profile", "").strip()
        verified_only = self.request.GET.get("verified_only", "") == "true"

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(manufacturer__icontains=q) | Q(model_number__icontains=q))
        if protocol:
            qs = qs.filter(protocol=protocol)
        if category:
            qs = qs.filter(category=category)
        if verified_only:
            qs = qs.filter(is_verified=True)

        if profile_key:
            return rank_templates_for_profile(qs, get_profile(profile_key))
        return qs.order_by("-is_verified", "-usage_count")

    def get_context_data(self, **kwargs):
        from apps.devices.solution_profiles import PROFILES

        context = super().get_context_data(**kwargs)
        context["active_tab"] = "templates"
        context["search_query"] = self.request.GET.get("q", "")
        context["selected_protocol"] = self.request.GET.get("protocol", "")
        context["selected_category"] = self.request.GET.get("category", "")
        context["selected_profile"] = self.request.GET.get("profile", "")
        context["verified_only"] = self.request.GET.get("verified_only", "") == "true"
        context["protocols"] = DeviceTemplate.PROTOCOL_CHOICES
        context["categories"] = DeviceTemplate.VERTICAL_CHOICES
        context["solution_profiles"] = PROFILES.values()
        return context


@require_permission("send_critical_commands")
@require_POST
def gateway_ota_update(request, team_slug, pk):
    """Trigger an OTA Firmware update on the gateway."""
    from .models import FirmwareRelease
    from .ota_signing import ensure_release_signed
    from .remote_control import CommandDenied, request_remote_command

    gateway = Gateway.objects.get(pk=pk, team=request.team)
    version = request.POST.get("version")

    release = FirmwareRelease.objects.filter(version=version, is_active=True).first()
    if not release:
        return JsonResponse({"error": "Firmware release not found."}, status=404)

    url = request.build_absolute_uri(release.file.url)
    try:
        release = ensure_release_signed(release, url)
    except ValidationError as e:
        message = "; ".join(e.messages) if hasattr(e, "messages") else str(e)
        return JsonResponse({"error": f"Firmware release is not signed: {message}"}, status=400)

    params = {
        "manifest": release.manifest,
        "signature": release.signature,
    }

    try:
        command = request_remote_command(
            gateway=gateway,
            operation="update_firmware",
            requested_by=request.user,
            params=params,
            reason=request.POST.get("reason", f"Install signed firmware {release.version}"),
        )
    except CommandDenied as exc:
        return JsonResponse({"error": str(exc), "code": exc.code}, status=400)

    return JsonResponse({"command_id": str(command.pk), "version": release.version, "status": command.status})
