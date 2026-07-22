from datetime import UTC, datetime
from types import SimpleNamespace

from apps.utils.timezones import format_site_datetime, get_site_timezone_name, localize_site_datetime


def test_format_site_datetime_for_target_operational_regions():
    instant = datetime(2026, 7, 13, 2, 42, 25, tzinfo=UTC)
    cases = [
        ("Asia/Singapore", "2026-07-13 10:42:25 +08"),
        ("Asia/Jakarta", "2026-07-13 09:42:25 WIB"),
        ("Asia/Bangkok", "2026-07-13 09:42:25 +07"),
        ("Asia/Tokyo", "2026-07-13 11:42:25 JST"),
        ("Australia/Sydney", "2026-07-13 12:42:25 AEST"),
        ("Pacific/Auckland", "2026-07-13 14:42:25 NZST"),
        ("UTC", "2026-07-13 02:42:25 UTC"),
    ]

    for timezone_name, expected in cases:
        site = SimpleNamespace(timezone=timezone_name)
        assert format_site_datetime(instant, site) == expected


def test_site_datetime_helpers_default_invalid_or_blank_timezones_to_utc():
    instant = datetime(2026, 7, 13, 2, 42, 25)

    assert get_site_timezone_name(SimpleNamespace(timezone="")) == "UTC"
    assert format_site_datetime(instant, SimpleNamespace(timezone="Not/AZone")) == "2026-07-13 02:42:25 UTC"
    assert localize_site_datetime(instant, SimpleNamespace(timezone="UTC")).tzinfo.key == "UTC"
