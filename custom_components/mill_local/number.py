"""Number platform for Mill Local integration."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MillLocalAPI
from .const import DOMAIN, FEATURE_LIMITED_HEATING_POWER
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MillNumberEntityDescription(NumberEntityDescription):
    """Describes a Mill number entity."""

    get_fn: Callable[[MillLocalAPI], Awaitable[dict[str, Any] | None]]
    set_fn: Callable[[MillLocalAPI, float], Awaitable[bool]]
    value_fn: Callable[[dict[str, Any]], float | None]
    required_feature: str | None = None


ALWAYS_AVAILABLE_DESCRIPTIONS: tuple[MillNumberEntityDescription, ...] = (
    MillNumberEntityDescription(
        key="calibration_offset",
        translation_key="calibration_offset",
        native_min_value=-6.0,
        native_max_value=6.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api: api.get_temperature_calibration_offset(),
        set_fn=lambda api, v: api.set_temperature_calibration_offset(v),
        value_fn=lambda data: data.get("value"),
    ),
    MillNumberEntityDescription(
        key="hysteresis_upper",
        translation_key="hysteresis_upper",
        native_min_value=0.1,
        native_max_value=5.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api: api.get_hysteresis_parameters(),
        set_fn=lambda api, v: api.set_hysteresis_upper(v),
        value_fn=lambda data: data.get("temp_hysteresis_upper"),
    ),
    MillNumberEntityDescription(
        key="hysteresis_lower",
        translation_key="hysteresis_lower",
        native_min_value=0.1,
        native_max_value=5.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        get_fn=lambda api: api.get_hysteresis_parameters(),
        set_fn=lambda api, v: api.set_hysteresis_lower(v),
        value_fn=lambda data: data.get("temp_hysteresis_lower"),
    ),
    MillNumberEntityDescription(
        key="open_window_drop_threshold",
        translation_key="open_window_drop_threshold",
        native_min_value=1.0,
        native_max_value=10.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api: api.get_open_window(),
        set_fn=lambda api, v: api.set_open_window_params(drop_temperature_threshold=v),
        value_fn=lambda data: data.get("drop_temperature_threshold"),
    ),
    MillNumberEntityDescription(
        key="open_window_max_time",
        translation_key="open_window_max_time",
        native_min_value=300,
        native_max_value=7200,
        native_step=60,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=lambda api: api.get_open_window(),
        set_fn=lambda api, v: api.set_open_window_params(max_time=int(v)),
        value_fn=lambda data: data.get("max_time"),
    ),
)

OPTIONAL_DESCRIPTIONS: tuple[MillNumberEntityDescription, ...] = (
    MillNumberEntityDescription(
        key="limited_heating_power",
        translation_key="limited_heating_power",
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        required_feature=FEATURE_LIMITED_HEATING_POWER,
        get_fn=lambda api: api.get_limited_heating_power(),
        set_fn=lambda api, v: api.set_limited_heating_power(int(v)),
        value_fn=lambda data: data.get("limited_heating_power"),
    ),
    MillNumberEntityDescription(
        key="max_heater_power",
        translation_key="max_heater_power",
        native_min_value=0,
        native_max_value=2000,
        native_step=100,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.CONFIG,
        required_feature=FEATURE_LIMITED_HEATING_POWER,
        get_fn=lambda api: None,  # Write-only endpoint
        set_fn=lambda api, v: api.set_max_heater_power(int(v)),
        value_fn=lambda data: None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local number entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = []

    for desc in ALWAYS_AVAILABLE_DESCRIPTIONS:
        entities.append(MillNumber(coordinator, desc))

    for desc in OPTIONAL_DESCRIPTIONS:
        if desc.required_feature and desc.required_feature in coordinator.supported_features:
            entities.append(MillNumber(coordinator, desc))

    async_add_entities(entities)


class MillNumber(CoordinatorEntity[MillLocalCoordinator], NumberEntity):
    """Config number entity that manages its own state."""

    entity_description: MillNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillNumberEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"
        self._value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            data = await self.entity_description.get_fn(self.coordinator.api)
            if data:
                self._value = self.entity_description.value_fn(data)
        except Exception:
            _LOGGER.debug("Could not fetch initial value for %s", self.entity_description.key)

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, value):
            self._value = value
            self.async_write_ha_state()
