import logging

from django.conf import settings

from apps.events.models import EmailDelivery
from apps.events.services import TrackedEmailDeliveryError, send_tracked_email
from apps.maintenance.models import MaintenanceTicket

logger = logging.getLogger("novena_hub")


def auto_create_ticket(alert, force=False):
    """
    Automatically creates a reactive maintenance ticket based on AlertRule configuration.
    If force is True, bypasses the rule.create_maintenance_ticket check.
    """
    rule = alert.rule
    if not rule.create_maintenance_ticket and not force:
        return None

    # Map alert severity to ticket priority
    priority = MaintenanceTicket.PriorityChoices.MEDIUM
    if rule.severity == "critical":
        priority = MaintenanceTicket.PriorityChoices.CRITICAL
    elif rule.severity == "warning":
        priority = MaintenanceTicket.PriorityChoices.HIGH
    elif rule.severity == "info":
        priority = MaintenanceTicket.PriorityChoices.LOW

    title = f"[{rule.get_severity_display().upper()}] {rule.name} on {alert.device.name}"
    description = (
        f"This maintenance ticket was created because an alert triggered on {alert.device.name}.\n"
        f"Reading: {alert.metric_label}\n"
        f"Observed value: {alert.trigger_value_display}\n"
        f"Alert limit: {alert.threshold_display}\n\n"
        "Next step: confirm the reading on site, inspect the equipment, and record the action taken."
    )

    # Determine notification flags from the rule
    send_email = rule.notify_email
    send_whatsapp = rule.notify_whatsapp
    # Enforce at least one channel constraint
    if not send_email and not send_whatsapp:
        send_email = True

    # Clone checklist state from template if set
    checklist_state = []
    if rule.maintenance_template:
        description += f"\n\nChecklist guidance:\n{rule.maintenance_template.description}"
        for item in rule.maintenance_template.checklist:
            checklist_state.append(
                {"task": item.get("task", ""), "required": item.get("required", False), "done": False}
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
        send_email_notification=send_email,
        send_whatsapp_notification=send_whatsapp,
        checklist_state=checklist_state,
    )

    logger.info(f"Auto-created ticket {ticket.id} from alert {alert.id}")
    return ticket


def send_ticket_assignment_email(ticket):
    """
    Sends an email notification to the assignee with ticket and checklist details.
    """
    user = ticket.assigned_to
    if not user or not user.email:
        logger.warning(f"No email recipient configured for assignee on TKT-{ticket.id}")
        return

    subject = f"[Novena] Job Assigned: TKT-{ticket.id} - {ticket.title}"

    checklist_str = ""
    if ticket.checklist_state:
        for idx, item in enumerate(ticket.checklist_state, 1):
            status = "[x]" if item.get("done") else "[ ]"
            checklist_str += f"{idx}. {status} {item.get('task')}\n"
    else:
        checklist_str = "No checklist tasks defined.\n"

    body = (
        f"Hello {user.get_display_name() or user.username},\n\n"
        f"You have been assigned a maintenance job:\n"
        f"Ticket ID: TKT-{ticket.id}\n"
        f"Title: {ticket.title}\n"
        f"Device: {ticket.device.name}\n"
        f"Priority: {ticket.get_priority_display()}\n\n"
        f"Description:\n{ticket.description}\n\n"
        f"Checklist Tasks:\n{checklist_str}\n"
        "Manage this ticket on the dashboard: "
        f"{settings.PROJECT_METADATA['URL']}/a/{ticket.team.slug}/maintenance/tickets/{ticket.id}/\n\n"
        f"Novena Operations Team"
    )

    try:
        send_tracked_email(
            team=ticket.team,
            notification_type=EmailDelivery.NotificationType.MAINTENANCE_ASSIGNMENT,
            subject=subject,
            text_body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipients=[user.email],
            maintenance_ticket=ticket,
            user_by_email={user.email.lower(): user},
            metadata={"ticket_id": ticket.id},
        )
        logger.info(f"Sent assignment email for TKT-{ticket.id} to {user.email}")
    except TrackedEmailDeliveryError as e:
        logger.error(f"Failed to send email for TKT-{ticket.id}: {e}")


def send_ticket_assignment_whatsapp(ticket):
    """
    Sends a WhatsApp message to the assignee with ticket and checklist details.
    """
    user = ticket.assigned_to
    if not user or not user.phone_number:
        logger.warning(f"No phone number configured for assignee on TKT-{ticket.id}")
        return

    from apps.alerts.tasks import send_whatsapp_message_task

    checklist_str = ""
    if ticket.checklist_state:
        for idx, item in enumerate(ticket.checklist_state, 1):
            status = "✅" if item.get("done") else "⬜"
            checklist_str += f"{idx}. {status} {item.get('task')}\n"
    else:
        checklist_str = "No checklist tasks defined.\n"

    msg = (
        f"🔧 *NEW JOB ASSIGNED: TKT-{ticket.id}*\n"
        f"Title: {ticket.title}\n"
        f"Device: {ticket.device.name}\n"
        f"Priority: {ticket.get_priority_display()}\n\n"
        f"📋 *Checklist:*\n{checklist_str}\n"
        f"To update this ticket:\n"
        f"- Reply 'DONE <number>' (e.g., 'DONE 1')\n"
        f"- Reply 'STATUS <status>' (e.g., 'STATUS In Progress')\n"
        f"- Reply with text to add a comment."
    )

    send_whatsapp_message_task.delay(user.phone_number, msg)
    logger.info(f"Queued WhatsApp notification for TKT-{ticket.id} to {user.phone_number}")


def process_incoming_whatsapp(sender_phone, text_body):
    """
    Resolves a user from the sender's phone number, interprets commands,
    updates Maintenance Tickets, and posts comments/checklists.
    """
    import re

    from apps.alerts.tasks import send_whatsapp_message_task
    from apps.maintenance.models import TicketComment
    from apps.users.models import CustomUser

    clean_sender = "".join(filter(str.isdigit, sender_phone))

    user = None
    for u in CustomUser.objects.exclude(phone_number=""):
        clean_user_phone = "".join(filter(str.isdigit, u.phone_number))
        if (
            clean_user_phone == clean_sender
            or clean_user_phone.endswith(clean_sender)
            or clean_sender.endswith(clean_user_phone)
        ):
            user = u
            break

    if not user:
        logger.warning(f"WhatsApp webhook received message from unregistered sender: {sender_phone}")
        return

    command = text_body.upper().strip()

    # Get active/assigned tickets
    active_tickets = MaintenanceTicket.objects.filter(assigned_to=user).exclude(
        status__in=[MaintenanceTicket.StatusChoices.RESOLVED, MaintenanceTicket.StatusChoices.CLOSED]
    )

    if command == "LIST":
        if not active_tickets.exists():
            send_whatsapp_message_task.delay(sender_phone, "You currently have no active tickets assigned to you.")
            return

        msg = "📋 *YOUR ACTIVE TICKETS:*\n"
        for t in active_tickets:
            msg += f"- TKT-{t.id}: {t.title} ({t.get_status_display()})\n"
        send_whatsapp_message_task.delay(sender_phone, msg)
        return

    ticket = None
    action_text = text_body

    # Check if prefixed by Ticket ID (e.g. "TKT-101 DONE 1" or "101 DONE 1")
    match = re.match(r"^(?:TKT-)?(\d+)\s+(.*)$", text_body, re.IGNORECASE)
    if match:
        ticket_id = int(match.group(1))
        action_text = match.group(2).strip()
        try:
            ticket = MaintenanceTicket.objects.get(id=ticket_id, assigned_to=user)
        except MaintenanceTicket.DoesNotExist:
            send_whatsapp_message_task.delay(
                sender_phone, f"Ticket TKT-{ticket_id} was not found or is not assigned to you."
            )
            return
    else:
        if active_tickets.count() == 1:
            ticket = active_tickets.first()
        elif active_tickets.count() > 1:
            send_whatsapp_message_task.delay(
                sender_phone,
                "You have multiple active tickets. Please prefix your message with the Ticket ID "
                "(e.g., '101 DONE 1' or 'TKT-101 belt checked') or type 'LIST'.",
            )
            return
        else:
            send_whatsapp_message_task.delay(sender_phone, "You currently have no active tickets assigned to you.")
            return

    action_upper = action_text.upper().strip()

    # 1. Done Command (e.g., "DONE 1")
    done_match = re.match(r"^DONE\s+(\d+)$", action_upper)
    if done_match:
        index = int(done_match.group(1)) - 1
        checklist = list(ticket.checklist_state)
        if 0 <= index < len(checklist):
            item = checklist[index]
            item["done"] = True
            ticket.checklist_state = checklist
            ticket.save()

            TicketComment.objects.create(
                team=ticket.team,
                ticket=ticket,
                author=user,
                content=f"Marked task '{item['task']}' as completed via WhatsApp.",
                is_system_generated=True,
            )

            send_whatsapp_message_task.delay(
                sender_phone, f"✅ Marked task '{item['task']}' as done on TKT-{ticket.id}."
            )
        else:
            send_whatsapp_message_task.delay(
                sender_phone,
                f"❌ Invalid task index {index + 1}. Ticket TKT-{ticket.id} has {len(checklist)} tasks.",
            )
        return

    # 2. Status Command (e.g., "STATUS Resolved")
    status_match = re.match(r"^STATUS\s+(.+)$", action_upper)
    if status_match:
        status_val = status_match.group(1).strip().lower().replace(" ", "_")
        if status_val == "in_progress":
            status_choice = MaintenanceTicket.StatusChoices.IN_PROGRESS
        elif status_val in ["waiting", "waiting_on_parts"]:
            status_choice = MaintenanceTicket.StatusChoices.WAITING
        elif status_val in ["resolved", "completed"]:
            status_choice = MaintenanceTicket.StatusChoices.RESOLVED
        elif status_val == "closed":
            status_choice = MaintenanceTicket.StatusChoices.CLOSED
        elif status_val == "open":
            status_choice = MaintenanceTicket.StatusChoices.OPEN
        else:
            status_choice = None

        if status_choice:
            old_status = ticket.get_status_display()
            ticket.status = status_choice
            ticket.save()

            TicketComment.objects.create(
                team=ticket.team,
                ticket=ticket,
                author=user,
                content=f"Changed status from '{old_status}' to '{ticket.get_status_display()}' via WhatsApp.",
                is_system_generated=True,
            )
            send_whatsapp_message_task.delay(
                sender_phone, f"⚡ Changed status of TKT-{ticket.id} to '{ticket.get_status_display()}'."
            )
        else:
            send_whatsapp_message_task.delay(
                sender_phone,
                "❌ Unknown status value. Choose: Open, In Progress, Waiting, Resolved, Closed.",
            )
        return

    # 3. Default to logging a Comment
    TicketComment.objects.create(
        team=ticket.team,
        ticket=ticket,
        author=user,
        content=action_text,
    )
    send_whatsapp_message_task.delay(sender_phone, f'💬 Added comment to TKT-{ticket.id}: "{action_text[:30]}..."')


def create_pm_ticket(schedule, current_usage=None):
    """
    Generates a MaintenanceTicket from a PreventiveSchedule configuration.
    Clones the associated checklist template and configures assignment.
    """
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
            checklist_state.append(
                {"task": item.get("task", ""), "required": item.get("required", False), "done": False}
            )

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
        assigned_to=schedule.assigned_to,
        send_email_notification=schedule.send_email_notification,
        send_whatsapp_notification=schedule.send_whatsapp_notification,
    )
    logger.info(f"Generated PM Ticket {ticket.id} for schedule {schedule.id}")
    return ticket


def advance_schedule_due_date(schedule):
    """
    Advances the next_due_at date of a schedule based on its interval.
    Handles Daily, Weekly, Monthly, Quarterly, and Yearly calculations.
    """
    from datetime import timedelta

    from dateutil.relativedelta import relativedelta
    from django.utils import timezone

    now = timezone.now()
    base_date = schedule.next_due_at or now

    if schedule.interval == "daily":
        schedule.next_due_at = base_date + timedelta(days=1)
    elif schedule.interval == "weekly":
        schedule.next_due_at = base_date + timedelta(weeks=1)
    elif schedule.interval == "monthly":
        schedule.next_due_at = base_date + relativedelta(months=1)
    elif schedule.interval == "quarterly":
        schedule.next_due_at = base_date + relativedelta(months=3)
    elif schedule.interval == "yearly":
        schedule.next_due_at = base_date + relativedelta(years=1)

    if schedule.next_due_at and schedule.next_due_at <= now:
        logger.warning(
            f"PM Schedule {schedule.id} generated a ticket but next_due_at is still in the past. Correcting."
        )
        schedule.next_due_at = now + timedelta(days=1)

    schedule.save(update_fields=["next_due_at"])
