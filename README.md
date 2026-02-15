# Mill Heater (Local)

A custom [Home Assistant](https://www.home-assistant.io/) integration for **Mill Generation 3 heaters** using their local REST API. Communicates directly with heaters over your local network — no cloud dependency, faster response times, and access to all device features.

## Supported Devices

| Device | Model Name |
|--------|-----------|
| Convection Heater Gen 3 | Mill HeaterGen3Convector |
| Convection Heater Max Gen 3 | Mill HeaterGen3ConvectorMax |

The Max model exposes additional controls (limited heating power, PID parameters) that the regular convector does not. The integration detects the device model automatically and creates entities accordingly.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add this repository URL and select **Integration** as the category
4. Search for "Mill Heater (Local)" and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/mill_local` directory into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Mill Heater (Local)"
3. Enter the IP address of your heater
4. Optionally provide a custom name (otherwise the device name is used)

Repeat for each heater. Each heater is configured independently.

**Tip:** Assign static IPs to your heaters in your router's DHCP settings to prevent IP changes. If an IP does change, use the **Reconfigure** option on the device page to update it without removing the device.

## Entities

### Climate

The main control entity. Supports:
- **HVAC modes:** Heat, Off
- **Preset modes:** None (manual thermostat), Weekly Program, Independent Device
- **Temperature range:** 5–35°C in 0.5° steps

### Sensors

| Entity | Description |
|--------|-------------|
| Current Power | Real-time power draw (W) |
| Energy | Cumulative energy consumption (kWh) — auto-calculated, works with HA Energy Dashboard |
| Control Signal | PID control signal 0–100% (diagnostic) |
| Raw Temperature | Temperature before calibration offset (diagnostic) |
| Calibration Offset | Current calibration offset value (diagnostic) |
| Firmware Version | Device firmware version (diagnostic) |

### Binary Sensors

| Entity | Description |
|--------|-------------|
| Open Window | Open window detected by the heater |
| Cloud Connected | Whether the heater is connected to Mill's cloud |
| Heating | Whether the heater is actively heating |

### Switches

| Entity | Description | Default |
|--------|-------------|---------|
| Open Window Detection | Enable/disable open window detection | Enabled |
| Child Lock | Enable/disable child lock | Enabled |
| Cloud Communication | Enable/disable cloud connection | **Disabled by default** |
| Commercial Lock | Enable/disable commercial lock | Disabled by default |

> **Warning:** Disabling Cloud Communication will disconnect the heater from the Mill app. The heater requires a reboot after changing this setting.

### Numbers

| Entity | Range | Description |
|--------|-------|-------------|
| Calibration Offset | -6 to 6°C | Temperature sensor calibration |
| Hysteresis Upper | 0.1–5°C | Upper hysteresis offset |
| Hysteresis Lower | 0.1–5°C | Lower hysteresis offset |
| Open Window Drop Threshold | 1–10°C | Temperature drop to trigger open window (disabled by default) |
| Open Window Max Time | 300–7200s | Maximum open window duration (disabled by default) |
| Limited Heating Power | 10–100% | Max power percentage (Max model only) |
| Max Heater Power | 0–2000W | Maximum heater power (Max model only) |

### Selects

| Entity | Options |
|--------|---------|
| Predictive Heating | Off, Simple, Advanced |
| Display Unit | Celsius, Fahrenheit |
| Controller Type | hysteresis_or_slow_pid, PID |

## Energy Tracking

The **Energy** sensor automatically calculates cumulative kWh from the heater's real-time power readings. It:

- Shows up in **Settings → Dashboards → Energy** as an individual device
- Persists across Home Assistant restarts
- Updates every 15 seconds

To add a heater to the Energy Dashboard:

1. Go to **Settings → Dashboards → Energy**
2. Under **Individual devices**, click **Add device**
3. Select the heater's Energy sensor

## Services

### `mill_local.set_vacation_mode`

Set or clear vacation mode on a heater.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| enabled | bool | Yes | Enable or disable vacation mode |
| temperature | float | No | Vacation temperature (°C) |
| start_timestamp | int | No | Start time (Unix timestamp in minutes) |
| end_timestamp | int | No | End time (Unix timestamp in minutes) |

### `mill_local.set_weekly_program`

Set the weekly program timers.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timers | list | Yes | List of `{name, timestamp}` pairs |

### `mill_local.reboot`

Reboot the heater's control MCU.

## Contributing Translations

The integration ships with English and Swedish translations. Community contributions for additional languages are welcome!

### How to add a new language

1. Fork this repository
2. Copy `custom_components/mill_local/translations/en.json` to `custom_components/mill_local/translations/{language_code}.json`
   - Use the standard [BCP 47 language code](https://www.iana.org/assignments/language-subtag-registry/) (e.g., `de` for German, `fr` for French, `nb` for Norwegian Bokmål, `fi` for Finnish)
3. Translate all the **values** in the JSON file — keep the keys unchanged
4. Submit a Pull Request

### Example

If you wanted to add German, you'd create `translations/de.json`:

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Mill-Heizung hinzufügen",
        "description": "Geben Sie die IP-Adresse Ihrer Mill Generation 3-Heizung ein.",
        "data": {
          "host": "IP-Adresse",
          "name": "Name (optional)"
        }
      }
    }
  }
}
```

### Currently available languages

| Language | Code | Status |
|----------|------|--------|
| English | `en` | Complete |
| Swedish | `sv` | Complete |

### Translation guidelines

- Translate user-facing text only — JSON keys must stay the same
- Keep technical terms (e.g., "PID", "hysteresis") as-is unless your language has a widely-used equivalent
- Entity names should match what users would expect to see in their language's Home Assistant UI
- Test your translation by placing the file in `custom_components/mill_local/translations/` and setting HA to your language

## Other Mill Gen 3 Devices

This integration has been tested with **Convection Heaters** (regular and Max models). The Mill Gen 3 local API also supports other device types that should work but have not been verified:

| Device Type | Status | Notes |
|-------------|--------|-------|
| Convection Heater | **Tested** | Full support |
| Convection Heater Max | **Tested** | Full support including power limits |
| Panel Heater | Untested | Likely works — shares the same API endpoints |
| Oil Heater | Untested | Has a unique power level endpoint (40/60/100%) not yet exposed |
| Wi-Fi Socket | Untested | Has a unique socket mode endpoint not yet exposed |

### Help us support more devices

If you own a Mill Gen 3 **panel heater**, **oil heater**, or **Wi-Fi socket**, we'd love your help! Please [open an issue](../../issues/new) with the output of these two commands (replace the IP with your device's IP):

```bash
curl http://<YOUR_HEATER_IP>/status
curl http://<YOUR_HEATER_IP>/control-status
```

This tells us the exact device name string and response format, which helps us add proper support for your device type.

## Known Limitations

- **No authentication:** The local API uses plain HTTP with no authentication. Anyone on your local network can control the heaters. The API supports setting an API key which enables HTTPS, but this is irreversible without a factory reset and is not supported by this integration.
- **Config entity staleness:** Settings changed via the Mill app or physical controls on the heater won't be reflected in Home Assistant until the integration is reloaded.
- **Energy sensor accuracy:** The 15-second polling interval means brief power fluctuations between polls aren't captured. This is adequate for heaters which typically run at full power or zero.
- **Write-only Max Heater Power:** The device has no endpoint to read the current max heater power value. The last value set through Home Assistant is stored locally and restored on restart.

## API Documentation

This integration uses the Mill Generation 3 Local REST API:
https://github.com/Mill-International-AS/Generation_3_REST_API
