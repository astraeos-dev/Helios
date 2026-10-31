"""Obliquity of the ecliptic and IAU 1980 nutation (libastro obliq.c, nutation.c)."""

from __future__ import annotations

import math

from . import _nutation_data
from .timescales import J2000

_ARCSEC_PER_CIRCLE = 1296000.0
# The nutation series store amplitudes in units of 0.0001"
_AMPLITUDE_SCALE = 1e4


def mean_obliquity(jd_tt: float) -> float:
    """Return the mean obliquity of the ecliptic in degrees (IAU 1980)."""
    t = (jd_tt - J2000) / 36525.0
    return 23.4392911 + t * (-46.8150 + t * (-0.00059 + t * 0.001813)) / 3600.0


def nutation(jd_tt: float) -> tuple[float, float]:
    """Return the nutation in longitude and in obliquity, in degrees.

    The 106 terms of the IAU 1980 theory, which reproduce the almanac values to
    0.001".
    """
    t = (jd_tt - J2000) / 36525.0
    t2 = t * t
    t3 = t2 * t
    t10 = t / 10.0

    arguments = []
    for c0, c1, c2, c3 in _nutation_data.DELAUNAY:
        turns = (c0 + c1 * t + c2 * t2 + c3 * t3) / _ARCSEC_PER_CIRCLE
        arguments.append((turns - math.floor(turns)) * 2.0 * math.pi)

    secular = iter(_nutation_data.SECULAR_TERMS)
    dpsi = deps = 0.0
    for multipliers, (amp_sin, amp_cos) in zip(
        _nutation_data.MULTIPLIERS, _nutation_data.CONSTANT_TERMS, strict=True
    ):
        if not (amp_sin or amp_cos):
            _, sin0, sin1, cos0, cos1 = next(secular)
            amp_sin = sin0 + sin1 * t10
            amp_cos = cos0 + cos1 * t10
        argument = sum(m * a for m, a in zip(multipliers, arguments, strict=True))
        dpsi += amp_sin * math.sin(argument)
        deps += amp_cos * math.cos(argument)

    return dpsi / _AMPLITUDE_SCALE / 3600.0, deps / _AMPLITUDE_SCALE / 3600.0
