"""Tests for Mill Local climate entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.climate import MillClimate
from custom_components.mill_local.const import (
    OPERATION_MODE_INDEPENDENT,
    OPERATION_MODE_WEEKLY,
    PRESET_INDEPENDENT_DEVICE,
    PRESET_NONE,
    PRESET_WEEKLY_PROGRAM,
)
from tests.conftest import MOCK_CONTROL_STATUS, MOCK_CONTROL_STATUS_OFF, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.data = MOCK_CONTROL_STATUS
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.config_entry.entry_id = "test"
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.api = AsyncMock()
    return coord


class TestClimateState:
    def test_current_temperature(self, coordinator):
        entity = MillClimate(coordinator)
        assert entity.current_temperature == 21.5

    def test_target_temperature(self, coordinator):
        entity = MillClimate(coordinator)
        assert entity.target_temperature == 22.0

    def test_hvac_mode_heat(self, coordinator):
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        assert entity.hvac_mode == HVACMode.HEAT

    def test_hvac_mode_off(self, coordinator):
        coordinator.data = MOCK_CONTROL_STATUS_OFF
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        assert entity.hvac_mode == HVACMode.OFF

    def test_preset_control_individually(self, coordinator):
        entity = MillClimate(coordinator)
        assert entity.preset_mode == PRESET_NONE

    def test_preset_weekly_program(self, coordinator):
        coordinator.data = {**MOCK_CONTROL_STATUS, "operation_mode": OPERATION_MODE_WEEKLY}
        entity = MillClimate(coordinator)
        assert entity.preset_mode == PRESET_WEEKLY_PROGRAM

    def test_preset_independent(self, coordinator):
        coordinator.data = {**MOCK_CONTROL_STATUS, "operation_mode": OPERATION_MODE_INDEPENDENT}
        entity = MillClimate(coordinator)
        assert entity.preset_mode == PRESET_INDEPENDENT_DEVICE

    def test_preset_off_mode(self, coordinator):
        coordinator.data = MOCK_CONTROL_STATUS_OFF
        entity = MillClimate(coordinator)
        assert entity.preset_mode is None

    def test_unknown_operation_mode(self, coordinator):
        coordinator.data = {**MOCK_CONTROL_STATUS, "operation_mode": "SomeFutureMode"}
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        assert entity.hvac_mode == HVACMode.HEAT
        assert entity.preset_mode is None


class TestClimateActions:
    async def test_set_temperature(self, coordinator):
        coordinator.api.set_temperature = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        await entity.async_set_temperature(temperature=23.5)
        coordinator.api.set_temperature.assert_called_once_with(23.5)
        coordinator.async_request_refresh.assert_called_once()

    async def test_set_hvac_mode_off(self, coordinator):
        coordinator.api.set_operation_mode = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        await entity.async_set_hvac_mode(HVACMode.OFF)
        coordinator.api.set_operation_mode.assert_called_once_with("Off")

    async def test_set_hvac_mode_heat(self, coordinator):
        # Start from OFF mode so switching to HEAT triggers set_operation_mode
        coordinator.data = MOCK_CONTROL_STATUS_OFF
        coordinator.api.set_operation_mode = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        coordinator.api.set_operation_mode.assert_called_once_with("Control individually")

    async def test_set_preset_weekly(self, coordinator):
        coordinator.api.set_operation_mode = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        await entity.async_set_preset_mode(PRESET_WEEKLY_PROGRAM)
        coordinator.api.set_operation_mode.assert_called_once_with("Weekly program")
