import logging
from apps.maintenance.models import MaintenanceTicket
from apps.alerts.models import AlertRule

logger = logging.getLogger('iot_platform')

def auto_create_ticket(alert):
    """
    Automatically creates a reactive maintenance ticket for warning/critical alerts.
    """
    if alert.rule.severity not in ['warning', 'critical']:
        return None

    # Map alert severity to ticket priority
    priority = MaintenanceTicket.PriorityChoices.HIGH
    if alert.rule.severity == 'critical':
        priority = MaintenanceTicket.PriorityChoices.CRITICAL
    elif alert.rule.severity == 'warning':
        priority = MaintenanceTicket.PriorityChoices.MEDIUM

    title = f"[{alert.rule.get_severity_display().upper()}] {alert.rule.name} on {alert.device.name}"
    description = (
        f"Automated ticket generated from alert on {alert.device.name}.\n"
        f"Telemetry Key: {alert.rule.telemetry_key}\n"
        f"Triggered Value: {alert.trigger_value} (Threshold: {alert.rule.condition} {alert.rule.threshold})"
    )

    ticket = MaintenanceTicket.objects.create(
        team=alert.team,
        device=alert.device,
        title=title,
        description=description,
        ticket_type=MaintenanceTicket.TypeChoices.REACTIVE,
        priority=priority,
        status=MaintenanceTicket.StatusChoices.OPEN,
        alert_reference=str(alert.id),
    )
    
    logger.info(f"Auto-created ticket {ticket.id} from alert {alert.id}")
    return ticket
