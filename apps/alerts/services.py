import logging
from datetime import timedelta

from django.db import models
from django.utils import timezone

from .models import Alert, AlertRule

logger = logging.getLogger("iot_platform")


def check_alerts_for_payload(device, key, value):
    """
    Checks all active alert rules for a specific telemetry data point.
    """
    if not isinstance(value, (int, float)):
        return

    # Find rules that apply to this device and key
    # or rules that apply to the site and key
    rules = AlertRule.objects.filter(is_active=True, telemetry_key=key).filter(
        models.Q(device=device) | models.Q(site=device.site)
    )

    for rule in rules:
        if evaluate_condition(rule, value):
            trigger_alert(rule, device, value)


def evaluate_condition(rule, value):
    """Evaluates if the telemetry value meets the rule threshold."""
    if rule.condition == "gt":
        return value > rule.threshold
    elif rule.condition == "lt":
        return value < rule.threshold
    elif rule.condition == "gte":
        return value >= rule.threshold
    elif rule.condition == "lte":
        return value <= rule.threshold
    elif rule.condition == "eq":
        return value == rule.threshold
    elif rule.condition == "neq":
        return value != rule.threshold
    return False


def trigger_alert(rule, device, value):
    """Creates an alert if not recently triggered (cooldown)."""
    cooldown_limit = timezone.now() - timedelta(minutes=rule.cooldown_minutes)

    recent_alert = Alert.objects.filter(
        rule=rule, device=device, status="active", triggered_at__gte=cooldown_limit
    ).exists()

    if not recent_alert:
        alert = Alert.objects.create(team=rule.team, rule=rule, device=device, trigger_value=value, status="active")
        logger.warning(f"ALERT TRIGGERED: {rule.name} for device {device.name} (Value: {value})")

        # Send email/webhook notifications
        from .notifications import send_alert_notifications

        send_alert_notifications(alert)

        # Auto-create maintenance ticket if applicable
        from apps.maintenance.services import auto_create_ticket

        auto_create_ticket(alert)
