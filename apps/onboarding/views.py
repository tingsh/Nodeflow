from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from apps.teams.decorators import login_and_team_required
from apps.devices.models import Site, Gateway, Device, DeviceTemplate
from apps.alerts.models import AlertRule

ONBOARDING_STEPS = [
    {"num": 1, "label": "Site"},
    {"num": 2, "label": "Gateway"},
    {"num": 3, "label": "Device"},
    {"num": 4, "label": "Alert"},
]

@login_and_team_required
def onboarding_start(request, team_slug):
    if Site.objects.filter(team=request.team).exists():
        return redirect('web_team:home', team_slug=team_slug)
    return render(request, "onboarding/welcome.html")

@login_and_team_required
def step_1_site(request, team_slug):
    site_id = request.session.get('onboarding_site_id')
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
            request.session['onboarding_site_id'] = site.id
            return redirect('web_team:onboarding:step_2_gateway', team_slug=team_slug)
            
    context = {"steps": ONBOARDING_STEPS, "current_step": 1, "site": site}
    return render(request, "onboarding/step_1_site.html", context)

@login_and_team_required
def step_2_gateway(request, team_slug):
    site_id = request.session.get('onboarding_site_id')
    if not site_id:
        return redirect('web_team:onboarding:step_1_site', team_slug=team_slug)
    site = get_object_or_404(Site, id=site_id, team=request.team)
    
    gateway_id = request.session.get('onboarding_gateway_id')
    gateway = Gateway.objects.filter(id=gateway_id, team=request.team).first() if gateway_id else None
    
    if request.method == "POST":
        name = request.POST.get("name")
        sn = request.POST.get("serial_number")
        if name and sn:
            # Check for existing gateway with same serial number
            existing_gateway = Gateway.objects.filter(serial_number=sn).first()
            if existing_gateway:
                if existing_gateway.team == request.team:
                    # Same team, just update the site/name and reuse
                    existing_gateway.site = site
                    existing_gateway.name = name
                    existing_gateway.save()
                    request.session['onboarding_gateway_id'] = existing_gateway.id
                    return redirect('web_team:onboarding:step_3_device', team_slug=team_slug)
                else:
                    # Different team, show error
                    context = {
                        "steps": ONBOARDING_STEPS, 
                        "current_step": 2, 
                        "site": site,
                        "gateway": gateway, # Pass the one we were editing if it failed
                        "error": "This Serial Number is already registered to another team. Please contact support if you believe this is an error."
                    }
                    return render(request, "onboarding/step_2_gateway.html", context)

            import secrets
            if gateway:
                gateway.name = name
                gateway.serial_number = sn
                gateway.save()
            else:
                gateway = Gateway.objects.create(
                    team=request.team, site=site, name=name, 
                    serial_number=sn, access_token=secrets.token_hex(20)
                )
            request.session['onboarding_gateway_id'] = gateway.id
            return redirect('web_team:onboarding:step_3_device', team_slug=team_slug)
            
    context = {"steps": ONBOARDING_STEPS, "current_step": 2, "site": site, "gateway": gateway}
    return render(request, "onboarding/step_2_gateway.html", context)

@login_and_team_required
def step_3_device(request, team_slug):
    gateway_id = request.session.get('onboarding_gateway_id')
    site_id = request.session.get('onboarding_site_id')
    if not gateway_id:
        return redirect('web_team:onboarding:step_2_gateway', team_slug=team_slug)
    gateway = get_object_or_404(Gateway, id=gateway_id, team=request.team)
    
    device_id = request.session.get('onboarding_device_id')
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
                device.device_type = template.device_type if template else 'sensor'
                device.protocol = template.protocol if template else 'modbus_tcp'
                device.save()
            else:
                device = Device.objects.create(
                    team=request.team, gateway=gateway, site_id=site_id, 
                    name=name, template=template,
                    device_type=template.device_type if template else 'sensor',
                    protocol=template.protocol if template else 'modbus_tcp'
                )
            request.session['onboarding_device_id'] = device.id
            return redirect('web_team:onboarding:step_4_alert', team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 3, "templates": templates, "device": device}
    return render(request, "onboarding/step_3_device.html", context)

@login_and_team_required
def step_4_alert(request, team_slug):
    device_id = request.session.get('onboarding_device_id')
    if not device_id:
        return redirect('web_team:onboarding:step_3_device', team_slug=team_slug)
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
                    team=request.team, device=device,
                    name=f"{device.name} High {key.replace('_', ' ').title()}",
                    telemetry_key=key, condition='gt', threshold=float(threshold), severity='critical'
                )
            return redirect('web_team:onboarding:complete', team_slug=team_slug)

    context = {"steps": ONBOARDING_STEPS, "current_step": 4, "device": device, "rule": existing_rule}
    return render(request, "onboarding/step_4_alert.html", context)

@login_and_team_required
def complete(request, team_slug):
    for key in ['onboarding_site_id', 'onboarding_gateway_id', 'onboarding_device_id']:
        if key in request.session:
            del request.session[key]
    return render(request, "onboarding/complete.html")
