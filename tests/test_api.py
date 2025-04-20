"""Tests for RemehaApi."""

import pytest

from custom_components.remeha_modbus.api import DeviceInstance
from custom_components.remeha_modbus.const import ZoneRegisters

from .conftest import get_api


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_single_variable(mock_modbus_client):
    """Test that the API can be created and a single register be read."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    assert await api.read_number_of_device_instances() == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_device_instance(mock_modbus_client):
    """Test that a device can be read through the modbus interface."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    device = await api.read_device_instance(1)
    assert device is not None
    assert device.id == 1
    assert device.hw_version == (2, 1)
    assert device.sw_version == (1, 1)
    assert str(device.board_category) == "EHC-10"
    assert device.article_number == 7853960


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_device_instances(mock_modbus_client):
    """Read all devices through the modbus interface."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    devices: list[DeviceInstance] = await api.read_device_instances()

    assert len(devices) == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_write_single_variable(mock_modbus_client):
    """Test that the API can write a single register."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    await api.async_write_primitive(ZoneRegisters.ROOM_MANUAL_SETPOINT, 20.5)
