"""Constants for Mill Local integration."""

from typing import Final

DOMAIN: Final = "mill_local"

# Config keys
CONF_SUPPORTED_FEATURES: Final = "supported_features"
CONF_MAC_ADDRESS: Final = "mac_address"
CONF_MODEL: Final = "model"
CONF_FIRMWARE: Final = "firmware"

# Feature flags (detected at setup, stored in config entry)
FEATURE_LIMITED_HEATING_POWER: Final = "limited_heating_power"
FEATURE_PID_PARAMETERS: Final = "pid_parameters"

# Defaults
DEFAULT_POLL_INTERVAL: Final = 15  # seconds
DEFAULT_TIMEOUT: Final = 5  # seconds
MAX_CONSECUTIVE_FAILURES: Final = 3

# Operation modes (EOperationMode enum from API)
OPERATION_MODE_OFF: Final = "Off"
OPERATION_MODE_WEEKLY: Final = "Weekly program"
OPERATION_MODE_INDEPENDENT: Final = "Independent device"
OPERATION_MODE_CONTROL: Final = "Control individually"

# Temperature types (ETemperatureType enum from API)
TEMP_TYPE_NORMAL: Final = "Normal"

# Predictive heating types (EPredictiveHeatingType enum from API)
PREDICTIVE_HEATING_OFF: Final = "Off"
PREDICTIVE_HEATING_SIMPLE: Final = "Simple"
PREDICTIVE_HEATING_ADVANCED: Final = "Advanced"

# Controller types
CONTROLLER_HYSTERESIS: Final = "hysteresis_or_slow_pid"
CONTROLLER_PID: Final = "PID"

# Display units
DISPLAY_CELSIUS: Final = "Celsius"
DISPLAY_FAHRENHEIT: Final = "Fahrenheit"

# Preset mode keys (HA preset names)
PRESET_NONE: Final = "none"
PRESET_WEEKLY_PROGRAM: Final = "weekly_program"
PRESET_INDEPENDENT_DEVICE: Final = "independent_device"

# Mapping: operation_mode string -> HA preset
OPERATION_MODE_TO_PRESET: Final = {
    OPERATION_MODE_CONTROL: PRESET_NONE,
    OPERATION_MODE_WEEKLY: PRESET_WEEKLY_PROGRAM,
    OPERATION_MODE_INDEPENDENT: PRESET_INDEPENDENT_DEVICE,
}

# Mapping: HA preset -> operation_mode string
PRESET_TO_OPERATION_MODE: Final = {
    PRESET_NONE: OPERATION_MODE_CONTROL,
    PRESET_WEEKLY_PROGRAM: OPERATION_MODE_WEEKLY,
    PRESET_INDEPENDENT_DEVICE: OPERATION_MODE_INDEPENDENT,
}

# Open window status values
OPEN_WINDOW_ACTIVE: Final = "Enabled active now"
