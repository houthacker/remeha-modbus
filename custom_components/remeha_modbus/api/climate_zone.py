"""Implementation of climate zones within the Remeha Modbus integration."""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from custom_components.remeha_modbus.const import Limits

_LOGGER = logging.getLogger(__name__)


class ClimateZoneType(Enum):
    """Enumerates the available zone types."""

    NOT_PRESENT = 0
    CH_ONLY = 1
    CH_AND_COOLING = 2
    DHW = 3
    PROCESS_HEAT = 4
    SWIMMING_POOL = 5
    OTHER = 254


class ClimateZoneFunction(Enum):
    """Enumerates the available zone functions."""

    DISABLED = 0
    DIRECT = 1
    MIXING_CIRCUIT = 2
    SWIMMING_POOL = 3
    HIGH_TEMPERATURE = 4
    FAN_CONVECTOR = 5
    DHW_TANK = 6
    ELECTRICAL_DHW_TANK = 7
    TIME_PROGRAM = 8
    PROCESS_HEAT = 9
    DHW_LAYERED = 10
    DHW_BIC = 11
    DHW_COMMERCIAL_TANK = 12
    DHW_PRIMARY = 254

    def is_supported(self) -> bool:
        """Return whether this `ClimateZoneFunction` is currently supported within this integration."""
        return self in [
            ClimateZoneFunction.MIXING_CIRCUIT,
            ClimateZoneFunction.DHW_PRIMARY,
        ]


class ClimateZoneMode(Enum):
    """Enumerates the modes a zone can be in."""

    SCHEDULING = 0
    MANUAL = 1
    ANTI_FROST = 2


class ClimateZoneScheduleId(Enum):
    """The climate zone time program selected by the user.

    Note: After updating the enum values, **ALWAYS** update the mapping to _attr_preset_modes of RemehaModbusClimateEntity!
    """

    SCHEDULE_1 = 0
    SCHEDULE_2 = 1
    SCHEDULE_3 = 2


class ClimateZoneHeatingMode(Enum):
    """The mode the zone is currently functioning in."""

    STANDBY = 0
    HEATING = 1
    COOLING = 2


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

    heating_mode: ClimateZoneHeatingMode
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

    dhw_tank_temperature: float | None
    """The current DHW tank temperature"""

    @property
    def current_setpoint(self) -> float | None:
        """Return the current setpoint of this zone.

        The actual returned setpoint field depends on the type of zone and
        the current zone mode.

        Returns:
            `float`: The current zone setpoint, or `-1` zone type or mode does not support a current setpoint.

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
                    # TODO get setpoint from schedule
                    _LOGGER.warning(
                        "Current setpoint not supported for DHW zones in SCHEDULING mode."
                    )
                    return -1
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
                    _LOGGER.warning("Ignoring requested DHW setpoint, adjust schedule to do this.")
                case ClimateZoneMode.MANUAL:
                    self.room_setpoint = value

        elif self.is_domestic_hot_water():
            match self.mode:
                case ClimateZoneMode.SCHEDULING:
                    # Ignore, user must adjust schedule.
                    # TODO implement temporary setpoint override
                    _LOGGER.warning("Ignoring requested DHW setpoint, adjust schedule to do this.")
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
