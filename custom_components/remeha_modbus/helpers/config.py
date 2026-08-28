"""Helpers for configuration.

The voluptuous helpers are those that don't exist in HA.
"""

from typing import Any

from aio_remeha_modbus.api.config import (
    Configuration,
    SerialConfiguration,
    TcpConfiguration,
    UdpConfiguration,
)
from aio_remeha_modbus.api.const import ConnectionType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TIMEOUT, CONF_TYPE
from homeassistant.exceptions import ConfigEntryError
from pydantic import TypeAdapter

from custom_components.remeha_modbus.const import (
    DOMAIN,
    ISSUE_CONFIG_ENTRY_CONNECTION_TYPE,
    ISSUE_CONFIG_ENTRY_KEY_ERROR,
    MODBUS_DEVICE_ADDRESS,
    MODBUS_SERIAL_BAUDRATE,
    MODBUS_SERIAL_BYTESIZE,
    MODBUS_SERIAL_PARITY,
    MODBUS_SERIAL_STOPBITS,
)


def _to_api_dict(entry: ConfigEntry) -> dict[str, Any]:
    d = {
        "connection_type": entry.data[CONF_TYPE],
        "device_address": entry.data[MODBUS_DEVICE_ADDRESS],
        CONF_PORT: entry.data[CONF_PORT],
    }

    match ConnectionType(entry.data[CONF_TYPE]):
        case ConnectionType.SERIAL:
            d = d | {
                "framer": entry.data["framer"],
            }

            for key in [
                MODBUS_SERIAL_BAUDRATE,
                MODBUS_SERIAL_BYTESIZE,
                MODBUS_SERIAL_PARITY,
                MODBUS_SERIAL_STOPBITS,
            ]:
                if key in entry.data:
                    d[key] = entry.data[key]
        case ConnectionType.TCP | ConnectionType.UDP:
            d["framer"] = "socket"
            d[CONF_HOST] = entry.data[CONF_HOST]

            if CONF_TIMEOUT in entry.data:
                d[CONF_TIMEOUT] = entry.data[CONF_TIMEOUT]
        case ConnectionType.RTU_OVER_TCP:
            d["framer"] = "rtu"
            d[CONF_HOST] = entry.data[CONF_HOST]

            if CONF_TIMEOUT in entry.data:
                d[CONF_TIMEOUT] = entry.data[CONF_TIMEOUT]

    return d


def to_api_configration(entry: ConfigEntry) -> Configuration:
    """Create a `Configuration` instance based on a `ConfigEntry`.

    Args:
        entry (ConfigEntry): The HA configuration entry.

    Returns:
        Configuration: The API configuration instance.

    Raises:
        ConfigEntryError: If the configuration is invalid.

    """

    connection_type = entry.data[CONF_TYPE]
    if connection_type not in ConnectionType:
        connection_types: str = ", ".join(e.value for e in ConnectionType)
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key=ISSUE_CONFIG_ENTRY_CONNECTION_TYPE,
            translation_placeholders={
                "connection_type": connection_type,
                "connection_types": connection_types,
            },
        )

    try:
        api_dict = _to_api_dict(entry)
        match ConnectionType(connection_type):
            case ConnectionType.SERIAL:
                return TypeAdapter(SerialConfiguration).validate_python(api_dict)
            case ConnectionType.TCP | ConnectionType.RTU_OVER_TCP:
                return TypeAdapter(TcpConfiguration).validate_python(api_dict)
            case ConnectionType.UDP:
                return TypeAdapter(UdpConfiguration).validate_python(api_dict)
    except KeyError as e:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key=ISSUE_CONFIG_ENTRY_KEY_ERROR,
            translation_placeholders={"key": str(e)},
        ) from e
