import datetime

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.users.models import CustomUser
from apps.dashboard.models import Dashboard, Widget


def get_user_signups(start: datetime.date | None = None, end: datetime.date | None = None, include_unconfirmed=None):
    extra_filter_kwargs = {}
    if include_unconfirmed is None:
        include_unconfirmed = settings.ACCOUNT_EMAIL_VERIFICATION != "mandatory"
    if not include_unconfirmed:
        extra_filter_kwargs = {
            "emailaddress__verified": True,
        }
    end = end or timezone.now()
    start = start or end - datetime.timedelta(days=90)
    data = (
        CustomUser.objects.filter(date_joined__gte=start, date_joined__lte=end, **extra_filter_kwargs)
        .annotate(date=TruncDate("date_joined"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    return data


def generate_default_dashboard(device):
    """
    Auto-generates a default Dashboard and Widget set for a provisioned Device
    based on its DeviceTemplate register map.
    """
    if not device.template or not device.template.register_map:
        return None

    # Check if a default dashboard for this device already exists
    dashboard, created = Dashboard.objects.get_or_create(
        team=device.team,
        device=device,
        defaults={
            "name": f"{device.name} Overview",
            "site": device.site,
            "is_default": True,
        }
    )

    if not created:
        # If it already exists, clear existing widgets to regenerate
        dashboard.widgets.all().delete()

    register_map = device.template.register_map
    row_idx = 0
    col_idx = 0

    for key, config in register_map.items():
        if not isinstance(config, dict):
            continue

        label = config.get("label", key.replace("_", " ").title())
        unit = config.get("unit", "")
        reg_type = config.get("type", "uint16")
        writable = config.get("writable", False)

        # Decide widget type
        if key in ["energy", "active_power", "output_frequency", "frequency_command"]:
            widget_type = "timeseries"
            width = 6
            height = 4
        elif reg_type == "bool":
            widget_type = "indicator"
            width = 3
            height = 3
        elif unit in ["V", "A", "°C", "bar", "m³/h", "%"] or key in ["voltage", "current", "temperature", "pressure", "flow_rate"]:
            widget_type = "gauge"
            width = 3
            height = 3
        else:
            widget_type = "value"
            width = 3
            height = 3

        # Add min/max configs for gauge
        widget_config = {}
        if widget_type == "gauge":
            if unit == "V":
                widget_config = {"min": 0, "max": 500}
            elif unit == "A":
                widget_config = {"min": 0, "max": 100}
            elif unit == "°C":
                widget_config = {"min": 0, "max": 120}
            elif unit == "bar":
                widget_config = {"min": 0, "max": 16}
            elif unit == "%":
                widget_config = {"min": 0, "max": 100}
            else:
                widget_config = {"min": config.get("min", 0), "max": config.get("max", 100)}

        Widget.objects.create(
            team=device.team,
            dashboard=dashboard,
            device=device,
            title=label,
            widget_type=widget_type,
            telemetry_key=key,
            unit=unit,
            row=row_idx,
            col=col_idx,
            width=width,
            height=height,
            config=widget_config
        )

        col_idx += width
        if col_idx >= 12:
            col_idx = 0
            row_idx += 1

    return dashboard

