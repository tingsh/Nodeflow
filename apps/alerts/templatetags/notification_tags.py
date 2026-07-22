from django import template

from apps.alerts.models import Alert
from apps.devices.models import Gateway

register = template.Library()


def _has_unresolved_discoveries(gateway):
    discovery_data = gateway.discovery_data or {}
    discovered_devices = discovery_data.get("devices") or []
    if not discovered_devices:
        return False

    registered_ports = {
        str(port) for port in gateway.devices.exclude(port__isnull=True).exclude(port="").values_list("port", flat=True)
    }
    for discovered in discovered_devices:
        port = discovered.get("interface") or discovered.get("port")
        if port and str(port) in registered_ports:
            continue
        return True
    return False


@register.simple_tag
def get_unread_notifications(team):
    if not team:
        return {"unread_count": 0, "alerts": [], "discoveries": []}

    # Get active alerts (limit to 5)
    alerts = Alert.objects.filter(team=team, status="active").order_by("-triggered_at")[:5]

    # Show only discovery reports that still need a customer decision.
    discovery_candidates = Gateway.objects.filter(team=team).exclude(discovery_data={}).exclude(discovery_data=None)
    discoveries = [gateway for gateway in discovery_candidates if _has_unresolved_discoveries(gateway)][:5]

    total_count = alerts.count() + len(discoveries)

    return {"unread_count": total_count, "alerts": alerts, "discoveries": discoveries}
