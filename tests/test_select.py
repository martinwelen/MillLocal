"""Tests for Mill Local select entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.select import SELECT_DESCRIPTIONS, MillSelect
from tests.conftest import (
    MOCK_CONTROLLER_TYPE,
    MOCK_DISPLAY_UNIT,
    MOCK_PREDICTIVE_HEATING,
    mock_config_entry_data,
)


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.api = AsyncMock()
    return coord


class TestSelectDescriptions:
    def test_predictive_heating_extraction(self):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "predictive_heating")
        assert desc.value_fn(MOCK_PREDICTIVE_HEATING) == "Off"

    def test_display_unit_extraction(self):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "display_unit")
        assert desc.value_fn(MOCK_DISPLAY_UNIT) == "Celsius"

    def test_controller_type_extraction(self):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "controller_type")
        assert desc.value_fn(MOCK_CONTROLLER_TYPE) == "hysteresis_or_slow_pid"


class TestMillSelect:
    async def test_initial_fetch(self, coordinator):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "predictive_heating")
        coordinator.api.get_predictive_heating_type = AsyncMock(
            return_value=MOCK_PREDICTIVE_HEATING
        )
        entity = MillSelect(coordinator, desc)
        await entity.async_added_to_hass()
        assert entity.current_option == "Off"

    async def test_select_option(self, coordinator):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "predictive_heating")
        coordinator.api.get_predictive_heating_type = AsyncMock(
            return_value=MOCK_PREDICTIVE_HEATING
        )
        coordinator.api.set_predictive_heating_type = AsyncMock(return_value=True)
        entity = MillSelect(coordinator, desc)
        entity.async_write_ha_state = MagicMock()
        await entity.async_added_to_hass()
        await entity.async_select_option("Advanced")
        assert entity.current_option == "Advanced"
