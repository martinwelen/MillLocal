"""Switch platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MillLocalAPI
from .const import DOMAIN
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MillSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Mill switch entity."""

    get_fn: Callable[[MillLocalAPI], Awaitable[dict[str, Any] | None]]
    set_fn: Callable[[MillLocalAPI, bool], Awaitable[bool]]
    value_fn: Callable[[dict[str, Any]], bool | None]


SWITCH_DESCRIPTIONS: tuple[MillSwitchEntityDescription, ...] = (
    MillSwitchEntityDescription(
        key="open_window_detection",
        translation_key="open_window_detection",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api: api.get_open_window(),
        set_fn=lambda api, v: api.set_open_window_enabled(v),
        value_fn=lambda data: data.get("enabled"),
    ),
    MillSwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api: api.get_child_lock(),
        set_fn=lambda api, v: api.set_child_lock(v),
        value_fn=lambda data: data.get("value"),
    ),
    MillSwitchEntityDescription(
        key="cloud_communication",
        translation_key="cloud_communication",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api: api.get_cloud_communication(),
        set_fn=lambda api, v: api.set_cloud_communication(v),
        value_fn=lambda data: data.get("value"),
    ),
    MillSwitchEntityDescription(
        key="commercial_lock",
        translation_key="commercial_lock",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api: api.get_commercial_lock(),
        set_fn=lambda api, v: api.set_commercial_lock(v),
        value_fn=lambda data: data.get("value"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local switch entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MillSwitch(coordinator, desc) for desc in SWITCH_DESCRIPTIONS
    )


class MillSwitch(CoordinatorEntity[MillLocalCoordinator], SwitchEntity):
    """Config switch entity that manages its own state."""

    entity_description: MillSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"
        self._is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            data = await self.entity_description.get_fn(self.coordinator.api)
            if data:
                self._is_on = self.entity_description.value_fn(data)
        except Exception:
            _LOGGER.debug("Could not fetch initial value for %s", self.entity_description.key)

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, False):
            self._is_on = False
            self.async_write_ha_state()
