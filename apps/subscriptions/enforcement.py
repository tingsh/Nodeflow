import logging

from apps.devices.models import Device, Gateway

logger = logging.getLogger("novena_hub")

DEFAULT_LIMIT = 3  # For teams with no active subscription
DEFAULT_GATEWAY_LIMIT = 1
DEFAULT_LATENCY_LIMIT = 10.0
DEFAULT_VISIBLE_TELEMETRY_HISTORY_DAYS = 7


def get_product_metadata_for_team(team):
    """Return the active subscription metadata for a team, if one exists."""
    if not team.subscription or not team.has_active_subscription():
        return None

    try:
        from apps.subscriptions.metadata import get_product_with_metadata

        subscription = team.active_stripe_subscription
        for item in subscription.items.select_related("price__product"):
            return get_product_with_metadata(item.price.product).metadata
    except Exception:
        logger.exception("Unable to resolve subscription metadata for team %s", getattr(team, "id", None))

    return None


def get_device_limit_for_team(team):
    """
    Returns the maximum number of devices allowed for a team.
    """
    product_metadata = get_product_metadata_for_team(team)
    if product_metadata:
        return product_metadata.device_limit

    return DEFAULT_LIMIT


def get_gateway_limit_for_team(team):
    """
    Returns the maximum number of gateways allowed for a team.
    """
    product_metadata = get_product_metadata_for_team(team)
    if product_metadata:
        return product_metadata.gateway_limit

    return DEFAULT_GATEWAY_LIMIT


def can_add_device(team):
    """
    Returns True if the team has not reached its device limit.
    """
    limit = get_device_limit_for_team(team)
    if limit == -1:  # Unlimited
        return True

    count = Device.objects.filter(team=team).count()
    return count < limit


def can_add_gateway(team):
    """
    Returns True if the team has not reached its gateway limit.
    """
    limit = get_gateway_limit_for_team(team)
    if limit == -1 or limit >= 9999:
        return True

    count = Gateway.objects.filter(team=team).exclude(lifecycle_status="released").count()
    return count < limit


def get_latency_limit_for_team(team):
    """
    Returns the minimum telemetry update interval (in seconds) allowed for a team.
    """
    product_metadata = get_product_metadata_for_team(team)
    if product_metadata:
        return product_metadata.telemetry_interval_seconds

    return DEFAULT_LATENCY_LIMIT


def get_effective_polling_interval_seconds(device):
    """Return the slower of equipment capability and subscription policy."""
    template = getattr(device, "template", None)
    template_interval = getattr(template, "default_polling_interval", None) if template else None
    try:
        template_interval = float(template_interval or 5)
    except (TypeError, ValueError):
        template_interval = 5.0
    requested_interval = (getattr(device, "connection_config", None) or {}).get("requested_polling_interval")
    try:
        requested_interval = float(requested_interval or template_interval)
    except (TypeError, ValueError):
        requested_interval = template_interval
    return max(1.0, requested_interval, float(get_latency_limit_for_team(device.team)))


def get_retention_limit_days_for_team(team):
    """
    Return the plan-controlled customer-visible telemetry history window.

    This is intentionally an access limit, not a physical deletion policy. Raw
    telemetry may remain in TimescaleDB until the global database retention
    policy expires, so upgrades can reveal already-retained history and
    downgrades can shrink access immediately without purging rows on the spot.
    """
    product_metadata = get_product_metadata_for_team(team)
    if product_metadata:
        return product_metadata.retention_days

    return DEFAULT_VISIBLE_TELEMETRY_HISTORY_DAYS
