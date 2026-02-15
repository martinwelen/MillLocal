"""Select platform for Mill Local integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MillLocalAPI
from .const import (
    CONTROLLER_HYSTERESIS,
    CONTROLLER_PID,
    DISPLAY_CELSIUS,
    DISPLAY_FAHRENHEIT,
    DOMAIN,
    PREDICTIVE_HEATING_ADVANCED,
    PREDICTIVE_HEATING_OFF,
    PREDICTIVE_HEATING_SIMPLE,
)
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MillSelectEntityDescription(SelectEntityDescription):
    """Describes a Mill select entity."""

    get_fn: Callable[[MillLocalAPI], Awaitable[dict[str, Any] | None]]
    set_fn: Callable[[MillLocalAPI, str], Awaitable[bool]]
    value_fn: Callable[[dict[str, Any]], str | None]


SELECT_DESCRIPTIONS: tuple[MillSelectEntityDescription, ...] = (
    MillSelectEntityDescription(
        key="predictive_heating",
        translation_key="predictive_heating",
        entity_category=EntityCategory.CONFIG,
        options=[PREDICTIVE_HEATING_OFF, PREDICTIVE_HEATING_SIMPLE, PREDICTIVE_HEATING_ADVANCED],
        get_fn=lambda api: api.get_predictive_heating_type(),
        set_fn=lambda api, v: api.set_predictive_heating_type(v),
        value_fn=lambda data: data.get("predictive_heating_type"),
    ),
    MillSelectEntityDescription(
        key="display_unit",
        translation_key="display_unit",
        entity_category=EntityCategory.CONFIG,
        options=[DISPLAY_CELSIUS, DISPLAY_FAHRENHEIT],
        get_fn=lambda api: api.get_display_unit(),
        set_fn=lambda api, v: api.set_display_unit(v),
        value_fn=lambda data: data.get("value"),
    ),
    MillSelectEntityDescription(
        key="controller_type",
        translation_key="controller_type",
        entity_category=EntityCategory.CONFIG,
        options=[CONTROLLER_HYSTERESIS, CONTROLLER_PID],
        get_fn=lambda api: api.get_controller_type(),
        set_fn=lambda api, v: api.set_controller_type(v),
        value_fn=lambda data: data.get("regulator_type"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local select entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MillSelect(coordinator, desc) for desc in SELECT_DESCRIPTIONS
    )


class MillSelect(CoordinatorEntity[MillLocalCoordinator], SelectEntity):
    """Config select entity that manages its own state."""

    entity_description: MillSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"
        self._current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            data = await self.entity_description.get_fn(self.coordinator.api)
            if data:
                self._current_option = self.entity_description.value_fn(data)
        except Exception:
            _LOGGER.debug("Could not fetch initial value for %s", self.entity_description.key)

    @property
    def current_option(self) -> str | None:
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, option):
            self._current_option = option
            self.async_write_ha_state()
