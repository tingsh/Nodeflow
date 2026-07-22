from unittest.mock import patch

import pytest

from apps.teams.invitations import send_invitation
from apps.teams.models import Invitation, Membership, Team
from apps.teams.roles import ROLE_ADMIN, ROLE_VIEWER
from apps.users.models import CustomUser


@pytest.mark.django_db
@patch("apps.teams.invitations.send_invitation_email_task.delay")
def test_send_invitation_queues_email_task(mock_delay, django_capture_on_commit_callbacks):
    team = Team.objects.create(name="Invite Team", slug="invite-team")
    inviter = CustomUser.objects.create_user(username="admin", email="admin@example.com", password="pwd")
    Membership.objects.create(team=team, user=inviter, role=ROLE_ADMIN)
    invitation = Invitation.objects.create(
        team=team,
        invited_by=inviter,
        email="new-member@example.com",
        role=ROLE_VIEWER,
    )

    with django_capture_on_commit_callbacks(execute=True):
        send_invitation(invitation)

    mock_delay.assert_called_once_with(str(invitation.id))
