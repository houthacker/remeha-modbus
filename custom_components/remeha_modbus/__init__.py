"""The Remeha Modbus integration."""

from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant
from pymodbus import FramerType, ModbusException
from pymodbus.client import (
    AsyncModbusSerialClient,
    AsyncModbusTcpClient,
    AsyncModbusUdpClient,
    ModbusBaseClient,
)

from .api import (
    ConnectionType,
    RemehaApi,
)
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


async def _create_api(name: str, config: MappingProxyType[str, Any]) -> RemehaApi:
    connection_type: ConnectionType = config[CONF_TYPE]
    client: ModbusBaseClient
    match connection_type:
        case ConnectionType.SERIAL:
            client = AsyncModbusSerialClient(
                port=config[CONF_PORT],
                baudrate=config[MODBUS_SERIAL_BAUDRATE],
                bytesize=config[MODBUS_SERIAL_BYTESIZE],
                framer=config[MODBUS_SERIAL_METHOD],
                parity=config[MODBUS_SERIAL_PARITY],
                stopbits=config[MODBUS_SERIAL_STOPBITS],
            )
        case ConnectionType.TCP:
            client = AsyncModbusTcpClient(
                host=config[CONF_HOST],
                port=int(config[CONF_PORT]),
                framer=FramerType.SOCKET,
                timeout=5,
            )
        case ConnectionType.UDP:
            client = AsyncModbusUdpClient(
                host=config[CONF_HOST],
                port=int(config[CONF_PORT]),
                framer=FramerType.SOCKET,
                timeout=5,
            )
        case ConnectionType.RTU_OVER_TCP:
            client = AsyncModbusTcpClient(
                host=config[CONF_HOST],
                port=int(config[CONF_PORT]),
                framer=FramerType.RTU,
                timeout=5,
            )

    return RemehaApi(
        name=name,
        connection_type=connection_type,
        client=client,
        device_address=config[MODBUS_DEVICE_ADDRESS],
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

    api: RemehaApi = await _create_api(name=modbus_hub_name, config=entry.data)

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
