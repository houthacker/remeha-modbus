"""Tests for ClimateZone."""

import pytest
from freezegun import freeze_time

from custom_components.remeha_modbus.api import (
    DeviceBoardCategory,
    DeviceBoardType,
    DeviceInstance,
)
from custom_components.remeha_modbus.api.climate_zone import ClimateZone
from custom_components.remeha_modbus.const import (
    ClimateZoneFunction,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    ClimateZoneType,
)
from tests.conftest import get_api


def test_device_board_category():
    """Test the different textual representations of the DeviceBoardCategory.

    Required because these are shown in the front-end.
    """
    assert str(DeviceBoardCategory(type=DeviceBoardType.CU_GH, generation=2)) == "CU-GH-2"
    assert str(DeviceBoardCategory(type=DeviceBoardType.CU_OH, generation=3)) == "CU-OH-3"
    assert str(DeviceBoardCategory(type=DeviceBoardType.EHC, generation=10)) == "EHC-10"
    assert str(DeviceBoardCategory(type=DeviceBoardType.MK, generation=3)) == "MK-3"
    assert str(DeviceBoardCategory(type=DeviceBoardType.SCB, generation=17)) == "SCB-17"
    assert str(DeviceBoardCategory(type=DeviceBoardType.EEC, generation=2)) == "EEC-2"
    assert str(DeviceBoardCategory(type=DeviceBoardType.GATEWAY, generation=8)) == "GTW-8"

    # Compare to a different type
    assert DeviceBoardCategory(type=DeviceBoardType.EHC, generation=10) != DeviceBoardType.EHC


def test_device_instance_equality():
    """Test the device instance equality is based on it and board type.

    This allows HA to update device info if for instance the software version changes.
    """

    assert DeviceInstance(
        id=3,
        board_category=DeviceBoardCategory(type=DeviceBoardType.EHC, generation=10),
        sw_version=(2, 1),
        hw_version=(1, 1),
        article_number=7853960,
    ) == DeviceInstance(
        id=3,
        board_category=DeviceBoardCategory(type=DeviceBoardType.EHC, generation=8),
        sw_version=(2, 2),
        hw_version=(1, 1),
        article_number=7802607,
    )

    # Compare to a different type
    assert DeviceInstance(
        id=3,
        board_category=DeviceBoardCategory(type=DeviceBoardType.EHC, generation=10),
        sw_version=(2, 1),
        hw_version=(1, 1),
        article_number=7853960,
    ) != DeviceBoardCategory(type=DeviceBoardType.EHC, generation=10)


def test_supported_climate_zone_functions():
    """Prevent regressions in the supported climate zone functions."""

    assert not ClimateZoneFunction.DISABLED.is_supported()
    assert not ClimateZoneFunction.DIRECT.is_supported()
    assert not ClimateZoneFunction.SWIMMING_POOL.is_supported()
    assert not ClimateZoneFunction.HIGH_TEMPERATURE.is_supported()
    # TODO supported FAN_CONVECTOR
    assert not ClimateZoneFunction.FAN_CONVECTOR.is_supported()
    assert not ClimateZoneFunction.DHW_TANK.is_supported()
    assert not ClimateZoneFunction.ELECTRICAL_DHW_TANK.is_supported()
    assert not ClimateZoneFunction.TIME_PROGRAM.is_supported()
    assert not ClimateZoneFunction.PROCESS_HEAT.is_supported()
    assert not ClimateZoneFunction.DHW_LAYERED.is_supported()
    assert not ClimateZoneFunction.DHW_LAYERED.is_supported()
    assert not ClimateZoneFunction.DHW_COMMERCIAL_TANK.is_supported()

    assert ClimateZoneFunction.MIXING_CIRCUIT.is_supported()
    assert ClimateZoneFunction.DHW_PRIMARY.is_supported()


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climate_zone_dhw_get_current_setpoint(mock_modbus_client):
    """Test retrieval of the current setpoint of a climate zone."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone | None = await api.async_read_zone(
        id=2, appliance=await api.async_read_appliance()
    )
    assert zone is not None

    assert zone.is_domestic_hot_water()

    # Prepare setpoint values
    zone.dhw_comfort_setpoint = 55
    zone.dhw_reduced_setpoint = 25

    # Validate setpoint in SCHEDULING mode
    zone.mode = ClimateZoneMode.SCHEDULING
    assert zone.current_setpoint != -1

    # Validate setpoint in MANUAL mode
    zone.mode = ClimateZoneMode.MANUAL
    assert zone.current_setpoint == 55

    # Validate setpoint in ANTI_FROST mode
    zone.mode = ClimateZoneMode.ANTI_FROST
    assert zone.current_setpoint == 25

    # Validate setpoint in unsupported type
    zone.type = ClimateZoneType.SWIMMING_POOL
    assert zone.current_setpoint == -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store_ch_scheduling.json"], indirect=True)
async def test_climate_zone_ch_get_current_cooling_setpoint(mock_modbus_client):
    """Test retrieval of the current setpoint of a CH climate zone."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone | None = await api.async_read_zone(
        id=1, appliance=await api.async_read_appliance()
    )
    assert zone is not None

    assert not zone.is_domestic_hot_water()
    assert zone.is_central_heating()

    # Remeha uses schedule 4 for cooling, but doesn't expose it as selected.
    # instead, schedule 1 is selected. RemehaApi maps this to schedule 4.
    assert zone.selected_schedule is ClimateZoneScheduleId.SCHEDULE_4

    # Validate the schedule for a monday (all days have the same schedule in the mock data)
    # Mock data is encoded as follows:
    # 00:00 - 07:00 SLEEP
    # 07:00 - 15:00 AWAY
    # 15:00 - 18:00 HOME
    # 18:00 - 21:00 COMFORT
    # 21:00 - 00:00 EVENING
    with freeze_time("2026-06-01 00:00:00", tz_offset=-2):
        assert zone.current_setpoint == 20.5

    with freeze_time("2026-06-01 07:00:00", tz_offset=-2):
        assert zone.current_setpoint == 21.5

    with freeze_time("2026-06-01 15:00:00", tz_offset=-2):
        assert zone.current_setpoint == 21.0

    with freeze_time("2026-06-01 18:00:00", tz_offset=-2):
        assert zone.current_setpoint == 20.0

    with freeze_time("2026-06-01 21:00:00", tz_offset=-2):
        assert zone.current_setpoint == 22.0


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climate_zone_set_current_setpoint(mock_modbus_client):
    """Test setting the current setpoint of a DHW zone."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone | None = await api.async_read_zone(
        id=2, appliance=await api.async_read_appliance()
    )
    assert zone is not None

    # Prepare setpoint values
    zone.room_setpoint = -1
    zone.dhw_comfort_setpoint = -1
    zone.dhw_reduced_setpoint = -1
    zone.temporary_setpoint = -1

    # Validate setpoint for CH zone in MANUAL mode
    zone.mode = ClimateZoneMode.MANUAL
    zone.type = ClimateZoneType.OTHER
    zone.function = ClimateZoneFunction.MIXING_CIRCUIT

    zone.current_setpoint = 20.5
    assert zone.current_setpoint == 20.5
    assert zone.room_setpoint == 20.5
    assert zone.dhw_comfort_setpoint == -1
    assert zone.dhw_reduced_setpoint == -1
    assert zone.temporary_setpoint == -1

    zone.room_setpoint = -1

    # Validate setpoint for DHW zone in MANUAL mode
    zone.type = ClimateZoneType.OTHER
    zone.function = ClimateZoneFunction.DHW_PRIMARY
    zone.mode = ClimateZoneMode.MANUAL

    zone.current_setpoint = 50
    assert zone.current_setpoint == 50
    assert zone.dhw_comfort_setpoint == 50
    assert zone.dhw_reduced_setpoint == -1
    assert zone.room_setpoint == -1
    assert zone.temporary_setpoint == -1

    zone.dhw_comfort_setpoint = -1

    # Validate setpoint for DHW zone in SCHEDULING mode
    zone.mode = ClimateZoneMode.SCHEDULING

    zone.current_setpoint = 50
    assert zone.current_setpoint == -1
    assert zone.dhw_comfort_setpoint == -1
    assert zone.dhw_reduced_setpoint == -1
    assert zone.room_setpoint == -1
    assert zone.temporary_setpoint == 50

    zone.temporary_setpoint = -1

    # Validate setpoint for DHW zone in ANTI_FROST mode
    zone.mode = ClimateZoneMode.ANTI_FROST

    zone.current_setpoint = 25
    assert zone.current_setpoint == 25
    assert zone.dhw_comfort_setpoint == -1
    assert zone.dhw_reduced_setpoint == 25
    assert zone.room_setpoint == -1
    assert zone.temporary_setpoint == -1

    zone.dhw_reduced_setpoint = -1

    # Validate setpoint outside of min/max values
    zone.current_setpoint = 25
    assert zone.current_setpoint == 25

    # Try to update
    zone.current_setpoint = zone.min_temp - 1.0
    assert zone.current_setpoint == 25

    zone.current_setpoint = zone.max_temp + 1.0
    assert zone.current_setpoint == 25

    # Validate setting setpoint for unsupported zone
    zone.type = ClimateZoneType.SWIMMING_POOL
    zone.current_setpoint = 30
    assert zone.current_setpoint == -1  # Unsupported zones report -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climate_zone_get_current_temperature(mock_modbus_client):
    """Test the retrieval of the current temperature of a climate zone."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone | None = await api.async_read_zone(
        id=2, appliance=await api.async_read_appliance()
    )
    assert zone is not None

    assert zone.is_domestic_hot_water()
    assert zone.current_temparature == 53.2

    zone.type = ClimateZoneType.SWIMMING_POOL
    assert zone.current_temparature == -1


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store.json"], indirect=True)
async def test_climate_zone_equality(mock_modbus_client):
    """Test the equality of climate zones."""

    api = get_api(mock_modbus_client=mock_modbus_client)
    zones: list[ClimateZone] = await api.async_read_zones(await api.async_read_appliance())

    assert zones[0] != zones[1]
    assert zones[1] != ClimateZoneMode.MANUAL
    assert zones[0] == zones[0]
    assert zones[1] == zones[1]


@pytest.mark.parametrize("mock_modbus_client", ["modbus_store_ch_scheduling.json"], indirect=True)
async def test_scheduling_temporary_setpoint(mock_modbus_client):
    """Test that a temporary setpoint can be set if the zone is in scheduling mode."""

    # Retrieve a single zone.
    api = get_api(mock_modbus_client=mock_modbus_client)
    zone: ClimateZone | None = await api.async_read_zone(1, await api.async_read_appliance())
    assert zone is not None
    assert zone.selected_schedule == ClimateZoneScheduleId.SCHEDULE_4

    # Override the setpoint
    assert zone.current_setpoint is not None
    current_setpoint: float = zone.current_setpoint
    temporary_setpoint = current_setpoint + 1

    zone.current_setpoint = temporary_setpoint

    # Temporary override for CH zones not yet implemented.
    assert zone.current_setpoint != temporary_setpoint
