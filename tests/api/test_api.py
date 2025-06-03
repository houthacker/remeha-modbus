"""Tests for RemehaApi."""

from datetime import datetime, time

import pytest

from custom_components.remeha_modbus.api import (
    Appliance,
    ApplianceErrorPriority,
    ApplianceStatus,
    ClimateZone,
    ConnectionType,
    DeviceInstance,
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.const import (
    REMEHA_SENSORS,
    ClimateZoneFunction,
    ClimateZoneHeatingMode,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    ClimateZoneType,
    DataType,
    ModbusVariableDescription,
    Weekday,
    ZoneRegisters,
)
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
    device = await api.async_read_device_instance(0)
    assert device is not None
    assert device.id == 0
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
async def test_read_sensor_values(mock_modbus_client):
    """Read values for a given list of variables that are configured as sensors."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    assert await api.async_read_sensor_values(descriptions=REMEHA_SENSORS.keys()) == dict(
        zip(
            REMEHA_SENSORS.keys(),
            [int("0223", 16), 3, 24.82, 20.44, 20.00, 21.14, 22.54, 1.2, 12.66],
            strict=True,
        )
    )


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_read_zone(mock_modbus_client):
    """Read a single zone."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone = await api.async_read_zone(id=1)

    assert zone is not None
    assert zone.current_setpoint == 20.0
    assert zone.current_temparature == 23.2
    assert zone.dhw_calorifier_hysteresis is None
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
    assert zone.selected_schedule is ClimateZoneScheduleId.SCHEDULE_1
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
    await api.async_write_variable(
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
async def test_write_variable(mock_modbus_client):
    """Test that the API can write a single register."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    await api.async_write_variable(ZoneRegisters.ROOM_MANUAL_SETPOINT, 20.5)

    # Retrieve a single zone
    zone: ClimateZone = await api.async_read_zone(1)

    # None
    await api.async_write_variable(
        variable=ZoneRegisters.CURRENT_HEATING_MODE,
        value=None,
        offset=api.get_zone_register_offset(zone),
    )

    update = await api.async_read_zone_update(zone=zone)
    assert update.heating_mode is None

    # Enum
    await api.async_write_variable(
        variable=ZoneRegisters.CURRENT_HEATING_MODE,
        value=ClimateZoneHeatingMode.HEATING,
        offset=api.get_zone_register_offset(zone),
    )

    update = await api.async_read_zone_update(zone=zone)
    assert update.heating_mode is ClimateZoneHeatingMode.HEATING

    # Try to write a datetime to a variable type which cannot handle it.
    with pytest.raises(ValueError):
        await api.async_write_variable(
            variable=ModbusVariableDescription(
                start_address=1, name="datetime_test", data_type=DataType.INT64
            ),
            value=datetime.now(),
        )


async def test_read_appliance(mock_modbus_client):
    """Test that the API can read the appliance status from the modbus device."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    appliance: Appliance = await api.async_read_appliance()

    assert appliance.current_error == int("0223", 16)  # H02.23 Flow rate error.
    assert appliance.error_priority == ApplianceErrorPriority.BLOCKING

    status: ApplianceStatus = appliance.status
    assert not status.flame_on
    assert not status.heat_pump_on
    assert not status.electrical_backup_on
    assert not status.electrical_backup2_on
    assert not status.dhw_electrical_backup_on
    assert status.service_required
    assert not status.power_down_reset_needed
    assert status.water_pressure_low
    assert status.appliance_pump_on
    assert not status.three_way_valve_open
    assert not status.three_way_valve
    assert not status.three_way_valve_closed
    assert not status.dhw_active
    assert not status.ch_active
    assert status.cooling_active


async def test_write_zone_schedule(mock_modbus_client):
    """Test that a time program can be written to the modbus device."""

    api = get_api(mock_modbus_client=mock_modbus_client)

    expected_schedule = ZoneSchedule(
        id=ClimateZoneScheduleId.SCHEDULE_2,
        zone_id=2,
        day=Weekday.FRIDAY,
        time_slots=[
            Timeslot(
                setpoint_type=TimeslotSetpointType.ECO,
                activity=TimeslotActivity.DHW,
                switch_time=time.fromisoformat("00:00"),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.COMFORT,
                activity=TimeslotActivity.DHW,
                switch_time=time.fromisoformat("10:00"),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.ECO,
                activity=TimeslotActivity.DHW,
                switch_time=time.fromisoformat("13:00"),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.COMFORT,
                activity=TimeslotActivity.DHW,
                switch_time=time.fromisoformat("18:00"),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.ECO,
                activity=TimeslotActivity.DHW,
                switch_time=time.fromisoformat("21:00"),
            ),
        ],
    )

    # Retrieve schedule from modbus, must be None.
    actual_schedule: ZoneSchedule = await api.async_read_zone_schedule(
        zone=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_2, day=Weekday.FRIDAY
    )
    assert actual_schedule is None

    # Now write the schedule
    await api.async_write_variable(
        variable=ZoneRegisters.TIME_PROGRAM_FRIDAY,
        value=expected_schedule,
        offset=api.get_zone_register_offset(zone=2)
        + api.get_schedule_register_offset(schedule=ClimateZoneScheduleId.SCHEDULE_2),
    )

    # Read it back and check if it was successful.
    actual_schedule = await api.async_read_zone_schedule(
        zone=2, schedule_id=ClimateZoneScheduleId.SCHEDULE_2, day=Weekday.FRIDAY
    )

    assert actual_schedule == expected_schedule
