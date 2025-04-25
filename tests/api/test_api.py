"""Tests for RemehaApi."""

import pytest

from custom_components.remeha_modbus.api import (
    ClimateZone,
    ClimateZoneFunction,
    ClimateZoneHeatingMode,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    ClimateZoneType,
    ConnectionType,
    DeviceInstance,
)
from custom_components.remeha_modbus.const import ZoneRegisters
from tests.conftest import get_api


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_api_properties(mock_modbus_client):
    """Test the modbus hub name."""

    api = get_api(mock_modbus_client=mock_modbus_client, name="remeha_modbus_hub")
    assert api.name == "remeha_modbus_hub"
    assert api.connection_type == ConnectionType.RTU_OVER_TCP
    assert await api.async_is_connected  # Always True for mocked api


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_api_connection(mock_modbus_client):
    """Test connecting to the modbus device."""

    api = get_api(mock_modbus_client=mock_modbus_client, name="remeha_modbus_hub")
    try:
        assert await api.async_connect()
    finally:
        await api.async_close()


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_single_variable(mock_modbus_client):
    """Test that the API can be created and a single register be read."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    assert await api.async_read_number_of_device_instances() == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_device_instance(mock_modbus_client):
    """Test that a device can be read through the modbus interface."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    device = await api.async_read_device_instance(1)
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
    devices: list[DeviceInstance] = await api.async_read_device_instances()

    assert len(devices) == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_zone(mock_modbus_client):
    """Read a single zone."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone = await api.async_read_zone(id=1)

    assert zone is not None
    assert zone.current_setpoint == 20.0
    assert zone.current_temparature == 23.2
    assert zone.dhw_calorifier_hysterisis is None
    assert zone.dhw_comfort_setpoint is None
    assert zone.dhw_reduced_setpoint is None
    assert zone.dhw_tank_temperature is None
    assert zone.function == ClimateZoneFunction.MIXING_CIRCUIT
    assert zone.heating_mode == ClimateZoneHeatingMode.COOLING
    assert zone.id == 1
    assert zone.mode == ClimateZoneMode.MANUAL
    assert zone.owning_device == 1
    assert zone.pump_running is True
    assert zone.room_setpoint == 20.0
    assert zone.room_temperature == 23.2
    assert zone.selected_schedule == ClimateZoneScheduleId.SCHEDULE_1
    assert zone.short_name == "CIRCA1"
    assert zone.type == ClimateZoneType.OTHER

    assert zone.is_central_heating() is True
    assert zone.is_domestic_hot_water() is False


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_not_present_zone(mock_modbus_client):
    """Read a zone that is of ZoneType.NOT_PRESENT."""
    api = get_api(mock_modbus_client=mock_modbus_client)

    assert await api.async_read_zone(id=3) is None


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_zone_update(mock_modbus_client):
    """Read a zone update from the modbus device."""

    api = get_api(mock_modbus_client=mock_modbus_client)

    # Read a single zone
    zone: ClimateZone = await api.async_read_zone(1)
    assert zone.is_central_heating()
    assert zone.mode == ClimateZoneMode.MANUAL

    # Update a variable directly at the modbus interface
    new_setpoint: float = zone.current_setpoint + 2
    await api.async_write_primitive(
        variable=ZoneRegisters.ROOM_MANUAL_SETPOINT,
        value=new_setpoint,
        offset=api.get_zone_register_offset(zone=zone),
    )

    # Retrieve the updated value
    updated_zone: ClimateZone = await api.async_read_zone_update(zone)

    # Zone identity must be equal to the original zone
    assert updated_zone == zone

    # Validate updated setpoint
    assert updated_zone.current_setpoint == new_setpoint


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_health_check(mock_modbus_client):
    """Test a health check can be run without raising an exception."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    await api.async_health_check()


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_zones(mock_modbus_client):
    """Read all zones through the modbus interface."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zones: list[ClimateZone] = await api.async_read_zones()

    assert len(zones) == 2


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_write_primitive(mock_modbus_client):
    """Test that the API can write a single register."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    await api.async_write_primitive(ZoneRegisters.ROOM_MANUAL_SETPOINT, 20.5)


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_write_enum(mock_modbus_client):
    """Test that the API can write an enum value to the modbus device."""

    # Retrieve a single zone.
    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone = await api.async_read_zone(1)

    # None
    await api.async_write_enum(
        variable=ZoneRegisters.CURRENT_HEATING_MODE,
        value=None,
        offset=api.get_zone_register_offset(zone),
    )

    update = await api.async_read_zone_update(zone=zone)
    assert update.heating_mode is None

    # non-enum
    with pytest.raises(
        expected_exception=TypeError,
        match=f"Expect value to be an Enum or None, but got {int.__name__}",
    ):
        await api.async_write_enum(
            variable=ZoneRegisters.CURRENT_HEATING_MODE,
            value=42,
            offset=api.get_zone_register_offset(zone),
        )

    # Enum
    await api.async_write_enum(
        variable=ZoneRegisters.CURRENT_HEATING_MODE,
        value=ClimateZoneHeatingMode.HEATING,
        offset=api.get_zone_register_offset(zone),
    )

    update = await api.async_read_zone_update(zone=zone)
    assert update.heating_mode is ClimateZoneHeatingMode.HEATING
