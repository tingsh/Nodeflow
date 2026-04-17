from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from .models import PreventiveSchedule, MaintenanceTicket
import logging

logger = logging.getLogger('iot_platform')

@shared_task
def generate_preventive_tickets():
    """
    Scans for active Preventive Schedules that are due (or overdue) and generates tickets.
    """
    now = timezone.now()
    schedules = PreventiveSchedule.objects.filter(is_active=True, next_due_at__lte=now)

    for schedule in schedules:
        # Create ticket
        priority = MaintenanceTicket.PriorityChoices.MEDIUM
        title = f"[PM] {schedule.title} on {schedule.device.name}"
        
        description = f"Scheduled maintenance automatically generated for interval: {schedule.get_interval_display()}"
        if schedule.template:
            description += f"\nTemplate Instructions:\n{schedule.template.description}"
            
        ticket = MaintenanceTicket.objects.create(
            team=schedule.team,
            device=schedule.device,
            title=title,
            description=description,
            ticket_type=MaintenanceTicket.TypeChoices.PREVENTIVE,
            priority=priority,
            status=MaintenanceTicket.StatusChoices.OPEN,
            schedule_reference=schedule,
        )
        
        # Calculate new next_due_at
        if schedule.interval == 'daily':
            schedule.next_due_at += timedelta(days=1)
        elif schedule.interval == 'weekly':
            schedule.next_due_at += timedelta(weeks=1)
        elif schedule.interval == 'monthly':
            schedule.next_due_at += relativedelta(months=1)
        elif schedule.interval == 'quarterly':
            schedule.next_due_at += relativedelta(months=3)
        elif schedule.interval == 'yearly':
            schedule.next_due_at += relativedelta(years=1)
            
        # If it's still in the past (e.g. system was off for months), jump to the future safely
        if schedule.next_due_at <= now:
            logger.warning(f"PM Schedule {schedule.id} generated a ticket but next_due_at is still in the past. Correcting.")
            schedule.next_due_at = now + timedelta(days=1) # Fallback to prevent infinite loops

        schedule.save(update_fields=['next_due_at'])
        logger.info(f"Generated PM Ticket {ticket.id} for schedule {schedule.id}")
