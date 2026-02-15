# Mill Local Integration Design

**Date:** 2026-02-15
**Status:** Approved

## Overview

Custom Home Assistant integration for Mill Generation 3 heaters using their local REST API (HTTP on port 80). Replaces the built-in Mill cloud integration with full local control, faster polling, and access to all device features. HACS-compatible.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Single coordinator + on-demand config reads | Simplest, follows HA conventions |
| HTTP client | HA's built-in aiohttp session | No extra dependency, proper lifecycle management |
| Feature detection | Probe at setup, store in config entry | Avoids repeated 404 probing at runtime |
| Endpoint coverage | All practically useful endpoints | Graceful 404 handling for model-specific ones |
| Testing | Unit tests with mocked API | Runs in CI without real heaters |
| Translations | English + Swedish | User is Swedish; community can contribute more |
| Energy tracking | Auto-created cumulative kWh sensor | No manual Riemann sum helper needed |
| HVAC modes | heat/off only | Presets carry operation mode detail |

## Supported Devices

| Model | API Name | Extra Endpoints |
|-------|----------|-----------------|
| Convection Heater Gen 3 | `Mill HeaterGen3Convector` | — |
| Convection Heater Max Gen 3 | `Mill HeaterGen3ConvectorMax` | `/limited-heating-power`, `/pid-parameters` |

Architecture supports adding panel heaters, oil heaters, and Wi-Fi sockets later.

## API Client (`api.py`)

Single `MillLocalAPI` class. Constructor takes `host: str` and `session: aiohttp.ClientSession`.

**Core reads** (coordinator): `get_status()`, `get_control_status()`

**Config reads** (on-demand): `get_open_window()`, `get_temperature_calibration_offset()`, `get_child_lock()`, `get_commercial_lock()`, `get_cloud_communication()`, `get_display_unit()`, `get_predictive_heating_type()`, `get_controller_type()`, `get_vacation_mode()`, `get_weekly_program()`, `get_timezone_offset()`, `get_hysteresis_parameters()`, `get_limited_heating_power()`, `get_pid_parameters()`, `get_commercial_lock_customization()`

**Writes**: All corresponding SET operations. Return `bool` for success/failure.

**Feature detection**: `detect_supported_features()` — probes optional endpoints, returns `set[str]` of supported feature keys.

**Error handling**: 5-second timeout per request. GET returns `None` for 404. All methods catch `aiohttp.ClientError` and `asyncio.TimeoutError`.

## Config Flow

1. User enters IP address (required), name (optional)
2. Validate via `GET /status` — extract model, firmware, MAC
3. MAC address = `unique_id` (prevents duplicates)
4. `detect_supported_features()` — probe optional endpoints, store result in `config_entry.data`
5. If no name provided, use device's `name` field
6. Supports reconfiguration (IP change) without removing device

## Coordinator

**`MillLocalCoordinator(DataUpdateCoordinator)`**:
- Polls `GET /control-status` every 15 seconds
- 3 consecutive failures → device unavailable
- Recovery → available again, reset failure counter
- Entity writes trigger `async_request_refresh()` for immediate re-poll

## Entity Design

### Climate Entity (1 per device)

| Feature | Value |
|---------|-------|
| HVAC modes | `heat`, `off` |
| Preset modes | `none`, `comfort`, `sleep`, `away`, `weekly_program`, `independent_device` |
| Temp range | 5-35 C, step 0.5 |
| Current temp | `ambient_temperature` |
| Target temp | `set_temperature` |

**HVAC mode mapping:**
- `heat` → heater is controllable (any mode except "Off")
- `off` → operation_mode "Off"

**Preset mode mapping:**
- `none` → "Control individually"
- `weekly_program` → "Weekly program"
- `independent_device` → "Independent device"

**Operation mode "Invalid"** or unknown → log warning, treat as `heat` with no preset.

### Sensor Entities

| Entity | Source | Device class | State class | Category |
|--------|--------|-------------|-------------|----------|
| Current Power | `control_status.current_power` | `power` | `measurement` | — |
| Energy | Calculated from power | `energy` | `total_increasing` | — |
| Control Signal | `control_status.control_signal` | — | `measurement` | `diagnostic` |
| Raw Temperature | `control_status.raw_ambient_temperature` | `temperature` | `measurement` | `diagnostic` |
| Calibration Offset | `/temperature-calibration-offset` | — | — | `diagnostic` |
| Firmware Version | `/status` → `version` | — | — | `diagnostic` |

**Energy sensor**: Uses `RestoreEntity`. Calculates `kWh += watts * hours_delta / 1000` every 15s. Persists across restarts. Shows in HA Energy Dashboard automatically.

### Binary Sensors (3 per device)

| Entity | Source | Device class | Category |
|--------|--------|-------------|----------|
| Open Window Active | `open_window_active_now` contains "active" | `window` | — |
| Connected to Cloud | `connected_to_cloud` | `connectivity` | `diagnostic` |
| Heating | `switched_on` | `heat` | — |

### Switches (4 per device)

| Entity | Endpoint | Category | Default enabled |
|--------|----------|----------|----------------|
| Open Window Detection | `/open-window` → `enabled` | `config` | yes |
| Child Lock | `/child-lock` | `config` | yes |
| Cloud Communication | `/cloud-communication` | `config` | **no** (risky) |
| Commercial Lock | `/commercial-lock` | `config` | **no** (commercial) |

Cloud Communication switch description warns that disabling it disconnects the Mill app and requires reboot.

### Number Entities (5-7 per device, model-dependent)

| Entity | Endpoint | Range | Step | Category | Availability |
|--------|----------|-------|------|----------|-------------|
| Calibration Offset | `/temperature-calibration-offset` | -6 to 6 C | 0.1 | `config` | All |
| Hysteresis Upper | `/hysteresis-parameters` | 0.1-5 C | 0.1 | `config` | All |
| Hysteresis Lower | `/hysteresis-parameters` | 0.1-5 C | 0.1 | `config` | All |
| Open Window Drop Threshold | `/open-window` | 1-10 C | 0.5 | `config` | All, disabled by default |
| Open Window Max Time | `/open-window` | 300-7200 s | 60 | `config` | All, disabled by default |
| Limited Heating Power | `/limited-heating-power` | 10-100 % | 1 | `config` | Max model only |
| Max Heater Power | `/max-heater-power` | 0-2000 W | 100 | `config` | Max model only |

`max-heater-power` is write-only. Last-set value stored in `config_entry.data`, restored on startup. Shows "unknown" if never set.

### Select Entities (3 per device)

| Entity | Endpoint | Options | Category |
|--------|----------|---------|----------|
| Predictive Heating | `/predictive-heating-type` | Off, Simple, Advanced | `config` |
| Display Unit | `/display-unit` | Celsius, Fahrenheit | `config` |
| Controller Type | `/controller-type` | hysteresis_or_slow_pid, PID | `config` |

### Services (3)

| Service | Purpose |
|---------|---------|
| `mill_local.set_vacation_mode` | Set/clear vacation mode with timestamps and temp |
| `mill_local.set_weekly_program` | Set weekly timer program |
| `mill_local.reboot` | Reboot the heater MCU |

## File Structure

```
custom_components/
  mill_local/
    __init__.py              # Integration setup, platforms
    manifest.json            # Integration metadata
    config_flow.py           # Config + reconfigure flows
    coordinator.py           # DataUpdateCoordinator
    api.py                   # Mill local API client
    climate.py               # Climate platform
    sensor.py                # Sensor platform (power, energy, diagnostics)
    binary_sensor.py         # Binary sensor platform
    switch.py                # Switch platform
    number.py                # Number platform
    select.py                # Select platform
    const.py                 # Constants, defaults, enums
    strings.json             # UI strings (English)
    translations/
      en.json                # English translations
      sv.json                # Swedish translations
tests/
  conftest.py                # Shared fixtures, mock API
  test_api.py                # API client tests
  test_config_flow.py        # Config flow tests
  test_coordinator.py        # Coordinator tests
  test_climate.py            # Climate entity tests
  test_sensor.py             # Sensor entity tests
  test_binary_sensor.py      # Binary sensor tests
  test_switch.py             # Switch entity tests
  test_number.py             # Number entity tests
  test_select.py             # Select entity tests
hacs.json                    # HACS metadata
README.md                    # Documentation with energy setup guide
```

## Known Limitations

1. **No authentication**: Local API has no auth by default. Anyone on the LAN can control heaters. API key support (`POST /set-api-key`) is irreversible without factory reset — not supported in v1.
2. **Config entity staleness**: Settings changed via Mill app or physical controls won't reflect in HA until entity reload. Acceptable trade-off for simplicity.
3. **Energy sensor accuracy**: 15-second polling means brief power fluctuations between polls aren't captured. Adequate for heaters that run at full power or zero.
4. **Write-only max-heater-power**: Stored locally, can't read actual device value.
