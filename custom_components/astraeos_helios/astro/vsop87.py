"""Heliocentric position of the Earth from the VSOP87D theory (libastro vsop87.c)."""

from __future__ import annotations

import math

from . import _vsop87_earth_data
from .timescales import J2000

# Days per Julian millennium, the time unit of the series
_MILLENNIUM = 365250.0
# The series store amplitudes multiplied by this factor
_AMPLITUDE_SCALE = 1e8


def _sum(series: tuple[tuple[tuple[float, float, float], ...], ...], t: float) -> float:
    total = 0.0
    power = 1.0
    for terms in series:
        total += power * sum(a * math.cos(b + c * t) for a, b, c in terms)
        power *= t
    return total / _AMPLITUDE_SCALE


def earth_heliocentric(jd_tt: float) -> tuple[float, float, float]:
    """Return the Earth's heliocentric longitude and latitude in radians and its
    distance from the Sun in AU, for the ecliptic and equinox of date (FK5).

    jd_tt is a Julian day in Terrestrial Time. The series are the ones libastro
    keeps: 0.3" in longitude, a few 1e-8 AU in distance.
    """
    t = (jd_tt - J2000) / _MILLENNIUM
    longitude = _sum(_vsop87_earth_data.L, t) % (2.0 * math.pi)
    latitude = _sum(_vsop87_earth_data.B, t)
    distance = _sum(_vsop87_earth_data.R, t)

    # From the dynamical equinox of VSOP87 to the FK5 system
    l1 = longitude - math.radians(13.97 * t - 0.031 * t * t)
    c1, s1 = math.cos(l1), math.sin(l1)
    longitude += math.radians(
        (-0.09033 + 0.03916 * (c1 + s1) * math.tan(latitude)) / 3600.0
    )
    latitude += math.radians(0.03916 * (c1 - s1) / 3600.0)
    return longitude, latitude, distance
