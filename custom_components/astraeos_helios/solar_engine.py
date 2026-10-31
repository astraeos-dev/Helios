"""Pure Python solar calculation engine.

The Sun's position comes from the astro package, a port of libastro (the C core
of PyEphem): VSOP87, IAU 1980 nutation, aberration, Delta T and parallax. Daily
events, refraction and the other chapter references follow Astronomical
Algorithms (J. Meeus, 2nd edition, Willmann-Bell, 1998).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
import functools
import math

from .astro import (
    SunObservation,
    SunPosition,
    constellation,
    delta_t,
    observe_sun,
    sun_position,
)

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
    constellation: str | None
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
    ALTITUDE_SUNRISE_SUNSET = (
        -0.8333
    )  # -50 arcminutes (refraction + solar semi-diameter)
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

    # The 13 IAU constellations along the ecliptic, in the Sun's order from the
    # March equinox, and the keys of their names
    CONSTELLATIONS: dict[str, str] = {
        "Psc": "pisces",
        "Ari": "aries",
        "Tau": "taurus",
        "Gem": "gemini",
        "Cnc": "cancer",
        "Leo": "leo",
        "Vir": "virgo",
        "Lib": "libra",
        "Sco": "scorpius",
        "Oph": "ophiuchus",
        "Sgr": "sagittarius",
        "Cap": "capricornus",
        "Aqr": "aquarius",
    }

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
        # Daily events only change at solar midnight, and finding the solar day takes
        # the solar midnights on both sides of it: keep the last few of each
        self._daily_events = functools.lru_cache(maxsize=4)(
            self._calculate_daily_events
        )
        self._solar_midnight = functools.lru_cache(maxsize=8)(
            self._calculate_solar_midnight
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
    def _position(jd: float) -> SunPosition:
        """Return the geocentric position of the Sun at a Julian day (UT)."""
        return sun_position(jd + delta_t(jd) / 86400.0)

    def _observe(self, jd: float) -> SunObservation:
        """Return the Sun seen by the observer at a Julian day (UT).

        Parallax is taken at sea level: 1000 m change it by 0.001", and leaving the
        elevation out keeps twilights independent of it, as they are by definition.
        """
        return observe_sun(jd, self.latitude, self.longitude)

    @staticmethod
    def _equation_of_time(position: SunPosition) -> float:
        """Return apparent minus mean solar time in minutes (Meeus Chapter 28, Eq. 28.1)."""
        tau = (position.jd_tt - 2451545.0) / 365250.0
        # Mean longitude of the Sun, mean equinox of date (Eq. 28.2)
        mean_longitude = 280.4664567 + tau * (
            360007.6982779
            + tau * (0.03032028 + tau * (1 / 49931 - tau * (1 / 15300 + tau / 2e6)))
        )
        true_obliquity = math.radians(
            position.mean_obliquity + position.nutation_obliquity
        )
        equation_deg = (
            mean_longitude
            - 0.0057183
            - position.right_ascension
            + position.nutation_longitude * math.cos(true_obliquity)
        )
        return 4.0 * ((equation_deg + 180.0) % 360.0 - 180.0)

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
            position = self._position(jd_midnight + fraction_of_day)
            eq_time = self._equation_of_time(position)
            decl_rad = math.radians(position.declination)

            # Solar noon in minutes from UTC midnight
            solar_noon_min = 720.0 - (4.0 * self.longitude) - eq_time

            if is_rising is None:
                fraction_of_day = solar_noon_min / 1440.0
                continue

            lat_rad = math.radians(self.latitude)
            alt_rad = math.radians(target_altitude)

            # Hour angle H0 (Meeus Chapter 15, Eq. 15.1)
            cos_h0 = (math.sin(alt_rad) - math.sin(lat_rad) * math.sin(decl_rad)) / (
                math.cos(lat_rad) * math.cos(decl_rad)
            )

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
            seen = self._observe(jd_midnight + refined)
            hour_angle, altitude = seen.hour_angle, seen.altitude
            if target_altitude is None:
                offset = hour_angle
                if abs(hour_angle) > 90.0:
                    offset -= math.copysign(180.0, hour_angle)
                correction = -offset / 360.0
            else:
                slope = (
                    360.0
                    * math.cos(math.radians(seen.declination))
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
        if dt_utc > self._solar_midnight(solar_date):
            return solar_date + timedelta(days=1)
        if dt_utc <= self._solar_midnight(solar_date - timedelta(days=1)):
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
            eq_time = self._equation_of_time(
                self._position(jd_midnight + fraction_of_day)
            )
            # Apparent solar time reaches 24:00 at this many minutes from UTC midnight
            fraction_of_day = (1440.0 - (4.0 * self.longitude) - eq_time) / 1440.0

        fraction_of_day = self._refine_event(jd_midnight, fraction_of_day, None)
        return midnight_utc + timedelta(days=fraction_of_day)

    def _is_up_at_solar_midnight(self, moment: datetime) -> bool:
        """Return True if the Sun stays above the horizon through its lower transit."""
        declination = self._position(self.to_julian_day(moment)).declination
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

    @staticmethod
    def _round_azimuth(azimuth_deg: float) -> float:
        """Round an azimuth to 0.01°, keeping 359.999° at 0.0° rather than 360.0°."""
        return round(azimuth_deg, 2) % 360.0

    def _azimuth_at(self, moment: datetime) -> float:
        """Return the azimuth of the Sun in degrees at a given moment."""
        return self._observe(self.to_julian_day(moment)).azimuth

    def _calculate_daily_events(
        self, local_date: date
    ) -> tuple[dict[str, datetime | None], dict[str, float], float]:
        """Return the events of a solar day, the Sun's azimuth at each event that
        happens, and the day length in minutes."""
        horizon = self.sunrise_sunset_altitude
        events = {
            "solar_noon": self._calculate_event_time(local_date, 0.0, None),
            "solar_midnight": self._solar_midnight(local_date),
            "sunrise": self._calculate_event_time(local_date, horizon, True),
            "sunset": self._calculate_event_time(local_date, horizon, False),
        }
        for name, altitude in (
            ("civil", self.ALTITUDE_CIVIL_TWILIGHT),
            ("nautical", self.ALTITUDE_NAUTICAL_TWILIGHT),
            ("astronomical", self.ALTITUDE_ASTRONOMICAL_TWILIGHT),
            ("blue_hour", self.ALTITUDE_BLUE_HOUR),
            ("golden_hour", self.ALTITUDE_GOLDEN_HOUR),
        ):
            events[f"{name}_dawn"] = self._calculate_event_time(
                local_date, altitude, True
            )
            events[f"{name}_dusk"] = self._calculate_event_time(
                local_date, altitude, False
            )

        azimuths = {
            name: self._round_azimuth(self._azimuth_at(moment))
            for name, moment in events.items()
            if moment is not None
        }
        day_length = self._calculate_day_length(
            events["solar_noon"], events["sunrise"], events["sunset"]
        )
        return events, azimuths, day_length

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

    def calculate(self, dt_utc: datetime, local_date: date | None = None) -> SolarData:
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
        seen = self._observe(jd)
        position = seen.position
        true_elevation_deg = seen.altitude

        # Atmospheric Refraction R (Saemundsson's formula, Meeus Chapter 16, Eq. 16.4)
        apparent_elevation_deg = true_elevation_deg + self._refraction(
            true_elevation_deg
        )

        events, event_azimuths, day_length_min = self._daily_events(local_date)

        # Mean elements of the Sun's orbit (Meeus Chapter 25, Eq. 25.2 to 25.4)
        t_tt = self.to_julian_century(position.jd_tt)
        mean_longitude = (280.46646 + t_tt * (36000.76983 + 0.0003032 * t_tt)) % 360.0
        mean_anomaly = (357.52911 + t_tt * (35999.05029 - 0.0001537 * t_tt)) % 360.0
        eccentricity = 0.016708634 - t_tt * (0.000042037 + 0.0000001267 * t_tt)
        # Nutation, and aberration of -20.4898" / R (Meeus Chapter 25, Eq. 25.10)
        apparent_longitude = (
            position.longitude
            + position.nutation_longitude
            - 20.4898 / 3600.0 / position.distance_au
        ) % 360.0

        # Same bounds as the blue and golden hour events: no horizon dip, as twilights
        is_golden_hour = (
            self.ALTITUDE_BLUE_HOUR < true_elevation_deg <= self.ALTITUDE_GOLDEN_HOUR
        )
        is_blue_hour = (
            self.ALTITUDE_CIVIL_TWILIGHT < true_elevation_deg <= self.ALTITUDE_BLUE_HOUR
        )

        return SolarData(
            julian_day=round(jd, 6),
            julian_century=round(self.to_julian_century(jd), 8),
            mean_longitude=round(mean_longitude, 4),
            mean_anomaly=round(mean_anomaly, 4),
            eccentricity=round(eccentricity, 8),
            # True minus mean longitude
            equation_of_center=round(
                (position.longitude - mean_longitude + 180.0) % 360.0 - 180.0, 4
            ),
            true_longitude=round(position.longitude, 4),
            apparent_longitude=round(apparent_longitude, 4),
            obliquity=round(position.mean_obliquity + position.nutation_obliquity, 4),
            right_ascension=round(position.right_ascension, 4),
            declination=round(position.declination, 4),
            equation_of_time=round(self._equation_of_time(position), 2),
            sun_distance_au=round(position.distance_au, 6),
            sun_distance_km=round(position.distance_au * ASTRONOMICAL_UNIT_KM),
            constellation=self.CONSTELLATIONS.get(
                constellation(
                    position.astrometric_right_ascension,
                    position.astrometric_declination,
                    position.jd_tt,
                )
            ),
            hour_angle=round(seen.hour_angle, 4),
            true_elevation=round(true_elevation_deg, 2),
            apparent_elevation=round(apparent_elevation_deg, 2),
            azimuth=self._round_azimuth(seen.azimuth),
            day_length_minutes=round(day_length_min, 2),
            solar_noon=events["solar_noon"],
            solar_midnight=events["solar_midnight"],
            sunrise=events["sunrise"],
            sunset=events["sunset"],
            civil_dawn=events["civil_dawn"],
            civil_dusk=events["civil_dusk"],
            nautical_dawn=events["nautical_dawn"],
            nautical_dusk=events["nautical_dusk"],
            astronomical_dawn=events["astronomical_dawn"],
            astronomical_dusk=events["astronomical_dusk"],
            blue_hour_dawn=events["blue_hour_dawn"],
            blue_hour_dusk=events["blue_hour_dusk"],
            golden_hour_dawn=events["golden_hour_dawn"],
            golden_hour_dusk=events["golden_hour_dusk"],
            # A copy: the cached dictionary is shared by every update of the day
            event_azimuths=dict(event_azimuths),
            # Sunrise/sunset thresholds apply to the geometric altitude: refraction is
            # already part of them, so comparing the apparent one would count it twice
            is_above_horizon=true_elevation_deg > self.sunrise_sunset_altitude,
            is_golden_hour=is_golden_hour,
            is_blue_hour=is_blue_hour,
        )
