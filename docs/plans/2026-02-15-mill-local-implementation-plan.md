# Mill Local Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a HACS-compatible Home Assistant custom integration for Mill Gen 3 heaters using their local REST API.

**Architecture:** Single DataUpdateCoordinator polling `/control-status` every 15s. Feature detection at setup stores supported endpoints in config entry. Config entities manage their own state (fetch on init, track writes). Energy sensor auto-calculates kWh.

**Tech Stack:** Python 3.12+, Home Assistant 2024.1+, aiohttp (via HA), pytest + pytest-asyncio + aioresponses

**References:**
- Design doc: `docs/plans/2026-02-15-mill-local-integration-design.md`
- Spec: `mill-local-integration-spec.md`
- Official API: https://github.com/Mill-International-AS/Generation_3_REST_API

**Important:** Do NOT perform SET operations on real heaters (192.168.86.31-34) without explicit user confirmation.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `custom_components/mill_local/manifest.json`
- Create: `custom_components/mill_local/const.py`
- Create: `custom_components/mill_local/__init__.py` (empty placeholder)
- Create: `hacs.json`
- Create: `requirements_test.txt`
- Create: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`

**Step 1: Create directory structure**

```bash
mkdir -p custom_components/mill_local/translations
mkdir -p tests
```

**Step 2: Create `custom_components/mill_local/manifest.json`**

```json
{
  "domain": "mill_local",
  "name": "Mill Heater (Local)",
  "codeowners": [],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/Mill-International-AS/Generation_3_REST_API",
  "iot_class": "local_polling",
  "requirements": [],
  "version": "1.0.0"
}
```

No `aiohttp` in requirements — it's provided by HA.

**Step 3: Create `hacs.json`**

```json
{
  "name": "Mill Heater (Local)",
  "render_readme": true
}
```

**Step 4: Create `custom_components/mill_local/const.py`**

```python
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
```

**Step 5: Create `custom_components/mill_local/__init__.py`** (placeholder)

```python
"""Mill Local integration."""
```

**Step 6: Create `requirements_test.txt`**

```
pytest>=7.0
pytest-asyncio>=0.23
pytest-cov>=4.0
aioresponses>=0.7
ruff>=0.3
```

**Step 7: Create `pyproject.toml`**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "A", "SIM"]
```

**Step 8: Update `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    name: Test & Lint
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: |
          pip install homeassistant
          pip install -r requirements_test.txt

      - name: Run tests
        run: pytest --tb=short -q

      - name: Lint
        run: ruff check .
```

**Step 9: Verify structure**

```bash
ls -R custom_components/
```

Expected: directory tree matching the spec.

**Step 10: Commit**

```bash
git add custom_components/ hacs.json requirements_test.txt pyproject.toml .github/
git commit -m "feat: project scaffolding with constants and CI"
```

---

## Task 2: API Client

**Files:**
- Create: `custom_components/mill_local/api.py`
- Create: `tests/conftest.py`
- Create: `tests/test_api.py`

**Step 1: Create `tests/conftest.py`** with shared test fixtures

```python
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
```

**Step 2: Create `tests/test_api.py`** with failing tests

```python
"""Tests for Mill Local API client."""

import asyncio
import json

import aiohttp
import pytest
from aioresponses import aioresponses

from custom_components.mill_local.api import CannotConnect, MillLocalAPI
from tests.conftest import (
    MOCK_CALIBRATION_OFFSET,
    MOCK_CHILD_LOCK,
    MOCK_CLOUD_COMMUNICATION,
    MOCK_CONTROL_STATUS,
    MOCK_CONTROLLER_TYPE,
    MOCK_DISPLAY_UNIT,
    MOCK_HOST,
    MOCK_HYSTERESIS,
    MOCK_LIMITED_HEATING_POWER,
    MOCK_OPEN_WINDOW,
    MOCK_PID_PARAMETERS,
    MOCK_PREDICTIVE_HEATING,
    MOCK_STATUS,
    MOCK_VACATION_MODE,
    MOCK_WEEKLY_PROGRAM,
)

BASE_URL = f"http://{MOCK_HOST}"


@pytest.fixture
async def api_client():
    """Create API client with a real aiohttp session."""
    async with aiohttp.ClientSession() as session:
        yield MillLocalAPI(MOCK_HOST, session)


class TestGetStatus:
    async def test_success(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/status", payload=MOCK_STATUS)
            result = await api_client.get_status()
            assert result["name"] == "Mill HeaterGen3Convector"
            assert result["mac_address"] == "AA:BB:CC:DD:EE:FF"

    async def test_timeout(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/status", exception=asyncio.TimeoutError())
            with pytest.raises(CannotConnect):
                await api_client.get_status()

    async def test_connection_error(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/status", exception=aiohttp.ClientError())
            with pytest.raises(CannotConnect):
                await api_client.get_status()

    async def test_bad_json(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/status", body="not json", content_type="text/plain")
            with pytest.raises(CannotConnect):
                await api_client.get_status()


class TestGetControlStatus:
    async def test_success(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/control-status", payload=MOCK_CONTROL_STATUS)
            result = await api_client.get_control_status()
            assert result["ambient_temperature"] == 21.5
            assert result["current_power"] == 800
            assert result["operation_mode"] == "Control individually"

    async def test_timeout(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/control-status", exception=asyncio.TimeoutError())
            with pytest.raises(CannotConnect):
                await api_client.get_control_status()


class TestConfigReads:
    """Test config endpoint GET methods that return None on failure."""

    async def test_get_open_window(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/open-window", payload=MOCK_OPEN_WINDOW)
            result = await api_client.get_open_window()
            assert result["enabled"] is True
            assert result["drop_temperature_threshold"] == 5

    async def test_get_child_lock(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/child-lock", payload=MOCK_CHILD_LOCK)
            result = await api_client.get_child_lock()
            assert result["value"] is False

    async def test_get_cloud_communication(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/cloud-communication", payload=MOCK_CLOUD_COMMUNICATION)
            result = await api_client.get_cloud_communication()
            assert result["value"] is True

    async def test_get_display_unit(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/display-unit", payload=MOCK_DISPLAY_UNIT)
            result = await api_client.get_display_unit()
            assert result["value"] == "Celsius"

    async def test_get_predictive_heating_type(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/predictive-heating-type", payload=MOCK_PREDICTIVE_HEATING)
            result = await api_client.get_predictive_heating_type()
            assert result["predictive_heating_type"] == "Off"

    async def test_get_controller_type(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/controller-type", payload=MOCK_CONTROLLER_TYPE)
            result = await api_client.get_controller_type()
            assert result["regulator_type"] == "hysteresis_or_slow_pid"

    async def test_get_calibration_offset(self, api_client):
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/temperature-calibration-offset",
                payload=MOCK_CALIBRATION_OFFSET,
            )
            result = await api_client.get_temperature_calibration_offset()
            assert result["value"] == 0

    async def test_get_hysteresis(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/hysteresis-parameters", payload=MOCK_HYSTERESIS)
            result = await api_client.get_hysteresis_parameters()
            assert result["temp_hysteresis_upper"] == 0.5

    async def test_endpoint_not_found_text(self, api_client):
        """Test that 'Nothing matches the given URI' is handled as not found."""
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/limited-heating-power",
                body="Nothing matches the given URI",
                content_type="text/plain",
            )
            result = await api_client.get_limited_heating_power()
            assert result is None

    async def test_endpoint_not_found_404(self, api_client):
        """Test that HTTP 404 is handled as not found."""
        with aioresponses() as m:
            m.get(f"{BASE_URL}/limited-heating-power", status=404)
            result = await api_client.get_limited_heating_power()
            assert result is None

    async def test_get_limited_heating_power_success(self, api_client):
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/limited-heating-power",
                payload=MOCK_LIMITED_HEATING_POWER,
            )
            result = await api_client.get_limited_heating_power()
            assert result["limited_heating_power"] == 70

    async def test_get_pid_parameters_success(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/pid-parameters", payload=MOCK_PID_PARAMETERS)
            result = await api_client.get_pid_parameters()
            assert result["kp"] == 70


class TestWrites:
    async def test_set_temperature(self, api_client):
        with aioresponses() as m:
            m.post(f"{BASE_URL}/set-temperature", payload={"status": "ok"})
            result = await api_client.set_temperature(22.5)
            assert result is True
            # Verify request body
            request = m.requests[("POST", f"{BASE_URL}/set-temperature")]
            body = json.loads(request[0].kwargs["data"])
            assert body == {"type": "Normal", "value": 22.5}

    async def test_set_operation_mode(self, api_client):
        with aioresponses() as m:
            m.post(f"{BASE_URL}/operation-mode", payload={"status": "ok"})
            result = await api_client.set_operation_mode("Weekly program")
            assert result is True

    async def test_set_child_lock(self, api_client):
        with aioresponses() as m:
            m.post(f"{BASE_URL}/child-lock", payload={"status": "ok"})
            result = await api_client.set_child_lock(True)
            assert result is True

    async def test_set_fails_on_error_response(self, api_client):
        with aioresponses() as m:
            m.post(
                f"{BASE_URL}/child-lock",
                payload={"status": "Failed to parse message body"},
            )
            result = await api_client.set_child_lock(True)
            assert result is False

    async def test_set_fails_on_timeout(self, api_client):
        with aioresponses() as m:
            m.post(f"{BASE_URL}/child-lock", exception=asyncio.TimeoutError())
            with pytest.raises(CannotConnect):
                await api_client.set_child_lock(True)


class TestFeatureDetection:
    async def test_detect_all_features(self, api_client):
        """Max model supports both optional endpoints."""
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/limited-heating-power",
                payload=MOCK_LIMITED_HEATING_POWER,
            )
            m.get(f"{BASE_URL}/pid-parameters", payload=MOCK_PID_PARAMETERS)
            features = await api_client.detect_supported_features()
            assert "limited_heating_power" in features
            assert "pid_parameters" in features

    async def test_detect_no_features(self, api_client):
        """Regular convector doesn't support optional endpoints."""
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/limited-heating-power",
                body="Nothing matches the given URI",
                content_type="text/plain",
            )
            m.get(
                f"{BASE_URL}/pid-parameters",
                body="Nothing matches the given URI",
                content_type="text/plain",
            )
            features = await api_client.detect_supported_features()
            assert len(features) == 0

    async def test_detect_partial_features(self, api_client):
        """Device supports one but not the other."""
        with aioresponses() as m:
            m.get(
                f"{BASE_URL}/limited-heating-power",
                payload=MOCK_LIMITED_HEATING_POWER,
            )
            m.get(
                f"{BASE_URL}/pid-parameters",
                body="Nothing matches the given URI",
                content_type="text/plain",
            )
            features = await api_client.detect_supported_features()
            assert "limited_heating_power" in features
            assert "pid_parameters" not in features


class TestHysteresisCompoundWrites:
    """Test read-modify-write for compound endpoints."""

    async def test_set_hysteresis_upper(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/hysteresis-parameters", payload=MOCK_HYSTERESIS)
            m.post(f"{BASE_URL}/hysteresis-parameters", payload={"status": "ok"})
            result = await api_client.set_hysteresis_upper(1.0)
            assert result is True
            request = m.requests[("POST", f"{BASE_URL}/hysteresis-parameters")]
            body = json.loads(request[0].kwargs["data"])
            assert body["temp_hysteresis_upper"] == 1.0
            assert body["temp_hysteresis_lower"] == 0.5  # unchanged

    async def test_set_hysteresis_lower(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/hysteresis-parameters", payload=MOCK_HYSTERESIS)
            m.post(f"{BASE_URL}/hysteresis-parameters", payload={"status": "ok"})
            result = await api_client.set_hysteresis_lower(2.0)
            assert result is True
            request = m.requests[("POST", f"{BASE_URL}/hysteresis-parameters")]
            body = json.loads(request[0].kwargs["data"])
            assert body["temp_hysteresis_upper"] == 0.5  # unchanged
            assert body["temp_hysteresis_lower"] == 2.0
```

**Step 3: Run tests to verify they fail**

```bash
pip install -r requirements_test.txt
pytest tests/test_api.py -v
```

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'custom_components.mill_local.api'`

**Step 4: Create `custom_components/mill_local/api.py`**

```python
"""Mill Local API client."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from .const import (
    DEFAULT_TIMEOUT,
    FEATURE_LIMITED_HEATING_POWER,
    FEATURE_PID_PARAMETERS,
    TEMP_TYPE_NORMAL,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Error to indicate we cannot connect to the device."""


class MillLocalAPI:
    """API client for Mill Gen 3 heaters via local REST API."""

    def __init__(self, host: str, session: aiohttp.ClientSession) -> None:
        self._host = host
        self._session = session
        self._base_url = f"http://{host}"

    @property
    def host(self) -> str:
        return self._host

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Make HTTP request to the heater.

        Returns parsed JSON dict on success, None if endpoint not found.
        Raises CannotConnect on network/timeout errors.
        """
        url = f"{self._base_url}{endpoint}"
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                resp = await self._session.request(method, url, json=json_data)
        except asyncio.TimeoutError as err:
            raise CannotConnect(f"Timeout connecting to {self._host}") from err
        except aiohttp.ClientError as err:
            raise CannotConnect(f"Error connecting to {self._host}: {err}") from err

        if resp.status == 404:
            return None

        try:
            text = await resp.text()
        except Exception as err:
            raise CannotConnect(
                f"Error reading response from {self._host}: {err}"
            ) from err

        if "Nothing matches" in text:
            return None

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            _LOGGER.error("Invalid JSON from %s%s: %s", self._host, endpoint, text[:200])
            return None

    def _check_ok(self, data: dict[str, Any] | None) -> bool:
        """Check if response has status ok."""
        return data is not None and data.get("status") == "ok"

    # ── Core reads (used by coordinator) ──────────────────────────

    async def get_status(self) -> dict[str, Any]:
        """Get device status. Raises CannotConnect on failure."""
        data = await self._request("GET", "/status")
        if not self._check_ok(data):
            raise CannotConnect(f"Invalid status response from {self._host}")
        return data

    async def get_control_status(self) -> dict[str, Any]:
        """Get control status. Raises CannotConnect on failure."""
        data = await self._request("GET", "/control-status")
        if not self._check_ok(data):
            raise CannotConnect(f"Invalid control-status response from {self._host}")
        return data

    # ── Config reads (on-demand, return None on failure) ──────────

    async def get_open_window(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/open-window")
        return data if self._check_ok(data) else None

    async def get_child_lock(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/child-lock")
        return data if self._check_ok(data) else None

    async def get_commercial_lock(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/commercial-lock")
        return data if self._check_ok(data) else None

    async def get_cloud_communication(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/cloud-communication")
        return data if self._check_ok(data) else None

    async def get_display_unit(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/display-unit")
        return data if self._check_ok(data) else None

    async def get_predictive_heating_type(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/predictive-heating-type")
        return data if self._check_ok(data) else None

    async def get_controller_type(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/controller-type")
        return data if self._check_ok(data) else None

    async def get_temperature_calibration_offset(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/temperature-calibration-offset")
        return data if self._check_ok(data) else None

    async def get_vacation_mode(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/vacation-mode")
        return data if self._check_ok(data) else None

    async def get_weekly_program(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/weekly-program")
        return data if self._check_ok(data) else None

    async def get_timezone_offset(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/timezone-offset")
        return data if self._check_ok(data) else None

    async def get_hysteresis_parameters(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/hysteresis-parameters")
        return data if self._check_ok(data) else None

    async def get_limited_heating_power(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/limited-heating-power")
        return data if self._check_ok(data) else None

    async def get_pid_parameters(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/pid-parameters")
        return data if self._check_ok(data) else None

    async def get_commercial_lock_customization(self) -> dict[str, Any] | None:
        data = await self._request("GET", "/commercial-lock-customization")
        return data if self._check_ok(data) else None

    # ── Writes (return True on success, False on failure) ─────────

    async def set_temperature(self, value: float) -> bool:
        data = await self._request(
            "POST", "/set-temperature", {"type": TEMP_TYPE_NORMAL, "value": value}
        )
        return self._check_ok(data)

    async def set_operation_mode(self, mode: str) -> bool:
        data = await self._request("POST", "/operation-mode", {"mode": mode})
        return self._check_ok(data)

    async def set_open_window_enabled(self, enabled: bool) -> bool:
        current = await self.get_open_window()
        if current is None:
            return False
        body = {
            "drop_temperature_threshold": current["drop_temperature_threshold"],
            "drop_time_range": current["drop_time_range"],
            "enabled": enabled,
            "increase_temperature_threshold": current["increase_temperature_threshold"],
            "increase_time_range": current["increase_time_range"],
            "max_time": current["max_time"],
        }
        data = await self._request("POST", "/open-window", body)
        return self._check_ok(data)

    async def set_open_window_params(self, **kwargs: Any) -> bool:
        """Update open window parameters. Pass only the fields to change."""
        current = await self.get_open_window()
        if current is None:
            return False
        body = {
            "drop_temperature_threshold": current["drop_temperature_threshold"],
            "drop_time_range": current["drop_time_range"],
            "enabled": current["enabled"],
            "increase_temperature_threshold": current["increase_temperature_threshold"],
            "increase_time_range": current["increase_time_range"],
            "max_time": current["max_time"],
        }
        body.update(kwargs)
        data = await self._request("POST", "/open-window", body)
        return self._check_ok(data)

    async def set_child_lock(self, value: bool) -> bool:
        data = await self._request("POST", "/child-lock", {"value": value})
        return self._check_ok(data)

    async def set_commercial_lock(self, value: bool) -> bool:
        data = await self._request("POST", "/commercial-lock", {"value": value})
        return self._check_ok(data)

    async def set_cloud_communication(self, value: bool) -> bool:
        data = await self._request("POST", "/cloud-communication", {"value": value})
        return self._check_ok(data)

    async def set_display_unit(self, value: str) -> bool:
        data = await self._request("POST", "/display-unit", {"value": value})
        return self._check_ok(data)

    async def set_predictive_heating_type(self, value: str) -> bool:
        data = await self._request(
            "POST", "/predictive-heating-type", {"predictive_heating_type": value}
        )
        return self._check_ok(data)

    async def set_controller_type(self, value: str) -> bool:
        data = await self._request(
            "POST", "/controller-type", {"regulator_type": value}
        )
        return self._check_ok(data)

    async def set_temperature_calibration_offset(self, value: float) -> bool:
        data = await self._request(
            "POST", "/temperature-calibration-offset", {"value": value}
        )
        return self._check_ok(data)

    async def set_limited_heating_power(self, value: int) -> bool:
        data = await self._request(
            "POST", "/limited-heating-power", {"limited_heating_power": value}
        )
        return self._check_ok(data)

    async def set_max_heater_power(self, power: int) -> bool:
        data = await self._request(
            "POST", "/max-heater-power", {"power": power, "calibrate": False}
        )
        return self._check_ok(data)

    async def set_hysteresis_upper(self, value: float) -> bool:
        """Set upper hysteresis offset (read-modify-write)."""
        current = await self.get_hysteresis_parameters()
        if current is None:
            return False
        data = await self._request(
            "POST",
            "/hysteresis-parameters",
            {
                "temp_hysteresis_upper": value,
                "temp_hysteresis_lower": current["temp_hysteresis_lower"],
            },
        )
        return self._check_ok(data)

    async def set_hysteresis_lower(self, value: float) -> bool:
        """Set lower hysteresis offset (read-modify-write)."""
        current = await self.get_hysteresis_parameters()
        if current is None:
            return False
        data = await self._request(
            "POST",
            "/hysteresis-parameters",
            {
                "temp_hysteresis_upper": current["temp_hysteresis_upper"],
                "temp_hysteresis_lower": value,
            },
        )
        return self._check_ok(data)

    async def set_vacation_mode(self, start: int, end: int) -> bool:
        data = await self._request(
            "POST",
            "/vacation-mode",
            {"start_timestamp": start, "end_timestamp": end},
        )
        return self._check_ok(data)

    async def set_weekly_program(self, timers: list[dict]) -> bool:
        data = await self._request("POST", "/weekly-program", {"timers": timers})
        return self._check_ok(data)

    async def set_timezone_offset(self, offset: int) -> bool:
        data = await self._request(
            "POST", "/timezone-offset", {"timezone_offset": offset}
        )
        return self._check_ok(data)

    async def reboot(self) -> bool:
        """Reboot the heater MCU. No JSON response expected."""
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                await self._session.post(f"{self._base_url}/reboot")
            return True
        except (asyncio.TimeoutError, aiohttp.ClientError):
            # Reboot may kill the connection before response — that's OK
            return True

    # ── Feature detection ─────────────────────────────────────────

    async def detect_supported_features(self) -> set[str]:
        """Probe optional endpoints to determine device capabilities."""
        features: set[str] = set()

        for feature, endpoint in (
            (FEATURE_LIMITED_HEATING_POWER, "/limited-heating-power"),
            (FEATURE_PID_PARAMETERS, "/pid-parameters"),
        ):
            try:
                data = await self._request("GET", endpoint)
                if data is not None and data.get("status") == "ok":
                    features.add(feature)
            except CannotConnect:
                pass

        return features
```

**Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add custom_components/mill_local/api.py tests/
git commit -m "feat: API client with full endpoint coverage and tests"
```

---

## Task 3: Coordinator

**Files:**
- Create: `custom_components/mill_local/coordinator.py`
- Create: `tests/test_coordinator.py`

**Step 1: Create `tests/test_coordinator.py`**

```python
"""Tests for Mill Local coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.mill_local.api import CannotConnect
from custom_components.mill_local.coordinator import MillLocalCoordinator
from custom_components.mill_local.const import DOMAIN
from tests.conftest import MOCK_CONTROL_STATUS, mock_config_entry_data


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.data = {}
    return hass


@pytest.fixture
def mock_api():
    api = AsyncMock()
    api.get_control_status = AsyncMock(return_value=MOCK_CONTROL_STATUS)
    api.host = "192.168.1.100"
    return api


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = mock_config_entry_data()
    entry.title = "Test Heater"
    return entry


class TestCoordinator:
    async def test_successful_update(self, mock_hass, mock_api, mock_entry):
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        data = await coordinator._async_update_data()
        assert data["ambient_temperature"] == 21.5
        assert data["current_power"] == 800
        mock_api.get_control_status.assert_called_once()

    async def test_update_failure_raises(self, mock_hass, mock_api, mock_entry):
        mock_api.get_control_status.side_effect = CannotConnect("timeout")
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        from homeassistant.helpers.update_coordinator import UpdateFailed

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    def test_device_info(self, mock_hass, mock_api, mock_entry):
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        info = coordinator.device_info
        assert info["manufacturer"] == "Mill"
        assert info["model"] == "Mill HeaterGen3Convector"

    def test_supported_features(self, mock_hass, mock_api, mock_entry):
        mock_entry.data = mock_config_entry_data(
            features=["limited_heating_power", "pid_parameters"]
        )
        coordinator = MillLocalCoordinator(mock_hass, mock_api, mock_entry)
        assert "limited_heating_power" in coordinator.supported_features
        assert "pid_parameters" in coordinator.supported_features
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_coordinator.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Create `custom_components/mill_local/coordinator.py`**

```python
"""DataUpdateCoordinator for Mill Local integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import CannotConnect, MillLocalAPI
from .const import (
    CONF_FIRMWARE,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SUPPORTED_FEATURES,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MillLocalCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for polling Mill heater control status."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: MillLocalAPI,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )
        self.api = api
        self.config_entry = entry
        self.supported_features: set[str] = set(
            entry.data.get(CONF_SUPPORTED_FEATURES, [])
        )

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.config_entry.data[CONF_MAC_ADDRESS])},
            manufacturer="Mill",
            model=self.config_entry.data[CONF_MODEL],
            sw_version=self.config_entry.data[CONF_FIRMWARE],
            name=self.config_entry.title,
        )

    @property
    def mac_address(self) -> str:
        return self.config_entry.data[CONF_MAC_ADDRESS]

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.api.get_control_status()
        except CannotConnect as err:
            raise UpdateFailed(f"Error communicating with heater: {err}") from err
```

**Step 4: Run tests**

```bash
pytest tests/test_coordinator.py -v
```

Expected: PASS (some tests may need `homeassistant` package — install it if not present: `pip install homeassistant`)

**Step 5: Commit**

```bash
git add custom_components/mill_local/coordinator.py tests/test_coordinator.py
git commit -m "feat: DataUpdateCoordinator for polling control status"
```

---

## Task 4: Config Flow

**Files:**
- Create: `custom_components/mill_local/config_flow.py`
- Create: `custom_components/mill_local/strings.json`
- Create: `custom_components/mill_local/translations/en.json`
- Create: `custom_components/mill_local/translations/sv.json`
- Create: `tests/test_config_flow.py`

**Step 1: Create `tests/test_config_flow.py`**

```python
"""Tests for Mill Local config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from custom_components.mill_local.config_flow import MillLocalConfigFlow
from custom_components.mill_local.const import DOMAIN
from tests.conftest import MOCK_HOST, MOCK_STATUS


class TestConfigFlow:
    def test_flow_init(self):
        flow = MillLocalConfigFlow()
        assert flow.DOMAIN == DOMAIN

    async def test_step_user_no_input(self):
        """Test initial form is shown."""
        flow = MillLocalConfigFlow()
        flow.hass = AsyncMock()
        result = await flow.async_step_user(user_input=None)
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    async def test_step_user_success(self):
        """Test successful configuration."""
        flow = MillLocalConfigFlow()
        flow.hass = AsyncMock()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = lambda: None
        flow.async_create_entry = lambda **kwargs: {"type": "create_entry", **kwargs}

        mock_api = AsyncMock()
        mock_api.get_status = AsyncMock(return_value=MOCK_STATUS)
        mock_api.detect_supported_features = AsyncMock(return_value=set())

        with patch(
            "custom_components.mill_local.config_flow.MillLocalAPI",
            return_value=mock_api,
        ), patch(
            "custom_components.mill_local.config_flow.async_get_clientsession",
        ):
            result = await flow.async_step_user(
                user_input={"host": MOCK_HOST, "name": "Test Heater"}
            )
            assert result["type"] == "create_entry"
            assert result["title"] == "Test Heater"
            assert result["data"]["mac_address"] == "AA:BB:CC:DD:EE:FF"

    async def test_step_user_cannot_connect(self):
        """Test connection failure shows error."""
        from custom_components.mill_local.api import CannotConnect

        flow = MillLocalConfigFlow()
        flow.hass = AsyncMock()

        mock_api = AsyncMock()
        mock_api.get_status = AsyncMock(side_effect=CannotConnect("timeout"))

        with patch(
            "custom_components.mill_local.config_flow.MillLocalAPI",
            return_value=mock_api,
        ), patch(
            "custom_components.mill_local.config_flow.async_get_clientsession",
        ):
            result = await flow.async_step_user(
                user_input={"host": MOCK_HOST}
            )
            assert result["type"] == "form"
            assert result["errors"] == {"base": "cannot_connect"}

    async def test_step_user_auto_name(self):
        """Test name auto-detected from device when not provided."""
        flow = MillLocalConfigFlow()
        flow.hass = AsyncMock()
        flow.async_set_unique_id = AsyncMock()
        flow._abort_if_unique_id_configured = lambda: None
        flow.async_create_entry = lambda **kwargs: {"type": "create_entry", **kwargs}

        mock_api = AsyncMock()
        mock_api.get_status = AsyncMock(return_value=MOCK_STATUS)
        mock_api.detect_supported_features = AsyncMock(return_value=set())

        with patch(
            "custom_components.mill_local.config_flow.MillLocalAPI",
            return_value=mock_api,
        ), patch(
            "custom_components.mill_local.config_flow.async_get_clientsession",
        ):
            result = await flow.async_step_user(
                user_input={"host": MOCK_HOST}
            )
            assert result["type"] == "create_entry"
            assert result["title"] == "Mill HeaterGen3Convector"
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config_flow.py -v
```

**Step 3: Create `custom_components/mill_local/config_flow.py`**

```python
"""Config flow for Mill Local integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CannotConnect, MillLocalAPI
from .const import (
    CONF_FIRMWARE,
    CONF_MAC_ADDRESS,
    CONF_MODEL,
    CONF_SUPPORTED_FEATURES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_NAME): str,
    }
)

RECONFIGURE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class MillLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Mill Local heaters."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            api = MillLocalAPI(host, session)

            try:
                status = await api.get_status()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during config flow")
                errors["base"] = "unknown"
            else:
                mac = status["mac_address"]
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()

                features = await api.detect_supported_features()
                name = user_input.get(CONF_NAME) or status["name"]

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_MAC_ADDRESS: mac,
                        CONF_MODEL: status["name"],
                        CONF_FIRMWARE: status["version"],
                        CONF_SUPPORTED_FEATURES: list(features),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration (IP change)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            api = MillLocalAPI(host, session)

            try:
                status = await api.get_status()
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reconfigure")
                errors["base"] = "unknown"
            else:
                # Verify same device by MAC
                entry = self._get_reconfigure_entry()
                if status["mac_address"] != entry.data[CONF_MAC_ADDRESS]:
                    errors["base"] = "different_device"
                else:
                    features = await api.detect_supported_features()
                    return self.async_update_reload_and_abort(
                        entry,
                        data_updates={
                            CONF_HOST: host,
                            CONF_FIRMWARE: status["version"],
                            CONF_SUPPORTED_FEATURES: list(features),
                        },
                    )

        entry = self._get_reconfigure_entry()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST, default=entry.data[CONF_HOST]
                    ): str,
                }
            ),
            errors=errors,
        )
```

**Step 4: Create `custom_components/mill_local/strings.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Add Mill Heater",
        "description": "Enter the IP address of your Mill Gen 3 heater.",
        "data": {
          "host": "IP Address",
          "name": "Name (optional)"
        }
      },
      "reconfigure": {
        "title": "Reconfigure Mill Heater",
        "description": "Update the IP address for this heater.",
        "data": {
          "host": "IP Address"
        }
      }
    },
    "error": {
      "cannot_connect": "Cannot connect to the heater. Verify the IP address and that the heater is powered on.",
      "different_device": "The device at this IP address is a different heater (different MAC address).",
      "unknown": "An unexpected error occurred."
    },
    "abort": {
      "already_configured": "This heater is already configured."
    }
  },
  "entity": {
    "sensor": {
      "current_power": { "name": "Current Power" },
      "energy": { "name": "Energy" },
      "control_signal": { "name": "Control Signal" },
      "raw_temperature": { "name": "Raw Temperature" },
      "calibration_offset": { "name": "Calibration Offset" },
      "firmware_version": { "name": "Firmware Version" }
    },
    "binary_sensor": {
      "open_window": { "name": "Open Window" },
      "cloud_connected": { "name": "Cloud Connected" },
      "heating": { "name": "Heating" }
    },
    "switch": {
      "open_window_detection": { "name": "Open Window Detection" },
      "child_lock": { "name": "Child Lock" },
      "cloud_communication": { "name": "Cloud Communication" },
      "commercial_lock": { "name": "Commercial Lock" }
    },
    "number": {
      "calibration_offset": { "name": "Calibration Offset" },
      "hysteresis_upper": { "name": "Hysteresis Upper" },
      "hysteresis_lower": { "name": "Hysteresis Lower" },
      "open_window_drop_threshold": { "name": "Open Window Drop Threshold" },
      "open_window_max_time": { "name": "Open Window Max Time" },
      "limited_heating_power": { "name": "Limited Heating Power" },
      "max_heater_power": { "name": "Max Heater Power" }
    },
    "select": {
      "predictive_heating": { "name": "Predictive Heating" },
      "display_unit": { "name": "Display Unit" },
      "controller_type": { "name": "Controller Type" }
    }
  }
}
```

**Step 5: Create `custom_components/mill_local/translations/en.json`**

Same content as `strings.json`. Copy it exactly.

**Step 6: Create `custom_components/mill_local/translations/sv.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Lagg till Mill-element",
        "description": "Ange IP-adressen for ditt Mill Generation 3-element.",
        "data": {
          "host": "IP-adress",
          "name": "Namn (valfritt)"
        }
      },
      "reconfigure": {
        "title": "Konfigurera om Mill-element",
        "description": "Uppdatera IP-adressen for detta element.",
        "data": {
          "host": "IP-adress"
        }
      }
    },
    "error": {
      "cannot_connect": "Kan inte ansluta till elementet. Kontrollera IP-adressen och att elementet ar paslaget.",
      "different_device": "Enheten pa denna IP-adress ar ett annat element (annan MAC-adress).",
      "unknown": "Ett oväntat fel uppstod."
    },
    "abort": {
      "already_configured": "Detta element ar redan konfigurerat."
    }
  },
  "entity": {
    "sensor": {
      "current_power": { "name": "Aktuell effekt" },
      "energy": { "name": "Energi" },
      "control_signal": { "name": "Styrsignal" },
      "raw_temperature": { "name": "Ratemperatur" },
      "calibration_offset": { "name": "Kalibreringsoffset" },
      "firmware_version": { "name": "Firmware-version" }
    },
    "binary_sensor": {
      "open_window": { "name": "Oppet fonster" },
      "cloud_connected": { "name": "Molnansluten" },
      "heating": { "name": "Varmer" }
    },
    "switch": {
      "open_window_detection": { "name": "Oppet fonster-detektering" },
      "child_lock": { "name": "Barnlas" },
      "cloud_communication": { "name": "Molnkommunikation" },
      "commercial_lock": { "name": "Kommersiellt las" }
    },
    "number": {
      "calibration_offset": { "name": "Kalibreringsoffset" },
      "hysteresis_upper": { "name": "Hysteres ovre" },
      "hysteresis_lower": { "name": "Hysteres undre" },
      "open_window_drop_threshold": { "name": "Fonster temperatursankningströskel" },
      "open_window_max_time": { "name": "Fonster max tid" },
      "limited_heating_power": { "name": "Begransad varmeeffekt" },
      "max_heater_power": { "name": "Max varmeeffekt" }
    },
    "select": {
      "predictive_heating": { "name": "Prediktiv uppvarmning" },
      "display_unit": { "name": "Displayenhet" },
      "controller_type": { "name": "Regulatortyp" }
    }
  }
}
```

**Step 7: Run tests**

```bash
pytest tests/test_config_flow.py -v
```

**Step 8: Commit**

```bash
git add custom_components/mill_local/config_flow.py custom_components/mill_local/strings.json custom_components/mill_local/translations/ tests/test_config_flow.py
git commit -m "feat: config flow with device validation and reconfigure support"
```

---

## Task 5: Integration Setup

**Files:**
- Modify: `custom_components/mill_local/__init__.py`

**Step 1: Write `custom_components/mill_local/__init__.py`**

```python
"""Mill Local integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MillLocalAPI
from .const import DOMAIN
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mill Local from a config entry."""
    session = async_get_clientsession(hass)
    api = MillLocalAPI(entry.data[CONF_HOST], session)

    coordinator = MillLocalCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
```

**Step 2: Commit**

```bash
git add custom_components/mill_local/__init__.py
git commit -m "feat: integration setup with platform forwarding"
```

---

## Task 6: Climate Entity

**Files:**
- Create: `custom_components/mill_local/climate.py`
- Create: `tests/test_climate.py`

**Step 1: Create `tests/test_climate.py`**

```python
"""Tests for Mill Local climate entity."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.climate import MillClimate
from custom_components.mill_local.const import (
    OPERATION_MODE_CONTROL,
    OPERATION_MODE_INDEPENDENT,
    OPERATION_MODE_OFF,
    OPERATION_MODE_WEEKLY,
    PRESET_INDEPENDENT_DEVICE,
    PRESET_NONE,
    PRESET_WEEKLY_PROGRAM,
)
from tests.conftest import MOCK_CONTROL_STATUS, MOCK_CONTROL_STATUS_OFF, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.data = MOCK_CONTROL_STATUS
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.config_entry.entry_id = "test"
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.api = AsyncMock()
    return coord


class TestClimateState:
    def test_current_temperature(self, coordinator):
        entity = MillClimate(coordinator)
        assert entity.current_temperature == 21.5

    def test_target_temperature(self, coordinator):
        entity = MillClimate(coordinator)
        assert entity.target_temperature == 22.0

    def test_hvac_mode_heat(self, coordinator):
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        assert entity.hvac_mode == HVACMode.HEAT

    def test_hvac_mode_off(self, coordinator):
        coordinator.data = MOCK_CONTROL_STATUS_OFF
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        assert entity.hvac_mode == HVACMode.OFF

    def test_preset_control_individually(self, coordinator):
        entity = MillClimate(coordinator)
        assert entity.preset_mode == PRESET_NONE

    def test_preset_weekly_program(self, coordinator):
        coordinator.data = {**MOCK_CONTROL_STATUS, "operation_mode": OPERATION_MODE_WEEKLY}
        entity = MillClimate(coordinator)
        assert entity.preset_mode == PRESET_WEEKLY_PROGRAM

    def test_preset_independent(self, coordinator):
        coordinator.data = {**MOCK_CONTROL_STATUS, "operation_mode": OPERATION_MODE_INDEPENDENT}
        entity = MillClimate(coordinator)
        assert entity.preset_mode == PRESET_INDEPENDENT_DEVICE

    def test_preset_off_mode(self, coordinator):
        coordinator.data = MOCK_CONTROL_STATUS_OFF
        entity = MillClimate(coordinator)
        assert entity.preset_mode is None

    def test_unknown_operation_mode(self, coordinator):
        coordinator.data = {**MOCK_CONTROL_STATUS, "operation_mode": "SomeFutureMode"}
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        assert entity.hvac_mode == HVACMode.HEAT
        assert entity.preset_mode is None


class TestClimateActions:
    async def test_set_temperature(self, coordinator):
        coordinator.api.set_temperature = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        await entity.async_set_temperature(temperature=23.5)
        coordinator.api.set_temperature.assert_called_once_with(23.5)
        coordinator.async_request_refresh.assert_called_once()

    async def test_set_hvac_mode_off(self, coordinator):
        coordinator.api.set_operation_mode = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        await entity.async_set_hvac_mode(HVACMode.OFF)
        coordinator.api.set_operation_mode.assert_called_once_with("Off")

    async def test_set_hvac_mode_heat(self, coordinator):
        coordinator.api.set_operation_mode = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        from homeassistant.components.climate import HVACMode
        await entity.async_set_hvac_mode(HVACMode.HEAT)
        coordinator.api.set_operation_mode.assert_called_once_with("Control individually")

    async def test_set_preset_weekly(self, coordinator):
        coordinator.api.set_operation_mode = AsyncMock(return_value=True)
        coordinator.async_request_refresh = AsyncMock()
        entity = MillClimate(coordinator)
        await entity.async_set_preset_mode(PRESET_WEEKLY_PROGRAM)
        coordinator.api.set_operation_mode.assert_called_once_with("Weekly program")
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_climate.py -v
```

**Step 3: Create `custom_components/mill_local/climate.py`**

```python
"""Climate platform for Mill Local integration."""

from __future__ import annotations

import logging
from typing import Any

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

import voluptuous as vol

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

    # ── Entity services ───────────────────────────────────────────

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
```

**Step 4: Run tests**

```bash
pytest tests/test_climate.py -v
```

**Step 5: Commit**

```bash
git add custom_components/mill_local/climate.py tests/test_climate.py
git commit -m "feat: climate entity with HVAC modes, presets, and services"
```

---

## Task 7: Sensor Entities

**Files:**
- Create: `custom_components/mill_local/sensor.py`
- Create: `tests/test_sensor.py`

**Step 1: Create `tests/test_sensor.py`**

```python
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
```

**Step 2: Run tests to verify fail**

```bash
pytest tests/test_sensor.py -v
```

**Step 3: Create `custom_components/mill_local/sensor.py`**

```python
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
```

**Step 4: Run tests**

```bash
pytest tests/test_sensor.py -v
```

**Step 5: Commit**

```bash
git add custom_components/mill_local/sensor.py tests/test_sensor.py
git commit -m "feat: sensor entities with auto-calculated energy tracking"
```

---

## Task 8: Binary Sensor Entities

**Files:**
- Create: `custom_components/mill_local/binary_sensor.py`
- Create: `tests/test_binary_sensor.py`

**Step 1: Create `tests/test_binary_sensor.py`**

```python
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
```

**Step 2: Run tests to verify fail**

**Step 3: Create `custom_components/mill_local/binary_sensor.py`**

```python
"""Binary sensor platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, OPEN_WINDOW_ACTIVE
from .coordinator import MillLocalCoordinator


@dataclass(frozen=True, kw_only=True)
class MillBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Mill binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[MillBinarySensorEntityDescription, ...] = (
    MillBinarySensorEntityDescription(
        key="open_window",
        translation_key="open_window",
        device_class=BinarySensorDeviceClass.WINDOW,
        value_fn=lambda data: data.get("open_window_active_now") == OPEN_WINDOW_ACTIVE,
    ),
    MillBinarySensorEntityDescription(
        key="cloud_connected",
        translation_key="cloud_connected",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("connected_to_cloud"),
    ),
    MillBinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.HEAT,
        value_fn=lambda data: data.get("switched_on"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local binary sensor entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MillBinarySensor(coordinator, desc) for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class MillBinarySensor(CoordinatorEntity[MillLocalCoordinator], BinarySensorEntity):
    """Binary sensor that reads from coordinator data."""

    entity_description: MillBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.value_fn(self.coordinator.data)
```

**Step 4: Run tests, commit**

```bash
pytest tests/test_binary_sensor.py -v
git add custom_components/mill_local/binary_sensor.py tests/test_binary_sensor.py
git commit -m "feat: binary sensor entities for window, cloud, heating status"
```

---

## Task 9: Switch Entities

**Files:**
- Create: `custom_components/mill_local/switch.py`
- Create: `tests/test_switch.py`

**Step 1: Create `tests/test_switch.py`**

```python
"""Tests for Mill Local switch entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.switch import MillSwitch, SWITCH_DESCRIPTIONS
from tests.conftest import MOCK_CHILD_LOCK, MOCK_OPEN_WINDOW, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.api = AsyncMock()
    return coord


class TestSwitchDescriptions:
    def test_child_lock_value_extraction(self):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        assert desc.value_fn(MOCK_CHILD_LOCK) is False

    def test_open_window_value_extraction(self):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "open_window_detection")
        assert desc.value_fn(MOCK_OPEN_WINDOW) is True


class TestMillSwitch:
    async def test_initial_fetch(self, coordinator):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        coordinator.api.get_child_lock = AsyncMock(return_value=MOCK_CHILD_LOCK)
        entity = MillSwitch(coordinator, desc)
        await entity.async_added_to_hass()
        assert entity.is_on is False

    async def test_turn_on(self, coordinator):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        coordinator.api.get_child_lock = AsyncMock(return_value=MOCK_CHILD_LOCK)
        coordinator.api.set_child_lock = AsyncMock(return_value=True)
        entity = MillSwitch(coordinator, desc)
        await entity.async_added_to_hass()
        await entity.async_turn_on()
        assert entity.is_on is True

    async def test_turn_off(self, coordinator):
        desc = next(d for d in SWITCH_DESCRIPTIONS if d.key == "child_lock")
        data = {**MOCK_CHILD_LOCK, "value": True}
        coordinator.api.get_child_lock = AsyncMock(return_value=data)
        coordinator.api.set_child_lock = AsyncMock(return_value=True)
        entity = MillSwitch(coordinator, desc)
        await entity.async_added_to_hass()
        await entity.async_turn_off()
        assert entity.is_on is False
```

**Step 2: Run tests to verify fail**

**Step 3: Create `custom_components/mill_local/switch.py`**

```python
"""Switch platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MillLocalAPI
from .const import DOMAIN
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MillSwitchEntityDescription(SwitchEntityDescription):
    """Describes a Mill switch entity."""

    get_fn: Callable[[MillLocalAPI], Awaitable[dict[str, Any] | None]]
    set_fn: Callable[[MillLocalAPI, bool], Awaitable[bool]]
    value_fn: Callable[[dict[str, Any]], bool | None]


SWITCH_DESCRIPTIONS: tuple[MillSwitchEntityDescription, ...] = (
    MillSwitchEntityDescription(
        key="open_window_detection",
        translation_key="open_window_detection",
        entity_category=EntityCategory.CONFIG,
        get_fn=MillLocalAPI.get_open_window,
        set_fn=MillLocalAPI.set_open_window_enabled,
        value_fn=lambda data: data.get("enabled"),
    ),
    MillSwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        get_fn=MillLocalAPI.get_child_lock,
        set_fn=MillLocalAPI.set_child_lock,
        value_fn=lambda data: data.get("value"),
    ),
    MillSwitchEntityDescription(
        key="cloud_communication",
        translation_key="cloud_communication",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=MillLocalAPI.get_cloud_communication,
        set_fn=MillLocalAPI.set_cloud_communication,
        value_fn=lambda data: data.get("value"),
    ),
    MillSwitchEntityDescription(
        key="commercial_lock",
        translation_key="commercial_lock",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        get_fn=MillLocalAPI.get_commercial_lock,
        set_fn=MillLocalAPI.set_commercial_lock,
        value_fn=lambda data: data.get("value"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local switch entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MillSwitch(coordinator, desc) for desc in SWITCH_DESCRIPTIONS
    )


class MillSwitch(CoordinatorEntity[MillLocalCoordinator], SwitchEntity):
    """Config switch entity that manages its own state."""

    entity_description: MillSwitchEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillSwitchEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"
        self._is_on: bool | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            data = await self.entity_description.get_fn(self.coordinator.api)
            if data:
                self._is_on = self.entity_description.value_fn(data)
        except Exception:
            _LOGGER.debug("Could not fetch initial value for %s", self.entity_description.key)

    @property
    def is_on(self) -> bool | None:
        return self._is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, True):
            self._is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, False):
            self._is_on = False
            self.async_write_ha_state()
```

**Step 4: Run tests, commit**

```bash
pytest tests/test_switch.py -v
git add custom_components/mill_local/switch.py tests/test_switch.py
git commit -m "feat: switch entities for locks, open window, cloud communication"
```

---

## Task 10: Number Entities

**Files:**
- Create: `custom_components/mill_local/number.py`
- Create: `tests/test_number.py`

**Step 1: Create `tests/test_number.py`**

```python
"""Tests for Mill Local number entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.number import (
    ALWAYS_AVAILABLE_DESCRIPTIONS,
    OPTIONAL_DESCRIPTIONS,
    MillNumber,
)
from custom_components.mill_local.const import FEATURE_LIMITED_HEATING_POWER
from tests.conftest import MOCK_CALIBRATION_OFFSET, MOCK_HYSTERESIS, mock_config_entry_data


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.supported_features = set()
    coord.api = AsyncMock()
    return coord


class TestNumberDescriptions:
    def test_calibration_offset_extraction(self):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "calibration_offset")
        assert desc.value_fn(MOCK_CALIBRATION_OFFSET) == 0

    def test_hysteresis_upper_extraction(self):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "hysteresis_upper")
        assert desc.value_fn(MOCK_HYSTERESIS) == 0.5

    def test_hysteresis_lower_extraction(self):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "hysteresis_lower")
        assert desc.value_fn(MOCK_HYSTERESIS) == 0.5


class TestMillNumber:
    async def test_initial_fetch(self, coordinator):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "calibration_offset")
        coordinator.api.get_temperature_calibration_offset = AsyncMock(
            return_value=MOCK_CALIBRATION_OFFSET
        )
        entity = MillNumber(coordinator, desc)
        await entity.async_added_to_hass()
        assert entity.native_value == 0

    async def test_set_value(self, coordinator):
        desc = next(d for d in ALWAYS_AVAILABLE_DESCRIPTIONS if d.key == "calibration_offset")
        coordinator.api.get_temperature_calibration_offset = AsyncMock(
            return_value=MOCK_CALIBRATION_OFFSET
        )
        coordinator.api.set_temperature_calibration_offset = AsyncMock(return_value=True)
        entity = MillNumber(coordinator, desc)
        await entity.async_added_to_hass()
        await entity.async_set_native_value(1.5)
        assert entity.native_value == 1.5
```

**Step 2: Run tests to verify fail**

**Step 3: Create `custom_components/mill_local/number.py`**

```python
"""Number platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
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
        get_fn=MillLocalAPI.get_temperature_calibration_offset,
        set_fn=MillLocalAPI.set_temperature_calibration_offset,
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
        get_fn=MillLocalAPI.get_hysteresis_parameters,
        set_fn=MillLocalAPI.set_hysteresis_upper,
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
        get_fn=MillLocalAPI.get_hysteresis_parameters,
        set_fn=MillLocalAPI.set_hysteresis_lower,
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
        get_fn=MillLocalAPI.get_open_window,
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
        get_fn=MillLocalAPI.get_open_window,
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
        get_fn=MillLocalAPI.get_limited_heating_power,
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
```

**Step 4: Run tests, commit**

```bash
pytest tests/test_number.py -v
git add custom_components/mill_local/number.py tests/test_number.py
git commit -m "feat: number entities for calibration, hysteresis, power limits"
```

---

## Task 11: Select Entities

**Files:**
- Create: `custom_components/mill_local/select.py`
- Create: `tests/test_select.py`

**Step 1: Create `tests/test_select.py`**

```python
"""Tests for Mill Local select entities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.mill_local.select import SELECT_DESCRIPTIONS, MillSelect
from tests.conftest import (
    MOCK_CONTROLLER_TYPE,
    MOCK_DISPLAY_UNIT,
    MOCK_PREDICTIVE_HEATING,
    mock_config_entry_data,
)


@pytest.fixture
def coordinator():
    coord = MagicMock()
    coord.config_entry = MagicMock()
    coord.config_entry.data = mock_config_entry_data()
    coord.mac_address = "AA:BB:CC:DD:EE:FF"
    coord.api = AsyncMock()
    return coord


class TestSelectDescriptions:
    def test_predictive_heating_extraction(self):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "predictive_heating")
        assert desc.value_fn(MOCK_PREDICTIVE_HEATING) == "Off"

    def test_display_unit_extraction(self):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "display_unit")
        assert desc.value_fn(MOCK_DISPLAY_UNIT) == "Celsius"

    def test_controller_type_extraction(self):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "controller_type")
        assert desc.value_fn(MOCK_CONTROLLER_TYPE) == "hysteresis_or_slow_pid"


class TestMillSelect:
    async def test_initial_fetch(self, coordinator):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "predictive_heating")
        coordinator.api.get_predictive_heating_type = AsyncMock(
            return_value=MOCK_PREDICTIVE_HEATING
        )
        entity = MillSelect(coordinator, desc)
        await entity.async_added_to_hass()
        assert entity.current_option == "Off"

    async def test_select_option(self, coordinator):
        desc = next(d for d in SELECT_DESCRIPTIONS if d.key == "predictive_heating")
        coordinator.api.get_predictive_heating_type = AsyncMock(
            return_value=MOCK_PREDICTIVE_HEATING
        )
        coordinator.api.set_predictive_heating_type = AsyncMock(return_value=True)
        entity = MillSelect(coordinator, desc)
        await entity.async_added_to_hass()
        await entity.async_select_option("Advanced")
        assert entity.current_option == "Advanced"
```

**Step 2: Run tests to verify fail**

**Step 3: Create `custom_components/mill_local/select.py`**

```python
"""Select platform for Mill Local integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import MillLocalAPI
from .const import (
    CONTROLLER_HYSTERESIS,
    CONTROLLER_PID,
    DISPLAY_CELSIUS,
    DISPLAY_FAHRENHEIT,
    DOMAIN,
    PREDICTIVE_HEATING_ADVANCED,
    PREDICTIVE_HEATING_OFF,
    PREDICTIVE_HEATING_SIMPLE,
)
from .coordinator import MillLocalCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class MillSelectEntityDescription(SelectEntityDescription):
    """Describes a Mill select entity."""

    get_fn: Callable[[MillLocalAPI], Awaitable[dict[str, Any] | None]]
    set_fn: Callable[[MillLocalAPI, str], Awaitable[bool]]
    value_fn: Callable[[dict[str, Any]], str | None]


SELECT_DESCRIPTIONS: tuple[MillSelectEntityDescription, ...] = (
    MillSelectEntityDescription(
        key="predictive_heating",
        translation_key="predictive_heating",
        entity_category=EntityCategory.CONFIG,
        options=[PREDICTIVE_HEATING_OFF, PREDICTIVE_HEATING_SIMPLE, PREDICTIVE_HEATING_ADVANCED],
        get_fn=MillLocalAPI.get_predictive_heating_type,
        set_fn=MillLocalAPI.set_predictive_heating_type,
        value_fn=lambda data: data.get("predictive_heating_type"),
    ),
    MillSelectEntityDescription(
        key="display_unit",
        translation_key="display_unit",
        entity_category=EntityCategory.CONFIG,
        options=[DISPLAY_CELSIUS, DISPLAY_FAHRENHEIT],
        get_fn=MillLocalAPI.get_display_unit,
        set_fn=MillLocalAPI.set_display_unit,
        value_fn=lambda data: data.get("value"),
    ),
    MillSelectEntityDescription(
        key="controller_type",
        translation_key="controller_type",
        entity_category=EntityCategory.CONFIG,
        options=[CONTROLLER_HYSTERESIS, CONTROLLER_PID],
        get_fn=MillLocalAPI.get_controller_type,
        set_fn=MillLocalAPI.set_controller_type,
        value_fn=lambda data: data.get("regulator_type"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mill Local select entities."""
    coordinator: MillLocalCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MillSelect(coordinator, desc) for desc in SELECT_DESCRIPTIONS
    )


class MillSelect(CoordinatorEntity[MillLocalCoordinator], SelectEntity):
    """Config select entity that manages its own state."""

    entity_description: MillSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MillLocalCoordinator,
        description: MillSelectEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.mac_address}_{description.key}"
        self._current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        try:
            data = await self.entity_description.get_fn(self.coordinator.api)
            if data:
                self._current_option = self.entity_description.value_fn(data)
        except Exception:
            _LOGGER.debug("Could not fetch initial value for %s", self.entity_description.key)

    @property
    def current_option(self) -> str | None:
        return self._current_option

    async def async_select_option(self, option: str) -> None:
        if await self.entity_description.set_fn(self.coordinator.api, option):
            self._current_option = option
            self.async_write_ha_state()
```

**Step 4: Run tests, commit**

```bash
pytest tests/test_select.py -v
git add custom_components/mill_local/select.py tests/test_select.py
git commit -m "feat: select entities for predictive heating, display unit, controller"
```

---

## Task 12: Services YAML

**Files:**
- Create: `custom_components/mill_local/services.yaml`

**Step 1: Create `custom_components/mill_local/services.yaml`**

```yaml
set_vacation_mode:
  fields:
    enabled:
      required: true
      selector:
        boolean:
    temperature:
      selector:
        number:
          min: 5
          max: 35
          step: 0.5
          unit_of_measurement: "°C"
    start_timestamp:
      selector:
        number:
          mode: box
    end_timestamp:
      selector:
        number:
          mode: box

set_weekly_program:
  fields:
    timers:
      required: true
      selector:
        object:

reboot:
```

**Step 2: Commit**

```bash
git add custom_components/mill_local/services.yaml
git commit -m "feat: service definitions for vacation mode, weekly program, reboot"
```

---

## Task 13: Final Integration — Run All Tests, Verify, Commit

**Step 1: Run full test suite**

```bash
pytest tests/ -v --tb=short
```

Expected: All tests pass.

**Step 2: Run linter**

```bash
ruff check custom_components/ tests/
```

Fix any lint issues.

**Step 3: Verify file structure**

```bash
find custom_components/ -type f | sort
```

Expected output:
```
custom_components/mill_local/__init__.py
custom_components/mill_local/api.py
custom_components/mill_local/binary_sensor.py
custom_components/mill_local/climate.py
custom_components/mill_local/config_flow.py
custom_components/mill_local/const.py
custom_components/mill_local/coordinator.py
custom_components/mill_local/manifest.json
custom_components/mill_local/number.py
custom_components/mill_local/select.py
custom_components/mill_local/sensor.py
custom_components/mill_local/services.yaml
custom_components/mill_local/strings.json
custom_components/mill_local/switch.py
custom_components/mill_local/translations/en.json
custom_components/mill_local/translations/sv.json
```

**Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "chore: lint fixes and final integration verification"
```
