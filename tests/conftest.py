"""Shared test fixtures for Mill Local tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mill_local.const import (
    CONF_FIRMWARE,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SUPPORTED_FEATURES,
    DOMAIN,
    FEATURE_LIMITED_HEATING_POWER,
    FEATURE_PID_PARAMETERS,
)

MOCK_HOST = "192.168.1.100"

MOCK_STATUS = {
    "name": "Mill HeaterGen3Convector",
    "custom_name": "",
    "version": "0x250317",
    "operation_key": "",
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "status": "ok",
}

MOCK_STATUS_MAX = {
    "name": "Mill HeaterGen3ConvectorMax",
    "custom_name": "",
    "version": "0x250317",
    "operation_key": "",
    "mac_address": "11:22:33:44:55:66",
    "status": "ok",
}

MOCK_CONTROL_STATUS = {
    "ambient_temperature": 21.5,
    "current_power": 800,
    "control_signal": 65,
    "lock_active": "No lock",
    "open_window_active_now": "Enabled not active now",
    "raw_ambient_temperature": 21.3,
    "set_temperature": 22.0,
    "switched_on": True,
    "connected_to_cloud": True,
    "operation_mode": "Control individually",
    "status": "ok",
}

MOCK_CONTROL_STATUS_OFF = {
    **MOCK_CONTROL_STATUS,
    "current_power": 0,
    "control_signal": 0,
    "switched_on": False,
    "operation_mode": "Off",
    "set_temperature": 6.0,
}

MOCK_OPEN_WINDOW = {
    "active_now": False,
    "drop_temperature_threshold": 5,
    "drop_time_range": 900,
    "increase_temperature_threshold": 3,
    "increase_time_range": 900,
    "max_time": 3600,
    "enabled": True,
    "status": "ok",
}

MOCK_CHILD_LOCK = {"value": False, "status": "ok"}
MOCK_COMMERCIAL_LOCK = {"value": False, "status": "ok"}
MOCK_CLOUD_COMMUNICATION = {"value": True, "status": "ok"}
MOCK_DISPLAY_UNIT = {"value": "Celsius", "status": "ok"}
MOCK_PREDICTIVE_HEATING = {"predictive_heating_type": "Off", "status": "ok"}
MOCK_CONTROLLER_TYPE = {"regulator_type": "hysteresis_or_slow_pid", "status": "ok"}
MOCK_CALIBRATION_OFFSET = {"value": 0, "status": "ok"}
MOCK_VACATION_MODE = {"start_timestamp": 0, "end_timestamp": 0, "status": "ok"}
MOCK_WEEKLY_PROGRAM = {"timers": [], "active": False, "status": "ok"}
MOCK_TIMEZONE_OFFSET = {"timezone_offset": 1440, "status": "ok"}
MOCK_HYSTERESIS = {
    "temp_hysteresis_upper": 0.5,
    "temp_hysteresis_lower": 0.5,
    "regulator_type": "hysteresis",
    "status": "ok",
}
MOCK_LIMITED_HEATING_POWER = {"limited_heating_power": 70, "status": "ok"}
MOCK_PID_PARAMETERS = {
    "kp": 70,
    "ki": 0.02,
    "kd": 4500,
    "kd_filter_N": 60,
    "windup_limit_percentage": 95,
    "status": "ok",
}
MOCK_COMMERCIAL_LOCK_CUSTOM = {
    "enabled": False,
    "min_allowed_temp_in_commercial_lock": 10.0,
    "max_allowed_temp_in_commercial_lock": 30.0,
    "status": "ok",
}


def mock_config_entry_data(
    host=MOCK_HOST,
    mac="AA:BB:CC:DD:EE:FF",
    model="Mill HeaterGen3Convector",
    firmware="0x250317",
    features=None,
):
    """Create mock config entry data dict."""
    return {
        "host": host,
        CONF_MAC_ADDRESS: mac,
        CONF_MODEL: model,
        CONF_FIRMWARE: firmware,
        CONF_SUPPORTED_FEATURES: list(features or []),
    }
