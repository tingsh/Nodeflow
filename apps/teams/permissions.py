from rest_framework import permissions
from rest_framework.request import Request

from .models import Membership, Team
from .roles import ROLE_OWNER, is_admin, is_member


class TeamAccessPermissions(permissions.BasePermission):
    """
    Permission to only allow admins of a team to edit the team object.

    Members of the team still have read-only access.
    """

    def has_permission(self, request, view):
        if getattr(view, "action", None) != "create":
            return True
        return bool(
            request.user.is_authenticated
            and Membership.objects.filter(
                user=request.user,
                role=ROLE_OWNER,
                team__status=Team.Status.ACTIVE,
            ).exists()
        )

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        # so we'll always allow GET, HEAD or OPTIONS requests for members
        if getattr(view, "action", None) == "destroy":
            return Membership.objects.filter(user=request.user, team=obj, role=ROLE_OWNER).exists()
        return _view_for_members_edit_for_admins(request, obj)


class TeamModelAccessPermissions(permissions.BasePermission):
    """
    Use this permission to only allow admins of a team to edit the underlying object.
    Assumes the model instance has a `team` attribute.

    Members of the team still have read-only access.
    """

    def has_object_permission(self, request, view, obj):
        return _view_for_members_edit_for_admins(request, obj.team)


def _view_for_members_edit_for_admins(request: Request, team: Team):
    if request.method in permissions.SAFE_METHODS:
        return is_member(request.user, team)
    return is_admin(request.user, team)
