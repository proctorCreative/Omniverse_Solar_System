"""Physical, coordinate-frame, and rendering constants."""

from __future__ import annotations

import math

AU_KM = 149_597_870.7
GAUSSIAN_K_RAD_PER_DAY = 0.01720209895
SECONDS_PER_DAY = 86_400.0
DEG_TO_RAD = math.pi / 180.0
RAD_TO_DEG = 180.0 / math.pi
J2000_JD = 2_451_545.0

# IAU 1976 mean obliquity at J2000.0: 84,381.448 arcseconds.
J2000_MEAN_OBLIQUITY_DEG = 23.43929111111111
J2000_MEAN_OBLIQUITY_RAD = J2000_MEAN_OBLIQUITY_DEG * DEG_TO_RAD

# DE440 target, approximate sidereal period in days. Pluto is intentionally
# included in the orrery's primary planet set.
PLANET_TARGETS = (
    ("Mercury", "MERCURY BARYCENTER", 87.9691),
    ("Venus", "VENUS BARYCENTER", 224.701),
    ("Earth", "EARTH", 365.256),
    ("Mars", "MARS BARYCENTER", 686.980),
    ("Jupiter", "JUPITER BARYCENTER", 4_332.589),
    ("Saturn", "SATURN BARYCENTER", 10_759.22),
    ("Uranus", "URANUS BARYCENTER", 30_688.5),
    ("Neptune", "NEPTUNE BARYCENTER", 60_182.0),
    ("Pluto", "PLUTO BARYCENTER", 90_560.0),
)

PLANET_COLORS = (
    (0.72, 0.70, 0.66, 1.0),
    (0.95, 0.75, 0.38, 1.0),
    (0.28, 0.58, 1.00, 1.0),
    (0.93, 0.36, 0.20, 1.0),
    (0.88, 0.67, 0.45, 1.0),
    (0.87, 0.78, 0.56, 1.0),
    (0.45, 0.86, 0.92, 1.0),
    (0.31, 0.48, 0.94, 1.0),
    (0.76, 0.64, 0.54, 1.0),
)
