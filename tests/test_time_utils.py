from datetime import datetime, timezone

from omniverse_solar_system.time_utils import calendar_to_jd, datetime_to_jd


def test_j2000():
    assert calendar_to_jd(2000, 1, 1.5) == 2451545.0
    assert datetime_to_jd(datetime(2000, 1, 1, 12, tzinfo=timezone.utc)) == 2451545.0
