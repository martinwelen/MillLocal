# Custom Home Assistant Integration: Mill Gen 3 Local API

## Project Overview

Build a custom Home Assistant integration for Mill Generation 3 heaters using their **local REST API** (HTTP on port 80). This replaces the built-in Mill cloud integration with full local control, faster polling, and access to all device features.

**Target:** HACS-compatible custom integration, installable via HACS custom repository.

### Official API Documentation

- **Local REST API:** https://github.com/Mill-International-AS/Generation_3_REST_API
- **Cloud API (reference only):** http://mn-be-prod-documentation.s3-website.eu-central-1.amazonaws.com/#/

The local API is simple HTTP — GET to read, POST with JSON body to write. All responses include a `"status"` field (`"ok"` on success).

### Why Not the Built-in Integration?

The built-in HA Mill integration's local mode (`mill_local` library) only uses 5 of 52+ available endpoints. This custom integration should expose all practically useful features.

---

## Device Information

### Supported Device Types

| Type | Model Name | `GET /status` name field |
|------|-----------|-------------------------|
| Convection Heater Gen 3 | GL-Convection Heater G3 | `Mill HeaterGen3Convector` |
| Convection Heater Max Gen 3 | GL-WIFI Convection MAX 1500W G3 | `Mill HeaterGen3ConvectorMax` |

Note: The API also supports panel heaters, oil heaters, and Wi-Fi sockets — but only convection heaters need to be supported initially. The architecture should allow adding more device types later.

### Test Devices

Four heaters available for testing on the local network:

| Name | IP | MAC | Max Power |
|------|-----|-----|-----------|
| Storstugan Vardagsrum Element | 192.168.86.31 | 10:06:1C:8F:83:EC | 1200W |
| Storstugan Sovrum Element | 192.168.86.32 | 10:06:1C:8C:18:64 | 1200W |
| Storstugan Hall Element | 192.168.86.33 | 10:06:1C:8B:F3:38 | 1200W |
| Storstugan Kök/Badrum Element | 192.168.86.34 | 08:F9:E0:04:22:04 | 1500W (Max model) |

The Max model supports additional endpoints (PID parameters, limited-heating-power) that the regular convectors don't. The integration should handle missing endpoints gracefully.

---

## Integration Architecture

### Config Flow

- **One config entry per heater** (each has its own IP)
- Config flow should ask for:
  - IP address (required)
  - Name (optional — can be auto-detected from device)
- Validation: call `GET /status` to verify connectivity and identify device type
- Use MAC address as unique ID to prevent duplicate entries
- Support reconfiguration (IP change) without removing the device

### Polling

- **Default poll interval: 15 seconds** (matching the built-in integration)
- Use `DataUpdateCoordinator` for centralized polling
- Poll `GET /control-status` for the main update cycle (contains temperature, power, mode, etc.)
- Poll less-frequently-changing data (open-window config, locks, etc.) at a slower rate or on-demand

### Device Info

From `GET /status`, populate HA device registry:
- **Manufacturer:** Mill
- **Model:** from `name` field (e.g., "Mill HeaterGen3Convector")
- **Firmware version:** from `version` field (e.g., "0x250317")
- **MAC address:** from `mac_address` field (used as unique identifier)

---

## Entities to Create

### Climate Entity (1 per device)

**Primary control entity.** Source: `GET /control-status`

| Feature | Details |
|---------|---------|
| HVAC modes | `heat`, `off`, `auto` |
| Temperature range | 5–35°C (step 0.5) |
| Current temperature | `ambient_temperature` from control-status |
| Target temperature | `set_temperature` from control-status |
| Preset modes | `none`, `weekly_program`, `independent_device` |

**HVAC mode mapping:**
- `heat` → operation_mode "Control individually" (follows single set value, no timers)
- `off` → operation_mode "OFF"
- `auto` → operation_mode "Weekly program" (follows schedule)

**Set temperature:** `POST /set-temperature` with body `{"type": "Normal", "value": <temp>}`
**Set operation mode:** `POST /operation-mode` with body `{"mode": "<mode string>"}`

### Sensor Entities

| Entity | Source | Device class | Unit | State class | Notes |
|--------|--------|-------------|------|-------------|-------|
| Current Power | `control-status` → `current_power` | `power` | W | `measurement` | Real-time power draw |
| Control Signal | `control-status` → `control_signal` | None | % | `measurement` | 0–100% heating output |
| Raw Temperature | `control-status` → `raw_ambient_temperature` | `temperature` | °C | `measurement` | Before calibration offset |
| Calibration Offset | `/temperature-calibration-offset` → `value` | None | °C | None | Diagnostic entity |
| Firmware Version | `/status` → `version` | None | None | None | Diagnostic entity |

**Energy tracking:** The `current_power` sensor should have `state_class: measurement` and `device_class: power` so users can create a Riemann sum integration helper in HA for kWh tracking.

### Switch Entities

| Entity | GET endpoint | POST endpoint | Body field | Entity category |
|--------|-------------|--------------|------------|-----------------|
| Open Window Detection | `/open-window` → `enabled` | `/open-window` | `{"enabled": bool}` | `config` |
| Child Lock | `/child-lock` → `value` | `/child-lock` | `{"value": bool}` | `config` |
| Cloud Communication | `/cloud-communication` → `value` | `/cloud-communication` | `{"value": bool}` | `config` |

Note: Commercial lock exists too but is for commercial installations — include as a diagnostic/disabled-by-default entity.

### Number Entities

| Entity | GET endpoint | POST endpoint | Min | Max | Step | Unit | Entity category |
|--------|-------------|--------------|-----|-----|------|------|-----------------|
| Calibration Offset | `/temperature-calibration-offset` | `/temperature-calibration-offset` | -6.0 | 6.0 | 0.1 | °C | `config` |
| Limited Heating Power | `/limited-heating-power` | `/limited-heating-power` | 10 | 100 | 1 | % | `config` |
| Max Heater Power | — (write-only) | `/max-heater-power` | 0 | 2000 | 100 | W | `config` |

Note: `limited-heating-power` and `max-heater-power` may not be available on all models. Handle 404/missing gracefully — don't create the entity if the endpoint doesn't exist on the device.

### Select Entities

| Entity | GET endpoint | POST endpoint | Options | Entity category |
|--------|-------------|--------------|---------|-----------------|
| Predictive Heating | `/predictive-heating-type` | `/predictive-heating-type` | `Off`, `Simple`, `Advanced` | `config` |
| Display Unit | `/display-unit` | `/display-unit` | `Celsius`, `Fahrenheit` | `config` |
| Controller Type | `/controller-type` | `/controller-type` | `hysteresis_or_slow_pid`, `PID` | `config` |

### Binary Sensor Entities

| Entity | Source | Device class |
|--------|--------|-------------|
| Open Window Active | `control-status` → `open_window_active_now` contains "active" | `window` |
| Connected to Cloud | `control-status` → `connected_to_cloud` | `connectivity` |
| Heating | `control-status` → `switched_on` | `heat` |

### Open Window Detection Parameters

The `GET /open-window` endpoint returns detailed configuration:

```json
{
  "active_now": false,
  "drop_temperature_threshold": 5,
  "drop_time_range": 900,
  "increase_temperature_threshold": 3,
  "increase_time_range": 900,
  "max_time": 3600,
  "enabled": true
}
```

These could be exposed as additional number entities (all `config` category, disabled by default) for advanced users who want to tune the open window detection sensitivity.

---

## Actual API Response Examples

These are real responses from the test devices.

### `GET /status`
```json
{
  "name": "Mill HeaterGen3Convector",
  "custom_name": "",
  "version": "0x250317",
  "operation_key": "",
  "mac_address": "10:06:1C:8F:83:EC",
  "status": "ok"
}
```

### `GET /control-status`
```json
{
  "ambient_temperature": 13.68,
  "current_power": 0,
  "control_signal": 0,
  "lock_active": "No lock",
  "open_window_active_now": "Enabled not active now",
  "raw_ambient_temperature": 13.68,
  "set_temperature": 6,
  "switched_on": false,
  "connected_to_cloud": true,
  "operation_mode": "Control individually",
  "status": "ok"
}
```

### `GET /operation-mode`
```json
{"mode": "Control individually", "status": "ok"}
```

### `GET /open-window`
```json
{
  "active_now": false,
  "drop_temperature_threshold": 5,
  "drop_time_range": 900,
  "increase_temperature_threshold": 3,
  "increase_time_range": 900,
  "max_time": 3600,
  "enabled": true,
  "status": "ok"
}
```

### `GET /vacation-mode`
```json
{"start_timestamp": 0, "end_timestamp": 0, "status": "ok"}
```

### `GET /weekly-program`
```json
{"timers": [], "active": false, "status": "ok"}
```

### `GET /predictive-heating-type`
```json
{"predictive_heating_type": "Off", "status": "ok"}
```

### `GET /pid-parameters` (Max model only)
```json
{
  "kp": 70,
  "ki": 0.02,
  "kd": 4500,
  "kd_filter_N": 60,
  "windup_limit_percentage": 95,
  "status": "ok"
}
```

### `GET /limited-heating-power` (Max model only)
```json
{"limited_heating_power": 70, "status": "ok"}
```

### `POST /set-temperature`
Request: `{"type": "Normal", "value": 22}`
Response: `{"status": "ok"}`

### `POST /operation-mode`
Request: `{"mode": "Control individually"}`
Response: `{"status": "ok"}`

---

## Services (Optional, Nice to Have)

### `mill_local.set_vacation_mode`
| Field | Type | Description |
|-------|------|-------------|
| `entity_id` | string | Target climate entity |
| `enabled` | bool | Enable/disable |
| `temperature` | float | Vacation temperature (°C) |
| `start_timestamp` | int | Start time (Unix) |
| `end_timestamp` | int | End time (Unix) |

### `mill_local.set_weekly_program`
| Field | Type | Description |
|-------|------|-------------|
| `entity_id` | string | Target climate entity |
| `program` | object | Weekly program schedule |

### `mill_local.reboot`
| Field | Type | Description |
|-------|------|-------------|
| `entity_id` | string | Target climate entity |

---

## HACS Requirements

### Repository Structure

```
custom_components/
  mill_local/
    __init__.py          # Integration setup
    manifest.json        # Integration metadata
    config_flow.py       # UI-based configuration
    climate.py           # Climate platform
    sensor.py            # Sensor platform
    switch.py            # Switch platform
    number.py            # Number platform
    select.py            # Select platform
    binary_sensor.py     # Binary sensor platform
    coordinator.py       # DataUpdateCoordinator
    api.py               # Mill local API client library
    const.py             # Constants
    strings.json         # UI strings (English)
    translations/
      en.json            # English translations
      sv.json            # Swedish translations
hacs.json                # HACS metadata
README.md                # Documentation
```

### `manifest.json`

```json
{
  "domain": "mill_local",
  "name": "Mill Heater (Local)",
  "codeowners": [],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/Mill-International-AS/Generation_3_REST_API",
  "iot_class": "local_polling",
  "requirements": ["aiohttp"],
  "version": "1.0.0"
}
```

### `hacs.json`

```json
{
  "name": "Mill Heater (Local)",
  "render_readme": true
}
```

---

## Error Handling

- **Connection timeout:** Mark device as unavailable after 3 consecutive failed polls
- **Endpoint not found (404 / "Nothing matches the given URI"):** Don't create entities for unsupported endpoints. Check during setup which endpoints the device supports.
- **"Failed to parse message body":** Indicates wrong request format — log error, don't crash
- **Device unavailable:** Set all entities to `unavailable` state, keep retrying at normal interval

---

## Design Principles

- **No cloud dependency** — everything runs locally over HTTP
- **Graceful degradation** — if an endpoint doesn't exist on a device model, skip it
- **One config entry per heater** — each device is independently configured
- **Minimal polling** — use a single `GET /control-status` call for the main update cycle; config entities poll less frequently or on-demand only
- **No breaking the cloud** — the integration should not disable cloud communication by default. The heater maintains its own cloud connection independently
- **Follow HA best practices** — use `DataUpdateCoordinator`, `ConfigEntry`, entity categories, device classes, proper state classes for statistics
