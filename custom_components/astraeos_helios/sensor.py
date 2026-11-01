"""Sensor platform for Helios integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeliosDataUpdateCoordinator
from .solar_engine import SolarData, SolarEngine, degrees_to_hms


@dataclass(frozen=True, kw_only=True)
class HeliosSensorEntityDescription(SensorEntityDescription):
    """Describes a Helios sensor entity."""

    value_fn: Callable[[SolarData], Any]
    attrs_fn: Callable[[SolarData], dict[str, Any]] | None = None


def _event_azimuth(key: str) -> Callable[[SolarData], dict[str, Any]]:
    """Return the attributes of an event sensor: the Sun's azimuth at the event."""

    def attrs(data: SolarData) -> dict[str, Any]:
        azimuth = data.event_azimuths.get(key)
        return {} if azimuth is None else {"azimuth": azimuth}

    return attrs


SENSOR_TYPES: tuple[HeliosSensorEntityDescription, ...] = (
    HeliosSensorEntityDescription(
        key="azimuth",
        translation_key="azimuth",
        native_unit_of_measurement=DEGREE,
        # Wraps from 360° to 0°: statistics need a circular mean
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        icon="mdi:compass-rose",
        value_fn=lambda data: data.azimuth,
    ),
    HeliosSensorEntityDescription(
        key="apparent_elevation",
        translation_key="apparent_elevation",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny",
        value_fn=lambda data: data.apparent_elevation,
    ),
    HeliosSensorEntityDescription(
        key="true_elevation",
        translation_key="true_elevation",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:angle-acute",
        value_fn=lambda data: data.true_elevation,
    ),
    HeliosSensorEntityDescription(
        key="declination",
        translation_key="declination",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:earth",
        value_fn=lambda data: data.declination,
    ),
    HeliosSensorEntityDescription(
        key="right_ascension",
        translation_key="right_ascension",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:orbit",
        value_fn=lambda data: data.right_ascension,
        attrs_fn=lambda data: {"hms": degrees_to_hms(data.right_ascension)},
    ),
    HeliosSensorEntityDescription(
        key="equation_of_time",
        translation_key="equation_of_time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-fast",
        value_fn=lambda data: data.equation_of_time,
    ),
    HeliosSensorEntityDescription(
        key="sun_distance_au",
        translation_key="sun_distance_au",
        native_unit_of_measurement="AU",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:ruler",
        value_fn=lambda data: data.sun_distance_au,
        attrs_fn=lambda data: {"distance_km": data.sun_distance_km},
    ),
    HeliosSensorEntityDescription(
        key="constellation",
        translation_key="constellation",
        device_class=SensorDeviceClass.ENUM,
        options=list(SolarEngine.CONSTELLATIONS.values()),
        icon="mdi:star-four-points",
        value_fn=lambda data: data.constellation,
    ),
    HeliosSensorEntityDescription(
        key="day_length",
        translation_key="day_length",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:theme-light-dark",
        value_fn=lambda data: data.day_length_minutes,
    ),
    HeliosSensorEntityDescription(
        key="julian_day",
        translation_key="julian_day",
        # A unitless ever-growing day count: long-term statistics are meaningless
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:calendar-clock",
        value_fn=lambda data: data.julian_day,
    ),
    HeliosSensorEntityDescription(
        key="solar_noon",
        translation_key="solar_noon",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunny-alert",
        value_fn=lambda data: data.solar_noon,
        attrs_fn=_event_azimuth("solar_noon"),
    ),
    HeliosSensorEntityDescription(
        key="solar_midnight",
        translation_key="solar_midnight",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-night",
        value_fn=lambda data: data.solar_midnight,
        attrs_fn=_event_azimuth("solar_midnight"),
    ),
    HeliosSensorEntityDescription(
        key="sunrise",
        translation_key="sunrise",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.sunrise,
        attrs_fn=_event_azimuth("sunrise"),
    ),
    HeliosSensorEntityDescription(
        key="sunset",
        translation_key="sunset",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-down",
        value_fn=lambda data: data.sunset,
        attrs_fn=_event_azimuth("sunset"),
    ),
    HeliosSensorEntityDescription(
        key="civil_dawn",
        translation_key="civil_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.civil_dawn,
        attrs_fn=_event_azimuth("civil_dawn"),
    ),
    HeliosSensorEntityDescription(
        key="civil_dusk",
        translation_key="civil_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:weather-sunset-down",
        value_fn=lambda data: data.civil_dusk,
        attrs_fn=_event_azimuth("civil_dusk"),
    ),
    HeliosSensorEntityDescription(
        key="nautical_dawn",
        translation_key="nautical_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.nautical_dawn,
        attrs_fn=_event_azimuth("nautical_dawn"),
    ),
    HeliosSensorEntityDescription(
        key="nautical_dusk",
        translation_key="nautical_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-sunset-down",
        value_fn=lambda data: data.nautical_dusk,
        attrs_fn=_event_azimuth("nautical_dusk"),
    ),
    HeliosSensorEntityDescription(
        key="astronomical_dawn",
        translation_key="astronomical_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-night",
        value_fn=lambda data: data.astronomical_dawn,
        attrs_fn=_event_azimuth("astronomical_dawn"),
    ),
    HeliosSensorEntityDescription(
        key="astronomical_dusk",
        translation_key="astronomical_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-night",
        value_fn=lambda data: data.astronomical_dusk,
        attrs_fn=_event_azimuth("astronomical_dusk"),
    ),
    HeliosSensorEntityDescription(
        key="blue_hour_dawn",
        translation_key="blue_hour_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.blue_hour_dawn,
        attrs_fn=_event_azimuth("blue_hour_dawn"),
    ),
    HeliosSensorEntityDescription(
        key="blue_hour_dusk",
        translation_key="blue_hour_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-sunset-down",
        value_fn=lambda data: data.blue_hour_dusk,
        attrs_fn=_event_azimuth("blue_hour_dusk"),
    ),
    HeliosSensorEntityDescription(
        key="golden_hour_dawn",
        translation_key="golden_hour_dawn",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-sunset-up",
        value_fn=lambda data: data.golden_hour_dawn,
        attrs_fn=_event_azimuth("golden_hour_dawn"),
    ),
    HeliosSensorEntityDescription(
        key="golden_hour_dusk",
        translation_key="golden_hour_dusk",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:weather-sunset-down",
        value_fn=lambda data: data.golden_hour_dusk,
        attrs_fn=_event_azimuth("golden_hour_dusk"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Helios sensors based on a config entry."""
    coordinator: HeliosDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HeliosSensor(coordinator, description) for description in SENSOR_TYPES
    )


class HeliosSensor(CoordinatorEntity[HeliosDataUpdateCoordinator], SensorEntity):
    """Representation of a Helios sensor."""

    entity_description: HeliosSensorEntityDescription
    _attr_has_entity_name = True
    # Derived from the state at every update: not worth a copy in the database
    _unrecorded_attributes = frozenset({"hms", "distance_km"})

    def __init__(
        self,
        coordinator: HeliosDataUpdateCoordinator,
        description: HeliosSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=coordinator.entry.title,
            manufacturer="astraeos",
            model="Solar calculator",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the attributes of the sensor, if it has any."""
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)