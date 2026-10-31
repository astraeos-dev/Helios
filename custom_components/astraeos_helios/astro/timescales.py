"""Calendar dates, Delta T and sidereal time (libastro mjd.c, deltat.c, utc_gst.c)."""

from __future__ import annotations

from datetime import datetime, timezone
import math

from . import _deltat_data

# libastro counts modified Julian dates from 1899 December 31 at 12h
MJD0 = 2415020.0
J2000 = 2451545.0
# Solar days per sidereal day
SIDEREAL_RATE = 0.9972695677


def julian_day(moment: datetime) -> float:
    """Return the Julian day of a datetime, read as UTC when it is naive."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = (moment - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds()
    return J2000 + seconds / 86400.0


def calendar_to_mjd(month: int, day: float, year: int) -> float:
    """Return the modified Julian date of a Julian (before 1582 October 15) or
    Gregorian calendar date. Year 0 does not exist: -1 is 1 BC."""
    m = month
    y = year + 1 if year < 0 else year
    if month < 3:
        m += 12
        y -= 1

    if year < 1582 or (year == 1582 and (month < 10 or (month == 10 and day < 15))):
        b = 0
    else:
        # int() truncates toward zero, as C integer division does
        a = int(y / 100)
        b = 2 - a + int(a / 4)

    c = int(365.25 * y - 0.75) - 694025 if y < 0 else int(365.25 * y) - 694025
    d = int(30.6001 * (m + 1))
    return b + c + d + day - 0.5


def mjd_to_calendar(mjd: float) -> tuple[int, float, int]:
    """Return the month, day (with its fraction) and year of a modified Julian date."""
    if mjd == 0.0:
        return 12, 31.5, 1899

    d = mjd + 0.5
    i = math.floor(d)
    f = d - i
    if f == 1:
        f = 0.0
        i += 1

    if i > -115860.0:
        a = math.floor(i / 36524.25 + 0.99835726) + 14
        i += 1 + a - math.floor(a / 4.0)

    b = math.floor(i / 365.25 + 0.802601)
    ce = i - math.floor(365.25 * b + 0.750001) + 416
    g = math.floor(ce / 30.6001)
    month = int(g - 1)
    day = ce - math.floor(30.6001 * g) + f
    year = int(b + 1899)

    if g > 13.5:
        month = int(g - 13)
    if month < 2.5:
        year = int(b + 1900)
    if year < 1:
        year -= 1
    return month, day, year


def mjd_to_year(mjd: float) -> float:
    """Return a modified Julian date as a decimal year, such as 2024.5."""
    _, _, year = mjd_to_calendar(mjd)
    if year == -1:
        year = -2
    start = calendar_to_mjd(1, 1.0, year)
    end = calendar_to_mjd(1, 1.0, year + 1)
    return year + (mjd - start) / (end - start)


def _long_term(year: float) -> float:
    """Morrison and Stephenson (2004) long-term fit of Delta T, in seconds."""
    b = 0.01 * (year - 1820.0)
    return 32.0 * b * b - 20.0


def delta_t(jd: float) -> float:
    """Return Delta T = TT - UT in seconds at a Julian day (UT).

    Tabulated from 1620 to the table's last year and interpolated (Besselian
    interpolation, Astronomical Almanac p. K11); Morrison and Stephenson (2004)
    every century before 1700 and their long-term fit beyond; a cubic joining
    the last tabulated value to that fit over the next century.
    """
    year = mjd_to_year(jd - MJD0)
    table = _deltat_data.TABLE
    first, last = _deltat_data.TABLE_START, _deltat_data.TABLE_END
    size = len(table)

    if year > last:
        if year > last + 100.0:
            return _long_term(year)
        # Cubic matching value and slope at both ends of the next 100 years
        a = 0.01 * table[-1]
        b = 0.001 * (table[-1] - table[-11])
        m0 = _long_term(last + 100.0)
        m1 = 0.64 * 0.01 * (last + 100.0 - 1820.0)
        d = 2.0e-6 * (50.0 * (m1 + b) - m0 + a)
        c = 1.0e-4 * (m0 - a - 100.0 * b - 1.0e6 * d)
        p = year - last
        return a + p * (b + p * (c + p * d))

    if year < 1700.0:
        if year <= -1000.0:
            return _long_term(year)
        historic = _deltat_data.HISTORIC
        index = (int(year) + 1000) // 100
        start = -1000 + 100 * index
        value = historic[index]
        return value + 0.01 * (year - start) * (historic[index + 1] - value)

    if math.isnan(year):
        return 0.0

    whole = math.floor(year)
    iy = int(whole - first)
    answer = float(table[iy])
    if iy + 1 >= size:
        return answer * 0.01
    p = year - whole
    answer += p * (table[iy + 1] - table[iy])
    if iy - 1 < 0 or iy + 2 >= size:
        return answer * 0.01

    # Differences of orders 1 to 4 around the interval
    diffs = []
    k = iy - 2
    for _ in range(5):
        diffs.append(0 if k < 0 or k + 1 >= size else table[k + 1] - table[k])
        k += 1
    for i in range(4):
        diffs[i] = diffs[i + 1] - diffs[i]
    b = 0.25 * p * (p - 1.0)
    answer += b * (diffs[1] + diffs[2])
    if iy + 2 >= size:
        return answer * 0.01

    for i in range(3):
        diffs[i] = diffs[i + 1] - diffs[i]
    b = 2.0 * b / 3.0
    answer += (p - 0.5) * b * diffs[1]
    if iy - 2 < 0 or iy + 3 > size:
        return answer * 0.01

    for i in range(2):
        diffs[i] = diffs[i + 1] - diffs[i]
    b = 0.125 * b * (p + 1.0) * (p - 2.0)
    answer += b * (diffs[0] + diffs[1])
    return answer * 0.01


def greenwich_mean_sidereal_time(jd: float) -> float:
    """Return the Greenwich mean sidereal time in hours at a Julian day (UT).

    IAU 1982 expression at 0h UT, advanced at the sidereal rate through the day.
    """
    mjd = jd - MJD0
    midnight = math.floor(mjd - 0.5) + 0.5
    hours = (mjd - midnight) * 24.0
    t = (midnight - (J2000 - MJD0)) / 36525.0
    at_midnight = 24110.54841 + (8640184.812866 + (0.093104 - 6.2e-6 * t) * t) * t
    return (hours / SIDEREAL_RATE + at_midnight / 3600.0) % 24.0
