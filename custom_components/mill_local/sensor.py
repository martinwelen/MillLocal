"""Sensor platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MillSensorEntityDescription(SensorEntityDescription):
    """Describes a Mill sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


SENSOR_DESCRIPTIONS: tuple[MillSensorEntityDescription, ...] = (
    MillSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda data: data.get("current_power"),
    ),
    MillSensorEntityDescription(
        key="control_signal",
        translation_key="control_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("control_signal"),
    ),
    MillSensorEntityDescription(
        key="raw_temperature",
        translation_key="raw_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("raw_ambient_temperature"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local sensor entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Coordinator-based sensors
    for desc in SENSOR_DESCRIPTIONS:
        entities.append(MillSensor(coordinator, desc))

    # Energy sensor (auto-calculated kWh)
    entities.append(MillEnergySensor(coordinator))

    # Config-based diagnostic sensors (fetched on-demand)
    entities.append(MillCalibrationOffsetSensor(coordinator))
    entities.append(MillFirmwareVersionSensor(coordinator))

    async_add_entities(entities)


class MillSensor(CoordinatorEntity[MillLocalCoordinator], SensorEntity):
    """Sensor that reads from coordinator data."""

    entity_description: MillSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"

    @property
    def native_value(self) -> StateType:
        return self.entity_description.value_fn(self.coordinator.data)


class MillEnergySensor(CoordinatorEntity[MillLocalCoordinator], RestoreEntity, SensorEntity):
    """Cumulative energy sensor calculated from power readings."""

    _attr_has_entity_name = True
    _attr_translation_key = "energy"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator: MillLocalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_energy"
        self._cumulative_energy: float = 0.0
        self._last_update: datetime | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restore previous cumulative value
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._cumulative_energy = float(last_state.state)
            except (ValueError, TypeError):
                self._cumulative_energy = 0.0
        self._last_update = dt_util.utcnow()

    @callback
    def _handle_coordinator_update(self) -> None:
        now = dt_util.utcnow()
        if self._last_update is not None:
            power_watts = self.coordinator.data.get("current_power", 0) or 0
            delta_hours = (now - self._last_update).total_seconds() / 3600
            self._cumulative_energy += power_watts * delta_hours / 1000
        self._last_update = now
        self.async_write_ha_state()

    @property
    def native_value(self) -> float:
        return round(self._cumulative_energy, 4)


class MillCalibrationOffsetSensor(CoordinatorEntity[MillLocalCoordinator], SensorEntity):
    """Diagnostic sensor for calibration offset (fetched on-demand)."""

    _attr_has_entity_name = True
    _attr_translation_key = "calibration_offset"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MillLocalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_calibration_offset_sensor"
        self._value: float | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            data = await self.coordinator.api.get_temperature_calibration_offset()
            if data:
                self._value = data["value"]
        except Exception:
            _LOGGER.debug("Could not fetch calibration offset")

    @property
    def native_value(self) -> float | None:
        return self._value


class MillFirmwareVersionSensor(CoordinatorEntity[MillLocalCoordinator], SensorEntity):
    """Diagnostic sensor for firmware version."""

    _attr_has_entity_name = True
    _attr_translation_key = "firmware_version"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: MillLocalCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_firmware_version"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.config_entry.data.get("firmware")
