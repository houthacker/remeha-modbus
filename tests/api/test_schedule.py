"""Tests for time schedules."""

from datetime import date, time
from unittest.mock import patch

import pytest
from homeassistant.const import UnitOfTemperature

from custom_components.remeha_modbus.api import HourlyForecast, WeatherForecast
from custom_components.remeha_modbus.api.schedule import (
    ClimateZoneScheduleId,
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    ZoneSchedule,
)
from custom_components.remeha_modbus.const import (
    BoilerConfiguration,
    BoilerEnergyLabel,
    PVSystem,
    PVSystemOrientation,
    Weekday,
)
from tests.conftest import get_api


def test_decode_time_schedule():
    """Test decoding a binary schedule."""

    encoded_schedule: bytes = bytes.fromhex("05 10c8 24 30c8 2a 20c8 36 40c8 60 00c8 87 0000 0000")
    schedule = ZoneSchedule.decode(
        id=2, zone_id=1, day=Weekday.MONDAY, encoded_schedule=encoded_schedule
    )

    assert schedule.id == 2
    assert schedule.zone_id == 1
    assert schedule.day == Weekday.MONDAY
    assert schedule.time_slots == [
        Timeslot(
            setpoint_type=TimeslotSetpointType.COMFORT,
            activity=TimeslotActivity.HEAT_COOL,
            switch_time=time(6, 0, 0),
        ),
        Timeslot(
            setpoint_type=TimeslotSetpointType.MORNING,
            activity=TimeslotActivity.HEAT_COOL,
            switch_time=time(7, 0, 0),
        ),
        Timeslot(
            setpoint_type=TimeslotSetpointType.AWAY,
            activity=TimeslotActivity.HEAT_COOL,
            switch_time=time(9, 0, 0),
        ),
        Timeslot(
            setpoint_type=TimeslotSetpointType.EVENING,
            activity=TimeslotActivity.HEAT_COOL,
            switch_time=time(16, 0, 0),
        ),
        Timeslot(
            setpoint_type=TimeslotSetpointType.ECO,
            activity=TimeslotActivity.HEAT_COOL,
            switch_time=time(22, 30, 0),
        ),
    ]


def test_encode_time_schedule():
    """Test encoding a binary schedule."""

    expected: bytes = bytes.fromhex("05 10c8 24 30c8 2a 20c8 36 40c8 60 00c8 87 0000 0000")
    schedule: ZoneSchedule = ZoneSchedule(
        id=2,
        zone_id=1,
        day=Weekday.MONDAY,
        time_slots=[
            Timeslot(
                setpoint_type=TimeslotSetpointType.COMFORT,
                activity=TimeslotActivity.HEAT_COOL,
                switch_time=time(6, 0, 0),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.MORNING,
                activity=TimeslotActivity.HEAT_COOL,
                switch_time=time(7, 0, 0),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.AWAY,
                activity=TimeslotActivity.HEAT_COOL,
                switch_time=time(9, 0, 0),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.EVENING,
                activity=TimeslotActivity.HEAT_COOL,
                switch_time=time(16, 0, 0),
            ),
            Timeslot(
                setpoint_type=TimeslotSetpointType.ECO,
                activity=TimeslotActivity.HEAT_COOL,
                switch_time=time(22, 30, 0),
            ),
        ],
    )

    assert schedule.encode() == expected


@pytest.mark.parametrize("json_fixture", ["weather_forecast.json"], indirect=True)
async def test_generate_dhw_time_schedule(json_fixture, mock_modbus_client):
    """Test generating a time schedule for heating the DHW boiler."""

    weather_forecast: WeatherForecast = WeatherForecast(
        unit_of_temperature=UnitOfTemperature.CELSIUS,
        forecasts=[HourlyForecast.from_dict(native_forecast) for native_forecast in json_fixture],
    )

    pv_system: PVSystem = PVSystem(
        nominal_power=5720,
        orientation=PVSystemOrientation.SOUTH,
        annual_efficiency_decrease=0.42,
        installation_date=date.today(),
        tilt=30.0,
    )

    boiler_config: BoilerConfiguration = BoilerConfiguration(
        volume=300, heat_loss_rate=None, energy_label=BoilerEnergyLabel.C
    )

    api = get_api(mock_modbus_client=mock_modbus_client)
    with patch(
        "custom_components.remeha_modbus.api.RemehaApi.create",
        new=lambda *args, **kwargs: api,
    ):
        appliance = await api.async_read_appliance()
        zone = await api.async_read_zone(id=2)
        schedule: ZoneSchedule = ZoneSchedule.generate(
            weather_forecast=weather_forecast,
            pv_system=pv_system,
            boiler_config=boiler_config,
            boiler_zone=zone,
            appliance_seasonal_mode=appliance.season_mode,
        )

        assert schedule == ZoneSchedule(
            id=ClimateZoneScheduleId.SCHEDULE_3,
            zone_id=zone.id,
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
