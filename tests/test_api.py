"""Tests for Mill Local API client."""

import asyncio
import json

import aiohttp
import pytest
from aioresponses import aioresponses
from yarl import URL

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
            request = m.requests[("POST", URL(f"{BASE_URL}/set-temperature"))]
            body = request[0].kwargs["json"]
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
            request = m.requests[("POST", URL(f"{BASE_URL}/hysteresis-parameters"))]
            body = request[0].kwargs["json"]
            assert body["temp_hysteresis_upper"] == 1.0
            assert body["temp_hysteresis_lower"] == 0.5  # unchanged

    async def test_set_hysteresis_lower(self, api_client):
        with aioresponses() as m:
            m.get(f"{BASE_URL}/hysteresis-parameters", payload=MOCK_HYSTERESIS)
            m.post(f"{BASE_URL}/hysteresis-parameters", payload={"status": "ok"})
            result = await api_client.set_hysteresis_lower(2.0)
            assert result is True
            request = m.requests[("POST", URL(f"{BASE_URL}/hysteresis-parameters"))]
            body = request[0].kwargs["json"]
            assert body["temp_hysteresis_upper"] == 0.5  # unchanged
            assert body["temp_hysteresis_lower"] == 2.0
