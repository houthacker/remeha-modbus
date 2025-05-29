"""Implementation of time programs in the Remeha Modbus device."""

import datetime
import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Self, cast

from dateutil import parser, relativedelta
from homeassistant.const import UnitOfTemperature

from custom_components.remeha_modbus.const import (
    AUTO_SCHEDULE_MINIMAL_END_HOUR,
    BOILER_MAX_ALLOWED_HEAT_DURATION,
    DOMAIN,
    MAXIMUM_NORMAL_SURFACE_IRRADIANCE_NL,
    PV_EFFICIENCY_TABLE,
    PV_MAX_TILT_DEGREES,
    REMEHA_TIME_PROGRAM_BYTE_SIZE,
    REMEHA_TIME_PROGRAM_TIME_STEP_MINUTES,
    WATER_SPECIFIC_HEAT_CAPACITY_KJ,
    BoilerConfiguration,
    BoilerEnergyLabel,
    ClimateZoneScheduleId,
    ForecastField,
    PVSystem,
    Weekday,
)
from custom_components.remeha_modbus.const import REMEHA_TIME_PROGRAM_SLOT_SIZE as SLOT_SIZE
from custom_components.remeha_modbus.errors import AutoSchedulingError
from custom_components.remeha_modbus.helpers.iterators import consecutive_groups

from .appliance import SeasonalMode


class ClimateZone:
    """Forward declaration."""


_LOGGER = logging.getLogger(__name__)


def _minutes_to_time(minutes_of_day: int) -> datetime.time:
    delta = relativedelta.relativedelta(minutes=minutes_of_day)
    return datetime.time(delta.hours, delta.minutes, 0)


def _time_to_minutes(tm: datetime.time) -> int:
    return tm.hour * 60 + tm.minute


def _energy_label_to_heat_loss_rate(label: BoilerEnergyLabel, volume: float) -> float:
    v_pow_04: float = math.pow(volume, 0.4)
    match label:
        case BoilerEnergyLabel.A_PLUS | BoilerEnergyLabel.A:
            return ((5.5 + 3.6 * v_pow_04) + (8.5 + 4.25 * v_pow_04)) * 0.5
        case BoilerEnergyLabel.B:
            return ((8.5 + 4.25 * v_pow_04) + (12 + 5.93 * v_pow_04)) * 0.5
        case BoilerEnergyLabel.C:
            return ((12 + 5.93 * v_pow_04) + (16.66 + 8.33 * v_pow_04)) * 0.5
        case BoilerEnergyLabel.D:
            return ((16.66 + 8.33 * v_pow_04) + (21 + 10.33 * v_pow_04)) * 0.5
        case _:
            return ((21 + 10.33 * v_pow_04) + (26 + 13.66 * v_pow_04)) * 0.5


@dataclass(frozen=True)
class HourlyForecast:
    """An hourly weather forecast entry."""

    start_time: datetime.datetime
    """The start time of the forecast."""

    temperature: float
    """The temperature in `temperature_unit`.

    At temperatures above 25 °C, the PV panel efficiency decreases with 4 percent every 10 degrees.
    """

    solar_irradiance: int | None
    """The global horizontal irradiance, in W/m2."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create a new `HourlyForecast` based on a dict containing weather forecast attributes."""

        return HourlyForecast(
            start_time=parser.parse(data[ForecastField.DATETIME]),
            temperature=float(data[ForecastField.TEMPERATURE]),
            solar_irradiance=int(data[ForecastField.SOLAR_IRRADIANCE])
            if ForecastField.SOLAR_IRRADIANCE in data
            else None,
        )


@dataclass(frozen=True)
class WeatherForecast:
    """A forecasted weather condition containing the necessary attributes to calculate a schedule."""

    unit_of_temperature: UnitOfTemperature
    """The unit of temperature used in the forecast entries."""

    forecasts: list[HourlyForecast]
    """A list containing the hourly forecasts for the next 24 hours."""


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
            int(self.activity.value).to_bytes()
            + int(self.setpoint_type.value).to_bytes()
            + time_steps.to_bytes()
        )

    def __lt__(self, other) -> bool:
        """Compare this `Timeslot` to another."""
        if isinstance(other, Timeslot):
            o: Timeslot = cast(Timeslot, other)
            return self.switch_time < o.switch_time

        return False

    def __str__(self):
        """Return a human-readable representation of this time slot."""
        return f"Timeslot(setpoint_type={self.setpoint_type.name}, activity={self.activity.name}, switch_time={self.switch_time})"

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

        time_steps = int.from_bytes(encoded_time_slot[2:3])
        setpoint_type = TimeslotSetpointType(int.from_bytes(encoded_time_slot[1:2]))
        activity = TimeslotActivity(int.from_bytes(encoded_time_slot[:1]))

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

    id: ClimateZoneScheduleId
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
    def decode(
        cls, id: ClimateZoneScheduleId, zone_id: int, day: Weekday, encoded_schedule: bytes
    ) -> Self:
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

    @classmethod
    def generate(
        cls,
        weather_forecast: WeatherForecast,
        pv_system: PVSystem,
        boiler_config: BoilerConfiguration,
        boiler_zone: ClimateZone,
        appliance_seasonal_mode: SeasonalMode,
    ) -> Self:
        """Generate a `ZoneSchedule` for the next day, based on the weather forecast.

        ### Notes
        - The id of the generated `ZoneSchedule` is always `3`.

        Args:
            weather_forecast (WeatherForecast): The weather forecast for the next 24 hours.
            pv_system (PVSystem): The PV system configuration.
            boiler_config (BoilerConfiguration): The DHW boiler configuration.
            boiler_zone (ClimateZone): The DHW climate zone.
            appliance_seasonal_mode (SeasonalMode): The current seasonal mode of the appliance.

        Returns:
            The generated `ZoneSchedule`.

        """
        _LOGGER.info("Generating ZoneSchedule for tomorrow...")

        if not weather_forecast.forecasts:
            raise AutoSchedulingError(
                translation_domain=DOMAIN, translation_key="auto_schedule_no_forecasts"
            )

        # We want to generate a planning for the next whole day, which must, to be useful,
        # end no earlier than 22:00.
        last_forecast: HourlyForecast = weather_forecast.forecasts[-1]
        if last_forecast.start_time.hour < AUTO_SCHEDULE_MINIMAL_END_HOUR:
            raise AutoSchedulingError(
                translation_domain=DOMAIN,
                translation_key="auto_schedule_forecast_not_enough_hours",
                translation_placeholders={
                    "max_forecast_time": f"{last_forecast.start_time.hour}:00",
                    "min_required_end_time": f"{AUTO_SCHEDULE_MINIMAL_END_HOUR}:00",
                },
            )

        # Calculate the amount of kWh required to heat to boiler to its setpoint, once
        # it reaches the heating threshold, round to two decimals.
        # This value is what we're looking for in the time blocks that we can use to schedule.
        default_required_heating_kwh: float = (
            math.ceil(
                (
                    (
                        boiler_config.volume
                        * WATER_SPECIFIC_HEAT_CAPACITY_KJ
                        * boiler_zone.dhw_calorifier_hysteresis
                    )
                    / 3600
                )
                * 100
            )
            / 100
        )
        _LOGGER.debug(
            "Default kWh required to heat DHW boiler from setpoint - hysteresis = %.2f",
            default_required_heating_kwh,
        )

        # Calculate the amount of kWh required to heat the boiler if it were to cool overnight,
        # from now until tomorrow 08.00.
        cooling_time_hours: int = int(
            (
                datetime.datetime.combine(
                    datetime.date.today() + datetime.timedelta(days=1), datetime.time(hour=8)
                )
                - datetime.datetime.now()
            ).total_seconds()
            / 3600
        )
        heat_loss_rate: float = (
            boiler_config.heat_loss_rate
            if boiler_config.heat_loss_rate
            else _energy_label_to_heat_loss_rate(
                label=boiler_config.energy_label, volume=boiler_config.volume
            )
        )

        # Emit a warning if the required energy to heat it up again in the morning is too large.
        required_heating_kwh_after_cooling: float = (heat_loss_rate * cooling_time_hours) / 1000
        if required_heating_kwh_after_cooling > default_required_heating_kwh:
            # TODO log a warning in the system log so the user can see it
            _LOGGER.warning(
                "DHW boiler is likely going to heat up at night, outside of planning schedule."
            )

        # In the summer, only allow DHW heating in the morning and the afternoon.
        # In the winter, only allow DHW heating when it's warmest.
        #
        # This prevents heating at night when there's no solar power, and also when
        # central heating or cooling should have priority.
        usable_hours = (
            [range(10, 23)]
            if appliance_seasonal_mode in [SeasonalMode.SUMMER_NEUTRAL_BAND, SeasonalMode.SUMMER]
            else [range(10, 17)]
        )

        # Calculate static PV system efficiency, based on orientation and tilt.
        # The tilt is rounded up to the next smallest multiple of ten.
        static_pv_efficiency: float = PV_EFFICIENCY_TABLE[pv_system.orientation][
            min(math.ceil(pv_system.tilt / 10) * 10, PV_MAX_TILT_DEGREES)
        ]
        _LOGGER.debug("Static PV efficiency is %.2f", static_pv_efficiency)

        # Calculate dynamic PV system efficiency, using efficiency decrease of its age.
        pv_efficiency: float = static_pv_efficiency
        if pv_system.annual_efficiency_decrease != 0.0:
            system_runtime: datetime.timedelta = datetime.date.today() - pv_system.installation_date
            decreased_percent: float = (
                system_runtime.days / 365
            ) * pv_system.annual_efficiency_decrease
            pv_efficiency *= (100 - decreased_percent) / 100
            _LOGGER.debug(
                "PV efficiency is %.2f after applying annual efficiency decrease", pv_efficiency
            )

        # This results in a forecasted yield in kWh for all of the 24 hrs
        forecasted_kwh_yield: dict[int, int] = {
            fc.start_time.hour: int(
                (
                    (fc.solar_irradiance / MAXIMUM_NORMAL_SURFACE_IRRADIANCE_NL)
                    * pv_system.nominal_power
                    * pv_efficiency
                )
                / 1000.0
            )
            for fc in weather_forecast.forecasts
            if fc.start_time.hour in [hour for r in usable_hours for hour in r]
        }

        # Generate rolling blocks of BOILER_MAX_ALLOWED_HEAT_DURATION hours which yield
        # enough kWh to heat the boiler up to its setpoint.
        def _generate_acceptable_hour_blocks():
            usable_hours_list = [hour for r in usable_hours for hour in r]
            for idx, _ in enumerate(usable_hours_list):
                hours_subset: list[int] = (
                    usable_hours_list[idx : idx + BOILER_MAX_ALLOWED_HEAT_DURATION]
                    if len(usable_hours_list) >= idx + BOILER_MAX_ALLOWED_HEAT_DURATION
                    else usable_hours_list[idx:]
                )

                # Calculate the total yield in kwh for the 3-hour block
                total_yield: int = sum([forecasted_kwh_yield.get(h, 0) for h in hours_subset])

                if total_yield >= default_required_heating_kwh:
                    # Only yield the subset if it is a closed range
                    yield (
                        hours_subset
                        if hours_subset[-1] - hours_subset[0] + 1 == len(hours_subset)
                        else []
                    )

        # Take two timeslots, allowing for both morning- and afternoon heating.
        acceptable_hour_blocks: list[list[int]] = list(_generate_acceptable_hour_blocks())
        accepted_hour_blocks: list[list[int]] = (
            [acceptable_hour_blocks[0]]
            if len(acceptable_hour_blocks) == 1
            else [acceptable_hour_blocks[0], acceptable_hour_blocks[-1]]
        )

        # The remaining hours are unaccepted.
        unaccepted_hour_blocks: list[list[int]] = [
            list(group)
            for group in consecutive_groups(
                [
                    h
                    for h in range(24)
                    if h not in {hour for r in accepted_hour_blocks for hour in r}
                ]
            )
        ]

        # Generate the timeslots using the accepted hours yielding enough kWh.
        def _generate_timeslots():
            unaccepted_timeslots: list[Timeslot] = [
                Timeslot(
                    setpoint_type=TimeslotSetpointType.ECO,
                    activity=TimeslotActivity.DHW,
                    switch_time=datetime.time(hour=block[0]),
                )
                for block in unaccepted_hour_blocks
            ]

            accepted_timeslots: list[Timeslot] = [
                Timeslot(
                    setpoint_type=TimeslotSetpointType.COMFORT,
                    activity=TimeslotActivity.DHW,
                    switch_time=datetime.time(hour=block[0]),
                )
                for block in accepted_hour_blocks
            ]

            all_timeslots: list[Timeslot] = [*unaccepted_timeslots, *accepted_timeslots]
            all_timeslots.sort()

            yield from all_timeslots

        schedule: ZoneSchedule = ZoneSchedule(
            id=ClimateZoneScheduleId.SCHEDULE_3,
            zone_id=boiler_zone.id,
            # When presented with old data (like in testing), the week day returned here is
            # probably not the actual current week day
            day=Weekday(weather_forecast.forecasts[-1].start_time.weekday()),
            time_slots=list(_generate_timeslots()),
        )

        _LOGGER.debug("Generated schedule:\n%s\n", str(schedule))

        return schedule

    def __str__(self):
        """Return a human-readable representation of this schedule."""
        return f"ZoneSchedule(id={self.id}, zone_id={self.zone_id}, day={self.day.name}, time_slots={self.time_slots})"


def get_current_timeslot(
    schedule: dict[Weekday, ZoneSchedule] | None, time_zone: datetime.tzinfo | None
) -> Timeslot | None:
    """Retrieve the current schedule time slot.

    Args:
        schedule (dict[Weekday, ZoneSchedule]): The selected schedule
        time_zone (datetime.tzinfo): The appliance time zone

    Returns:
        The current schedule time slot, or `None` if `schedule` is `None`.

    """

    if schedule is None:
        return None

    now: datetime.datetime = datetime.datetime.now(time_zone)
    day_schedule: ZoneSchedule | None = schedule.get(Weekday(now.weekday()), None)

    return (
        next(
            reversed(
                [
                    time_slot
                    for time_slot in day_schedule.time_slots
                    if time_slot.switch_time.hour < now.hour
                ]
            ),
            None,
        )
        if day_schedule
        else None
    )
