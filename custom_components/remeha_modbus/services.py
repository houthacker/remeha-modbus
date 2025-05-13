"""Remeha Modbus service calls."""

import logging

from homeassistant.components.weather import SERVICE_GET_FORECASTS
from homeassistant.components.weather.const import DOMAIN as WeatherDomain
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_SERVICE_NAME,
    CONFIG_AUTO_SCHEDULE,
    DOMAIN,
    WEATHER_ENTITY_ID,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

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

    async def dhw_auto_schedule(call: ServiceCall) -> None:
        forecasts: dict = await hass.services.async_call(
            domain=WeatherDomain,
            service=SERVICE_GET_FORECASTS,
            target={"entity_id": config.data[WEATHER_ENTITY_ID], "type": "hourly"},
            blocking=True,
            return_response=True,
        )

        weather_entity_id: str = config.data[WEATHER_ENTITY_ID]

        await coordinator.async_dhw_auto_schedule(
            forecast=forecasts.get(weather_entity_id, {}).get("forecast", [])
        )

    hass.services.async_register(
        domain=DOMAIN,
        service=AUTO_SCHEDULE_SERVICE_NAME,
        service_func=dhw_auto_schedule,
    )
