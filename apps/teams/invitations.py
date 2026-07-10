from django.db import transaction

from apps.users.models import CustomUser

from .models import Invitation
from .tasks import send_invitation_email_task


def send_invitation(invitation):
    transaction.on_commit(lambda: send_invitation_email_task.delay(str(invitation.id)))


def process_invitation(invitation: Invitation, user: CustomUser):
    invitation.team.members.add(user, through_defaults={"role": invitation.role})
    invitation.is_accepted = True
    invitation.accepted_by = user
    invitation.save()


def get_invitation_id_from_request(request):
    return (
        # URL takes precedence over session/cookie
        request.GET.get("invitation_id") or request.session.get("invitation_id")
    )


def clear_invite_from_session(request):
    if "invitation_id" in request.session:
        del request.session["invitation_id"]
