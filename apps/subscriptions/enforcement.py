import logging

from apps.devices.models import Device

logger = logging.getLogger("iot_platform")

# Plan Limits
# mapping slug -> limit
PLAN_DEVICE_LIMITS = {
    "starter": 10,
    "professional": 50,
    "business": 200,
}

DEFAULT_LIMIT = 3  # For teams with no active subscription


def get_device_limit_for_team(team):
    """
    Returns the maximum number of devices allowed for a team.
    """
    if not team.subscription or not team.has_active_subscription():
        return DEFAULT_LIMIT

    # Get the product slug from metadata
    wrapped = team.wrapped_subscription
    if wrapped and wrapped.product:
        # We'll use the product slug from Pegasus metadata
        from apps.subscriptions.metadata import get_product_with_metadata

        product_metadata = get_product_with_metadata(wrapped.product).metadata
        slug = product_metadata.slug
        return PLAN_DEVICE_LIMITS.get(slug, DEFAULT_LIMIT)

    return DEFAULT_LIMIT


def can_add_device(team):
    """
    Returns True if the team has not reached its device limit.
    """
    limit = get_device_limit_for_team(team)
    if limit == -1:  # Unlimited
        return True

    count = Device.objects.filter(team=team).count()
    return count < limit


# Latency limits gating: slug -> min interval in seconds
PLAN_LATENCY_LIMITS = {
    "starter": 10.0,       # 10s refresh
    "professional": 5.0,  # 5s refresh
    "business": 1.0,      # 1s refresh (Real-time)
}

DEFAULT_LATENCY_LIMIT = 10.0  # Default for free tier/no active subscription


def get_latency_limit_for_team(team):
    """
    Returns the minimum telemetry update interval (in seconds) allowed for a team.
    """
    if not team.subscription or not team.has_active_subscription():
        return DEFAULT_LATENCY_LIMIT

    wrapped = team.wrapped_subscription
    if wrapped and wrapped.product:
        from apps.subscriptions.metadata import get_product_with_metadata

        product_metadata = get_product_with_metadata(wrapped.product).metadata
        slug = product_metadata.slug
        return PLAN_LATENCY_LIMITS.get(slug, DEFAULT_LATENCY_LIMIT)

    return DEFAULT_LATENCY_LIMIT

