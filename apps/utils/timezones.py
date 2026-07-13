from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone
from django.utils.translation import gettext

DEFAULT_OPERATIONAL_TIMEZONE = "UTC"


def get_common_timezones():
    # This is an example list of 30 common timezones. You may want to modify it for your own app.
    return [
        "Africa/Cairo",
        "Africa/Johannesburg",
        "Africa/Nairobi",
        "America/Anchorage",
        "America/Argentina/Buenos_Aires",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Mexico_City",
        "America/New_York",
        "America/Sao_Paulo",
        "America/Toronto",
        "Asia/Dubai",
        "Asia/Jerusalem",
        "Asia/Jakarta",
        "Asia/Kolkata",
        "Asia/Kuala_Lumpur",
        "Asia/Bangkok",
        "Asia/Seoul",
        "Asia/Shanghai",
        "Asia/Singapore",
        "Asia/Tokyo",
        "Australia/Perth",
        "Australia/Sydney",
        "Europe/Athens",
        "Europe/London",
        "Europe/Moscow",
        "Europe/Paris",
        "Pacific/Auckland",
        "Pacific/Fiji",
        "Pacific/Honolulu",
        "Pacific/Tongatapu",
        "UTC",
    ]


def get_timezones_display():
    all_tzs = get_common_timezones()
    return zip([""] + all_tzs, [gettext("Not Set")] + all_tzs, strict=False)


def get_site_timezone_name(site):
    timezone_name = getattr(site, "timezone", None) or DEFAULT_OPERATIONAL_TIMEZONE
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return DEFAULT_OPERATIONAL_TIMEZONE
    return timezone_name


def get_site_timezone(site):
    return ZoneInfo(get_site_timezone_name(site))


def localize_site_datetime(value, site):
    if value is None:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, UTC)
    return timezone.localtime(value, get_site_timezone(site))


def format_site_datetime(value, site, date_format="%Y-%m-%d %H:%M:%S %Z"):
    localized = localize_site_datetime(value, site)
    return "" if localized is None else localized.strftime(date_format)


def site_timezone_metadata(site):
    now = datetime.now(UTC)
    return {
        "timezone": get_site_timezone_name(site),
        "timezone_abbr": format_site_datetime(now, site, "%Z"),
    }
