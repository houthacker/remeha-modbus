"""Helpers for configuration.

The voluptuous helpers are those that don't exist in HA.
"""

from types import MappingProxyType
from typing import Any

from aio_remeha_modbus.api import RemehaApi
from homeassistant.components.modbus.connection import ModbusParams, async_get_temporary_unit
from homeassistant.components.modbus.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    RTUOVERTCP,
    SERIAL,
    TCP,
    UDP,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from modbus_connection import ModbusSerialParams, ModbusTcpParams, ModbusUdpParams

from custom_components.remeha_modbus.const import (
    CONF_FRAMER,
    MODBUS_DEVICE_ADDRESS,
)


def to_modbus_params(config: MappingProxyType[str, Any]) -> tuple[ModbusParams, int]:
    """Convert the given config to modbus connection parameters.

    Args:
        config (MappingProxy[str, Any]): The configuration map.

    Returns:
        A tuple of the configuration params and the modbus device address.

    """
    params: ModbusParams | None = None
    if config[CONF_TYPE] == SERIAL:
        params = ModbusSerialParams(
            device=config[CONF_PORT],
            baudrate=config.get(CONF_BAUDRATE, 9600),
            bytesize=config.get(CONF_BYTESIZE, 8),
            parity=config.get(CONF_PARITY, "N"),
            stopbits=config.get(CONF_STOPBITS, 1),
            framer=config[CONF_FRAMER],
        )
    elif config[CONF_TYPE] == TCP:
        params = ModbusTcpParams(host=config[CONF_HOST], port=config[CONF_PORT], framer="socket")
    elif config[CONF_TYPE] == UDP:
        params = ModbusUdpParams(host=config[CONF_HOST], port=config[CONF_PORT], framer="socket")
    elif config[CONF_TYPE] == RTUOVERTCP:
        params = ModbusTcpParams(host=config[CONF_HOST], port=config[CONF_PORT], framer="rtu")
    else:
        raise KeyError(config[CONF_TYPE])

    return (params, config[MODBUS_DEVICE_ADDRESS])


async def async_probe_connection(hass: HomeAssistant, data: MappingProxyType[str, Any]) -> None:
    """Verify the configured connection parameters.

    Raises:
        RemehaModbusError if the health check fails.

    """

    params, unit_id = to_modbus_params(config=MappingProxyType(data))
    async with async_get_temporary_unit(hass=hass, params=params, unit_id=unit_id) as unit:
        await RemehaApi.async_health_check(unit=unit)
