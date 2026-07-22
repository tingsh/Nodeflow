import logging

from celery import shared_task
from django.utils import timezone

from .models import PreventiveSchedule
from .services import advance_schedule_due_date, create_pm_ticket

logger = logging.getLogger("novena_hub")


@shared_task
def generate_preventive_tickets():
    """
    Scans for active Preventive Schedules (both calendar and usage based) and generates tickets.
    """
    now = timezone.now()

    # 1. Calendar-based schedules
    calendar_schedules = PreventiveSchedule.objects.filter(is_active=True, is_usage_based=False, next_due_at__lte=now)

    for schedule in calendar_schedules:
        create_pm_ticket(schedule)
        advance_schedule_due_date(schedule)

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
