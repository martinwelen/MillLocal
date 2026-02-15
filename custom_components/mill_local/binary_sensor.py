"""Binary sensor platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPEN_WINDOW_ACTIVE
from .coordinator import MillLocalCoordinator


@dataclass(frozen=True, kw_only=True)
class MillBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Mill binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[MillBinarySensorEntityDescription, ...] = (
    MillBinarySensorEntityDescription(
        key="open_window",
        translation_key="open_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda data: data.get("open_window_active_now") == OPEN_WINDOW_ACTIVE,
    ),
    MillBinarySensorEntityDescription(
        key="cloud_connected",
        translation_key="cloud_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("connected_to_cloud"),
    ),
    MillBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda data: data.get("switched_on"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local binary sensor entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MillBinarySensor(coordinator, desc) for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class MillBinarySensor(CoordinatorEntity[MillLocalCoordinator], BinarySensorEntity):
    """Binary sensor that reads from coordinator data."""

    entity_description: MillBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
