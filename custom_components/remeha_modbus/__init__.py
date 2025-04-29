"""The Remeha Modbus integration."""

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.const import CONF_NAME, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from pymodbus import ModbusException

from custom_components.remeha_modbus.api import (
    ConnectionType,
    RemehaApi,
)
from custom_components.remeha_modbus.coordinator import RemehaUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.NUMBER, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remeha Modbus based on a config entry."""

    modbus_hub_name = entry.data[CONF_NAME]
    modbus_type = entry.data[CONF_TYPE]

    if modbus_type not in ConnectionType:
        connection_types: str = ", ".join(e.value for e in ConnectionType)
        raise ConfigEntryError(
            f"{modbus_type} is not a valid connection type. Use one of [{connection_types}]"
        )

    api: RemehaApi = RemehaApi.create(name=modbus_hub_name, config=entry.data)

    # Ensure the modbus device is reachable and actually talking Modbus
    # before forwarding setup to other platforms.
    try:
        await api.async_connect()
        await api.async_health_check()
    except ModbusException as ex:
        raise ConfigEntryNotReady(f"Error while executing modbus health check: {ex}") from ex

    coordinator = RemehaUpdateCoordinator(hass=hass, config_entry=entry, api=api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = {"api": api, "coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Remeha Modbus configuration."""

    # Close the connection to the modbus server.
    coordinator: RemehaUpdateCoordinator = entry.runtime_data["coordinator"]
    api: RemehaApi = entry.runtime_data["api"]
    await coordinator.async_shutdown()
    await api.async_close()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
