from django import template

from apps.teams.models import Membership, Team
from apps.teams.roles import ROLE_OWNER, is_admin, is_member

register = template.Library()


@register.filter
def is_member_of(user, team):
    return is_member(user, team)


@register.filter
def is_admin_of(user, team):
    return is_admin(user, team)


@register.filter
def can_create_team(user):
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(
        user=user,
        role=ROLE_OWNER,
        team__status=Team.Status.ACTIVE,
    ).exists()
