"""Changes of coordinates (libastro eq_ecl.c, nutation.c, aberration.c, precess.c,
parallax.c, aa_hadec.c). Angles are in radians."""

from __future__ import annotations

import math

from .timescales import J2000

_TWO_PI = 2.0 * math.pi


def spherical_to_cartesian(
    lon: float, lat: float, r: float
) -> tuple[float, float, float]:
    rcb = r * math.cos(lat)
    return rcb * math.cos(lon), rcb * math.sin(lon), r * math.sin(lat)


def cartesian_to_spherical(x: float, y: float, z: float) -> tuple[float, float, float]:
    """Return longitude in [0, 2pi), latitude and radius."""
    rho = x * x + y * y
    if rho > 0.0:
        return (
            math.atan2(y, x) % _TWO_PI,
            math.atan(z / math.sqrt(rho)),
            math.sqrt(rho + z * z),
        )
    lat = 0.0 if z == 0.0 else math.copysign(math.pi / 2.0, z)
    return 0.0, lat, abs(z)


def ecliptic_to_equatorial(
    lon: float, lat: float, obliquity: float
) -> tuple[float, float]:
    """Return the right ascension in [0, 2pi) and declination of ecliptic coordinates."""
    se, ce = math.sin(obliquity), math.cos(obliquity)
    sy, cy = math.sin(lat), max(math.cos(lat), 1e-20)
    sx, cx = math.sin(lon), math.cos(lon)
    dec = math.asin(max(-1.0, min(1.0, sy * ce + cy * se * sx)))
    ra = math.atan2(sx * ce - sy / cy * se, cx) % _TWO_PI
    return ra, dec


def nutate(
    ra: float, dec: float, obliquity: float, dpsi: float, deps: float
) -> tuple[float, float]:
    """Move equatorial coordinates from the mean to the true equator and equinox.

    Three rotations: to the ecliptic by the mean obliquity, along it by the
    nutation in longitude, back by the true obliquity.
    """
    se, ce = math.sin(obliquity), math.cos(obliquity)
    sp, cp = math.sin(dpsi), math.cos(dpsi)
    sede, cede = math.sin(obliquity + deps), math.cos(obliquity + deps)
    x0, y0, z0 = spherical_to_cartesian(ra, dec, 1.0)
    x = cp * x0 - sp * ce * y0 - sp * se * z0
    y = (
        cede * sp * x0
        + (cede * cp * ce + sede * se) * y0
        + (cede * cp * se - sede * ce) * z0
    )
    z = (
        sede * sp * x0
        + (sede * cp * ce - cede * se) * y0
        + (sede * cp * se + cede * ce) * z0
    )
    ra, dec, _ = cartesian_to_spherical(x, y, z)
    return ra, dec


def aberrate(ra: float, dec: float, jd_tt: float) -> tuple[float, float]:
    """Apply the annual aberration to equatorial coordinates of date.

    Montenbruck's form: within 0.2" of the complete one below a declination of 89.9°.
    """
    x, y, z = spherical_to_cartesian(ra, dec, 1.0)
    earth = _TWO_PI * (0.27908 + 100.00214 * (jd_tt - J2000) / 36525.0)
    cos_earth = math.cos(earth)
    ra, dec, _ = cartesian_to_spherical(
        x - 0.994e-4 * math.sin(earth),
        y + 0.912e-4 * cos_earth,
        z + 0.395e-4 * cos_earth,
    )
    return ra, dec


def precess(
    ra: float, dec: float, from_year: float, to_year: float
) -> tuple[float, float]:
    """Precess equatorial coordinates between two equinoxes given as decimal years.

    Rigorous precession through J2000.0 (Astronomical Ephemeris 1989, p. B18).
    """
    alpha, delta = math.degrees(ra), math.degrees(dec)

    def angles(year: float) -> tuple[float, float, float]:
        t = (year - 2000.0) / 100.0
        zeta = 0.6406161 * t + 0.0000839 * t * t + 0.0000050 * t * t * t
        z = 0.6406161 * t + 0.0003041 * t * t + 0.0000051 * t * t * t
        theta = 0.5567530 * t - 0.0001185 * t * t - 0.0000116 * t * t * t
        return math.radians(zeta), math.radians(z), math.radians(theta)

    if abs(from_year - 2000.0) > 0.02:
        zeta, z, theta = angles(from_year)
        a, d = math.radians(alpha) - z, math.radians(delta)
        x = math.sin(a) * math.cos(d)
        y = math.cos(a) * math.cos(theta) * math.cos(d) + math.sin(theta) * math.sin(d)
        w = -math.cos(a) * math.sin(theta) * math.cos(d) + math.cos(theta) * math.sin(d)
        alpha = (math.degrees(math.atan2(x, y) - zeta)) % 360.0
        delta = math.degrees(math.asin(w))

    if abs(to_year - 2000.0) > 0.02:
        zeta, z, theta = angles(to_year)
        a, d = math.radians(alpha) + zeta, math.radians(delta)
        x = math.sin(a) * math.cos(d)
        y = math.cos(a) * math.cos(theta) * math.cos(d) - math.sin(theta) * math.sin(d)
        w = math.cos(a) * math.sin(theta) * math.cos(d) + math.cos(theta) * math.sin(d)
        alpha = (math.degrees(math.atan2(x, y) + z)) % 360.0
        delta = math.degrees(math.asin(w))

    return math.radians(alpha), math.radians(delta)


def topocentric(
    hour_angle: float, dec: float, latitude: float, height: float, distance: float
) -> tuple[float, float, float]:
    """Return the hour angle in [0, 2pi), declination and distance seen from the
    observer instead of the Earth's centre (parallax).

    latitude is geodetic; height and distance are in equatorial Earth radii.
    """
    flattening = 1.0 / 298.257
    e2 = (2.0 - flattening) * flattening
    sphi, cphi = math.sin(latitude), math.cos(latitude)
    robs = 1.0 / math.sqrt(1.0 - e2 * sphi * sphi)
    xobs = (robs + height) * cphi
    zobs = (robs * (1.0 - e2) + height) * sphi
    x, y, z = spherical_to_cartesian(-hour_angle, dec, distance)
    ha, dec, distance = cartesian_to_spherical(x - xobs, y, z - zobs)
    return (-ha) % _TWO_PI, dec, distance


def horizontal(latitude: float, hour_angle: float, dec: float) -> tuple[float, float]:
    """Return the altitude and the azimuth in [0, 2pi), from north through east."""
    # Spherical triangle pole, zenith, body (libastro solve_sphere)
    a, b = -hour_angle, math.pi / 2.0 - dec
    cc, sc = math.sin(latitude), math.cos(latitude)
    cb, sb = math.cos(b), math.sin(b)
    cos_zenith = max(-1.0, min(1.0, cb * cc + sb * sc * math.cos(a)))
    if sc < 1e-7:
        azimuth = a if cc < 0 else math.pi - a
    else:
        azimuth = math.atan2(math.sin(a) * sb * sc, cb - cos_zenith * cc)
    return math.pi / 2.0 - math.acos(cos_zenith), azimuth % _TWO_PI
