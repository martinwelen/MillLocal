"""Tests for Mill Local coordinator."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from custom_components.mill_local.api import CannotConnect
from custom_components.mill_local.coordinator import MillLocalCoordinator
from custom_components.mill_local.const import DOMAIN
from tests.conftest import MOCK_CONTROL_STATUS, mock_config_entry_data


@pytest.fixture(autouse=True)
def patch_ha_internals():
    """Patch HA internals that require runtime setup."""
    with patch("homeassistant.helpers.frame._hass", MagicMock()):
        yield


@pytest.fixture
async def mock_hass():
    hass = MagicMock()
    hass.data = {}
    # Use the real running event loop so HA internals work
    hass.loop = asyncio.get_running_loop()
    hass.bus = MagicMock()
    hass.bus.async_listen_once = MagicMock()
    return hass


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.get_control_status = AsyncMock(return_value=MOCK_CONTROL_STATUS)
    api.host = "192.168.1.100"
    return api


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = mock_config_entry_data()
    entry.title = "Test Heater"
    return entry


class TestCoordinator:
    async def test_successful_update(self, mock_hass, mock_api, mock_entry):
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        data = await coordinator._async_update_data()
        assert data["ambient_temperature"] == 21.5
        assert data["current_power"] == 800
        mock_api.get_control_status.assert_called_once()

    async def test_update_failure_raises(self, mock_hass, mock_api, mock_entry):
        mock_api.get_control_status.side_effect = CannotConnect("timeout")
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        from homeassistant.helpers.update_coordinator import UpdateFailed

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_device_info(self, mock_hass, mock_api, mock_entry):
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        info = coordinator.device_info
        assert info["manufacturer"] == "Mill"
        assert info["model"] == "Mill HeaterGen3Convector"

    async def test_supported_features(self, mock_hass, mock_api, mock_entry):
        mock_entry.data = mock_config_entry_data(
            features=["limited_heating_power", "pid_parameters"]
        )
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        assert "limited_heating_power" in coordinator.supported_features
        assert "pid_parameters" in coordinator.supported_features
