from django import template

from apps.teams.roles import has_permission

register = template.Library()


@register.simple_tag(takes_context=True)
def has_perm(context, permission):
    """
    Template tag to check team-level permissions.
    Usage:
    {% load team_permissions %}
    {% has_perm 'manage_devices' as can_manage_devices %}
    {% if can_manage_devices %} ... {% endif %}
    """
    request = context.get("request")
    if not request or not hasattr(request, "team") or not request.team:
        return False

    return has_permission(request.user, request.team, permission)
