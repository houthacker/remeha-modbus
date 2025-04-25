"""Implementation of time programs in the Remeha Modbus device."""

import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Self

from dateutil import relativedelta

from custom_components.remeha_modbus.const import (
    REMEHA_TIME_PROGRAM_BYTE_SIZE,
    REMEHA_TIME_PROGRAM_TIME_STEP_MINUTES,
)
from custom_components.remeha_modbus.const import (
    REMEHA_TIME_PROGRAM_SLOT_SIZE as SLOT_SIZE,
)


def _minutes_to_time(minutes_of_day: int) -> datetime.time:
    delta = relativedelta.relativedelta(minutes=minutes_of_day)
    return datetime.time(delta.hours, delta.minutes, 0)


def _time_to_minutes(tm: datetime.time) -> int:
    return tm.hour * 60 + tm.minute


class Weekday(Enum):
    """Enumeration for days of the week."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 6
    SUNDAY = 7


class TimeslotActivity(Enum):
    """The type of activity that must run during the containing TimeSlot."""

    HEAT_COOL = int("c8", 16)
    DHW = int("00", 16)


class TimeslotSetpointType(Enum):
    """The setpoint that must be reached during the containing TimeSlot.

    The names used here are the default names as shown in the Remeha Home app. In the app, these names
    can be changed.
    """

    ECO = 0
    """Reduced setpoint. For `TimeslotActivity.HEAT_COOL` this is named 'Sleeping' in the Remeha Home app. """

    COMFORT = int("10", 16)
    """Comfort setpoint. For `TimeslotActivity.HEAT_COOL` this is named 'At home' in the Remeha Home app."""

    AWAY = int("20", 16)
    """Setpoint in 'away' mode."""

    MORNING = int("30", 16)
    """Setpoint in 'morning' mode."""

    EVENING = int("40", 16)
    """Setpoint in 'evening' mode."""


@dataclass
class Timeslot:
    """A zone schedule time slot."""

    setpoint_type: TimeslotSetpointType
    """The type of setpoint for this time slot."""

    activity: TimeslotActivity
    """The type of activity for this time slot."""

    switch_time: datetime.time
    """The start time of this time slot."""

    def encode(self) -> bytes:
        """Encode this time slot into a `bytes` object."""

        time_steps: int = int(
            int(_time_to_minutes(self.switch_time)) / REMEHA_TIME_PROGRAM_TIME_STEP_MINUTES
        )

        return (
            int(self.setpoint_type.value).to_bytes()
            + int(self.activity.value).to_bytes()
            + time_steps.to_bytes()
        )

    @classmethod
    def decode(cls, encoded_time_slot: bytes) -> Self:
        """Decode a `bytes` object intoa a `Timeslot`.

        Args:
            encoded_time_slot (bytes): The encoded time slot. Must be 3 bytes.

        Raises:
            `ValueError`: If `encoded_time_slot` is not exactly 3 bytes.

        """
        # slot_bytes must be exactly 3 bytes.
        if len(encoded_time_slot) != SLOT_SIZE:
            raise ValueError(
                f"Cannod decode time program: require time slot of {SLOT_SIZE} bytes but got {len(encoded_time_slot)}."
            )

        setpoint_type = TimeslotSetpointType(int.from_bytes(encoded_time_slot[:1]))
        activity = TimeslotActivity(int.from_bytes(encoded_time_slot[1:2]))
        time_steps = int.from_bytes(encoded_time_slot[2:3])

        return Timeslot(
            activity=activity,
            setpoint_type=setpoint_type,
            switch_time=_minutes_to_time(time_steps * REMEHA_TIME_PROGRAM_TIME_STEP_MINUTES),
        )


@dataclass
class ZoneSchedule:
    """Implementation of the Remeha Modbus scheduling format.

    The GTW-08 parameter list shows that a user can choose from 3 distinct heating schedules
    for a given zone. For cooling, one schedule can be used. All schedules are divided in 7 time programs, one for each weekday.

    ### Time program encoding
    A time program is encoded in a binary string, and is 20 bytes (10 registers) in size.
    It is encoded as follows:

    | Byte index  |          Contents           | Data type |
    |:-----------:|:----------------------------|:----------|
    |    `0`      | Number of switches (max 6)  | `UINT8`   |
    |    `1`      | Temperature 1               | `UINT16`  |
    |    `3`      | Switch time 1               | `UINT8`   |
    |    `4`      | Temperature 2               | `UINT16`  |
    |    `6`      | Switch time 2               | `UINT8`   |
    |    ...      |            ...              |   ...     |
    |   `16`      | Temperature 6               | `UINT16`  |
    |   `18`      | Switch time 6               | `UINT8`   |

    #### Temperature encoding
    The switch temperature is encoded into activities (heat/cool, dhw, dhw primary).
    The setpoints of these activities are defined elswhere. The activities are defined as follows:

    | Name      | MSB     | LSB                     |
    |:----------|:-------:|------------------------:|
    | At home   | `0x10`  |    `0xc8` (heat/cool)   |
    | Morning   | `0x30`  |    `0xc8` (heat/cool)   |
    | Away      | `0x20`  |    `0xc8` (heat/cool)   |
    | Evening   | `0x40`  |    `0xc8` (heat/cool)   |
    | Sleeping  | `0x00`  |    `0xc8` (heat/cool)   |
    | Eco       | `0x00`  |    `0x00` (DHW primary) |
    | Comfort   | `0x10`  |    `0x00` (DHW primary) |


    #### Switch time encoding
    The switch time is encoded as a number, indicating the amount of 10-minute
    steps from 00:00 local time. This means that a value of 10 stands for 01:40AM.
    """

    id: int
    """The one-based id of the time program."""

    zone_id: int
    """The one-based id of the containing zone."""

    day: Weekday
    """The weekday of this program"""

    time_slots: list[Timeslot]
    """The defined time slots for this schedule."""

    def encode(self) -> bytes:
        """Encode this `ZoneSchedule` into `bytes`.

        **Note** The resulting bytes do not encode `id`, `zone_id` and `day`. These attributes are used to
        find the correct modbus register to put the schedule in.

        """

        time_slot_count: bytes = int(len(self.time_slots)).to_bytes()
        not_padded_slots: bytes = b"".join(
            [time_slot_count, *[t.encode() for t in self.time_slots]]
        )

        # Add padding null-bytes until length is REMEHA_TIME_PROGRAM_BYTE_SIZE bytes.
        return b"".join(
            [
                not_padded_slots,
                *[b"\00" for _ in range(REMEHA_TIME_PROGRAM_BYTE_SIZE - len(not_padded_slots))],
            ]
        )

    @classmethod
    def decode(cls, id: int, zone_id: int, day: Weekday, encoded_schedule: bytes) -> Self:
        """Decode a `bytes` object containing the schedule into a `ZoneSchedule`.

        Args:
            id (int): The one-based id of the schedule.
            zone_id (int): The one-based id of the `ClimateZone` containing the schedule.
            day (Weekday): The day of the week this schedule is active in.
            encoded_schedule (bytes): The binary data containing the encoded schedule. Must be exactly 20 bytes.

        Raises:
            `ValueError` if `encoded_schedule` is not exactly 20 bytes in size.

        """
        if len(encoded_schedule) != REMEHA_TIME_PROGRAM_BYTE_SIZE:
            raise ValueError(
                f"Cannot decode time program: require {REMEHA_TIME_PROGRAM_BYTE_SIZE} bytes but got {len(encoded_schedule)}."
            )

        no_of_slots: int = int.from_bytes(encoded_schedule[0:1])

        def _generate_timeslots():
            for slot_index in range(1, no_of_slots * SLOT_SIZE, SLOT_SIZE):
                slot_bytes: bytes = encoded_schedule[slot_index : slot_index + SLOT_SIZE]

                yield Timeslot.decode(encoded_time_slot=slot_bytes)

        return ZoneSchedule(id=id, zone_id=zone_id, day=day, time_slots=list(_generate_timeslots()))
