"""Config flow for the Remeha Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import (
    CONNECTION_RTU_OVER_TCP,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    CONNECTION_UDP,
    DOMAIN,
    HA_CONFIG_MINOR_VERSION,
    HA_CONFIG_VERSION,
    MODBUS_DEVICE_ADDRESS,
    MODBUS_SERIAL_BAUDRATE,
    MODBUS_SERIAL_BYTESIZE,
    MODBUS_SERIAL_METHOD,
    MODBUS_SERIAL_METHOD_ASCII,
    MODBUS_SERIAL_METHOD_RTU,
    MODBUS_SERIAL_PARITY,
    MODBUS_SERIAL_PARITY_EVEN,
    MODBUS_SERIAL_PARITY_NONE,
    MODBUS_SERIAL_PARITY_ODD,
    MODBUS_SERIAL_STOPBITS,
)

_LOGGER = logging.getLogger(__name__)

# Schema for first form, configuring generic modbus properties.
STEP_MODBUS_GENERIC_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_TYPE): vol.In(
            [CONNECTION_TCP, CONNECTION_UDP, CONNECTION_RTU_OVER_TCP, CONNECTION_SERIAL]
        ),
        vol.Required(MODBUS_DEVICE_ADDRESS, default=100): cv.positive_int,
    }
)

STEP_RECONFIGURE_GENERIC_DATA = vol.Schema(
    {
        vol.Required(CONF_TYPE): vol.In(
            [CONNECTION_TCP, CONNECTION_UDP, CONNECTION_RTU_OVER_TCP, CONNECTION_SERIAL]
        ),
        vol.Required(MODBUS_DEVICE_ADDRESS, default=100): cv.positive_int,
    }
)

# Schema for modbus serial connections.
MODBUS_SERIAL_SCHEMA = vol.Schema(
    {
        vol.Required(MODBUS_SERIAL_BAUDRATE, default=115200): cv.positive_int,
        vol.Required(MODBUS_SERIAL_BYTESIZE, default=8): vol.All(int, vol.In([5, 6, 7, 8])),
        vol.Required(MODBUS_SERIAL_METHOD, default=MODBUS_SERIAL_METHOD_RTU): vol.In(
            [MODBUS_SERIAL_METHOD_RTU, MODBUS_SERIAL_METHOD_ASCII]
        ),
        vol.Required(MODBUS_SERIAL_PARITY, default=MODBUS_SERIAL_PARITY_NONE): vol.In(
            [
                MODBUS_SERIAL_PARITY_EVEN,
                MODBUS_SERIAL_PARITY_ODD,
                MODBUS_SERIAL_PARITY_NONE,
            ]
        ),
        vol.Required(CONF_PORT): vol.Any(cv.port, cv.string),
        vol.Required(MODBUS_SERIAL_STOPBITS, default=2): vol.All(int, vol.In([1, 2])),
    }
)

# Schema for modbus socket connections.
MODBUS_SOCKET_SCHEMA = vol.Schema(
    {vol.Required(CONF_HOST): cv.string, vol.Required(CONF_PORT): cv.port}
)


async def validate_modbus_generic_config(
    hass: HomeAssistant, data: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input that should contain the gemeric modbus configuration."""

    return {
        CONF_NAME: data[CONF_NAME],
        CONF_TYPE: data[CONF_TYPE],
        MODBUS_DEVICE_ADDRESS: int(data[MODBUS_DEVICE_ADDRESS]),
    }


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remeha Modbus."""

    VERSION = HA_CONFIG_VERSION
    MINOR_VERSION = HA_CONFIG_MINOR_VERSION

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure the modbus settings."""

        errors: dict[str, str] = {}
        self.data: dict[str, Any] = {}
        if user_input is not None:
            try:
                self.data = await validate_modbus_generic_config(self.hass, user_input)

                # Assign a unique id to force a single config entry for this device.
                await self.async_set_unique_id(self.data[CONF_NAME])

                # And abort if a config entry for this device already exists.
                self._abort_if_unique_id_configured()
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while creating generic modbus configuration."
                )
                errors["base"] = "unknown"
            else:
                if self.data[CONF_TYPE] == CONNECTION_SERIAL:
                    return self.async_show_form(
                        step_id="modbus_serial",
                        data_schema=MODBUS_SERIAL_SCHEMA,
                        errors=errors,
                    )

                return self.async_show_form(
                    step_id="modbus_socket",
                    data_schema=MODBUS_SOCKET_SCHEMA,
                    errors=errors,
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_MODBUS_GENERIC_SCHEMA, errors=errors
        )

    async def async_step_modbus_serial(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure modbus over a serial connection."""

        if user_input is not None and user_input[MODBUS_SERIAL_BAUDRATE] is not None:
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=self.data | user_input
                )
            return self.async_create_entry(title="Remeha Modbus", data=self.data | user_input)

        return self.async_show_form(step_id="modbus_serial", data_schema=MODBUS_SERIAL_SCHEMA)

    async def async_step_modbus_socket(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure modbus over a socket connection."""

        errors: dict[str, str] = {}
        if user_input is not None and user_input[CONF_HOST] is not None:
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(), data_updates=self.data | user_input
                )
            return self.async_create_entry(title="Remeha Modbus", data=self.data | user_input)

        return self.async_show_form(
            step_id="modbus_socket", data_schema=MODBUS_SOCKET_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(self: ConfigFlow, user_input: dict[str, Any] | None = None):
        """Reconfigure the modbus connection."""

        errors: dict[str, str] = {}
        self.data: dict[str, Any] = {}
        if user_input is not None:
            reconf_entry: ConfigEntry = self._get_reconfigure_entry()

            self.data = await validate_modbus_generic_config(
                self.hass, user_input | {CONF_NAME: reconf_entry.data[CONF_NAME]}
            )
            await self.async_set_unique_id(reconf_entry.unique_id)
            self._abort_if_unique_id_mismatch()

            # Forward to either serial or socket settings.
            if self.data[CONF_TYPE] == CONNECTION_SERIAL:
                return self.async_show_form(
                    step_id="modbus_serial", data_schema=MODBUS_SERIAL_SCHEMA, errors=errors
                )

            return self.async_show_form(
                step_id="modbus_socket", data_schema=MODBUS_SOCKET_SCHEMA, errors=errors
            )

        return self.async_show_form(
            step_id="reconfigure", data_schema=STEP_RECONFIGURE_GENERIC_DATA, errors=errors
        )
