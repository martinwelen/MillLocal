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
