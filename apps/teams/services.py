from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.teams.models import Invitation, Team


def close_team(team, closed_by, confirmation_team_name, reason="owner_self_service"):
    confirmation_team_name = (confirmation_team_name or "").strip()
    if confirmation_team_name != team.name:
        raise ValidationError(_("Type the team name exactly to confirm closure."))

    if team.has_active_subscription():
        raise ValidationError(_("Cancel the active subscription before closing this team."))

    with transaction.atomic():
        team = Team.objects.select_for_update().get(pk=team.pk)
        if team.status == Team.Status.CLOSED:
            return team

        team.status = Team.Status.CLOSED
        team.closed_at = timezone.now()
        team.closed_by = closed_by
        team.closed_reason = reason
        team.save(update_fields=["status", "closed_at", "closed_by", "closed_reason", "updated_at"])

        Invitation.objects.filter(team=team, is_accepted=False).update(is_accepted=True)
        _disable_team_operations(team)
    return team


def _disable_team_operations(team):
    from apps.alerts.models import AlertRule
    from apps.automations.models import Automation
    from apps.dashboard.models import SharedDashboard
    from apps.devices.models import Gateway
    from apps.maintenance.models import PreventiveSchedule, SharedTicketLink

    AlertRule.objects.filter(team=team, is_active=True).update(
        is_active=False,
        notify_email=False,
        notify_whatsapp=False,
        notify_webhook="",
        create_maintenance_ticket=False,
    )
    Automation.objects.filter(team=team, is_active=True).update(is_active=False)
    PreventiveSchedule.objects.filter(team=team, is_active=True).update(
        is_active=False,
        send_email_notification=False,
        send_whatsapp_notification=False,
    )
    SharedDashboard.objects.filter(team=team, is_active=True).update(is_active=False)
    SharedTicketLink.objects.filter(team=team, is_active=True).update(is_active=False)
    Gateway.objects.filter(team=team).update(status="offline")
