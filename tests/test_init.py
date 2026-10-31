"""Tests for setting up, reloading and unloading Helios."""

from __future__ import annotations

from datetime import timedelta
import re

import pytest

pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="requires pytest-homeassistant-custom-component (see requirements_test.txt)",
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.astraeos_helios.binary_sensor import BINARY_SENSOR_TYPES
from custom_components.astraeos_helios.const import CONF_UPDATE_INTERVAL, DOMAIN
from custom_components.astraeos_helios.sensor import SENSOR_TYPES

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="48.8566_2.3522",
        data={
            CONF_NAME: "Home",
            CONF_LATITUDE: 48.8566,
            CONF_LONGITUDE: 2.3522,
            CONF_ELEVATION: 35.0,
            CONF_UPDATE_INTERVAL: 60,
        },
    )
    entry.add_to_hass(hass)
    return entry


async def test_setup_and_unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == len(SENSOR_TYPES) + len(BINARY_SENSOR_TYPES)
    for entity in entities:
        assert hass.states.get(entity.entity_id) is not None, entity.entity_id
    # Unique ID from before binary sensors had descriptions: keeps existing entities
    assert registry.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{entry.entry_id}_above_horizon"
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_options_update_reloads_entry(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.config_entries.async_update_entry(
        entry, options={CONF_ELEVATION: 1000.0, CONF_UPDATE_INTERVAL: 120}
    )
    await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert coordinator.engine.elevation_meters == 1000.0
    assert coordinator.update_interval == timedelta(seconds=120)


async def test_sensor_attributes(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)

    def state(key: str):
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_{key}"
        )
        return hass.states.get(entity_id)

    assert re.fullmatch(
        r"\d{2}h \d{2}m \d{2}\.\ds", state("right_ascension").attributes["hms"]
    )
    distance = state("sun_distance_au")
    assert distance.name == "Home Distance"
    assert distance.attributes["distance_km"] == pytest.approx(
        float(distance.state) * 149_597_870.7, abs=150
    )

    constellation = state("constellation")
    assert constellation.state in constellation.attributes["options"]

    # Every event of the day carries the Sun's azimuth when it happens
    for key in ("solar_noon", "solar_midnight", "civil_dawn", "golden_hour_dusk"):
        assert 0.0 <= state(key).attributes["azimuth"] < 360.0, key
    assert "azimuth" not in state("azimuth").attributes
