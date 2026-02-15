"""Tests for Mill Local sensor entities."""

from unittest.mock import MagicMock

import pytest

from custom_components.mill_local.sensor import (
    SENSOR_DESCRIPTIONS,
    MillSensor,
)
from tests.conftest import MOCK_CONTROL_STATUS, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.data = MOCK_CONTROL_STATUS
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    return coord


class TestSensorDescriptions:
    def test_current_power(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "current_power")
        assert desc.value_fn(MOCK_CONTROL_STATUS) == 800

    def test_control_signal(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "control_signal")
        assert desc.value_fn(MOCK_CONTROL_STATUS) == 65

    def test_raw_temperature(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "raw_temperature")
        assert desc.value_fn(MOCK_CONTROL_STATUS) == 21.3

    def test_zero_power(self):
        data = {**MOCK_CONTROL_STATUS, "current_power": 0}
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "current_power")
        assert desc.value_fn(data) == 0

    def test_missing_key(self):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "current_power")
        assert desc.value_fn({}) is None


class TestMillSensor:
    def test_native_value(self, coordinator):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "current_power")
        entity = MillSensor(coordinator, desc)
        assert entity.native_value == 800

    def test_unique_id(self, coordinator):
        desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "current_power")
        entity = MillSensor(coordinator, desc)
        assert entity.unique_id == "AA:BB:CC:DD:EE:FF_current_power"
