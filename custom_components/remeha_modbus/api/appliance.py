"""Implementation of appliance-scoped functionality."""

from enum import Enum
from typing import Self

from pydantic.dataclasses import dataclass


class SeasonalMode(Enum):
    """Defines the current seasonal mode of the appliance."""

    WINTER = 0

    WINTER_FROST_PROTECTION = 1

    SUMMER_NEUTRAL_BAND = 2

    SUMMER = 3


class ApplianceErrorPriority(Enum):
    """Defines the current error state of the appliance."""

    LOCKING = 0
    """This error type has the highest priority. The appliance is locked because of a physical defect or missing configuration unit, to prevent further damage."""

    BLOCKING = 3
    """This error type has high priority. The appliance is blocked because of multiple prior warnings."""

    WARNING = 6
    """This error type has medium priority. If ignored, the appliance will block the water flow to prevent damage."""

    NO_ERROR = 255
    """This error type has low priority. No action required."""


@dataclass(config={"extra": "ignore"})
class ApplianceStatus:
    """The appliance status shows various boolean status fields about the applliance."""

    flame_on: bool
    """Whether the appliance flame is on."""

    heat_pump_on: bool
    """Whether the appliance heat pump is on."""

    electrical_backup_on: bool
    """Whether the central heating electrical backup is on."""

    electrical_backup2_on: bool
    """Whether the 2nd central heating electrical backup is on."""

    dhw_electrical_backup_on: bool
    """Whether the DHW electrical backup is on."""

    service_required: bool
    """Whether the appliance requires service."""

    power_down_reset_needed: bool
    """Whether the appliance must be powered down and reset. Leave it powered off at least 20 seconds."""

    water_pressure_low: bool
    """Whether the water pressure is low."""

    appliance_pump_on: bool
    """Whether the main pump is on."""

    three_way_valve_open: bool
    """Whether the 3-way valve is open."""

    three_way_valve: bool
    """Unknown, but relate to 3-way valve obviously."""

    three_way_valve_closed: bool
    """Whether the 3-way valve is closed."""

    dhw_active: bool
    """Whether the DHW system is active."""

    ch_active: bool
    """Whether the CH system is active."""

    cooling_active: bool
    """Whether the cooling system is active."""

    @classmethod
    def from_bits(cls, bits: tuple[int, int]) -> Self:
        """Create a new ApplianceStatue instance using the given bit list.

        Args:
          bits (tuple[int, int]): The  bit values from the appliance status.

        """

        def _get_bit(index: int, value: int) -> bool:
            return (value >> index) & 1 == 1

        status: int = bits[1] << 8 | bits[0]

        return ApplianceStatus(
            flame_on=_get_bit(0, status),
            heat_pump_on=_get_bit(1, status),
            electrical_backup_on=_get_bit(2, status),
            electrical_backup2_on=_get_bit(3, status),
            dhw_electrical_backup_on=_get_bit(4, status),
            service_required=_get_bit(5, status),
            power_down_reset_needed=_get_bit(6, status),
            water_pressure_low=_get_bit(7, status),
            appliance_pump_on=_get_bit(8, status),
            three_way_valve_open=_get_bit(9, status),
            three_way_valve=_get_bit(10, status),
            three_way_valve_closed=_get_bit(11, status),
            dhw_active=_get_bit(12, status),
            ch_active=_get_bit(13, status),
            cooling_active=_get_bit(14, status),
        )


@dataclass
class Appliance:
    """Represents a Remeha appliance.

    An `Appliance` stores information about the appliance that cannot be linked to any of
    the other available api types, like appliance error status or burning hours counters.
    """

    current_error: int | None
    """The current error, encoded in two unsigned bytes. `None` means no error.

    The joined bytes show the error that can be looked up in the manual
    , e.g. `0x0207` is error `02.07`.

    """

    error_priority: ApplianceErrorPriority
    """Shows the current appliance error priority."""

    status: ApplianceStatus | None
    """Shows various status fields."""

    season_mode: SeasonalMode
    """The current seasonal mode of the appliance."""

    def error_as_str(self) -> str:
        """Return a user-friendly string representing the error."""

        prefix: str
        match self.error_priority:
            case ApplianceErrorPriority.NO_ERROR:
                return "OK"
            case ApplianceErrorPriority.WARNING:
                prefix = "A"
            case ApplianceErrorPriority.BLOCKING:
                prefix = "H"
            case ApplianceErrorPriority.LOCKING:
                prefix = "E"
            case _:
                prefix = "?"

        return (
            f"{prefix}{(self.current_error >> 8):02d}.{(self.current_error & int('00ff', 16)):02d}"
        )
