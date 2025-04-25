"""Test the Remeha Modbus config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from custom_components.remeha_modbus.const import (
    CONNECTION_RTU_OVER_TCP,
    CONNECTION_SERIAL,
    CONNECTION_TCP,
    DOMAIN,
    MODBUS_DEVICE_ADDRESS,
    MODBUS_SERIAL_BAUDRATE,
    MODBUS_SERIAL_BYTESIZE,
    MODBUS_SERIAL_METHOD,
    MODBUS_SERIAL_METHOD_RTU,
    MODBUS_SERIAL_PARITY,
    MODBUS_SERIAL_PARITY_NONE,
    MODBUS_SERIAL_STOPBITS,
)
from tests.conftest import get_api, setup_platform


async def test_generic_config_invalid_data(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that invalid configuration data raises an exception."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with pytest.raises(InvalidData):
        # Fill in the form correctly
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "test_serial_modbus_hub",
                CONF_TYPE: CONNECTION_SERIAL,
                MODBUS_DEVICE_ADDRESS: "not-a-number",
            },
        )

    await hass.async_block_till_done()


async def test_config_modbus_serial(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test for modbus serial configuration setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Fill in the form correctly
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "test_serial_modbus_hub", CONF_TYPE: CONNECTION_SERIAL},
    )
    await hass.async_block_till_done()

    # We should have been presented with the 2nd form, to fill in the
    # serial connection details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            MODBUS_SERIAL_BAUDRATE: 9600,
            MODBUS_SERIAL_BYTESIZE: 8,
            MODBUS_SERIAL_METHOD: MODBUS_SERIAL_METHOD_RTU,
            MODBUS_SERIAL_PARITY: MODBUS_SERIAL_PARITY_NONE,
            CONF_PORT: "/dev/ttyUSB0",
            MODBUS_SERIAL_STOPBITS: 2,
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Remeha Modbus"
    assert result["data"] == {
        CONF_NAME: "test_serial_modbus_hub",
        CONF_TYPE: CONNECTION_SERIAL,
        MODBUS_DEVICE_ADDRESS: 100,
        MODBUS_SERIAL_BAUDRATE: 9600,
        MODBUS_SERIAL_BYTESIZE: 8,
        MODBUS_SERIAL_METHOD: MODBUS_SERIAL_METHOD_RTU,
        MODBUS_SERIAL_PARITY: MODBUS_SERIAL_PARITY_NONE,
        CONF_PORT: "/dev/ttyUSB0",
        MODBUS_SERIAL_STOPBITS: 2,
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_config_modbus_socket(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test for modbus serial configuration setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    # Fill in the form with a socket modbus connection type.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "test_socket_modbus_hub", CONF_TYPE: CONNECTION_RTU_OVER_TCP},
    )
    await hass.async_block_till_done()

    # We should have been presented with the 2nd form, to fill in the
    # socket connection details.
    assert result["type"] is FlowResultType.FORM

    # Fill in the details, check the result.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.1", CONF_PORT: 502}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Remeha Modbus"
    assert result["data"] == {
        CONF_NAME: "test_socket_modbus_hub",
        CONF_TYPE: CONNECTION_RTU_OVER_TCP,
        MODBUS_DEVICE_ADDRESS: 100,
        CONF_HOST: "192.168.1.1",
        CONF_PORT: 502,
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_reconfigure_non_unique_id(hass: HomeAssistant, mock_modbus_client) -> None:
    """Test that reconfiguring the modbus connection fails if the hub name is changed as well."""
    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda name, config: api,
    ):
        # First setup the platform with the mocked ConfigEntry
        await setup_platform(hass=hass)
        await hass.async_block_till_done()

        states = hass.states.async_all()
        assert len(states) == 2

        entries = hass.config_entries.async_entries(domain=DOMAIN)
        assert len(entries) == 1

        config_entry: ConfigEntry = entries[0]

        # Then update the connection to another connection type.
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_TYPE: CONNECTION_TCP}
        )
        await hass.async_block_till_done()

        # We should have been presented with the 2nd form, to fill in the
        # socket connection details.
        assert result["type"] is FlowResultType.FORM

        # Fill in the details, check the result.
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_HOST: "also.does.not.matter", CONF_PORT: 502}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.ABORT

        entries = hass.config_entries.async_entries(domain=DOMAIN)

        # No extra entries must be added
        assert len(entries) == 1

        # But the fields must be updated.
        config_entry = entries[0]
        assert config_entry.data == {
            CONF_NAME: "test_hub",
            CONF_TYPE: CONNECTION_TCP,
            MODBUS_DEVICE_ADDRESS: 100,
            CONF_HOST: "also.does.not.matter",
            CONF_PORT: 502,
        }
