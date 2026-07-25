from django.db import transaction

from apps.teams.models import Team

from .models import (
    CommandOutbox,
    ControlActivation,
    RemoteCommand,
    RemoteCommandApproval,
    RemoteControlScope,
)


@transaction.atomic
def disaster_recovery_control_reset(*, reason="Hub restore/recovery"):
    """Invalidate restored work globally without ever replaying an old write."""
    pending = [
        RemoteCommand.Status.REQUESTED,
        RemoteCommand.Status.AWAITING_APPROVAL,
        RemoteCommand.Status.APPROVED,
        RemoteCommand.Status.QUEUED,
        RemoteCommand.Status.DISPATCHING,
    ]
    affected = RemoteCommand.objects.filter(status__in=pending).update(
        status=RemoteCommand.Status.CANCELLED,
        error_code="disaster_recovery_reset",
        error_message=reason,
    )
    CommandOutbox.objects.filter(
        status__in=[CommandOutbox.Status.PENDING, CommandOutbox.Status.CLAIMED]
    ).update(status=CommandOutbox.Status.CANCELLED, last_error=reason)
    RemoteCommandApproval.objects.filter(status=RemoteCommandApproval.Status.PENDING).update(
        status=RemoteCommandApproval.Status.INVALIDATED,
        decision_reason=reason,
    )
    RemoteControlScope.objects.update(
        mode=RemoteControlScope.Mode.SUSPENDED,
        reason=reason,
    )
    ControlActivation.objects.filter(status=ControlActivation.Status.ACTIVE).update(
        status=ControlActivation.Status.SUSPENDED,
        suspended_reason=reason,
    )
    for team in Team.objects.select_for_update().all():
        team.remote_control_epoch += 1
        team.remote_control_mode = Team.RemoteControlMode.LOCKED_DOWN
        team.save(update_fields=["remote_control_epoch", "remote_control_mode", "updated_at"])
    return affected


@transaction.atomic
def rollback_policy_as_new_epoch(*, team, actor, reason):
    """Rollback means a new epoch and recommissioning; old signed commands stay invalid."""
    if not team.membership_set.filter(user=actor, role__in=["owner", "admin"]).exists():
        raise PermissionError("Only a customer owner or administrator can roll back control policy.")
    team = Team.objects.select_for_update().get(pk=team.pk)
    team.remote_control_epoch += 1
    team.remote_control_mode = Team.RemoteControlMode.MONITORING_ONLY
    team.save(update_fields=["remote_control_epoch", "remote_control_mode", "updated_at"])
    RemoteControlScope.objects.filter(team=team).update(
        mode=RemoteControlScope.Mode.SUSPENDED,
        reason=reason,
    )
    ControlActivation.objects.filter(team=team, status=ControlActivation.Status.ACTIVE).update(
        status=ControlActivation.Status.SUSPENDED,
        suspended_reason=reason,
    )
    return team.remote_control_epoch
