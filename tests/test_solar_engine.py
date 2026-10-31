"""Tests for the solar engine, using worked examples from Astronomical Algorithms."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import importlib
from pathlib import Path
import sys
import types

from astraeos_astro import sun_position
import pytest

# Import the engine without the integration's __init__, which needs Home Assistant
if "astraeos_helios" not in sys.modules:
    _package = types.ModuleType("astraeos_helios")
    _package.__path__ = [
        str(Path(__file__).resolve().parents[1] / "custom_components" / "astraeos_helios")
    ]
    sys.modules["astraeos_helios"] = _package
solar_engine = importlib.import_module("astraeos_helios.solar_engine")

SolarEngine = solar_engine.SolarEngine

PARIS = (48.8566, 2.3522)
TROMSO = (69.6492, 18.9553)


def test_julian_day_meeus_example_7a() -> None:
    """1957 October 4.81 UT → JD 2436116.31 (Meeus Example 7.a)."""
    dt = datetime(1957, 10, 4, 19, 26, 24, tzinfo=timezone.utc)
    assert SolarEngine.to_julian_day(dt) == pytest.approx(2436116.31, abs=1e-6)


def test_julian_day_j2000() -> None:
    """J2000.0 epoch is JD 2451545.0 and T = 0."""
    dt = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    jd = SolarEngine.to_julian_day(dt)
    assert jd == pytest.approx(2451545.0)
    assert SolarEngine.to_julian_century(jd) == pytest.approx(0.0)


def test_naive_datetime_treated_as_utc() -> None:
    naive = datetime(2024, 6, 21, 12, 0, 0)
    aware = naive.replace(tzinfo=timezone.utc)
    assert SolarEngine.to_julian_day(naive) == SolarEngine.to_julian_day(aware)


def test_sun_position_meeus_examples_25b_and_28a() -> None:
    """1992 October 13.0 TD: α = 13h13m30.749s, δ = -7°47'01.74" with the full VSOP87
    (Meeus Example 25.b), equation of time 13m42.6s (Example 28.a)."""
    position = sun_position(2448908.5)
    assert position.right_ascension == pytest.approx(
        (13 + 13 / 60 + 30.749 / 3600) * 15, abs=0.1 / 3600
    )
    assert position.declination == pytest.approx(
        -(7 + 47 / 60 + 1.74 / 3600), abs=0.1 / 3600
    )
    assert SolarEngine._equation_of_time(position) == pytest.approx(
        13 + 42.6 / 60, abs=0.1 / 60
    )


def test_daily_events_are_ordered() -> None:
    engine = SolarEngine(*PARIS)
    data = engine.calculate(datetime(2024, 6, 21, 12, 0, tzinfo=timezone.utc))

    events = [
        data.nautical_dawn,
        data.civil_dawn,
        data.blue_hour_dawn,
        data.sunrise,
        data.golden_hour_dawn,
        data.solar_noon,
        data.golden_hour_dusk,
        data.sunset,
        data.blue_hour_dusk,
        data.civil_dusk,
        data.nautical_dusk,
        data.solar_midnight,
    ]
    assert all(event is not None for event in events)
    assert events == sorted(events)


def test_paris_summer_solstice() -> None:
    """Paris, 2024-06-21: sunrise ≈ 03:47 UTC, sunset ≈ 19:58 UTC, ~16h10 of daylight."""
    engine = SolarEngine(*PARIS)
    data = engine.calculate(datetime(2024, 6, 21, 12, 0, tzinfo=timezone.utc))

    sunrise_min = data.sunrise.hour * 60 + data.sunrise.minute
    sunset_min = data.sunset.hour * 60 + data.sunset.minute
    assert sunrise_min == pytest.approx(3 * 60 + 47, abs=3)
    assert sunset_min == pytest.approx(19 * 60 + 58, abs=3)
    assert data.day_length_minutes == pytest.approx(16 * 60 + 10, abs=5)

    # Astronomical night never fully falls in Paris around the solstice
    assert data.astronomical_dawn is None
    assert data.astronomical_dusk is None

    # Sun is high in the southern sky shortly after local solar noon
    assert data.is_above_horizon
    assert data.true_elevation == pytest.approx(64.5, abs=1.0)
    assert 150.0 < data.azimuth < 210.0


def test_polar_night() -> None:
    engine = SolarEngine(*TROMSO)
    data = engine.calculate(datetime(2024, 12, 21, 12, 0, tzinfo=timezone.utc))

    assert data.sunrise is None
    assert data.sunset is None
    assert data.solar_noon is not None
    assert data.day_length_minutes == 0.0
    assert not data.is_above_horizon


def test_polar_day() -> None:
    engine = SolarEngine(*TROMSO)
    data = engine.calculate(datetime(2024, 6, 21, 0, 0, tzinfo=timezone.utc))

    assert data.sunrise is None
    assert data.sunset is None
    assert data.day_length_minutes == 1440.0
    # Midnight sun
    assert data.is_above_horizon


AUCKLAND = (-36.8485, 174.7633)
HONOLULU = (21.3069, -157.8583)


def test_events_use_local_day_east_of_greenwich() -> None:
    """08:00 NZST on 2024-06-21 is still 2024-06-20 in UTC."""
    nzst = timezone(timedelta(hours=12))
    engine = SolarEngine(*AUCKLAND)
    data = engine.calculate(datetime(2024, 6, 20, 20, 0, tzinfo=timezone.utc))

    # Sunrise ≈ 07:33 NZST, sunset ≈ 17:11 NZST on June 21
    assert data.sunrise.astimezone(nzst).date() == date(2024, 6, 21)
    assert data.sunset.astimezone(nzst).date() == date(2024, 6, 21)
    assert data.solar_noon.astimezone(nzst).date() == date(2024, 6, 21)


def test_events_use_local_day_west_of_greenwich() -> None:
    """18:00 HST on 2024-06-21 is already 2024-06-22 in UTC."""
    hst = timezone(timedelta(hours=-10))
    engine = SolarEngine(*HONOLULU)
    data = engine.calculate(datetime(2024, 6, 22, 4, 0, tzinfo=timezone.utc))

    # Sunrise ≈ 05:51 HST, sunset ≈ 19:16 HST on June 21
    assert data.sunrise.astimezone(hst).date() == date(2024, 6, 21)
    assert data.sunset.astimezone(hst).date() == date(2024, 6, 21)
    sunset_local = data.sunset.astimezone(hst)
    assert sunset_local.hour * 60 + sunset_local.minute == pytest.approx(19 * 60 + 16, abs=3)


def test_explicit_local_date_overrides_solar_day() -> None:
    engine = SolarEngine(*PARIS)
    dt = datetime(2024, 6, 21, 23, 30, tzinfo=timezone.utc)
    data = engine.calculate(dt, local_date=date(2024, 6, 22))
    assert data.sunrise.date() == date(2024, 6, 22)


REYKJAVIK = (64.15, -21.94)
APIA = (-13.83, -171.76)
KIRITIMATI = (1.87, -157.43)

EVENT_ATTRS = (
    "astronomical_dawn",
    "nautical_dawn",
    "civil_dawn",
    "blue_hour_dawn",
    "sunrise",
    "golden_hour_dawn",
    "solar_noon",
    "golden_hour_dusk",
    "sunset",
    "blue_hour_dusk",
    "civil_dusk",
    "nautical_dusk",
    "astronomical_dusk",
)


def test_dusk_after_civil_midnight_stays_current() -> None:
    """Reykjavik (UTC+0), 2024-06-21: the Sun sets at 00:04 on June 22."""
    engine = SolarEngine(*REYKJAVIK)
    sunset = engine.calculate(datetime(2024, 6, 21, 13, 0, tzinfo=timezone.utc)).sunset
    assert sunset.date() == date(2024, 6, 22)

    # Past civil midnight, the sunset still to come must still be the one shown
    after_midnight = datetime(2024, 6, 22, 0, 1, tzinfo=timezone.utc)
    assert engine.calculate(after_midnight).sunset == sunset


@pytest.mark.parametrize(
    "coordinates",
    [PARIS, TROMSO, REYKJAVIK, AUCKLAND, HONOLULU, APIA],
    ids=["paris", "tromso", "reykjavik", "auckland", "honolulu", "apia"],
)
def test_every_event_is_current_when_it_happens(
    coordinates: tuple[float, float],
) -> None:
    """Each event is shown right before it happens, so time triggers fire."""
    engine = SolarEngine(*coordinates)
    margin = timedelta(seconds=1)
    for day in range(0, 366, 5):
        moment = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(engine.calculate(moment).solar_noon)
        for attr in EVENT_ATTRS:
            event = getattr(data, attr)
            if event is None:
                continue
            assert getattr(engine.calculate(event - margin), attr) == event
            assert getattr(engine.calculate(event + margin), attr) == event


@pytest.mark.parametrize(
    "coordinates",
    [PARIS, TROMSO, REYKJAVIK, AUCKLAND, HONOLULU, APIA],
    ids=["paris", "tromso", "reykjavik", "auckland", "honolulu", "apia"],
)
def test_solar_midnight_ends_the_solar_day(coordinates: tuple[float, float]) -> None:
    """The Sun is at its lower transit, and the next solar day starts right after."""
    engine = SolarEngine(*coordinates)
    margin = timedelta(seconds=1)
    for day in range(0, 366, 5):
        moment = datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(engine.calculate(moment).solar_noon)
        midnight = data.solar_midnight

        assert abs(engine.calculate(midnight).hour_angle) == pytest.approx(180.0, abs=0.02)
        assert engine.calculate(midnight - margin).solar_midnight == midnight
        next_noon = engine.calculate(midnight + margin).solar_noon
        assert (next_noon - midnight).total_seconds() == pytest.approx(12 * 3600, abs=60)


@pytest.mark.parametrize(
    ("attr", "altitude"),
    [
        ("blue_hour_dawn", -4.0),
        ("blue_hour_dusk", -4.0),
        ("golden_hour_dawn", 6.0),
        ("golden_hour_dusk", 6.0),
    ],
)
def test_blue_and_golden_hour_thresholds(attr: str, altitude: float) -> None:
    """Blue hour: civil twilight to -4°; golden hour: -4° to +6° (geometric)."""
    engine = SolarEngine(*PARIS, elevation_meters=1000.0)
    for day in range(0, 366, 7):
        moment = datetime(2024, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
        event = getattr(engine.calculate(moment), attr)
        # Like twilights, they do not depend on the observer's elevation
        assert event == getattr(SolarEngine(*PARIS).calculate(moment), attr)
        assert engine.calculate(event).true_elevation == pytest.approx(altitude, abs=0.02)


@pytest.mark.parametrize("elevation", [0.0, 1000.0])
def test_blue_and_golden_hour_flags_match_events(elevation: float) -> None:
    """Paris: the flags switch at civil twilight, -4° and +6°, morning and evening."""
    engine = SolarEngine(*PARIS, elevation_meters=elevation)
    margin = timedelta(seconds=30)

    def flags(moment: datetime) -> tuple[bool, bool]:
        data = engine.calculate(moment)
        return data.is_blue_hour, data.is_golden_hour

    for day in range(0, 366, 7):
        moment = datetime(2024, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(moment)
        # (blue hour, golden hour) right before and right after each bound
        bounds = [
            (data.civil_dawn, (False, False), (True, False)),
            (data.blue_hour_dawn, (True, False), (False, True)),
            (data.golden_hour_dawn, (False, True), (False, False)),
            (data.golden_hour_dusk, (False, False), (False, True)),
            (data.blue_hour_dusk, (False, True), (True, False)),
            (data.civil_dusk, (True, False), (False, False)),
        ]
        for event, before, after in bounds:
            assert flags(event - margin) == before
            assert flags(event + margin) == after


TRANSITION_FLAGS = {
    "civil_dawn": "is_blue_hour",
    "blue_hour_dawn": "is_golden_hour",
    "sunrise": "is_above_horizon",
    "golden_hour_dawn": "is_golden_hour",
    "golden_hour_dusk": "is_golden_hour",
    "sunset": "is_above_horizon",
    "blue_hour_dusk": "is_golden_hour",
    "civil_dusk": "is_blue_hour",
}


@pytest.mark.parametrize(
    "coordinates",
    [PARIS, TROMSO, REYKJAVIK, AUCKLAND, HONOLULU, APIA],
    ids=["paris", "tromso", "reykjavik", "auckland", "honolulu", "apia"],
)
def test_binary_states_switch_within_a_second_of_their_events(
    coordinates: tuple[float, float],
) -> None:
    """A refresh one second after an event finds the new state (see coordinator)."""
    engine = SolarEngine(*coordinates)
    margin = timedelta(seconds=1)
    for day in range(0, 366, 5):
        moment = datetime(2024, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(moment)
        for attr, flag in TRANSITION_FLAGS.items():
            event = getattr(data, attr)
            if event is None:
                continue
            before = getattr(engine.calculate(event - margin), flag)
            after = getattr(engine.calculate(event + margin), flag)
            assert before != after, f"{attr} {event}"


def test_next_transition_follows_the_day() -> None:
    """Paris, 2024-06-21: every event that changes a state, then solar midnight."""
    data = SolarEngine(*PARIS).calculate(datetime(2024, 6, 21, 12, tzinfo=timezone.utc))
    transitions = [getattr(data, attr) for attr in TRANSITION_FLAGS]
    transitions.append(data.solar_midnight)
    assert transitions == sorted(transitions)

    assert data.next_transition(data.nautical_dawn) == data.civil_dawn
    assert data.next_transition(data.solar_noon) == data.golden_hour_dusk
    for event, following in zip(transitions, transitions[1:]):
        assert data.next_transition(event) == event
        assert data.next_transition(event + timedelta(seconds=1)) == following
    assert data.next_transition(data.solar_midnight + timedelta(seconds=1)) is None


def test_golden_hour_without_blue_hour_far_north() -> None:
    """Tromsø, 2024-06-21: the Sun never drops below -4° but still dips under +6°."""
    engine = SolarEngine(*TROMSO)
    data = engine.calculate(datetime(2024, 6, 21, 12, tzinfo=timezone.utc))
    assert data.blue_hour_dawn is None
    assert data.blue_hour_dusk is None
    assert data.golden_hour_dawn is not None
    assert data.golden_hour_dusk is not None

    midnight = engine.calculate(data.solar_midnight)
    assert midnight.is_golden_hour
    assert not midnight.is_blue_hour


def test_golden_hour_all_day_far_north() -> None:
    """Tromsø, 2024-01-25: the Sun rises but stays under +6°, so no golden hour ends."""
    engine = SolarEngine(*TROMSO)
    data = engine.calculate(datetime(2024, 1, 25, 11, tzinfo=timezone.utc))
    assert data.sunrise is not None
    assert data.golden_hour_dawn is None
    assert data.golden_hour_dusk is None
    assert engine.calculate(data.solar_noon).is_golden_hour


def test_blue_hour_in_polar_night() -> None:
    """Tromsø, 2024-12-21: the Sun never rises but peaks at -3°, past -4°."""
    engine = SolarEngine(*TROMSO)
    data = engine.calculate(datetime(2024, 12, 21, 11, tzinfo=timezone.utc))
    assert data.sunrise is None
    assert data.blue_hour_dawn < data.solar_noon < data.blue_hour_dusk
    assert data.golden_hour_dawn is None
    assert data.golden_hour_dusk is None

    noon = engine.calculate(data.solar_noon)
    assert noon.is_golden_hour
    assert not noon.is_blue_hour


@pytest.mark.parametrize(
    ("coordinates", "utc_offset"),
    [(APIA, 13), (KIRITIMATI, 14)],
    ids=["apia", "kiritimati"],
)
def test_events_on_local_day_across_the_date_line(
    coordinates: tuple[float, float], utc_offset: int
) -> None:
    """Samoa and Kiribati use a time zone a day ahead of their longitude."""
    zone = timezone(timedelta(hours=utc_offset))
    engine = SolarEngine(*coordinates)
    data = engine.calculate(datetime(2024, 6, 21, 10, 0, tzinfo=zone))

    for event in (data.sunrise, data.solar_noon, data.sunset):
        assert event.astimezone(zone).date() == date(2024, 6, 21)


def test_apparent_elevation_is_continuous_and_increasing() -> None:
    """No jump at the -1° limit of Saemundsson's formula (Meeus Chapter 16)."""
    limit = SolarEngine.REFRACTION_FORMULA_LIMIT
    refraction = SolarEngine._refraction
    assert refraction(limit - 1e-9) == pytest.approx(refraction(limit), abs=1e-6)

    altitudes = [h / 100.0 for h in range(-9000, 9001)]
    apparent = [h + refraction(h) for h in altitudes]
    assert all(low < high for low, high in zip(apparent, apparent[1:]))

    # About 34' when the Sun's centre appears on the horizon, fading far below it
    assert refraction(-0.57) * 60.0 == pytest.approx(34.0, abs=1.0)
    assert refraction(-18.0) < 0.05


def test_day_length_matches_sunrise_and_sunset() -> None:
    engine = SolarEngine(*PARIS)
    for day in range(0, 366, 7):
        moment = datetime(2024, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(moment)
        expected = (data.sunset - data.sunrise).total_seconds() / 60.0
        assert data.day_length_minutes == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("elevation", [0.0, 1000.0])
def test_day_length_around_polar_day_and_night(elevation: float) -> None:
    """Tromsø, 2024: day length agrees with the events of each solar day."""
    engine = SolarEngine(*TROMSO, elevation_meters=elevation)
    seen = set()
    for day in range(366):
        moment = datetime(2024, 1, 1, 11, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(moment)
        if data.sunrise is not None and data.sunset is not None:
            seen.add("rise and set")
            expected = (data.sunset - data.sunrise).total_seconds() / 60.0
            assert data.day_length_minutes == pytest.approx(expected, abs=0.01)
        elif data.sunrise is None and data.sunset is None:
            seen.add("neither")
            expected = 1440.0 if data.is_above_horizon else 0.0
            assert data.day_length_minutes == expected
        else:
            # Midnight sun starts or ends: up until (or from) solar midnight
            seen.add("only one")
            assert 0.0 < data.day_length_minutes < 1440.0
    assert seen == {"rise and set", "neither", "only one"}


def test_above_horizon_switches_at_sunrise_and_sunset_far_north() -> None:
    """Tromsø, 2024-08-10: counting refraction twice put it 3 min early/late."""
    engine = SolarEngine(*TROMSO)
    day = engine.calculate(datetime(2024, 8, 10, 11, 0, tzinfo=timezone.utc))
    margin = timedelta(seconds=60)

    assert not engine.calculate(day.sunrise - margin).is_above_horizon
    assert engine.calculate(day.sunrise + margin).is_above_horizon
    assert engine.calculate(day.sunset - margin).is_above_horizon
    assert not engine.calculate(day.sunset + margin).is_above_horizon


def test_horizon_dip() -> None:
    assert SolarEngine.horizon_dip(0.0) == 0.0
    # Below sea level (Dead Sea shore): the horizon is not lowered
    assert SolarEngine.horizon_dip(-430.0) == 0.0
    # 1.76' × √100 = 17.6'
    assert SolarEngine.horizon_dip(100.0) == pytest.approx(17.6 / 60.0)


def test_elevation_lengthens_the_day() -> None:
    """At 1000 m the Sun rises earlier and sets later; twilights are unchanged."""
    dt = datetime(2024, 3, 20, 12, 0, tzinfo=timezone.utc)
    sea_level = SolarEngine(*PARIS).calculate(dt)
    summit = SolarEngine(*PARIS, elevation_meters=1000.0).calculate(dt)

    sunrise_shift = (sea_level.sunrise - summit.sunrise).total_seconds() / 60.0
    sunset_shift = (summit.sunset - sea_level.sunset).total_seconds() / 60.0
    assert sunrise_shift == pytest.approx(5.6, abs=0.2)
    assert sunset_shift == pytest.approx(5.6, abs=0.2)
    assert summit.day_length_minutes - sea_level.day_length_minutes == pytest.approx(
        sunrise_shift + sunset_shift, abs=0.5
    )

    assert summit.solar_noon == sea_level.solar_noon
    assert summit.civil_dawn == sea_level.civil_dawn
    assert summit.civil_dusk == sea_level.civil_dusk


@pytest.mark.parametrize("elevation", [0.0, 1000.0])
def test_above_horizon_matches_sunrise_and_sunset(elevation: float) -> None:
    engine = SolarEngine(*PARIS, elevation_meters=elevation)
    day = engine.calculate(datetime(2024, 6, 21, 12, 0, tzinfo=timezone.utc))
    margin = timedelta(seconds=30)

    assert not engine.calculate(day.sunrise - margin).is_above_horizon
    assert engine.calculate(day.sunrise + margin).is_above_horizon
    assert engine.calculate(day.sunset - margin).is_above_horizon
    assert not engine.calculate(day.sunset + margin).is_above_horizon


def _angle_between(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


@pytest.mark.parametrize(
    "coordinates", [PARIS, TROMSO, AUCKLAND], ids=["paris", "tromso", "auckland"]
)
def test_event_azimuths_are_the_sun_azimuth_at_each_event(
    coordinates: tuple[float, float],
) -> None:
    engine = SolarEngine(*coordinates)
    for day in range(0, 366, 15):
        moment = datetime(2024, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=day)
        data = engine.calculate(moment)
        happening = {
            name for name in data.event_azimuths if getattr(data, name) is not None
        }
        assert happening == set(data.event_azimuths)
        for name, azimuth in data.event_azimuths.items():
            # Due north rounds to 0.0°, never to 360.0°
            assert 0.0 <= azimuth < 360.0, name
            at_event = engine.calculate(getattr(data, name)).azimuth
            assert _angle_between(azimuth, at_event) < 0.02, name


def test_noon_and_midnight_azimuths() -> None:
    """The Sun is due south at noon and due north at midnight north of the tropics,
    and the other way round in the south."""
    moment = datetime(2024, 3, 20, 12, tzinfo=timezone.utc)
    paris = SolarEngine(*PARIS).calculate(moment).event_azimuths
    assert _angle_between(paris["solar_noon"], 180.0) < 0.05
    assert _angle_between(paris["solar_midnight"], 0.0) < 0.05

    auckland = SolarEngine(*AUCKLAND).calculate(moment).event_azimuths
    assert _angle_between(auckland["solar_noon"], 0.0) < 0.05
    assert _angle_between(auckland["solar_midnight"], 180.0) < 0.05


def test_degrees_to_hms() -> None:
    to_hms = solar_engine.degrees_to_hms
    # Meeus Example 25.a: α = 198.38083° = 13h13m31.4s
    assert to_hms(198.38083) == "13h 13m 31.4s"
    assert to_hms(0.0) == "00h 00m 00.0s"
    assert to_hms(15.0) == "01h 00m 00.0s"
    # Rounding up to the next minute, hour and day
    assert to_hms(14.99999) == "01h 00m 00.0s"
    assert to_hms(359.99999) == "00h 00m 00.0s"
    assert to_hms(-15.0) == "23h 00m 00.0s"


def test_distance_in_km() -> None:
    """2024 perihelion and aphelion, as PyEphem gives them."""
    engine = SolarEngine(*PARIS)
    for moment, au in (
        (datetime(2024, 1, 3, 0, 39, tzinfo=timezone.utc), 0.983307),
        (datetime(2024, 7, 5, 5, 6, tzinfo=timezone.utc), 1.016726),
    ):
        data = engine.calculate(moment)
        assert data.sun_distance_au == pytest.approx(au, abs=1e-6)
        assert data.sun_distance_km == pytest.approx(
            data.sun_distance_au * solar_engine.ASTRONOMICAL_UNIT_KM, abs=150
        )


# When the Sun enters each constellation in 2024, by PyEphem's IAU boundaries
CONSTELLATION_ENTRIES_2024 = (
    ("2024-01-20T13:46", "capricornus"),
    ("2024-02-17T00:19", "aquarius"),
    ("2024-03-12T01:52", "pisces"),
    ("2024-04-18T13:52", "aries"),
    ("2024-05-14T01:17", "taurus"),
    ("2024-06-21T08:48", "gemini"),
    ("2024-07-20T13:37", "cancer"),
    ("2024-08-10T12:39", "leo"),
    ("2024-09-16T13:55", "virgo"),
    ("2024-10-31T02:15", "libra"),
    ("2024-11-23T05:15", "scorpius"),
    ("2024-11-29T17:11", "ophiuchus"),
    ("2024-12-18T00:42", "sagittarius"),
)


def test_constellation_through_the_year() -> None:
    """The Sun crosses 13 constellations, Ophiuchus included, on PyEphem's minute."""
    engine = SolarEngine(*PARIS)
    margin = timedelta(minutes=1)
    previous = CONSTELLATION_ENTRIES_2024[-1][1]
    for entry, name in CONSTELLATION_ENTRIES_2024:
        moment = datetime.fromisoformat(entry).replace(tzinfo=timezone.utc)
        assert engine.calculate(moment - margin).constellation == previous, name
        assert engine.calculate(moment + margin).constellation == name, name
        previous = name


@pytest.mark.parametrize(
    "entry", ["1950-11-23T04:53", "2100-11-24T17:45"], ids=["1950", "2100"]
)
def test_scorpius_entry_far_from_2000(entry: str) -> None:
    """The ecliptic slides along the slanted Libra-Scorpius boundary over time."""
    engine = SolarEngine(*PARIS)
    moment = datetime.fromisoformat(entry).replace(tzinfo=timezone.utc)
    margin = timedelta(minutes=1)
    assert engine.calculate(moment - margin).constellation == "libra"
    assert engine.calculate(moment + margin).constellation == "scorpius"
