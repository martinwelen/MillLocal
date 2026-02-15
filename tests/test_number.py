"""Tests for Mill Local number entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.number import (
    ALWAYS_AVAILABLE_DESCRIPTIONS,
    MillNumber,
)
from tests.conftest import MOCK_CALIBRATION_OFFSET, MOCK_HYSTERESIS, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.supported_features = set()
    coord.api = AsyncMock()
    return coord


class TestNumberDescriptions:
    def test_calibration_offset_extraction(self):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "calibration_offset")
        assert desc.value_fn(MOCK_CALIBRATION_OFFSET) == 0

    def test_hysteresis_upper_extraction(self):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "hysteresis_upper")
        assert desc.value_fn(MOCK_HYSTERESIS) == 0.5

    def test_hysteresis_lower_extraction(self):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "hysteresis_lower")
        assert desc.value_fn(MOCK_HYSTERESIS) == 0.5


class TestMillNumber:
    async def test_initial_fetch(self, coordinator):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "calibration_offset")
        coordinator.api.get_temperature_calibration_offset = AsyncMock(
            return_value=MOCK_CALIBRATION_OFFSET
        )
        entity = MillNumber(coordinator, desc)
        await entity.async_added_to_hass()
        assert entity.native_value == 0

    async def test_set_value(self, coordinator):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "calibration_offset")
        coordinator.api.get_temperature_calibration_offset = AsyncMock(
            return_value=MOCK_CALIBRATION_OFFSET
        )
        coordinator.api.set_temperature_calibration_offset = AsyncMock(return_value=True)
        entity = MillNumber(coordinator, desc)
        entity.async_write_ha_state = MagicMock()
        await entity.async_added_to_hass()
        await entity.async_set_native_value(1.5)
        assert entity.native_value == 1.5
