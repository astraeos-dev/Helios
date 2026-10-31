"""Pure Python solar calculation engine.

Equations and chapter references come from Astronomical Algorithms
(J. Meeus, 2nd edition, Willmann-Bell, 1998).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import math

# Astronomical unit in kilometres (IAU 2012 Resolution B2)
ASTRONOMICAL_UNIT_KM = 149_597_870.7


def degrees_to_hms(degrees: float) -> str:
    """Return an angle as hours, minutes and seconds of time, such as "13h 13m 31.4s"."""
    # Tenths of a second of time: 1° = 4 min = 2400 tenths
    tenths = round(degrees % 360.0 * 2400.0) % 864_000
    hours, tenths = divmod(tenths, 36_000)
    minutes, tenths = divmod(tenths, 600)
    return f"{hours:02d}h {minutes:02d}m {tenths / 10:04.1f}s"


@dataclass(frozen=True)
class SolarData:
    """Container for calculated solar position and times."""

    julian_day: float
    julian_century: float
    mean_longitude: float
    mean_anomaly: float
    eccentricity: float
    equation_of_center: float
    true_longitude: float
    apparent_longitude: float
    obliquity: float
    right_ascension: float
    declination: float
    equation_of_time: float
    sun_distance_au: float
    sun_distance_km: float
    constellation: str
    hour_angle: float
    true_elevation: float
    apparent_elevation: float
    azimuth: float
    day_length_minutes: float
    solar_noon: datetime | None
    solar_midnight: datetime | None
    sunrise: datetime | None
    sunset: datetime | None
    civil_dawn: datetime | None
    civil_dusk: datetime | None
    nautical_dawn: datetime | None
    nautical_dusk: datetime | None
    astronomical_dawn: datetime | None
    astronomical_dusk: datetime | None
    blue_hour_dawn: datetime | None
    blue_hour_dusk: datetime | None
    golden_hour_dawn: datetime | None
    golden_hour_dusk: datetime | None
    # Azimuth of the Sun at each daily event above, keyed by its field name
    event_azimuths: dict[str, float]
    is_above_horizon: bool
    is_golden_hour: bool
    is_blue_hour: bool

    def next_transition(self, moment: datetime) -> datetime | None:
        """Return the first event from moment on that can change a binary state.

        Covers sunrise, sunset and the bounds of the blue and golden hours, plus
        solar midnight, where the timestamps move on to the next solar day.
        """
        events = (
            self.civil_dawn,
            self.blue_hour_dawn,
            self.sunrise,
            self.golden_hour_dawn,
            self.golden_hour_dusk,
            self.sunset,
            self.blue_hour_dusk,
            self.civil_dusk,
            self.solar_midnight,
        )
        return min(
            (event for event in events if event is not None and event >= moment),
            default=None,
        )


class SolarEngine:
    """Astronomical calculation engine for solar position and daily events."""

    # Standard altitude thresholds in degrees (Meeus Chapter 15, p. 101)
    ALTITUDE_SUNRISE_SUNSET = -0.8333  # -50 arcminutes (refraction + solar semi-diameter)
    ALTITUDE_CIVIL_TWILIGHT = -6.0
    ALTITUDE_NAUTICAL_TWILIGHT = -12.0
    ALTITUDE_ASTRONOMICAL_TWILIGHT = -18.0
    # Photographic light, not astronomical standards: the blue hour runs from civil
    # twilight (-6°) to -4°, the golden hour from -4° to +6°
    ALTITUDE_BLUE_HOUR = -4.0
    ALTITUDE_GOLDEN_HOUR = 6.0

    # Lowest true altitude where Saemundsson's refraction formula holds (Chapter 16)
    REFRACTION_FORMULA_LIMIT = -1.0

    # Corrections of an event time, in days: larger ones are not trusted, and
    # smaller ones (under 10 ms) end the refinement
    MAX_EVENT_CORRECTION = 10.0 / 1440.0
    EVENT_PRECISION = 1e-7

    # Where the Sun enters each constellation along the ecliptic: J2000.0 ecliptic
    # longitude in 2000 and its drift in degrees per century, as the ecliptic moves
    # against the IAU boundaries. Found with PyEphem's IAU boundaries, 1900 to 2100.
    CONSTELLATION_BOUNDARIES: tuple[tuple[float, float, str], ...] = (
        (28.6869, -0.0028, "aries"),
        (53.4172, -0.0030, "taurus"),
        (90.1401, -0.0002, "gemini"),
        (117.9880, 0.0021, "cancer"),
        (138.0384, 0.0025, "leo"),
        (173.8508, 0.0, "virgo"),
        (217.8100, -0.0031, "libra"),
        (241.0486, 0.0543, "scorpius"),
        (247.6377, -0.0022, "ophiuchus"),
        (266.2376, -0.0006, "sagittarius"),
        (299.6561, 0.0022, "capricornus"),
        (327.4876, 0.0022, "aquarius"),
        (351.6505, -0.0018, "pisces"),
    )

    def __init__(
        self,
        latitude: float,
        longitude: float,
        elevation_meters: float = 0.0,
    ) -> None:
        """Initialize the solar engine with observer coordinates.

        Note on longitude convention:
        Standard GIS/Home Assistant uses East positive, West negative.
        Meeus uses West positive in some formulas; conversions are handled internally.
        """
        self.latitude = latitude
        self.longitude = longitude
        self.elevation_meters = elevation_meters
        # Sunrise/sunset threshold lowered by the dip of the visible horizon
        self.sunrise_sunset_altitude = self.ALTITUDE_SUNRISE_SUNSET - self.horizon_dip(
            elevation_meters
        )

    @staticmethod
    def horizon_dip(elevation_meters: float) -> float:
        """Return the dip of the visible horizon in degrees for an observer's height.

        An elevated observer sees past the astronomical horizon, so the Sun rises
        earlier and sets later. Uses the almanac approximation dip = 1.76' x sqrt(h)
        (h in meters, terrestrial refraction included); Meeus Chapter 15 assumes h = 0.
        Twilights and the blue and golden hours are defined against the astronomical
        horizon and are not affected.
        """
        if elevation_meters <= 0.0:
            return 0.0
        return 1.76 * math.sqrt(elevation_meters) / 60.0

    @staticmethod
    def to_julian_day(dt_utc: datetime) -> float:
        """Calculate Julian Day (JD) from a UTC datetime (Meeus Chapter 7, Eq. 7.1)."""
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt_utc.astimezone(timezone.utc)

        year = dt_utc.year
        month = dt_utc.month
        day_fraction = (
            dt_utc.day
            + (
                dt_utc.hour
                + (dt_utc.minute + (dt_utc.second + dt_utc.microsecond / 1e6) / 60.0)
                / 60.0
            )
            / 24.0
        )

        if month <= 2:
            year -= 1
            month += 12

        a_val = math.floor(year / 100.0)
        b_val = 2 - a_val + math.floor(a_val / 4.0)

        jd = (
            math.floor(365.25 * (year + 4716))
            + math.floor(30.6001 * (month + 1))
            + day_fraction
            + b_val
            - 1524.5
        )
        return jd

    @staticmethod
    def to_julian_century(jd: float) -> float:
        """Calculate Julian Century (T) from J2000.0 (Meeus Chapter 25, Eq. 25.1)."""
        return (jd - 2451545.0) / 36525.0

    @staticmethod
    def _solar_coordinates(t_century: float) -> dict[str, float]:
        """Compute solar coordinates for a given Julian Century T (Meeus Chapter 25 & 28)."""
        # Geometric Mean Longitude of the Sun L0 (Eq. 25.2)
        l0 = (
            280.46646 + t_century * (36000.76983 + 0.0003032 * t_century)
        ) % 360.0

        # Mean Anomaly of the Sun M (Eq. 25.3)
        m_deg = (
            357.52911 + t_century * (35999.05029 - 0.0001537 * t_century)
        ) % 360.0
        m_rad = math.radians(m_deg)

        # Eccentricity of Earth's Orbit e (Eq. 25.4)
        eccentricity = 0.016708634 - t_century * (
            0.000042037 + 0.0000001267 * t_century
        )

        # Sun's Equation of the Center C (Chapter 25, p. 164)
        c_deg = (
            (1.914602 - t_century * (0.004817 + 0.000014 * t_century))
            * math.sin(m_rad)
            + (0.019993 - 0.000101 * t_century) * math.sin(2.0 * m_rad)
            + 0.000289 * math.sin(3.0 * m_rad)
        )

        # Sun's True Longitude and True Anomaly
        true_longitude = (l0 + c_deg) % 360.0
        true_anomaly_rad = math.radians(m_deg + c_deg)

        # Sun's Radius Vector (Distance in AU, Eq. 25.5)
        distance_au = (1.000001018 * (1.0 - eccentricity * eccentricity)) / (
            1.0 + eccentricity * math.cos(true_anomaly_rad)
        )

        # Longitude of the Ascending Node of the Moon's mean orbit (Chapter 25, p. 164)
        omega_deg = 125.04 - 1934.136 * t_century
        omega_rad = math.radians(omega_deg)

        # Sun's Apparent Longitude lambda (Eq. 25.8)
        apparent_longitude = (
            true_longitude - 0.00569 - 0.00478 * math.sin(omega_rad)
        ) % 360.0
        lambda_rad = math.radians(apparent_longitude)

        # Mean Obliquity of the Ecliptic epsilon0 (Meeus Chapter 22, Eq. 22.2)
        seconds = 21.448 - t_century * (
            46.8150 + t_century * (0.00059 - 0.001813 * t_century)
        )
        epsilon0_deg = 23.0 + (26.0 + (seconds / 60.0)) / 60.0

        # Corrected Obliquity epsilon (Eq. 25.8)
        obliquity_deg = epsilon0_deg + 0.00256 * math.cos(omega_rad)
        obliquity_rad = math.radians(obliquity_deg)

        # Right Ascension alpha (Eq. 25.6) and Declination delta (Eq. 25.7)
        right_ascension_rad = math.atan2(
            math.cos(obliquity_rad) * math.sin(lambda_rad),
            math.cos(lambda_rad),
        )
        right_ascension_deg = math.degrees(right_ascension_rad) % 360.0

        declination_rad = math.asin(
            math.sin(obliquity_rad) * math.sin(lambda_rad)
        )
        declination_deg = math.degrees(declination_rad)

        # Equation of Time in minutes (Meeus Chapter 28, Eq. 28.3)
        y_val = math.tan(obliquity_rad / 2.0) ** 2
        l0_rad = math.radians(l0)
        eq_time_rad = (
            y_val * math.sin(2.0 * l0_rad)
            - 2.0 * eccentricity * math.sin(m_rad)
            + 4.0 * eccentricity * y_val * math.sin(m_rad) * math.cos(2.0 * l0_rad)
            - 0.5 * y_val * y_val * math.sin(4.0 * l0_rad)
            - 1.25 * eccentricity * eccentricity * math.sin(2.0 * m_rad)
        )
        equation_of_time_min = 4.0 * math.degrees(eq_time_rad)

        return {
            "l0": l0,
            "m_deg": m_deg,
            "eccentricity": eccentricity,
            "c_deg": c_deg,
            "true_longitude": true_longitude,
            "apparent_longitude": apparent_longitude,
            "obliquity": obliquity_deg,
            "right_ascension": right_ascension_deg,
            "declination": declination_deg,
            "equation_of_time": equation_of_time_min,
            "distance_au": distance_au,
        }

    def _calculate_event_time(
        self,
        local_date: date,
        target_altitude: float,
        is_rising: bool | None,
    ) -> datetime | None:
        """Calculate Sunrise, Sunset, Twilight, or Solar Noon using Meeus Chapter 15.

        Uses a two-pass refinement for high accuracy across the day.
        If is_rising is None, computes Solar Noon (Transit).
        local_date is the date of the solar day in local mean solar time: anchoring
        on its UTC midnight puts the transit near 12:00 local mean time, and offsets
        beyond [0, 1440) minutes land on the adjacent UTC day far from Greenwich.
        """
        midnight_utc = datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )
        jd_midnight = self.to_julian_day(midnight_utc)

        # Two-pass iterative refinement
        fraction_of_day = 0.5
        for _ in range(2):
            t_century = self.to_julian_century(jd_midnight + fraction_of_day)
            coords = self._solar_coordinates(t_century)
            eq_time = coords["equation_of_time"]
            decl_rad = math.radians(coords["declination"])

            # Solar noon in minutes from UTC midnight
            solar_noon_min = 720.0 - (4.0 * self.longitude) - eq_time

            if is_rising is None:
                fraction_of_day = solar_noon_min / 1440.0
                continue

            lat_rad = math.radians(self.latitude)
            alt_rad = math.radians(target_altitude)

            # Hour angle H0 (Meeus Chapter 15, Eq. 15.1)
            cos_h0 = (
                math.sin(alt_rad) - math.sin(lat_rad) * math.sin(decl_rad)
            ) / (math.cos(lat_rad) * math.cos(decl_rad))

            # Check for circumpolar sun (polar day or polar night)
            if cos_h0 < -1.0 or cos_h0 > 1.0:
                return None

            h0_deg = math.degrees(math.acos(cos_h0))
            delta_minutes = 4.0 * h0_deg

            if is_rising:
                event_minutes = solar_noon_min - delta_minutes
            else:
                event_minutes = solar_noon_min + delta_minutes

            fraction_of_day = event_minutes / 1440.0

        fraction_of_day = self._refine_event(
            jd_midnight,
            fraction_of_day,
            None if is_rising is None else target_altitude,
        )
        return midnight_utc + timedelta(days=fraction_of_day)

    def _refine_event(
        self,
        jd_midnight: float,
        fraction_of_day: float,
        target_altitude: float | None,
    ) -> float:
        """Correct an event time with the Sun's position at that time (Chapter 15).

        The equation of time estimate can be a few seconds off the elevation that
        calculate() finds, enough for a refresh at the event to show the previous
        state. Meeus corrects a transit by -H / 360° and a rising or setting by
        (h - h0) / (360° cos δ cos φ sin H) days (p. 103). target_altitude None
        means a transit: the upper one near H = 0°, the lower one near ±180°.
        Keeps the estimate when the corrections do not settle, as when the Sun
        barely reaches the altitude.
        """
        refined = fraction_of_day
        for _ in range(5):
            jd = jd_midnight + refined
            t_century = self.to_julian_century(jd)
            coords = self._solar_coordinates(t_century)
            hour_angle, altitude = self._hour_angle_and_altitude(
                jd, t_century, coords
            )
            if target_altitude is None:
                offset = hour_angle
                if abs(hour_angle) > 90.0:
                    offset -= math.copysign(180.0, hour_angle)
                correction = -offset / 360.0
            else:
                slope = (
                    360.0
                    * math.cos(math.radians(coords["declination"]))
                    * math.cos(math.radians(self.latitude))
                    * math.sin(math.radians(hour_angle))
                )
                if slope == 0.0:
                    return fraction_of_day
                correction = (altitude - target_altitude) / slope
            if abs(correction) > self.MAX_EVENT_CORRECTION:
                return fraction_of_day
            refined += correction
            if abs(correction) < self.EVENT_PRECISION:
                return refined
        return fraction_of_day

    def _solar_date(self, dt_utc: datetime) -> date:
        """Return the local mean solar date of the solar day containing dt_utc.

        A solar day runs from one solar midnight to the next, so every dawn and dusk
        of the day happens while it is current, even a dusk after civil midnight.
        It only depends on longitude, which also keeps the right day where the time
        zone is a day away from it (UTC+13/+14 west of the 180th meridian).
        """
        solar_date = (dt_utc + timedelta(hours=self.longitude / 15.0)).date()
        # Local mean time drifts from the true Sun by the equation of time (±16 min)
        if dt_utc > self._calculate_solar_midnight(solar_date):
            return solar_date + timedelta(days=1)
        if dt_utc <= self._calculate_solar_midnight(solar_date - timedelta(days=1)):
            return solar_date - timedelta(days=1)
        return solar_date

    def _calculate_solar_midnight(self, local_date: date) -> datetime:
        """Return the lower transit of the Sun that ends the solar day of local_date.

        The Sun is at its lowest, half a turn of hour angle after solar noon. Uses the
        same two-pass refinement of the equation of time as the transit (Chapter 15).
        """
        midnight_utc = datetime(
            local_date.year,
            local_date.month,
            local_date.day,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )
        jd_midnight = self.to_julian_day(midnight_utc)

        fraction_of_day = 1.0
        for _ in range(2):
            t_century = self.to_julian_century(jd_midnight + fraction_of_day)
            eq_time = self._solar_coordinates(t_century)["equation_of_time"]
            # Apparent solar time reaches 24:00 at this many minutes from UTC midnight
            fraction_of_day = (1440.0 - (4.0 * self.longitude) - eq_time) / 1440.0

        fraction_of_day = self._refine_event(jd_midnight, fraction_of_day, None)
        return midnight_utc + timedelta(days=fraction_of_day)

    def _is_up_at_solar_midnight(self, moment: datetime) -> bool:
        """Return True if the Sun stays above the horizon through its lower transit."""
        t_century = self.to_julian_century(self.to_julian_day(moment))
        declination = self._solar_coordinates(t_century)["declination"]
        # Altitude at lower transit: sin(h) = sin φ sin δ - cos φ cos δ = -cos(φ + δ)
        lowest_altitude = math.degrees(
            math.asin(-math.cos(math.radians(self.latitude + declination)))
        )
        return lowest_altitude > self.sunrise_sunset_altitude

    def _calculate_day_length(
        self,
        solar_noon: datetime,
        sunrise: datetime | None,
        sunset: datetime | None,
    ) -> float:
        """Return the minutes the Sun spends above the horizon during the solar day.

        The solar day runs from solar midnight to solar midnight (solar noon ± 12 h).
        Without a sunrise (or sunset) in it, the Sun is either up from (or until)
        solar midnight, as around the midnight sun, or it does not rise at all.
        """
        day_start = solar_noon - timedelta(hours=12)
        day_end = solar_noon + timedelta(hours=12)
        if sunrise is None and self._is_up_at_solar_midnight(day_start):
            sunrise = day_start
        if sunset is None and self._is_up_at_solar_midnight(day_end):
            sunset = day_end
        if sunrise is None or sunset is None:
            return 0.0
        return (sunset - sunrise).total_seconds() / 60.0

    def _hour_angle_and_altitude(
        self, jd: float, t_century: float, coords: dict[str, float]
    ) -> tuple[float, float]:
        """Return the local hour angle and the true altitude of the Sun in degrees."""
        # Mean Sidereal Time at Greenwich theta0 in degrees (Meeus Chapter 12, Eq. 12.4)
        theta0 = (
            280.46061837
            + 360.98564736629 * (jd - 2451545.0)
            + 0.000387933 * (t_century**2)
            - (t_century**3) / 38710000.0
        ) % 360.0

        # Local Hour Angle H (East longitude is positive, Meeus Chapter 13)
        hour_angle_deg = (
            theta0 + self.longitude - coords["right_ascension"]
        ) % 360.0
        if hour_angle_deg > 180.0:
            hour_angle_deg -= 360.0

        lat_rad = math.radians(self.latitude)
        decl_rad = math.radians(coords["declination"])

        # True Altitude h0 (Meeus Chapter 13, Eq. 13.6)
        sin_h0 = math.sin(lat_rad) * math.sin(decl_rad) + math.cos(
            lat_rad
        ) * math.cos(decl_rad) * math.cos(math.radians(hour_angle_deg))
        sin_h0 = max(-1.0, min(1.0, sin_h0))
        return hour_angle_deg, math.degrees(math.asin(sin_h0))

    def _azimuth(self, hour_angle_deg: float, declination_deg: float) -> float:
        """Return the azimuth of the Sun in degrees, North = 0°, East = 90°."""
        hour_angle_rad = math.radians(hour_angle_deg)
        lat_rad = math.radians(self.latitude)
        # Azimuth A measured from South (Meeus Chapter 13, Eq. 13.5), converted to North=0°
        azimuth_south_rad = math.atan2(
            math.sin(hour_angle_rad),
            math.cos(hour_angle_rad) * math.sin(lat_rad)
            - math.tan(math.radians(declination_deg)) * math.cos(lat_rad),
        )
        return (math.degrees(azimuth_south_rad) + 180.0) % 360.0

    @staticmethod
    def _round_azimuth(azimuth_deg: float) -> float:
        """Round an azimuth to 0.01°, keeping 359.999° at 0.0° rather than 360.0°."""
        return round(azimuth_deg, 2) % 360.0

    def _azimuth_at(self, moment: datetime) -> float:
        """Return the azimuth of the Sun in degrees at a given moment."""
        jd = self.to_julian_day(moment)
        t_century = self.to_julian_century(jd)
        coords = self._solar_coordinates(t_century)
        hour_angle_deg, _ = self._hour_angle_and_altitude(jd, t_century, coords)
        return self._azimuth(hour_angle_deg, coords["declination"])

    @classmethod
    def _constellation(cls, true_longitude: float, t_century: float) -> str:
        """Return the constellation the Sun is in, by its J2000.0 ecliptic longitude.

        The true longitude of date loses the general precession in longitude since
        J2000.0 (Meeus Chapter 21, Eq. 21.5). Without aberration, as the boundaries
        were found: the Sun changes constellation within 10 min of PyEphem.
        """
        precession_arcsec = (5029.0966 + 1.11113 * t_century) * t_century
        longitude = (true_longitude - precession_arcsec / 3600.0) % 360.0
        constellation = cls.CONSTELLATION_BOUNDARIES[-1][2]
        for start, drift, name in cls.CONSTELLATION_BOUNDARIES:
            if longitude < start + drift * t_century:
                break
            constellation = name
        return constellation

    @classmethod
    def _refraction(cls, true_elevation_deg: float) -> float:
        """Return atmospheric refraction in degrees for a true (geometric) altitude.

        Saemundsson's formula (Meeus Chapter 16, Eq. 16.4) is not valid below about
        -1°. Under that limit refraction decays as 1/tan(h), the form NOAA uses below
        the horizon, scaled to match at the limit so the apparent altitude stays
        continuous.
        """
        altitude = max(true_elevation_deg, cls.REFRACTION_FORMULA_LIMIT)
        refraction_arcmin = 1.02 / math.tan(
            math.radians(altitude + 10.3 / (altitude + 5.11))
        )
        refraction_deg = max(0.0, refraction_arcmin / 60.0)
        if true_elevation_deg < cls.REFRACTION_FORMULA_LIMIT:
            refraction_deg *= math.tan(
                math.radians(-cls.REFRACTION_FORMULA_LIMIT)
            ) / math.tan(math.radians(-true_elevation_deg))
        return refraction_deg

    def calculate(
        self, dt_utc: datetime, local_date: date | None = None
    ) -> SolarData:
        """Compute complete solar position and daily solar events for a UTC datetime.

        Daily events belong to the solar day containing dt_utc (see _solar_date).
        local_date overrides it with the solar day of that date in local mean
        solar time.
        """
        if dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
        else:
            dt_utc = dt_utc.astimezone(timezone.utc)

        if local_date is None:
            local_date = self._solar_date(dt_utc)

        jd = self.to_julian_day(dt_utc)
        t_century = self.to_julian_century(jd)
        coords = self._solar_coordinates(t_century)
        hour_angle_deg, true_elevation_deg = self._hour_angle_and_altitude(
            jd, t_century, coords
        )

        # Atmospheric Refraction R (Saemundsson's formula, Meeus Chapter 16, Eq. 16.4)
        apparent_elevation_deg = true_elevation_deg + self._refraction(
            true_elevation_deg
        )

        azimuth_deg = self._azimuth(hour_angle_deg, coords["declination"])

        # Daily solar time events
        solar_noon = self._calculate_event_time(local_date, 0.0, None)
        solar_midnight = self._calculate_solar_midnight(local_date)
        sunrise = self._calculate_event_time(
            local_date, self.sunrise_sunset_altitude, True
        )
        sunset = self._calculate_event_time(
            local_date, self.sunrise_sunset_altitude, False
        )
        civil_dawn = self._calculate_event_time(
            local_date, self.ALTITUDE_CIVIL_TWILIGHT, True
        )
        civil_dusk = self._calculate_event_time(
            local_date, self.ALTITUDE_CIVIL_TWILIGHT, False
        )
        nautical_dawn = self._calculate_event_time(
            local_date, self.ALTITUDE_NAUTICAL_TWILIGHT, True
        )
        nautical_dusk = self._calculate_event_time(
            local_date, self.ALTITUDE_NAUTICAL_TWILIGHT, False
        )
        astronomical_dawn = self._calculate_event_time(
            local_date, self.ALTITUDE_ASTRONOMICAL_TWILIGHT, True
        )
        astronomical_dusk = self._calculate_event_time(
            local_date, self.ALTITUDE_ASTRONOMICAL_TWILIGHT, False
        )
        blue_hour_dawn = self._calculate_event_time(
            local_date, self.ALTITUDE_BLUE_HOUR, True
        )
        blue_hour_dusk = self._calculate_event_time(
            local_date, self.ALTITUDE_BLUE_HOUR, False
        )
        golden_hour_dawn = self._calculate_event_time(
            local_date, self.ALTITUDE_GOLDEN_HOUR, True
        )
        golden_hour_dusk = self._calculate_event_time(
            local_date, self.ALTITUDE_GOLDEN_HOUR, False
        )

        day_length_min = self._calculate_day_length(solar_noon, sunrise, sunset)

        events = {
            "solar_noon": solar_noon,
            "solar_midnight": solar_midnight,
            "sunrise": sunrise,
            "sunset": sunset,
            "civil_dawn": civil_dawn,
            "civil_dusk": civil_dusk,
            "nautical_dawn": nautical_dawn,
            "nautical_dusk": nautical_dusk,
            "astronomical_dawn": astronomical_dawn,
            "astronomical_dusk": astronomical_dusk,
            "blue_hour_dawn": blue_hour_dawn,
            "blue_hour_dusk": blue_hour_dusk,
            "golden_hour_dawn": golden_hour_dawn,
            "golden_hour_dusk": golden_hour_dusk,
        }
        event_azimuths = {
            name: self._round_azimuth(self._azimuth_at(moment))
            for name, moment in events.items()
            if moment is not None
        }

        # Same bounds as the blue and golden hour events: no horizon dip, as twilights
        is_golden_hour = (
            self.ALTITUDE_BLUE_HOUR < true_elevation_deg <= self.ALTITUDE_GOLDEN_HOUR
        )
        is_blue_hour = (
            self.ALTITUDE_CIVIL_TWILIGHT < true_elevation_deg <= self.ALTITUDE_BLUE_HOUR
        )

        return SolarData(
            julian_day=round(jd, 6),
            julian_century=round(t_century, 8),
            mean_longitude=round(coords["l0"], 4),
            mean_anomaly=round(coords["m_deg"], 4),
            eccentricity=round(coords["eccentricity"], 8),
            equation_of_center=round(coords["c_deg"], 4),
            true_longitude=round(coords["true_longitude"], 4),
            apparent_longitude=round(coords["apparent_longitude"], 4),
            obliquity=round(coords["obliquity"], 4),
            right_ascension=round(coords["right_ascension"], 4),
            declination=round(coords["declination"], 4),
            equation_of_time=round(coords["equation_of_time"], 2),
            sun_distance_au=round(coords["distance_au"], 6),
            sun_distance_km=round(coords["distance_au"] * ASTRONOMICAL_UNIT_KM),
            constellation=self._constellation(coords["true_longitude"], t_century),
            hour_angle=round(hour_angle_deg, 4),
            true_elevation=round(true_elevation_deg, 2),
            apparent_elevation=round(apparent_elevation_deg, 2),
            azimuth=self._round_azimuth(azimuth_deg),
            day_length_minutes=round(day_length_min, 2),
            solar_noon=solar_noon,
            solar_midnight=solar_midnight,
            sunrise=sunrise,
            sunset=sunset,
            civil_dawn=civil_dawn,
            civil_dusk=civil_dusk,
            nautical_dawn=nautical_dawn,
            nautical_dusk=nautical_dusk,
            astronomical_dawn=astronomical_dawn,
            astronomical_dusk=astronomical_dusk,
            blue_hour_dawn=blue_hour_dawn,
            blue_hour_dusk=blue_hour_dusk,
            golden_hour_dawn=golden_hour_dawn,
            golden_hour_dusk=golden_hour_dusk,
            event_azimuths=event_azimuths,
            # Sunrise/sunset thresholds apply to the geometric altitude: refraction is
            # already part of them, so comparing the apparent one would count it twice
            is_above_horizon=true_elevation_deg > self.sunrise_sunset_altitude,
            is_golden_hour=is_golden_hour,
            is_blue_hour=is_blue_hour,
        )