"""The IAU constellation containing a position (libastro constel.c).

Method of Roman (1987, PASP 99, 695): precess the position to B1875.0, where
the boundaries follow lines of constant right ascension and declination, and
take the first boundary row that encloses it.
"""

from __future__ import annotations

import math

from . import _constellation_data
from .frames import precess
from .timescales import MJD0, calendar_to_mjd, mjd_to_year

NAMES: dict[str, str] = _constellation_data.NAMES
_B1875 = mjd_to_year(calendar_to_mjd(1, 1.0, 1875))


def constellation(
    right_ascension: float, declination: float, jd_equinox: float
) -> str | None:
    """Return the abbreviation of the constellation containing a position, such as "Sco".

    Coordinates are in degrees, for the mean equator and equinox of jd_equinox.
    """
    ra, dec = precess(
        math.radians(right_ascension),
        math.radians(declination),
        mjd_to_year(jd_equinox - MJD0),
        _B1875,
    )
    # Units of the boundary table, truncated as in C
    ra_units = int(math.degrees(ra) / 15.0 * 1800.0)
    dec_units = int(math.degrees(dec) * 60.0)
    if dec < 0.0:
        dec_units -= 1

    band = int((dec_units + 5400) / 300)
    if not 0 <= band <= 36:
        return None
    for lower_ra, upper_ra, lower_dec, abbreviation in _constellation_data.BOUNDS[
        _constellation_data.START[band] :
    ]:
        if lower_dec <= dec_units and lower_ra <= ra_units < upper_ra:
            return abbreviation
    return None
