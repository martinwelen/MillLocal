"""Climate platform for Mill Local integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    OPERATION_MODE_CONTROL,
    OPERATION_MODE_OFF,
    OPERATION_MODE_TO_PRESET,
    PRESET_INDEPENDENT_DEVICE,
    PRESET_NONE,
    PRESET_TO_OPERATION_MODE,
    PRESET_WEEKLY_PROGRAM,
)
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local climate entity."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MillClimate(coordinator)])

    # Register entity services
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "set_vacation_mode",
        {
            vol.Required("enabled"): bool,
            vol.Optional("temperature"): vol.Coerce(float),
            vol.Optional("start_timestamp"): vol.Coerce(int),
            vol.Optional("end_timestamp"): vol.Coerce(int),
        },
        "async_set_vacation_mode",
    )
    platform.async_register_entity_service(
        "set_weekly_program",
        {
            vol.Required("timers"): list,
        },
        "async_set_weekly_program",
    )
    platform.async_register_entity_service(
        "reboot",
        {},
        "async_reboot",
    )


class MillClimate(CoordinatorEntity[MillLocalCoordinator], ClimateEntity):
    """Climate entity for Mill heater."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name as entity name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5.0
    _attr_max_temp = 35.0
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = [PRESET_NONE, PRESET_WEEKLY_PROGRAM, PRESET_INDEPENDENT_DEVICE]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator: MillLocalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_climate"

    @property
    def current_temperature(self) -> float | None:
        return self.coordinator.data.get("ambient_temperature")

    @property
    def target_temperature(self) -> float | None:
        return self.coordinator.data.get("set_temperature")

    @property
    def hvac_mode(self) -> HVACMode:
        mode = self.coordinator.data.get("operation_mode", "")
        if mode == OPERATION_MODE_OFF:
            return HVACMode.OFF
        return HVACMode.HEAT

    @property
    def preset_mode(self) -> str | None:
        mode = self.coordinator.data.get("operation_mode", "")
        if mode == OPERATION_MODE_OFF:
            return None
        return OPERATION_MODE_TO_PRESET.get(mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.coordinator.api.set_temperature(temp)
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api.set_operation_mode(OPERATION_MODE_OFF)
        else:
            # When turning on, use "Control individually" as default
            current_mode = self.coordinator.data.get("operation_mode", "")
            if current_mode == OPERATION_MODE_OFF:
                await self.coordinator.api.set_operation_mode(OPERATION_MODE_CONTROL)
            # If already in a heat mode, don't change the operation mode
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        operation_mode = PRESET_TO_OPERATION_MODE.get(preset_mode)
        if operation_mode:
            await self.coordinator.api.set_operation_mode(operation_mode)
            await self.coordinator.async_request_refresh()

    # -- Entity services --

    async def async_set_vacation_mode(
        self,
        enabled: bool,
        temperature: float | None = None,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
    ) -> None:
        if enabled:
            if temperature is not None:
                await self.coordinator.api.set_temperature(temperature)
            await self.coordinator.api.set_vacation_mode(
                start_timestamp or 0, end_timestamp or 0
            )
        else:
            await self.coordinator.api.set_vacation_mode(0, 0)
        await self.coordinator.async_request_refresh()

    async def async_set_weekly_program(self, timers: list) -> None:
        await self.coordinator.api.set_weekly_program(timers)
        await self.coordinator.async_request_refresh()

    async def async_reboot(self) -> None:
        await self.coordinator.api.reboot()
