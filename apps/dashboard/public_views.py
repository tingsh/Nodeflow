from django.shortcuts import render, get_object_or_404
from django.http import Http404
from django.utils import timezone
from .models import SharedDashboard

def public_dashboard(request, token):
    link = get_object_or_404(SharedDashboard, token=token)
    
    if not link.is_active:
        raise Http404("This shared link has been deactivated.")
        
    if link.is_expired:
        raise Http404("This shared link has expired.")

    # Check if a password is required
    session_key = f'unlocked_dashboard_{link.token}'
    is_unlocked = request.session.get(session_key, False)

    if link.password_hash and not is_unlocked:
        if request.method == 'POST':
            password = request.POST.get('password')
            if link.check_password(password):
                request.session[session_key] = True
            else:
                return render(request, "dashboard/public/password_prompt.html", {
                    "error": "Incorrect password.",
                    "link": link
                })
        else:
            return render(request, "dashboard/public/password_prompt.html", {"link": link})

    # Record view stats on successful load (not on password prompts)
    if request.method == 'GET':
        link.view_count += 1
        link.last_viewed_at = timezone.now()
        link.save(update_fields=['view_count', 'last_viewed_at'])

    # Gather data for the team's dashboard
    # Let's get the summary stats, active alerts, and site statuses
    from apps.telemetry.services import get_site_summary_stats
    from apps.alerts.models import Alert
    
    # Kiosk mode hides navigation and applies tight padding
    kiosk_mode = request.GET.get('kiosk') == '1'

    sites = link.team.site_set.all()
    site_stats = []
    for site in sites:
        stats = get_site_summary_stats(site)
        site_stats.append({
            "site": site,
            "stats": stats
        })

    active_alerts = Alert.objects.filter(
        device__team=link.team,
        status='active'
    ).order_by('-triggered_at')[:10]

    context = {
        "link": link,
        "team": link.team,
        "site_stats": site_stats,
        "active_alerts": active_alerts,
        "kiosk_mode": kiosk_mode,
    }
    
    return render(request, "dashboard/public/public_dashboard.html", context)
