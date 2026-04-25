import secrets

from django.shortcuts import get_object_or_404, redirect, render

from apps.alerts.models import AlertRule
from apps.devices.models import Device, DeviceTemplate, Gateway, Site
from apps.teams.decorators import require_permission

ONBOARDING_STEPS = [
    {"num": 1, "label": "Site"},
    {"num": 2, "label": "Gateway"},
    {"num": 3, "label": "Device"},
    {"num": 4, "label": "Alert"},
]


@require_permission("manage_devices")
def onboarding_start(request, team_slug):
    if Site.objects.filter(team=request.team).exists():
        return redirect("web_team:home", team_slug=team_slug)
    return render(request, "onboarding/welcome.html")


@require_permission("manage_devices")
def step_1_site(request, team_slug):
    site_id = request.session.get("onboarding_site_id")
    site = Site.objects.filter(id=site_id, team=request.team).first() if site_id else None

    if request.method == "POST":
        name = request.POST.get("name")
        address = request.POST.get("address", "")
        if name:
            if site:
                site.name = name
                site.address = address
                site.save()
            else:
                site = Site.objects.create(team=request.team, name=name, address=address)
            request.session["onboarding_site_id"] = site.id
            if request.session.get("setup_mode"):
                return redirect("web_team:onboarding:step_connectivity", team_slug=team_slug)
            return redirect("web_team:onboarding:step_2_gateway", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 1, "site": site}
    return render(request, "onboarding/step_1_site.html", context)


@require_permission("manage_devices")
def step_2_gateway(request, team_slug):
    from apps.devices.mqtt_provisioning import provision_gateway_mqtt
    from apps.devices.services import validate_claim_code

    site_id = request.session.get("onboarding_site_id")
    if not site_id:
        return redirect("web_team:onboarding:step_1_site", team_slug=team_slug)
    site = get_object_or_404(Site, id=site_id, team=request.team)

    gateway_id = request.session.get("onboarding_gateway_id")
    gateway = Gateway.objects.filter(id=gateway_id, team=request.team).first() if gateway_id else None

    if request.method == "POST":
        name = request.POST.get("name")
        sn = request.POST.get("serial_number", "").strip().upper()
        claim_code = request.POST.get("claim_code", "").strip().upper()

        error = None
        if not name or not sn:
            error = "Gateway name and serial number are required."
        elif len(sn) < 3 or len(sn) > 50:
            error = "Serial number must be between 3 and 50 characters."
        elif not claim_code:
            error = "Claim code is required. Check the sticker on the bottom of your gateway."
        elif not validate_claim_code(sn, claim_code):
            error = "Invalid claim code. Please check the sticker on the bottom of your gateway."

        if error:
            context = {
                "steps": ONBOARDING_STEPS,
                "current_step": 2,
                "site": site,
                "gateway": gateway,
                "error": error,
            }
            return render(request, "onboarding/step_2_gateway.html", context)

        # Check for existing gateway with same serial number
        existing_gateway = Gateway.objects.filter(serial_number=sn).first()
        if existing_gateway:
            if existing_gateway.team == request.team:
                existing_gateway.site = site
                existing_gateway.name = name
                existing_gateway.save()
                request.session["onboarding_gateway_id"] = existing_gateway.id
                return redirect("web_team:onboarding:step_2b_wait", team_slug=team_slug)
            else:
                context = {
                    "steps": ONBOARDING_STEPS,
                    "current_step": 2,
                    "site": site,
                    "gateway": gateway,
                    "error": (
                        "This Serial Number is already registered to another team. "
                        "Please contact support if you believe this is an error."
                    ),
                }
                return render(request, "onboarding/step_2_gateway.html", context)

        # Create new gateway with claim code as MQTT password
        mqtt_password = claim_code.upper()
        if gateway:
            gateway.name = name
            gateway.serial_number = sn
            gateway.mqtt_username = sn
            gateway.mqtt_password = mqtt_password
            gateway.save()
        else:
            gateway = Gateway.objects.create(
                team=request.team,
                site=site,
                name=name,
                serial_number=sn,
                access_token=secrets.token_hex(20),
                mqtt_username=sn,
                mqtt_password=mqtt_password,
            )

        # Provision MQTT credentials on Mosquitto
        try:
            provision_gateway_mqtt(gateway, mqtt_password)
        except Exception:
            pass  # Non-blocking — Edge will connect once Mosquitto is available

        request.session["onboarding_gateway_id"] = gateway.id
        return redirect("web_team:onboarding:step_2b_wait", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 2, "site": site, "gateway": gateway}
    return render(request, "onboarding/step_2_gateway.html", context)


@require_permission("manage_devices")
def step_2b_wait(request, team_slug):
    """Intermediate step: wait for the gateway to come online after claiming."""
    gateway_id = request.session.get("onboarding_gateway_id")
    if not gateway_id:
        return redirect("web_team:onboarding:step_2_gateway", team_slug=team_slug)
    gateway = get_object_or_404(Gateway, id=gateway_id, team=request.team)

    # If already online, skip straight to discovery step
    if gateway.status == "online":
        return redirect("web_team:onboarding:step_3_discover", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 2, "gateway": gateway}
    return render(request, "onboarding/step_2b_wait.html", context)


@require_permission("view_devices")
def gateway_status_poll(request, team_slug):
    """HTMX endpoint: returns a small HTML fragment with current gateway status."""
    gateway_id = request.session.get("onboarding_gateway_id")
    if not gateway_id:
        return render(request, "onboarding/partials/gateway_status_badge.html", {"status": "unknown"})
    gateway = Gateway.objects.filter(id=gateway_id, team=request.team).first()
    status = gateway.status if gateway else "unknown"
    return render(request, "onboarding/partials/gateway_status_badge.html", {"status": status, "gateway": gateway})


@require_permission("manage_devices")
def step_3_discover(request, team_slug):
    """Discovery-based bulk device provisioning step (gateway connectivity path)."""
    from apps.devices.config_generator import generate_and_push_config

    gateway_id = request.session.get("onboarding_gateway_id")
    site_id = request.session.get("onboarding_site_id")
    if not gateway_id:
        return redirect("web_team:onboarding:step_2_gateway", team_slug=team_slug)
    gateway = get_object_or_404(Gateway, id=gateway_id, team=request.team)

    discovery_data = gateway.discovery_data or {}
    discovered_devices = discovery_data.get("devices", [])
    templates = DeviceTemplate.objects.all()

    if request.method == "POST":
        # Bulk provision: process each selected discovered device
        provisioned_count = 0
        device_indices = request.POST.getlist("device_index")

        for idx in device_indices:
            name = request.POST.get(f"name_{idx}", "").strip()
            template_id = request.POST.get(f"template_{idx}")
            if not name or not template_id:
                continue

            try:
                template = DeviceTemplate.objects.get(id=template_id)
            except DeviceTemplate.DoesNotExist:
                continue

            disc = discovered_devices[int(idx)] if int(idx) < len(discovered_devices) else {}
            port_key = disc.get("interface") or disc.get("port", "")

            disc_meta = {
                "interface": disc.get("interface"),
                "connection": disc.get("connection"),
                "slave_id": disc.get("slave_id"),
                "baud_rate": disc.get("baud_rate"),
                "signature": disc.get("signature"),
                "identification": disc.get("identification"),
            }

            Device.objects.create(
                team=request.team,
                gateway=gateway,
                site_id=site_id,
                port=str(port_key),
                name=name,
                template=template,
                device_type=template.device_type,
                protocol=template.protocol,
                connection_config=template.register_map,
                discovery_meta=disc_meta,
            )
            provisioned_count += 1

        # Push connector config to Edge after bulk provisioning
        if provisioned_count > 0:
            try:
                generate_and_push_config(gateway)
            except Exception:
                pass

        # Store first device for the alert step
        first_device = gateway.devices.first()
        if first_device:
            request.session["onboarding_device_id"] = first_device.id

        return redirect("web_team:onboarding:step_4_alert", team_slug=team_slug)

    context = {
        "steps": ONBOARDING_STEPS,
        "current_step": 3,
        "gateway": gateway,
        "discovered_devices": discovered_devices,
        "templates": templates,
    }
    return render(request, "onboarding/step_3_discover.html", context)


@require_permission("view_devices")
def discovery_poll(request, team_slug):
    """HTMX endpoint: returns discovery device list fragment."""
    gateway_id = request.session.get("onboarding_gateway_id")
    if not gateway_id:
        return render(request, "onboarding/partials/discovery_devices.html", {"discovered_devices": []})
    gateway = Gateway.objects.filter(id=gateway_id, team=request.team).first()
    discovered_devices = (gateway.discovery_data or {}).get("devices", []) if gateway else []
    templates = DeviceTemplate.objects.all()
    return render(request, "onboarding/partials/discovery_devices.html", {
        "discovered_devices": discovered_devices,
        "templates": templates,
        "gateway": gateway,
    })


@require_permission("manage_devices")
def step_3_device(request, team_slug):
    gateway_id = request.session.get("onboarding_gateway_id")
    site_id = request.session.get("onboarding_site_id")
    if not gateway_id:
        return redirect("web_team:onboarding:step_2_gateway", team_slug=team_slug)
    gateway = get_object_or_404(Gateway, id=gateway_id, team=request.team)

    device_id = request.session.get("onboarding_device_id")
    device = Device.objects.filter(id=device_id, team=request.team).first() if device_id else None

    templates = DeviceTemplate.objects.all()

    if request.method == "POST":
        name = request.POST.get("name")
        template_id = request.POST.get("template")
        if name:
            template = None
            if template_id:
                template = DeviceTemplate.objects.get(id=template_id)

            if device:
                device.name = name
                device.template = template
                device.device_type = template.device_type if template else "sensor"
                device.protocol = template.protocol if template else "modbus_tcp"
                device.save()
            else:
                device = Device.objects.create(
                    team=request.team,
                    gateway=gateway,
                    site_id=site_id,
                    name=name,
                    template=template,
                    device_type=template.device_type if template else "sensor",
                    protocol=template.protocol if template else "modbus_tcp",
                )
            request.session["onboarding_device_id"] = device.id
            return redirect("web_team:onboarding:step_4_alert", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 3, "templates": templates, "device": device}
    return render(request, "onboarding/step_3_device.html", context)


@require_permission("manage_alerts")
def step_4_alert(request, team_slug):
    device_id = request.session.get("onboarding_device_id")
    if not device_id:
        return redirect("web_team:onboarding:step_3_device", team_slug=team_slug)
    device = get_object_or_404(Device, id=device_id, team=request.team)

    # Alert rules are often multiple, but for the wizard we usually just handle one.
    existing_rule = AlertRule.objects.filter(device=device).first()

    if request.method == "POST":
        key = request.POST.get("key", "active_power")
        threshold = request.POST.get("threshold")
        if threshold:
            if existing_rule:
                existing_rule.telemetry_key = key
                existing_rule.threshold = float(threshold)
                existing_rule.name = f"{device.name} High {key.replace('_', ' ').title()}"
                existing_rule.save()
            else:
                AlertRule.objects.create(
                    team=request.team,
                    device=device,
                    name=f"{device.name} High {key.replace('_', ' ').title()}",
                    telemetry_key=key,
                    condition="gt",
                    threshold=float(threshold),
                    severity="critical",
                )
            return redirect("web_team:onboarding:complete", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 4, "device": device, "rule": existing_rule}
    return render(request, "onboarding/step_4_alert.html", context)


@require_permission("manage_devices")
def complete(request, team_slug):
    for key in [
        "onboarding_site_id",
        "onboarding_gateway_id",
        "onboarding_device_id",
        "setup_mode",
        "connectivity_type",
    ]:
        if key in request.session:
            del request.session[key]
    return render(request, "onboarding/complete.html")


# Setup Wizard Views for Existing Customers


@require_permission("manage_devices")
def setup_start(request, team_slug):
    request.session["setup_mode"] = True
    return render(request, "onboarding/setup_start.html")


@require_permission("manage_devices")
def setup_step_site(request, team_slug):
    sites = Site.objects.filter(team=request.team)

    if request.method == "POST":
        site_id = request.POST.get("site_id")
        if site_id == "new":
            return redirect("web_team:onboarding:step_1_site", team_slug=team_slug)
        elif site_id:
            request.session["onboarding_site_id"] = int(site_id)
            return redirect("web_team:onboarding:step_connectivity", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 1, "sites": sites}
    return render(request, "onboarding/setup_step_site.html", context)


@require_permission("manage_devices")
def setup_step_connectivity(request, team_slug):
    if request.method == "POST":
        connectivity = request.POST.get("connectivity")
        request.session["connectivity_type"] = connectivity
        if connectivity == "gateway":
            return redirect("web_team:onboarding:step_2_gateway", team_slug=team_slug)
        else:
            # Direct connection skips gateway step
            request.session["onboarding_gateway_id"] = None
            return redirect("web_team:onboarding:step_3_device", team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 2}  # We'll reuse the progress bar
    return render(request, "onboarding/setup_step_connectivity.html", context)
