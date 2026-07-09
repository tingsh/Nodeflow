from __future__ import annotations

from apps.users.models import CustomUser

ROLE_OWNER = "owner"
ROLE_ADMIN = "admin"
ROLE_MANAGER = "manager"
ROLE_OPERATOR = "operator"
ROLE_VIEWER = "viewer"

ROLE_CHOICES = (
    (ROLE_OWNER, "Owner"),
    (ROLE_ADMIN, "Administrator"),
    (ROLE_MANAGER, "Site Manager"),
    (ROLE_OPERATOR, "Operator"),
    (ROLE_VIEWER, "Viewer"),
)

ROLE_DESCRIPTIONS = {
    ROLE_OWNER: "Full access to all features, including billing and team ownership transfer.",
    ROLE_ADMIN: "Full access to manage devices, alerts, and teams.",
    ROLE_MANAGER: "Can manage devices and alerts for assigned sites.",
    ROLE_OPERATOR: "Real-time monitoring and alert acknowledgment.",
    ROLE_VIEWER: "Read-only access to dashboards and reports.",
}

# Permission map
PERMISSIONS = {
    "view_dashboard": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_VIEWER],
    "manage_devices": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "view_devices": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_VIEWER],
    "manage_alerts": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "acknowledge_alerts": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR],
    "send_commands": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "send_critical_commands": [ROLE_OWNER, ROLE_ADMIN],
    "manage_automations": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "view_automations": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "manage_team": [ROLE_OWNER, ROLE_ADMIN],
    "delete_team": [ROLE_OWNER],
    "manage_billing": [ROLE_OWNER],
    "manage_shared_links": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "manage_maintenance": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER],
    "view_maintenance": [ROLE_OWNER, ROLE_ADMIN, ROLE_MANAGER, ROLE_OPERATOR, ROLE_VIEWER],
}


def is_member(user: CustomUser, team) -> bool:
    if not team:
        return False
    return team.members.filter(id=user.id).exists()


def is_admin(user: CustomUser, team) -> bool:
    if not team:
        return False

    from .models import Membership

    return Membership.objects.filter(team=team, user=user, role__in=[ROLE_OWNER, ROLE_ADMIN]).exists()


def has_permission(user: CustomUser, team, permission: str) -> bool:
    """Check if a user has a specific permission within a team."""
    if not team or not user.is_authenticated:
        return False

    from .models import Membership

    try:
        membership = Membership.objects.get(user=user, team=team)
        return membership.role in PERMISSIONS.get(permission, [])
    except Membership.DoesNotExist:
        return False
