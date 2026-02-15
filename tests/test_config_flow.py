"""Tests for Mill Local config flow."""

from unittest.mock import AsyncMock, patch

from custom_components.mill_local.config_flow import MillLocalConfigFlow
from tests.conftest import MOCK_HOST, MOCK_STATUS


class TestConfigFlow:
    def test_flow_init(self):
        flow = MillLocalConfigFlow()
        assert flow.VERSION == 1

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
        from custom_components.mill_local.api import CannotConnectError

        flow = MillLocalConfigFlow()
        flow.hass = AsyncMock()

        mock_api = AsyncMock()
        mock_api.get_status = AsyncMock(side_effect=CannotConnectError("timeout"))

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
