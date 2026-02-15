"""DataUpdateCoordinator for Mill Local integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import CannotConnect, MillLocalAPI
from .const import (
    CONF_FIRMWARE,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SUPPORTED_FEATURES,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MillLocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for polling Mill heater control status."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: MillLocalAPI,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.api = api
        self.supported_features: set[str] = set(
            entry.data.get(CONF_SUPPORTED_FEATURES, [])
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.data[CONF_MAC_ADDRESS])},
            manufacturer="Mill",
            model=self.config_entry.data[CONF_MODEL],
            sw_version=self.config_entry.data[CONF_FIRMWARE],
            name=self.config_entry.title,
        )

    @property
    def mac_address(self) -> str:
        return self.config_entry.data[CONF_MAC_ADDRESS]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_control_status()
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with heater: {err}") from err
