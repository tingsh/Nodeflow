import hashlib

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.contrib.sessions.models import Session
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.api.models import UserAPIKey
from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_OWNER


def sole_owned_active_teams(user):
    """Return active teams where this user is the only owner."""
    owned_team_ids = Membership.objects.filter(user=user, role=ROLE_OWNER, team__status=Team.Status.ACTIVE).values_list(
        "team_id", flat=True
    )
    blocking_ids = []
    for team_id in owned_team_ids:
        owner_count = Membership.objects.filter(team_id=team_id, role=ROLE_OWNER).count()
        if owner_count == 1:
            blocking_ids.append(team_id)
    return Team.objects.filter(id__in=blocking_ids, status=Team.Status.ACTIVE).order_by("name")


def close_user_account(user, password, confirmation_email, reason="self_service"):
    if not user.check_password(password):
        raise ValidationError(_("Enter your current password to close this account."))

    normalized_confirmation = (confirmation_email or "").strip().lower()
    current_email = (user.email or "").strip().lower()
    if normalized_confirmation != current_email:
        raise ValidationError(_("Type your account email exactly to confirm account closure."))

    blocking_teams = list(sole_owned_active_teams(user))
    if blocking_teams:
        raise ValidationError(
            _("Transfer ownership or close these teams before closing your account: {teams}.").format(
                teams=", ".join(team.name for team in blocking_teams)
            )
        )

    with transaction.atomic():
        user = user.__class__.objects.select_for_update().get(pk=user.pk)
        original_email = (user.email or "").strip().lower()
        if original_email:
            user.original_email_hash = hashlib.sha256(original_email.encode("utf-8")).hexdigest()
        user.email = f"closed-user-{user.id}@closed.novena.local"
        user.username = f"closed-user-{user.id}"
        user.first_name = ""
        user.last_name = ""
        user.phone_number = ""
        user.job_title = ""
        user.department = ""
        user.avatar = ""
        user.language = None
        user.timezone = ""
        user.is_active = False
        user.closed_at = timezone.now()
        user.closed_reason = reason
        user.save(
            update_fields=[
                "email",
                "username",
                "first_name",
                "last_name",
                "phone_number",
                "job_title",
                "department",
                "avatar",
                "language",
                "timezone",
                "is_active",
                "closed_at",
                "closed_reason",
                "original_email_hash",
            ]
        )
        UserAPIKey.objects.filter(user=user, revoked=False).update(revoked=True)
        EmailAddress.objects.filter(user=user).delete()
        SocialAccount.objects.filter(user=user).delete()
        _clear_user_sessions(user)
    return user


def _clear_user_sessions(user):
    user_id = str(user.pk)
    for session in Session.objects.filter(expire_date__gte=timezone.now()):
        data = session.get_decoded()
        if data.get("_auth_user_id") == user_id:
            session.delete()
