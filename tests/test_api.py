"""Tests for RemehaApi."""

import pytest

from custom_components.remeha_modbus.api import ConnectionType, RemehaApi
from custom_components.remeha_modbus.const import ZoneRegisters


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_single_variable(mock_modbus_client):
    """Test that the API can be created and a single register be read."""

    api = RemehaApi(
        name="test_api",
        connection_type=ConnectionType.RTU_OVER_TCP,
        client=mock_modbus_client,
        device_address=100,
    )

    assert await api.read_number_of_device_instances() == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_write_single_variable(mock_modbus_client):
    """Test that the API can write a single register."""

    api = RemehaApi(
        name="test_api",
        connection_type=ConnectionType.RTU_OVER_TCP,
        client=mock_modbus_client,
        device_address=100,
    )

    await api.async_write_primitive(ZoneRegisters.ROOM_MANUAL_SETPOINT, 20.5)
