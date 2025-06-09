"""Remeha Modbus service calls."""

import logging

from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.components.weather.const import ATTR_WEATHER_TEMPERATURE_UNIT
from homeassistant.components.weather.const import DOMAIN as WeatherDomain
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from pymodbus import ModbusException

from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SERVICE_NAME,
    CONFIG_AUTO_SCHEDULE,
    DOMAIN,
    PUSH_SCHEDULE_CLIMATE_ENTITY,
    PUSH_SCHEDULE_SERVICE_NAME,
    PUSH_SCHEDULE_SERVICE_SCHEMA,
    PUSH_SCHEDULE_WEEKDAY,
    READ_REGISTERS_REGISTER_COUNT,
    READ_REGISTERS_SERVICE_NAME,
    READ_REGISTERS_SERVICE_SCHEMA,
    READ_REGISTERS_START_REGISTER,
    READ_REGISTERS_STRUCT_FORMAT,
    WEATHER_ENTITY_ID,
    Weekday,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import (
    RemehaIncorrectServiceCall,
    RemehaServiceException,
    RequiredServiceMissing,
)
from custom_components.remeha_modbus.schedule_sync.synchronizer import ScheduleSynchronizer

_LOGGER = logging.getLogger(__name__)


def register_services(
    hass: HomeAssistant, config: ConfigEntry, coordinator: RemehaUpdateCoordinator
) -> None:
    """Register all services of this integration."""

    if not coordinator.get_climates(lambda climate: climate.is_domestic_hot_water()):
        _LOGGER.warning(
            "Not registering service '%s' since no DHW climate was discovered by this integration.",
            AUTO_SCHEDULE_SERVICE_NAME,
        )
        return

    if config.data[CONFIG_AUTO_SCHEDULE] is False:
        _LOGGER.info(
            "DHW auto scheduling is not required by configuration, but service is still registered since manual calls are also allowed."
        )

    async def dhw_auto_schedule(_: ServiceCall) -> None:
        _LOGGER.debug("Retrieving weather forecast...")
        forecasts: dict = await hass.services.async_call(
            domain=WeatherDomain,
            service=SERVICE_GET_FORECASTS,
            target={"entity_id": config.data[WEATHER_ENTITY_ID], "type": "hourly"},
            blocking=True,
            return_response=True,
        )
        _LOGGER.debug("Weather forecast retrieved.")

        weather_entity_id: str = config.data[WEATHER_ENTITY_ID]
        temperature_unit: str = hass.states.get(weather_entity_id).attributes[
            ATTR_WEATHER_TEMPERATURE_UNIT
        ]

        if temperature_unit not in UnitOfTemperature:
            raise RemehaIncorrectServiceCall(
                translation_domain=DOMAIN,
                translation_key="auto_schedule_unsupported_temperature_unit",
                translation_placeholders={
                    "entity_id": weather_entity_id,
                    "unit_of_temperature": temperature_unit,
                },
            )

        await coordinator.async_dhw_auto_schedule(
            hourly_forecasts=forecasts.get(weather_entity_id, {}).get("forecast", []),
            temperature_unit=UnitOfTemperature(temperature_unit),
        )

    async def async_read_registers(call: ServiceCall) -> ServiceResponse:
        start_register: int = int(call.data[READ_REGISTERS_START_REGISTER])
        register_count: int = int(call.data[READ_REGISTERS_REGISTER_COUNT])
        struct_format: str = call.data[READ_REGISTERS_STRUCT_FORMAT]

        try:
            return {
                "value": await coordinator.async_read_registers(
                    start_register=start_register,
                    register_count=register_count,
                    struct_format=struct_format,
                )
            }
        except ModbusException as e:
            raise RemehaServiceException(
                translation_domain=DOMAIN, translation_key="read_registers_modbus_error"
            ) from e

    async def async_push_schedule(call: ServiceCall) -> None:
        synchronizer = ScheduleSynchronizer(hass=hass, coordinator=coordinator)
        dhw_state = hass.states.get(call.data[PUSH_SCHEDULE_CLIMATE_ENTITY])
        dhw = coordinator.get_climate(id=dhw_state.attributes["zone_id"])
        schedule = dhw.current_schedule[Weekday[str(call.data[PUSH_SCHEDULE_WEEKDAY]).upper()]]

        try:
            await synchronizer.async_push_schedule(schedule=schedule)
        except RequiredServiceMissing as e:
            raise RemehaIncorrectServiceCall from e

    hass.services.async_register(
        domain=DOMAIN,
        service=AUTO_SCHEDULE_SERVICE_NAME,
        service_func=dhw_auto_schedule,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=READ_REGISTERS_SERVICE_NAME,
        service_func=async_read_registers,
        schema=READ_REGISTERS_SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        domain=DOMAIN,
        service=PUSH_SCHEDULE_SERVICE_NAME,
        service_func=async_push_schedule,
        schema=PUSH_SCHEDULE_SERVICE_SCHEMA,
    )
