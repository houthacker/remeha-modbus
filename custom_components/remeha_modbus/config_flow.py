"""Config flow for the Remeha Modbus integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.components.weather.const import DOMAIN as WeatherDomain
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.data_entry_flow import section
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SELECTED_SCHEDULE,
    CONFIG_AUTO_SCHEDULE,
    CONFIG_SCHEDULE_EDITING,
    CONNECTION_RTU_OVER_TCP,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    CONNECTION_UDP,
    DHW_BOILER_CONFIG_SECTION,
    DHW_BOILER_ENERGY_LABEL,
    DHW_BOILER_HEAT_LOSS_RATE,
    DHW_BOILER_VOLUME,
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
    PV_ANNUAL_EFFICIENCY_DECREASE,
    PV_CONFIG_SECTION,
    PV_INSTALLATION_DATE,
    PV_MAX_TILT_DEGREES,
    PV_MIN_TILT_DEGREES,
    PV_NOMINAL_POWER_WP,
    PV_ORIENTATION,
    PV_TILT,
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
    WEATHER_ENTITY_ID,
    BoilerEnergyLabel,
    PVSystemOrientation,
)
from custom_components.remeha_modbus.helpers import config_validation as remeha_cv

_LOGGER = logging.getLogger(__name__)


# Schema for auto scheduling support
def _auto_scheduling_schema(current: ConfigEntry | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                WEATHER_ENTITY_ID,
                default=current.data[WEATHER_ENTITY_ID] if current else vol.UNDEFINED,
            ): selector({"entity": {"filter": {"domain": WeatherDomain}}}),
            vol.Required(
                AUTO_SCHEDULE_SELECTED_SCHEDULE,
                default=current.data[AUTO_SCHEDULE_SELECTED_SCHEDULE]
                if current
                else REMEHA_PRESET_SCHEDULE_1,
            ): selector(
                {
                    "select": {
                        "mode": "dropdown",
                        "translation_key": "select_default_auto_schedule_id",
                        "options": [
                            REMEHA_PRESET_SCHEDULE_1,
                            REMEHA_PRESET_SCHEDULE_2,
                            REMEHA_PRESET_SCHEDULE_3,
                        ],
                    }
                }
            ),
            vol.Required(PV_CONFIG_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            PV_NOMINAL_POWER_WP,
                            default=current.data[PV_CONFIG_SECTION][PV_NOMINAL_POWER_WP]
                            if current
                            else vol.UNDEFINED,
                        ): cv.positive_int,
                        vol.Optional(
                            PV_ORIENTATION,
                            default=current.data[PV_CONFIG_SECTION].get(
                                PV_ORIENTATION, vol.UNDEFINED
                            )
                            if current
                            else PVSystemOrientation.SOUTH,
                        ): remeha_cv.str_enum(PVSystemOrientation),
                        vol.Optional(
                            PV_TILT,
                            default=current.data[PV_CONFIG_SECTION].get(PV_TILT, vol.UNDEFINED)
                            if current
                            else 30.0,
                        ): vol.All(
                            vol.Coerce(float),
                            vol.Range(min=PV_MIN_TILT_DEGREES, max=PV_MAX_TILT_DEGREES),
                        ),
                        vol.Optional(
                            PV_ANNUAL_EFFICIENCY_DECREASE,
                            default=current.data[PV_CONFIG_SECTION].get(
                                PV_ANNUAL_EFFICIENCY_DECREASE, vol.UNDEFINED
                            )
                            if current
                            else 0.0,
                        ): cv.positive_float,
                        vol.Optional(
                            PV_INSTALLATION_DATE,
                            default=current.data[PV_CONFIG_SECTION].get(
                                PV_INSTALLATION_DATE, vol.UNDEFINED
                            )
                            if current
                            else vol.UNDEFINED,
                        ): selector({"date": {}}),
                    }
                ),
                {"collapsed": False},
            ),
            vol.Required(DHW_BOILER_CONFIG_SECTION): section(
                vol.Schema(
                    {
                        vol.Required(
                            DHW_BOILER_VOLUME,
                            default=current.data[DHW_BOILER_CONFIG_SECTION][DHW_BOILER_VOLUME]
                            if current
                            else vol.UNDEFINED,
                        ): cv.positive_int,
                        vol.Optional(
                            DHW_BOILER_HEAT_LOSS_RATE,
                            default=current.data[DHW_BOILER_CONFIG_SECTION].get(
                                DHW_BOILER_HEAT_LOSS_RATE, vol.UNDEFINED
                            )
                            if current
                            else 0.0,
                        ): cv.positive_float,
                        vol.Optional(
                            DHW_BOILER_ENERGY_LABEL,
                            current.data[DHW_BOILER_CONFIG_SECTION].get(
                                DHW_BOILER_ENERGY_LABEL, vol.UNDEFINED
                            )
                            if current
                            else vol.UNDEFINED,
                        ): remeha_cv.str_enum(BoilerEnergyLabel),
                    }
                ),
                {"collapsed": False},
            ),
        }
    )


def _modbus_serial_schema(current: ConfigEntry | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                MODBUS_SERIAL_BAUDRATE,
                default=current.data[MODBUS_SERIAL_BAUDRATE] if current else 115200,
            ): cv.positive_int,
            vol.Required(
                MODBUS_SERIAL_BYTESIZE,
                default=current.data[MODBUS_SERIAL_BYTESIZE] if current else 8,
            ): vol.All(int, vol.In([5, 6, 7, 8])),
            vol.Required(
                MODBUS_SERIAL_METHOD,
                default=current.data[MODBUS_SERIAL_METHOD] if current else MODBUS_SERIAL_METHOD_RTU,
            ): vol.In([MODBUS_SERIAL_METHOD_RTU, MODBUS_SERIAL_METHOD_ASCII]),
            vol.Required(
                MODBUS_SERIAL_PARITY,
                default=current.data[MODBUS_SERIAL_PARITY]
                if current
                else MODBUS_SERIAL_PARITY_NONE,
            ): vol.In(
                [
                    MODBUS_SERIAL_PARITY_EVEN,
                    MODBUS_SERIAL_PARITY_ODD,
                    MODBUS_SERIAL_PARITY_NONE,
                ]
            ),
            vol.Required(
                CONF_PORT, default=current.data[CONF_PORT] if current else vol.UNDEFINED
            ): vol.Any(cv.port, cv.string),
            vol.Required(
                MODBUS_SERIAL_STOPBITS,
                default=current.data[MODBUS_SERIAL_STOPBITS] if current else 2,
            ): vol.All(int, vol.In([1, 2])),
        }
    )


def _modbus_socket_schema(current: ConfigEntry | None = None) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_HOST, default=current.data[CONF_HOST] if current else vol.UNDEFINED
            ): cv.string,
            vol.Required(
                CONF_PORT, default=current.data[CONF_PORT] if current else vol.UNDEFINED
            ): cv.port,
        }
    )


def _validate_modbus_generic_config(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input that should contain the gemeric modbus configuration."""

    return {
        CONF_NAME: data[CONF_NAME],
        CONF_TYPE: data[CONF_TYPE],
        MODBUS_DEVICE_ADDRESS: int(data[MODBUS_DEVICE_ADDRESS]),
        CONFIG_AUTO_SCHEDULE: bool(data[CONFIG_AUTO_SCHEDULE]),
        CONFIG_SCHEDULE_EDITING: bool(data[CONFIG_SCHEDULE_EDITING]),
    }


def _validate_auto_scheduling_config(data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input that selects the weather entity and provides pv info."""

    pv_options: dict[str, Any] = data[PV_CONFIG_SECTION]
    dhw_options: dict[str, Any] = data[DHW_BOILER_CONFIG_SECTION]
    return {
        WEATHER_ENTITY_ID: data[WEATHER_ENTITY_ID],
        AUTO_SCHEDULE_SELECTED_SCHEDULE: data[AUTO_SCHEDULE_SELECTED_SCHEDULE],
        PV_CONFIG_SECTION: {
            PV_NOMINAL_POWER_WP: pv_options[PV_NOMINAL_POWER_WP],
            PV_ORIENTATION: pv_options[PV_ORIENTATION],
            PV_TILT: pv_options[PV_TILT],
            PV_ANNUAL_EFFICIENCY_DECREASE: pv_options[PV_ANNUAL_EFFICIENCY_DECREASE],
            PV_INSTALLATION_DATE: pv_options.get(PV_INSTALLATION_DATE),
        },
        DHW_BOILER_CONFIG_SECTION: {
            DHW_BOILER_VOLUME: dhw_options.get(DHW_BOILER_VOLUME),
            DHW_BOILER_HEAT_LOSS_RATE: dhw_options.get(DHW_BOILER_HEAT_LOSS_RATE),
            DHW_BOILER_ENERGY_LABEL: dhw_options.get(DHW_BOILER_ENERGY_LABEL),
        },
    }


class RemehaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Remeha Modbus."""

    VERSION = HA_CONFIG_VERSION
    MINOR_VERSION = HA_CONFIG_MINOR_VERSION

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Configure the modbus settings."""

        errors: dict[str, str] = {}
        self.data: dict[str, Any] = {}
        if user_input is not None:
            try:
                self.data = _validate_modbus_generic_config(user_input)

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
                if self.data[CONFIG_AUTO_SCHEDULE] is True:
                    return self.async_show_form(
                        step_id="auto_scheduling",
                        data_schema=_auto_scheduling_schema(),
                        errors=errors,
                    )

                if self.data[CONF_TYPE] == CONNECTION_SERIAL:
                    return self.async_show_form(
                        step_id="modbus_serial",
                        data_schema=_modbus_serial_schema(),
                        errors=errors,
                    )

                return self.async_show_form(
                    step_id="modbus_socket",
                    data_schema=_modbus_socket_schema(),
                    errors=errors,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME): cv.string,
                    vol.Required(CONF_TYPE): vol.In(
                        [CONNECTION_TCP, CONNECTION_UDP, CONNECTION_RTU_OVER_TCP, CONNECTION_SERIAL]
                    ),
                    vol.Required(MODBUS_DEVICE_ADDRESS, default=100): cv.positive_int,
                    vol.Optional(CONFIG_SCHEDULE_EDITING, default=False): cv.boolean,
                    vol.Optional(CONFIG_AUTO_SCHEDULE, default=False): cv.boolean,
                }
            ),
            errors=errors,
        )

    async def async_step_auto_scheduling(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a weather entity and configure solar system."""

        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                self.data |= _validate_auto_scheduling_config(user_input)
            except Exception:
                _LOGGER.exception(
                    "Unexpected exception while creating auto scheduling configuration."
                )
                errors["base"] = "unknown"

            if self.data[CONF_TYPE] == CONNECTION_SERIAL:
                return self.async_show_form(
                    step_id="modbus_serial",
                    data_schema=_modbus_serial_schema(
                        current=self._get_reconfigure_entry()
                        if self.source == SOURCE_RECONFIGURE
                        else None
                    ),
                    errors=errors,
                )

            return self.async_show_form(
                step_id="modbus_socket",
                data_schema=_modbus_socket_schema(
                    current=self._get_reconfigure_entry()
                    if self.source == SOURCE_RECONFIGURE
                    else None
                ),
                errors=errors,
            )

        return self.async_show_form(
            step_id="auto_scheduling", data_schema=_auto_scheduling_schema(), errors=errors
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

        return self.async_show_form(
            step_id="modbus_serial",
            data_schema=_modbus_serial_schema(
                current=self._get_reconfigure_entry() if self.source == SOURCE_RECONFIGURE else None
            ),
        )

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
            step_id="modbus_socket",
            data_schema=_modbus_socket_schema(
                current=self._get_reconfigure_entry() if self.source == SOURCE_RECONFIGURE else None
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self: ConfigFlow, user_input: dict[str, Any] | None = None):
        """Reconfigure the modbus connection."""

        errors: dict[str, str] = {}
        self.data: dict[str, Any] = {}
        reconf_entry: ConfigEntry = self._get_reconfigure_entry()

        if user_input is not None:
            self.data = _validate_modbus_generic_config(
                user_input | {CONF_NAME: reconf_entry.data[CONF_NAME]}
            )
            await self.async_set_unique_id(reconf_entry.unique_id)
            self._abort_if_unique_id_mismatch()

            if self.data[CONFIG_AUTO_SCHEDULE] is True:
                return self.async_show_form(
                    step_id="auto_scheduling",
                    data_schema=_auto_scheduling_schema(current=reconf_entry),
                    errors=errors,
                )

            # Forward to either serial or socket settings.
            if self.data[CONF_TYPE] == CONNECTION_SERIAL:
                return self.async_show_form(
                    step_id="modbus_serial",
                    data_schema=_modbus_serial_schema(current=reconf_entry),
                    errors=errors,
                )

            return self.async_show_form(
                step_id="modbus_socket",
                data_schema=_modbus_socket_schema(current=reconf_entry),
                errors=errors,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TYPE, default=reconf_entry.data[CONF_TYPE]): vol.In(
                        [CONNECTION_TCP, CONNECTION_UDP, CONNECTION_RTU_OVER_TCP, CONNECTION_SERIAL]
                    ),
                    vol.Required(
                        MODBUS_DEVICE_ADDRESS, default=reconf_entry.data[MODBUS_DEVICE_ADDRESS]
                    ): cv.positive_int,
                    vol.Required(
                        CONFIG_SCHEDULE_EDITING, default=reconf_entry.data[CONFIG_SCHEDULE_EDITING]
                    ): cv.boolean,
                    vol.Required(
                        CONFIG_AUTO_SCHEDULE, default=reconf_entry.data[CONFIG_AUTO_SCHEDULE]
                    ): cv.boolean,
                }
            ),
            errors=errors,
        )
