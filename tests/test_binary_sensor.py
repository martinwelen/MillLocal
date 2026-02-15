"""Tests for Mill Local binary sensor entities."""

import pytest

from custom_components.mill_local.binary_sensor import BINARY_SENSOR_DESCRIPTIONS
from tests.conftest import MOCK_CONTROL_STATUS


class TestBinarySensorDescriptions:
    def test_open_window_not_active(self):
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "open_window")
        assert desc.value_fn(MOCK_CONTROL_STATUS) is False

    def test_open_window_active(self):
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "open_window")
        data = {**MOCK_CONTROL_STATUS, "open_window_active_now": "Enabled active now"}
        assert desc.value_fn(data) is True

    def test_open_window_disabled(self):
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "open_window")
        data = {**MOCK_CONTROL_STATUS, "open_window_active_now": "Disabled not active now"}
        assert desc.value_fn(data) is False

    def test_cloud_connected(self):
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "cloud_connected")
        assert desc.value_fn(MOCK_CONTROL_STATUS) is True

    def test_heating_on(self):
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "heating")
        assert desc.value_fn(MOCK_CONTROL_STATUS) is True

    def test_heating_off(self):
        desc = next(d for d in BINARY_SENSOR_DESCRIPTIONS if d.key == "heating")
        data = {**MOCK_CONTROL_STATUS, "switched_on": False}
        assert desc.value_fn(data) is False
