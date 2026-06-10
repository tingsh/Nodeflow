import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail

from apps.devices.models import Gateway
from apps.maintenance.models import MaintenanceTicket

logger = logging.getLogger("iot_platform")


@shared_task
def check_gateway_heartbeats():
    """
    Checks if any gateway has missed its heartbeat (last_seen > 15 minutes ago).
    If so, updates status to 'offline', raises a reactive maintenance ticket,
    and notifies team members.
    """
    now = timezone.now()
    threshold_time = now - timedelta(minutes=15)

    # Find gateways currently online that haven't sent telemetry in 15 minutes
    offline_gateways = Gateway.objects.filter(status="online", last_seen__lt=threshold_time)

    for gateway in offline_gateways:
        gateway.status = "offline"
        gateway.save(update_fields=["status"])
        
        logger.warning(f"GATEWAY OFFLINE: Gateway {gateway.serial_number} at site {gateway.site.name} has missed heartbeats.")

        # Try to find a device on this gateway to attach the ticket to
        device = gateway.devices.first()
        if device:
            # Create a reactive maintenance ticket
            ticket = MaintenanceTicket.objects.create(
                team=gateway.site.team,
                device=device,
                title=f"[CRITICAL] Gateway {gateway.serial_number} is Offline",
                description=(
                    f"Gateway with Serial Number {gateway.serial_number} at site '{gateway.site.name}' "
                    f"has gone offline. No heartbeat has been received since {gateway.last_seen}.\n\n"
                    f"Please check the local power supply, network connection, and edge gateway daemon status."
                ),
                ticket_type=MaintenanceTicket.TypeChoices.REACTIVE,
                priority=MaintenanceTicket.PriorityChoices.CRITICAL,
                status=MaintenanceTicket.StatusChoices.OPEN,
            )
            logger.info(f"Auto-created critical ticket TKT-{ticket.id} for offline gateway {gateway.serial_number}")

        # Send alert emails to the team members
        try:
            team = gateway.site.team
            emails = [member.email for member in team.members.all() if member.email]
            if emails:
                subject = f"[CRITICAL] Gateway Offline: {gateway.serial_number} ({gateway.site.name})"
                message = (
                    f"Alert: Gateway {gateway.serial_number} at Site '{gateway.site.name}' is offline.\n"
                    f"No telemetry has been received since {gateway.last_seen}.\n\n"
                    f"A critical maintenance ticket has been automatically created.\n"
                    f"Dashboard URL: {settings.SITE_URL}/a/{team.slug}/maintenance/"
                )
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=emails,
                    fail_silently=True
                )
                logger.info(f"Offline notification email sent to {len(emails)} recipients.")
        except Exception as e:
            logger.error(f"Failed to send gateway offline email: {e}")
