import logging
from datetime import timedelta

from celery import shared_task
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from .models import MaintenanceTicket, PreventiveSchedule

logger = logging.getLogger("iot_platform")


def create_pm_ticket(schedule, current_usage=None):
    priority = MaintenanceTicket.PriorityChoices.MEDIUM
    title = f"[PM] {schedule.title} on {schedule.device.name}"

    if schedule.is_usage_based:
        description = (
            f"Usage-based maintenance automatically generated.\n"
            f"Trigger metric: {schedule.usage_telemetry_key}\n"
            f"Threshold delta: {schedule.usage_threshold}\n"
            f"Current value: {current_usage} (Last triggered at: {schedule.last_trigger_usage_value})"
        )
    else:
        description = f"Scheduled maintenance automatically generated for interval: {schedule.get_interval_display()}"

    checklist_state = []
    if schedule.template:
        description += f"\n\nTemplate Instructions:\n{schedule.template.description}"
        # Copy template checklist
        for item in schedule.template.checklist:
            checklist_state.append({
                "task": item.get("task", ""),
                "required": item.get("required", False),
                "done": False
            })

    ticket = MaintenanceTicket.objects.create(
        team=schedule.team,
        device=schedule.device,
        title=title,
        description=description,
        ticket_type=MaintenanceTicket.TypeChoices.PREVENTIVE,
        priority=priority,
        status=MaintenanceTicket.StatusChoices.OPEN,
        schedule_reference=schedule,
        checklist_state=checklist_state,
    )
    logger.info(f"Generated PM Ticket {ticket.id} for schedule {schedule.id}")
    return ticket


@shared_task
def generate_preventive_tickets():
    """
    Scans for active Preventive Schedules (both calendar and usage based) and generates tickets.
    """
    now = timezone.now()

    # 1. Calendar-based schedules
    calendar_schedules = PreventiveSchedule.objects.filter(
        is_active=True, is_usage_based=False, next_due_at__lte=now
    )

    for schedule in calendar_schedules:
        create_pm_ticket(schedule)

        # Calculate new next_due_at
        if schedule.interval == "daily":
            schedule.next_due_at += timedelta(days=1)
        elif schedule.interval == "weekly":
            schedule.next_due_at += timedelta(weeks=1)
        elif schedule.interval == "monthly":
            schedule.next_due_at += relativedelta(months=1)
        elif schedule.interval == "quarterly":
            schedule.next_due_at += relativedelta(months=3)
        elif schedule.interval == "yearly":
            schedule.next_due_at += relativedelta(years=1)

        # If it's still in the past (e.g. system was off for months), jump to the future safely
        if schedule.next_due_at <= now:
            logger.warning(
                f"PM Schedule {schedule.id} generated a ticket but next_due_at is still in the past. Correcting."
            )
            schedule.next_due_at = now + timedelta(days=1)

        schedule.save(update_fields=["next_due_at"])

    # 2. Usage-based schedules
    from apps.telemetry.services import get_latest_telemetry_value

    usage_schedules = PreventiveSchedule.objects.filter(is_active=True, is_usage_based=True)
    for schedule in usage_schedules:
        current_val = get_latest_telemetry_value(schedule.device, schedule.usage_telemetry_key)
        if current_val is not None:
            try:
                current_usage = float(current_val)
                last_trigger = float(schedule.last_trigger_usage_value or 0.0)
                threshold = float(schedule.usage_threshold or 0.0)

                if current_usage >= last_trigger + threshold:
                    create_pm_ticket(schedule, current_usage)
                    schedule.last_trigger_usage_value = current_usage
                    schedule.save(update_fields=["last_trigger_usage_value"])
            except (ValueError, TypeError):
                pass

