"""Remeha Modbus service calls."""

import logging

from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.components.weather.const import ATTR_WEATHER_TEMPERATURE_UNIT
from homeassistant.components.weather.const import DOMAIN as WeatherDomain
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SERVICE_NAME,
    CONFIG_AUTO_SCHEDULE,
    DOMAIN,
    WEATHER_ENTITY_ID,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator
from custom_components.remeha_modbus.errors import RemehaIncorrectServiceCall

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

    hass.services.async_register(
        domain=DOMAIN,
        service=AUTO_SCHEDULE_SERVICE_NAME,
        service_func=dhw_auto_schedule,
    )
