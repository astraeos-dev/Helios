"""Geocentric and topocentric position of the Sun (libastro sun.c, circum.c)."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .frames import aberrate, ecliptic_to_equatorial, horizontal, nutate, topocentric
from .nutation import mean_obliquity, nutation
from .timescales import delta_t, greenwich_mean_sidereal_time
from .vsop87 import earth_heliocentric

# Metres per astronomical unit and equatorial radius of the Earth, as libastro
ASTRONOMICAL_UNIT_M = 1.4959787e11
EARTH_RADIUS_M = 6.37816e6


@dataclass(frozen=True)
class SunPosition:
    """Geocentric position of the Sun at a moment. Angles in degrees."""

    jd_tt: float
    # Geometric ecliptic coordinates, mean equinox of date
    longitude: float
    latitude: float
    distance_au: float
    mean_obliquity: float
    nutation_longitude: float
    nutation_obliquity: float
    # Mean equator and equinox of date: no nutation, no aberration
    astrometric_right_ascension: float
    astrometric_declination: float
    # Apparent: true equator and equinox of date, aberration included
    right_ascension: float
    declination: float


@dataclass(frozen=True)
class SunObservation:
    """The Sun seen by an observer at a moment. Angles in degrees."""

    position: SunPosition
    delta_t: float
    # Local apparent sidereal time
    sidereal_time: float
    # Topocentric: parallax included, refraction not
    hour_angle: float
    declination: float
    altitude: float
    azimuth: float


def sun_position(jd_tt: float) -> SunPosition:
    """Return the geocentric position of the Sun at a Julian day in TT."""
    earth_lon, earth_lat, distance = earth_heliocentric(jd_tt)
    lon = (earth_lon - math.pi) % (2.0 * math.pi)
    lat = -earth_lat

    obliquity = mean_obliquity(jd_tt)
    dpsi, deps = nutation(jd_tt)
    eps = math.radians(obliquity)
    mean_ra, mean_dec = ecliptic_to_equatorial(lon, lat, eps)
    ra, dec = nutate(mean_ra, mean_dec, eps, math.radians(dpsi), math.radians(deps))
    ra, dec = aberrate(ra, dec, jd_tt)

    return SunPosition(
        jd_tt=jd_tt,
        longitude=math.degrees(lon),
        latitude=math.degrees(lat),
        distance_au=distance,
        mean_obliquity=obliquity,
        nutation_longitude=dpsi,
        nutation_obliquity=deps,
        astrometric_right_ascension=math.degrees(mean_ra),
        astrometric_declination=math.degrees(mean_dec),
        right_ascension=math.degrees(ra),
        declination=math.degrees(dec),
    )


def observe_sun(
    jd: float, latitude: float, longitude: float, elevation_m: float = 0.0
) -> SunObservation:
    """Return the Sun seen at a Julian day (UT) from a place.

    latitude is geodetic and longitude positive east, in degrees; elevation_m is
    the height above sea level in metres.
    """
    dt = delta_t(jd)
    position = sun_position(jd + dt / 86400.0)

    # Apparent sidereal time: mean, plus the equation of the equinoxes
    eps = math.radians(position.mean_obliquity + position.nutation_obliquity)
    sidereal = (
        greenwich_mean_sidereal_time(jd) * 15.0
        + longitude
        + position.nutation_longitude * math.cos(eps)
    ) % 360.0

    lat = math.radians(latitude)
    hour_angle, dec, _ = topocentric(
        math.radians(sidereal - position.right_ascension),
        math.radians(position.declination),
        lat,
        elevation_m / EARTH_RADIUS_M,
        position.distance_au * ASTRONOMICAL_UNIT_M / EARTH_RADIUS_M,
    )
    altitude, azimuth = horizontal(lat, hour_angle, dec)

    hour_angle_deg = math.degrees(hour_angle)
    if hour_angle_deg > 180.0:
        hour_angle_deg -= 360.0
    return SunObservation(
        position=position,
        delta_t=dt,
        sidereal_time=sidereal,
        hour_angle=hour_angle_deg,
        declination=math.degrees(dec),
        altitude=math.degrees(altitude),
        azimuth=math.degrees(azimuth),
    )
