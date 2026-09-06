from omniverse_solar_system.constants import PLANET_COLORS, PLANET_TARGETS


def test_pluto_is_ninth_primary_planet() -> None:
    assert len(PLANET_TARGETS) == 9
    assert PLANET_TARGETS[-1][0] == "Pluto"
    assert PLANET_TARGETS[-1][1] == "PLUTO BARYCENTER"
    assert len(PLANET_COLORS) == len(PLANET_TARGETS)
