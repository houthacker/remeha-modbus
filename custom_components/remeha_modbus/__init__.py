"""The Remeha Modbus integration."""

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from pymodbus import ModbusException

from .api import ConnectionType, RemehaApi, RemehaModbusSerialApi, RemehaModbusSocketApi
from .const import (
    MODBUS_DEVICE_ADDRESS,
    MODBUS_SERIAL_BAUDRATE,
    MODBUS_SERIAL_BYTESIZE,
    MODBUS_SERIAL_METHOD,
    MODBUS_SERIAL_PARITY,
    MODBUS_SERIAL_STOPBITS,
)
from .coordinator import RemehaUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def _create_api(name: str, type: ConnectionType, entry: ConfigEntry) -> RemehaApi:
    match type:
        case ConnectionType.SERIAL:
            return RemehaModbusSerialApi(
                name=name,
                port=entry.data[CONF_PORT],
                baudrate=entry.data[MODBUS_SERIAL_BAUDRATE],
                bytesize=entry.data[MODBUS_SERIAL_BYTESIZE],
                method=entry.data[MODBUS_SERIAL_METHOD],
                parity=entry.data[MODBUS_SERIAL_PARITY],
                stopbits=entry.data[MODBUS_SERIAL_STOPBITS],
                device_address=entry.data[MODBUS_DEVICE_ADDRESS],
            )
        case _:
            return RemehaModbusSocketApi(
                name=name,
                host=entry.data[CONF_HOST],
                port=entry.data[CONF_PORT],
                connection_type=entry.data[CONF_TYPE],
                device_address=entry.data[MODBUS_DEVICE_ADDRESS],
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Remeha Modbus based on a config entry."""

    modbus_hub_name = entry.data[CONF_NAME]
    modbus_type = entry.data[CONF_TYPE]

    if modbus_type not in ConnectionType:
        connection_types: str = ", ".join(e.value for e in ConnectionType)
        raise ConfigEntryError(
            f"{modbus_type} is not a valid connection type. Use one of [{connection_types}]"
        )

    api: RemehaApi = await _create_api(modbus_hub_name, modbus_type, entry)

    # Ensure the modbus device is reachable and actually talking Modbus
    # before forwarding setup to other platforms.
    try:
        await api.connect()
        await api.health_check()
    except ModbusException as ex:
        raise ConfigEntryNotReady(
            f"Error while executing modbus health check: {ex}"
        ) from ex

    coordinator = RemehaUpdateCoordinator(hass=hass, config_entry=entry, api=api)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = {"api": api, "coordinator": coordinator}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
