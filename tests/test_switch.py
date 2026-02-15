"""Tests for Mill Local switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.switch import SWITCH_DESCRIPTIONS, MillSwitch
from tests.conftest import MOCK_CHILD_LOCK, MOCK_OPEN_WINDOW, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.api = AsyncMock()
    return coord


class TestSwitchDescriptions:
    def test_child_lock_value_extraction(self):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        assert desc.value_fn(MOCK_CHILD_LOCK) is False

    def test_open_window_value_extraction(self):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "open_window_detection")
        assert desc.value_fn(MOCK_OPEN_WINDOW) is True


class TestMillSwitch:
    async def test_initial_fetch(self, coordinator):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        coordinator.api.get_child_lock = AsyncMock(return_value=MOCK_CHILD_LOCK)
        entity = MillSwitch(coordinator, desc)
        await entity.async_added_to_hass()
        assert entity.is_on is False

    async def test_turn_on(self, coordinator):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        coordinator.api.get_child_lock = AsyncMock(return_value=MOCK_CHILD_LOCK)
        coordinator.api.set_child_lock = AsyncMock(return_value=True)
        entity = MillSwitch(coordinator, desc)
        entity.async_write_ha_state = MagicMock()
        await entity.async_added_to_hass()
        await entity.async_turn_on()
        assert entity.is_on is True

    async def test_turn_off(self, coordinator):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        data = {**MOCK_CHILD_LOCK, "value": True}
        coordinator.api.get_child_lock = AsyncMock(return_value=data)
        coordinator.api.set_child_lock = AsyncMock(return_value=True)
        entity = MillSwitch(coordinator, desc)
        entity.async_write_ha_state = MagicMock()
        await entity.async_added_to_hass()
        await entity.async_turn_off()
        assert entity.is_on is False
