"""Fixtures for testing."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.util.json import JsonObjectType
from pymodbus.client import ModbusBaseClient
from pytest_homeassistant_custom_component.common import load_json_object_fixture

from custom_components.remeha_modbus.api import ConnectionType, RemehaApi


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

        async def write_to_store(address: int, values: list[int], **kwargs):
            for idx, r in enumerate(values):
                store["server"]["registers"][str(address + idx)] = (
                    int(r).to_bytes(2).hex()
                )

            write_pdu.side_effect = AsyncMock()
            write_pdu.isError = Mock(return_value=False)
            write_pdu.dev_id = 100

            return write_pdu

        mock.read_holding_registers.side_effect = get_from_store
        mock.write_registers = write_to_store

        return mock
