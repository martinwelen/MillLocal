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

    # -- Core reads (used by coordinator) --

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

    # -- Config reads (on-demand, return None on failure) --

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

    # -- Writes (return True on success, False on failure) --

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
            # Reboot may kill the connection before response -- that's OK
            return True

    # -- Feature detection --

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
