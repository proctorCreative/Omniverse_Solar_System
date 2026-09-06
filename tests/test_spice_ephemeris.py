from datetime import datetime, timedelta, timezone

from omniverse_solar_system.spice_ephemeris import SpiceEphemeris


class FakeSpice:
    def __init__(self) -> None:
        self.received = None

    def str2et(self, value: str) -> float:
        self.received = value
        return 123.5


def make_ephemeris_with_fake_spice() -> tuple[SpiceEphemeris, FakeSpice]:
    ephemeris = SpiceEphemeris.__new__(SpiceEphemeris)
    fake = FakeSpice()
    ephemeris.spice = fake
    return ephemeris, fake


def test_spice_time_uses_iso_z_suffix() -> None:
    ephemeris, fake = make_ephemeris_with_fake_spice()
    result = ephemeris._et(datetime(2026, 7, 29, 7, 1, 2, 345678, tzinfo=timezone.utc))
    assert result == 123.5
    assert fake.received == "2026-07-29T07:01:02.345678Z"


def test_spice_time_normalizes_offset_to_utc() -> None:
    ephemeris, fake = make_ephemeris_with_fake_spice()
    phoenix = timezone(timedelta(hours=-7))
    ephemeris._et(datetime(2026, 7, 29, 0, 1, 2, tzinfo=phoenix))
    assert fake.received == "2026-07-29T07:01:02.000000Z"


def test_spice_time_treats_naive_datetime_as_utc() -> None:
    ephemeris, fake = make_ephemeris_with_fake_spice()
    ephemeris._et(datetime(2026, 7, 29, 7, 1, 2))
    assert fake.received == "2026-07-29T07:01:02.000000Z"


def test_spice_ephemeris_requests_equatorial_j2000_frame() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "omniverse_solar_system"
        / "spice_ephemeris.py"
    ).read_text()
    assert '"J2000", "NONE", "SUN"' in source
    assert '"ECLIPJ2000", "NONE", "SUN"' not in source
