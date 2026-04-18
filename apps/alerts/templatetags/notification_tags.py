from django import template

from apps.alerts.models import Alert
from apps.devices.models import Gateway

register = template.Library()


@register.simple_tag
def get_unread_notifications(team):
    if not team:
        return {"unread_count": 0, "alerts": [], "discoveries": []}

    # Get active alerts (limit to 5)
    alerts = Alert.objects.filter(team=team, status="active").order_by("-triggered_at")[:5]

    # Get gateways with recent discovery data (limit to 5)
    # This assumes discovery_data exists and is non-empty
    discoveries = Gateway.objects.filter(team=team).exclude(discovery_data={}).exclude(discovery_data=None)[:5]

    total_count = alerts.count() + discoveries.count()

    return {"unread_count": total_count, "alerts": alerts, "discoveries": discoveries}
