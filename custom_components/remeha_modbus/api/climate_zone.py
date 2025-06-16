"""Implementation of climate zones within the Remeha Modbus integration."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic.dataclasses import dataclass

from custom_components.remeha_modbus.const import (
    ClimateZoneFunction,
    ClimateZoneHeatingMode,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    ClimateZoneType,
    Limits,
    Weekday,
)

from .schedule import Timeslot, TimeslotSetpointType, ZoneSchedule, get_current_timeslot

_LOGGER = logging.getLogger(__name__)


@dataclass(eq=False)
class ClimateZone:
    """Defines a climate zone following the GTW-08 parameter list.

    In the GTW-08 parameter list, a climate zone contains all fields for all zone types.
    The API must stay as close as possible to the original mapping and therefore a
    `ClimateZone` does not differentiate between zone types.
    However, the entities created from `ClimateZone` instances have distinct types for all supported zone types.
    """

    id: int
    """The one-based climate zone id"""

    type: ClimateZoneType
    """The type of climate zone"""

    function: ClimateZoneFunction
    """The climate zone function"""

    short_name: str
    """The climate zone short name"""

    owning_device: int | None
    """The id of the device owning the zone."""

    mode: ClimateZoneMode
    """The current mode the zone is in"""

    selected_schedule: ClimateZoneScheduleId | None
    """The currently selected schedule.

    Although this property is optional, it needn't be `None` if `mode != ClimateZoneMode.SCHEDULING`.
    """

    current_schedule: dict[Weekday, ZoneSchedule | None]
    """If `selected_schedule` has a value, `current_schedule` contains the schedule for all week days."""

    heating_mode: ClimateZoneHeatingMode | None
    """The current heating mode of the climate zone"""

    temporary_setpoint: float | None
    """Temporary room setpoint override. Only available when mode is SCHEDULING."""

    room_setpoint: float | None
    """The current room temperature setpoint"""

    dhw_comfort_setpoint: float | None
    """The setpoint for DHW in comfort mode"""

    dhw_reduced_setpoint: float | None
    """The setpoint for DHW in reduced (eco) mode"""

    dhw_calorifier_hysteresis: float | None
    """Hysteresis to start DHW tank load"""

    temporary_setpoint_end_time: datetime | None
    """End time of temporary setpoint override"""

    room_temperature: float | None
    """The current room temperature"""

    dhw_tank_temperature: float | None
    """The current DHW tank temperature"""

    pump_running: bool
    """Whether the zone pump is currently running"""

    time_zone: ZoneInfo | None
    """The time zone of the related appliance"""

    def _current_dhw_scheduling_setpoint(self) -> float:
        if self.temporary_setpoint_end_time is not None:
            if (
                self.temporary_setpoint_end_time is not None
                and self.temporary_setpoint_end_time >= datetime.now(tz=self.time_zone)
            ):
                # A setpoint override is currently active.
                return self.temporary_setpoint

        current_timeslot: Timeslot | None = get_current_timeslot(
            schedule=self.current_schedule, time_zone=self.time_zone
        )
        if current_timeslot:
            match current_timeslot.setpoint_type:
                case TimeslotSetpointType.ECO:
                    return self.dhw_reduced_setpoint
                case TimeslotSetpointType.COMFORT:
                    return self.dhw_comfort_setpoint

        return -1

    @property
    def current_setpoint(self) -> float | None:
        """Return the current setpoint of this zone.

        The actual returned setpoint field depends on the type of zone and
        the current zone mode.

        Returns:
            `float`: The current zone setpoint, or `-1` if zone type or mode does not support a current setpoint.

        """

        if self.is_central_heating():
            match self.mode:
                case ClimateZoneMode.SCHEDULING:
                    # TODO get setpoint from schedule
                    _LOGGER.warning(
                        "Current setpoint not supported for CH zones in SCHEDULING mode."
                    )
                    return -1
                case ClimateZoneMode.MANUAL:
                    return self.room_setpoint
                case ClimateZoneMode.ANTI_FROST:
                    return self.min_temp
        if self.is_domestic_hot_water():
            match self.mode:
                case ClimateZoneMode.SCHEDULING:
                    return self._current_dhw_scheduling_setpoint()
                case ClimateZoneMode.MANUAL:
                    return self.dhw_comfort_setpoint
                case ClimateZoneMode.ANTI_FROST:
                    return self.dhw_reduced_setpoint

        _LOGGER.warning("Current setpoint not supported for climate zones of type %s", self.type)
        return -1

    @current_setpoint.setter
    def current_setpoint(self, value: float):
        """Set the current setpoint of this zone."""

        # Check requested setpoint against min/max
        if value < self.min_temp or value > self.max_temp:
            _LOGGER.warning(
                "Ignoring requested setpoint of %0.2f since it is outside allowed range (%0.2f, %0.2f)",
                value,
                self.min_temp,
                self.max_temp,
            )
            return

        if self.is_central_heating():
            match self.mode:
                case ClimateZoneMode.SCHEDULING:
                    # Ignore, user must adjust schedule.
                    # TODO implement temporary setpoint override
                    _LOGGER.warning(
                        "Not setting CH climate temporary setpoint, adjust schedule to do this."
                    )
                case ClimateZoneMode.MANUAL:
                    self.room_setpoint = value
                case _:
                    pass

        elif self.is_domestic_hot_water():
            match self.mode:
                case ClimateZoneMode.SCHEDULING:
                    # The required end time is set by the HA climate entity.
                    self.temporary_setpoint = value
                case ClimateZoneMode.MANUAL:
                    self.dhw_comfort_setpoint = value
                case ClimateZoneMode.ANTI_FROST:
                    self.dhw_reduced_setpoint = value
        else:
            _LOGGER.warning(
                "Setting setpoint not supported for climate zones of type %s", self.type
            )

    @property
    def current_temparature(self) -> float:
        """Return the current temperature of this zone.

        The actual returned temperature field depends on the type of zone.
        """

        if self.is_central_heating():
            return self.room_temperature

        if self.is_domestic_hot_water():
            return self.dhw_tank_temperature

        _LOGGER.warning("Current temperature not supported for climate zones of type %s", self.type)
        return -1

    @property
    def max_temp(self) -> float:
        """The highest allowed setpoint for this zone.

        The maximum temperature differs per zone type:
        * For DHW (Domestinc Hot Water) it's 65 degrees C
        * For CH (Central Heating) or mixing circuits it's 30 degrees C
        * For all others it's the lowest value of the above.
            This is to ensure unknown zone types won't get a flow temperature they can't handle.
        """

        if self.is_central_heating():
            return Limits.CH_MAX_TEMP

        if self.is_domestic_hot_water():
            return Limits.DHW_MAX_TEMP

        return min(Limits.CH_MAX_TEMP, Limits.DHW_MAX_TEMP)

    @property
    def min_temp(self) -> float:
        """The lowest allowed setpoint for this zone.

        The minimum temperature differs per zone type:
        * For DHW (Domestinc Hot Water) it's 6 degrees C
        * For CH (Central Heating) or mixing circuits it's 10 degrees C
        * For all others it's the highest value of the above.
            This is to ensure unknown zone types won't get a flow temperature they can't handle.
        """

        if self.is_central_heating():
            return Limits.CH_MIN_TEMP

        if self.is_domestic_hot_water():
            return Limits.DHW_MIN_TEMP

        return max(Limits.CH_MIN_TEMP, Limits.DHW_MIN_TEMP)

    def is_central_heating(self) -> bool:
        """Determine if this zone is a CH (central heating) zone."""

        return self.type in [
            ClimateZoneType.CH_ONLY,
            ClimateZoneType.CH_AND_COOLING,
        ] or (
            self.type == ClimateZoneType.OTHER
            and self.function == ClimateZoneFunction.MIXING_CIRCUIT
        )

    def is_domestic_hot_water(self) -> bool:
        """Determine if this zone is a DHW (domestic hot water) zone."""

        return self.type == ClimateZoneType.DHW or (
            self.type == ClimateZoneType.OTHER
            and self.function
            in [
                ClimateZoneFunction.DHW_BIC,
                ClimateZoneFunction.DHW_COMMERCIAL_TANK,
                ClimateZoneFunction.DHW_LAYERED,
                ClimateZoneFunction.DHW_PRIMARY,
                ClimateZoneFunction.DHW_TANK,
                ClimateZoneFunction.ELECTRICAL_DHW_TANK,
            ]
        )

    def __eq__(self, other) -> bool:
        """Compare this `ClimateZone` with another for equality.

        For equality, only the properties `id`, `type` and `function` are considered.

        Returns:
            `bool`: `True` if the objects are considered equal, `False` otherwise.

        """
        if isinstance(other, self.__class__):
            return (
                self.id == other.id and self.type == other.type and self.function == other.function
            )

        return False
