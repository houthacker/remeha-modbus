"""Fixtures for testing."""

import uuid
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonObjectType
from pymodbus.client import ModbusBaseClient
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    load_json_object_fixture,
)

from custom_components.remeha_modbus.api import ConnectionType, RemehaApi
from custom_components.remeha_modbus.const import (
    CONNECTION_RTU_OVER_TCP,
    DOMAIN,
    MODBUS_DEVICE_ADDRESS,
)


def get_api(
    mock_modbus_client: ModbusBaseClient,
    name: str = "test_api",
    device_address: int = 100,
) -> RemehaApi:
    """Create a new RemehaApi instance with a mocked modbus client."""

    # mock_modbus_client MUST be a mock, otherwise a real connection might be made and mess up the appliance.
    if not isinstance(mock_modbus_client, Mock):
        pytest.fail(
            f"Trying to create RemehaApi with non-mock type {type(mock_modbus_client).__qualname__}."
        )

    return RemehaApi(
        name=name,
        connection_type=ConnectionType.RTU_OVER_TCP,
        client=mock_modbus_client,
        device_address=device_address,
    )


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "custom_components.remeha_modbus.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_modbus_client(request) -> AsyncMock:
    """Create a mocked pymodbus client.

    The registers for the modbus client are retrieved from the `request` and will be
    looked up using `load_json_object_fixture`. See `fixtures/modbus_store.json` as an example.
    """

    with (
        patch("pymodbus.client.AsyncModbusTcpClient", autospec=True) as mock,
        patch(
            "pymodbus.pdu.register_message.ReadHoldingRegistersResponse", autospec=True
        ) as read_pdu,
        patch(
            "pymodbus.pdu.register_message.WriteMultipleRegistersRequest", autospec=True
        ) as write_pdu,
    ):
        store: JsonObjectType = load_json_object_fixture(request.param)

        def get_registers(address: int, count: int) -> list[int]:
            return [
                int(store["server"]["registers"][str(r)], 16)
                for r in range(address, address + count)
            ]

        async def get_from_store(address: int, count: int, **kwargs):
            read_pdu.side_effect = AsyncMock()
            read_pdu.isError = Mock(return_value=False)
            read_pdu.registers = get_registers(address, count)
            read_pdu.dev_id = 100

            return read_pdu

        async def close():
            return AsyncMock()

        async def write_to_store(address: int, values: list[int], **kwargs):
            for idx, r in enumerate(values):
                store["server"]["registers"][str(address + idx)] = (
                    int(r).to_bytes(2).hex()
                )

            write_pdu.side_effect = AsyncMock()
            write_pdu.isError = Mock(return_value=False)
            write_pdu.dev_id = 100

            return write_pdu

        mock.connected = MagicMock(return_value=True)
        mock.read_holding_registers.side_effect = get_from_store
        mock.write_registers = write_to_store
        mock.close = close

        return mock


async def setup_platform(hass: HomeAssistant):
    """Set up the platform."""

    config_entry = create_config_entry()
    config_entry.add_to_hass(hass=hass)

    # We don't want lingering timers after the tests are done, so disable the updates of the update coordinator.
    with patch(
        "custom_components.remeha_modbus.coordinator.RemehaUpdateCoordinator.update_interval",
        0,
    ):
        await hass.config_entries.async_setup(entry_id=config_entry.entry_id)
        await hass.async_block_till_done()


def create_config_entry(
    hub_name: str = "test_hub", device_address: int = 100
) -> MockConfigEntry:
    """Mock a config entry for Remeha Modbus integration."""

    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Remeha Modbus {hub_name}",
        unique_id=str(uuid.uuid4()),
        data={
            CONF_NAME: hub_name,
            CONF_TYPE: CONNECTION_RTU_OVER_TCP,
            MODBUS_DEVICE_ADDRESS: device_address,
            CONF_HOST: "does.not.matter",
            CONF_PORT: 8899,
        },
        version=0,
        minor_version=1,
    )
