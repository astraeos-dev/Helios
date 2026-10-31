"""Tests for the astro package, a port of libastro, the C core of PyEphem."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib
from pathlib import Path
import random
import sys
import types

import pytest

# Import the package without the integration's __init__, which needs Home Assistant
if "astraeos_helios" not in sys.modules:
    _package = types.ModuleType("astraeos_helios")
    _package.__path__ = [
        str(
            Path(__file__).resolve().parents[1]
            / "custom_components"
            / "astraeos_helios"
        )
    ]
    sys.modules["astraeos_helios"] = _package
astro = importlib.import_module("astraeos_helios.astro")
timescales = importlib.import_module("astraeos_helios.astro.timescales")


def _angle_between(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def test_julian_day() -> None:
    assert astro.julian_day(datetime(2000, 1, 1, 12, tzinfo=timezone.utc)) == 2451545.0
    # Meeus Example 7.a: 1957 October 4.81
    moment = datetime(1957, 10, 4, 19, 26, 24, tzinfo=timezone.utc)
    assert astro.julian_day(moment) == pytest.approx(2436116.31, abs=1e-8)


@pytest.mark.parametrize(
    ("month", "day", "year"),
    [
        (1, 1.0, 1875),
        (10, 15.5, 1582),
        (10, 4.25, 1582),
        (2, 29.0, 2024),
        (3, 1.0, -44),
    ],
)
def test_calendar_round_trip(month: int, day: float, year: int) -> None:
    mjd = timescales.calendar_to_mjd(month, day, year)
    assert timescales.mjd_to_calendar(mjd) == (month, pytest.approx(day), year)


def test_gregorian_reform() -> None:
    """Thursday 1582 October 4 (Julian) is followed by Friday October 15 (Gregorian)."""
    assert timescales.calendar_to_mjd(10, 15.0, 1582) - timescales.calendar_to_mjd(
        10, 4.0, 1582
    ) == pytest.approx(1.0)


def test_greenwich_mean_sidereal_time() -> None:
    """Meeus Example 12.a: 1987 April 10 at 0h UT, 13h10m46.3668s."""
    jd = astro.julian_day(datetime(1987, 4, 10, tzinfo=timezone.utc))
    expected = 13 + 10 / 60 + 46.3668 / 3600
    assert astro.greenwich_mean_sidereal_time(jd) == pytest.approx(expected, abs=1e-7)


def test_nutation_and_obliquity() -> None:
    """Meeus Example 22.a: 1987 April 10 at 0h TD."""
    jd = astro.julian_day(datetime(1987, 4, 10, tzinfo=timezone.utc))
    dpsi, deps = astro.nutation(jd)
    assert dpsi * 3600 == pytest.approx(-3.788, abs=0.001)
    assert deps * 3600 == pytest.approx(9.443, abs=0.001)
    expected = 23 + 26 / 60 + 27.407 / 3600
    assert astro.mean_obliquity(jd) == pytest.approx(expected, abs=0.001 / 3600)


# PyEphem 4.2.1: Delta T, apparent geocentric RA and Dec, distance, then
# topocentric altitude and azimuth without refraction, and constellation
PYEPHEM_REFERENCES = (
    ("2024-03-20T12:00", 48.8566, 2.3522, 35, 72.3677, 0.3377446, 0.1465486,
     0.99596500, 41.286007, 180.698610, "Psc"),
    ("1987-04-10T19:21", -33.87, 151.21, 0, 55.4544, 18.8316169, 7.9682439,
     1.00189269, -11.788372, 88.252253, "Psc"),
    ("2050-12-21T04:30", 69.6492, 18.9553, 0, 109.9389, 269.4389901, -23.4293791,
     0.98382318, -22.936426, 95.782468, "Sgr"),
    ("1910-07-01T22:00", -13.83, -171.76, 1000, 10.9493, 99.9519954, 23.1366191,
     1.01672912, 46.898831, 31.205628, "Gem"),
)  # fmt: skip


@pytest.mark.parametrize("reference", PYEPHEM_REFERENCES, ids=lambda r: r[0][:4])
def test_sun_matches_pyephem(reference: tuple) -> None:
    when, lat, lon, elevation, dt, ra, dec, distance, alt, az, abbreviation = reference
    jd = astro.julian_day(datetime.fromisoformat(when).replace(tzinfo=timezone.utc))
    seen = astro.observe_sun(jd, lat, lon, elevation)
    position = seen.position

    assert seen.delta_t == pytest.approx(dt, abs=1e-4)
    # 0.001": the references are rounded to 1e-7°
    assert _angle_between(position.right_ascension, ra) < 1e-6
    assert position.declination == pytest.approx(dec, abs=1e-6)
    assert position.distance_au == pytest.approx(distance, abs=1e-7)
    # PyEphem keeps altitude and azimuth in single precision
    assert seen.altitude == pytest.approx(alt, abs=1e-5)
    assert _angle_between(seen.azimuth, az) < 1e-5
    assert (
        astro.constellation(
            position.astrometric_right_ascension,
            position.astrometric_declination,
            position.jd_tt,
        )
        == abbreviation
    )


@pytest.mark.parametrize(
    ("ra", "dec", "abbreviation"),
    [
        (279.2347, 38.7837, "Lyr"),  # Vega
        (101.2872, -16.7161, "CMa"),  # Sirius
        (37.9546, 89.2641, "UMi"),  # Polaris
        (247.3519, -26.4320, "Sco"),  # Antares
        (88.7929, 7.4071, "Ori"),  # Betelgeuse
        (186.6496, -63.0991, "Cru"),  # Acrux
    ],
)
def test_constellation_of_stars(ra: float, dec: float, abbreviation: str) -> None:
    assert astro.constellation(ra, dec, 2451545.0) == abbreviation
    assert astro.CONSTELLATION_NAMES[abbreviation]


def test_sweep_against_pyephem() -> None:
    """Random moments from 1900 to 2100 and places, against PyEphem itself."""
    ephem = pytest.importorskip("ephem")
    import math

    rng = random.Random(2024)
    start = datetime(1900, 1, 1, tzinfo=timezone.utc)
    for _ in range(300):
        moment = start + timedelta(days=rng.uniform(0, 73000))
        lat, lon = rng.uniform(-66.0, 66.0), rng.uniform(-180.0, 180.0)
        seen = astro.observe_sun(astro.julian_day(moment), lat, lon)
        date = ephem.Date(moment.replace(tzinfo=None))
        sun = ephem.Sun(date)
        observer = ephem.Observer()
        observer.lat, observer.lon, observer.pressure = str(lat), str(lon), 0
        observer.date = date
        local = ephem.Sun(observer)

        assert seen.delta_t == pytest.approx(ephem.delta_t(date), abs=1e-6)
        assert (
            _angle_between(seen.position.right_ascension, math.degrees(sun.g_ra)) < 1e-6
        )
        assert seen.position.declination == pytest.approx(
            math.degrees(sun.g_dec), abs=1e-6
        )
        assert seen.position.distance_au == pytest.approx(sun.earth_distance, abs=1e-7)
        assert seen.altitude == pytest.approx(math.degrees(local.alt), abs=1e-4)
        if seen.altitude > -85.0:
            assert _angle_between(seen.azimuth, math.degrees(local.az)) < 1e-3
        position = seen.position
        assert (
            astro.constellation(
                position.astrometric_right_ascension,
                position.astrometric_declination,
                position.jd_tt,
            )
            == ephem.constellation(sun)[0]
        )
