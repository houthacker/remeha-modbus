"""Tests for time schedules."""

from datetime import time

from custom_components.remeha_modbus.api.schedule import (
    Timeslot,
    TimeslotActivity,
    TimeslotSetpointType,
    Weekday,
    ZoneSchedule,
)


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
