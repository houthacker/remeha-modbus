"""Constants for the Remeha Modbus integration."""

from datetime import date
from enum import Enum, StrEnum
from typing import Final, Self

import voluptuous as vol
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.helpers import config_validation as cv
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

from custom_components.remeha_modbus.helpers import config_validation as remeha_cv

DOMAIN: Final[str] = "remeha_modbus"

# Versioning for the config flow.
HA_CONFIG_VERSION = 1
HA_CONFIG_MINOR_VERSION = 2

MAXIMUM_NORMAL_SURFACE_IRRADIANCE_NL: Final[int] = 1000
"""The maximum normal surface irradiance in The Netherlands, in W/m²"""

WATER_SPECIFIC_HEAT_CAPACITY_KJ: Final[float] = 4.18
"""The amount of energy required to warm 1 kilogram of water by one degree K"""

AUTO_SCHEDULE_MINIMAL_END_HOUR: Final[int] = 21
"""The minimal latest hour required to create a useful auto schedule.

This means that if a schedule is planned before this hour, it cannot succeed
because then no full day can be planned ahead.
"""

BOILER_MAX_ALLOWED_HEAT_DURATION: Final[int] = 3
"""The maximum amount of hours the boiler will get to heat up.

If the central heating- the heat pump unit can modulate, this
is the estimated amount of time required since that is most
energy-efficient. When the unit is unable to modulate, this time
is much shorter, but it will cost more energy.
"""


PV_MIN_TILT_DEGREES: Final[int] = 10
"""The minimum supported PV system tilt"""

PV_MAX_TILT_DEGREES: Final[int] = 90
"""The maximum supported PV system tilt"""


# DHW auto scheduling
class ForecastField(StrEnum):
    """Describe the weather forecast action response field names that are relevant for this integration."""

    DATETIME = "datetime"
    CONDITION = "condition"
    TEMPERATURE = "temperature"
    PRECIPITATION = "precipitation"
    SOLAR_IRRADIANCE = "solar_irradiance"
    """Solar irradiance is not a field that's available by default"""


class PVSystemOrientation(StrEnum):
    """Describe the PV system orientations."""

    EAST_WEST = "EW"
    """East/West evenly distributes total PV power over east and west."""
    NORTH = "N"
    NORTH_NORTH_EAST = "NNE"
    NORTH_EAST = "NE"
    EAST_NORTH_EAST = "ENE"
    EAST = "E"
    EAST_SOUTH_EAST = "ESE"
    SOUTH_EAST = "SE"
    SOUTH_SOUTH_EAST = "SSE"
    SOUTH = "S"
    SOUTH_SOUTH_WEST = "SSW"
    SOUTH_WEST = "SW"
    WEST_SOUTH_WEST = "WSW"
    WEST = "W"
    WEST_NORTH_WEST = "WNW"
    NORTH_WEST = "NW"
    NORTH_NORTH_WEST = "NNW"


PV_EFFICIENCY_TABLE = {
    PVSystemOrientation.NORTH: {
        10: 0.77,
        20: 0.68,
        30: 0.59,
        40: 0.50,
        50: 0.40,
        60: 0.35,
        70: 0.30,
        80: 0.25,
        90: 0.20,
    },
    PVSystemOrientation.NORTH_NORTH_EAST: {
        10: 0.78,
        20: 0.70,
        30: 0.59,
        40: 0.50,
        50: 0.45,
        60: 0.39,
        70: 0.35,
        80: 0.30,
        90: 0.25,
    },
    PVSystemOrientation.NORTH_EAST: {
        10: 0.79,
        20: 0.73,
        30: 0.65,
        40: 0.59,
        50: 0.53,
        60: 0.46,
        70: 0.42,
        80: 0.38,
        90: 0.35,
    },
    PVSystemOrientation.EAST_NORTH_EAST: {
        10: 0.83,
        20: 0.78,
        30: 0.73,
        40: 0.68,
        50: 0.62,
        60: 0.57,
        70: 0.52,
        80: 0.46,
        90: 0.42,
    },
    PVSystemOrientation.EAST: {
        10: 0.85,
        20: 0.82,
        30: 0.80,
        40: 0.76,
        50: 0.72,
        60: 0.67,
        70: 0.62,
        80: 0.55,
        90: 0.50,
    },
    PVSystemOrientation.EAST_SOUTH_EAST: {
        10: 0.87,
        20: 0.87,
        30: 0.86,
        40: 0.85,
        50: 0.81,
        60: 0.76,
        70: 0.71,
        80: 0.65,
        90: 0.58,
    },
    PVSystemOrientation.SOUTH_EAST: {
        10: 0.90,
        20: 0.92,
        30: 0.93,
        40: 0.92,
        50: 0.87,
        60: 0.84,
        70: 0.78,
        80: 0.71,
        90: 0.62,
    },
    PVSystemOrientation.SOUTH_SOUTH_EAST: {
        10: 0.91,
        20: 0.94,
        30: 0.96,
        40: 0.95,
        50: 0.92,
        60: 0.88,
        70: 0.82,
        80: 0.75,
        90: 0.65,
    },
    PVSystemOrientation.SOUTH: {
        10: 0.91,
        20: 0.95,
        30: 0.97,
        40: 0.96,
        50: 0.94,
        60: 0.90,
        70: 0.84,
        80: 0.75,
        90: 0.65,
    },
    PVSystemOrientation.SOUTH_SOUTH_WEST: {
        10: 0.91,
        20: 0.95,
        30: 0.96,
        40: 0.95,
        50: 0.92,
        60: 0.87,
        70: 0.82,
        80: 0.74,
        90: 0.68,
    },
    PVSystemOrientation.SOUTH_WEST: {
        10: 0.90,
        20: 0.92,
        30: 0.93,
        40: 0.92,
        50: 0.87,
        60: 0.84,
        70: 0.78,
        80: 0.70,
        90: 0.63,
    },
    PVSystemOrientation.WEST_SOUTH_WEST: {
        10: 0.87,
        20: 0.87,
        30: 0.87,
        40: 0.85,
        50: 0.81,
        60: 0.76,
        70: 0.71,
        80: 0.64,
        90: 0.57,
    },
    PVSystemOrientation.WEST: {
        10: 0.85,
        20: 0.82,
        30: 0.80,
        40: 0.76,
        50: 0.72,
        60: 0.68,
        70: 0.62,
        80: 0.55,
        90: 0.49,
    },
    PVSystemOrientation.WEST_NORTH_WEST: {
        10: 0.82,
        20: 0.77,
        30: 0.71,
        40: 0.68,
        50: 0.62,
        60: 0.57,
        70: 0.52,
        80: 0.46,
        90: 0.42,
    },
    PVSystemOrientation.NORTH_WEST: {
        10: 0.79,
        20: 0.72,
        30: 0.65,
        40: 0.59,
        50: 0.52,
        60: 0.47,
        70: 0.43,
        80: 0.38,
        90: 0.34,
    },
    PVSystemOrientation.NORTH_NORTH_WEST: {
        10: 0.78,
        20: 0.69,
        30: 0.60,
        40: 0.51,
        50: 0.44,
        60: 0.39,
        70: 0.35,
        80: 0.30,
        90: 0.26,
    },
}


class BoilerEnergyLabel(StrEnum):
    """Energy label for DHW boiler.

    The energy label is used to provide an alternative method of calculating heat loss rate.
    See also https://www.energielabel.nl/apparaten/boiler-en-geiser (Dutch)
    """

    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


@dataclass(frozen=True)
class PVSystem:
    """Parameters that describe a PV system."""

    nominal_power: Final[int]
    """The total Wp of the system."""

    orientation: Final[PVSystemOrientation]
    """The direction the PV system faces."""

    tilt: Final[float | None]
    """The tilt of the PV system, in degrees."""

    annual_efficiency_decrease: Final[float | None]
    """The annual decrease of efficiency, in percent."""

    installation_date: Final[date | None]
    """The installation date """


@dataclass(frozen=True)
class BoilerConfiguration:
    """The configuration of a DHW boiler."""

    volume: Final[float | None]
    """The volume of the boiler in m³"""

    heat_loss_rate: Final[float | None]
    """The heat loss rate in Watt"""

    energy_label: Final[BoilerEnergyLabel | None]
    """The boiler energy label, if the heat loss rate is not available."""


class Weekday(Enum):
    """Enumeration for days of the week."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 6
    SUNDAY = 7


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


CONFIG_AUTO_SCHEDULE: Final[str] = "auto_schedule"

READ_REGISTERS_SERVICE_NAME: Final[str] = "read_registers"
READ_REGISTERS_START_REGISTER: Final[str] = "start_register"
READ_REGISTERS_REGISTER_COUNT: Final[str] = "register_count"
READ_REGISTERS_STRUCT_FORMAT: Final[str] = "struct_format"

READ_REGISTERS_SERVICE_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(READ_REGISTERS_START_REGISTER): cv.positive_int,
        vol.Required(READ_REGISTERS_REGISTER_COUNT, default=1): cv.positive_int,
        vol.Required(READ_REGISTERS_STRUCT_FORMAT, default="=H"): remeha_cv.struct_format,
    }
)

# Keep in sync with services.yaml service name.
AUTO_SCHEDULE_SERVICE_NAME: Final[str] = "dhw_auto_schedule"

AUTO_SCHEDULE_DEFAULT_ID: Final[ClimateZoneScheduleId] = ClimateZoneScheduleId.SCHEDULE_1
"""The default schedule id for auto scheduling."""

WEATHER_ENTITY_ID: Final[str] = "weather_entity_id"
"""Config key for the Weather entity to retrieve the forecast of."""

AUTO_SCHEDULE_SELECTED_SCHEDULE: Final[str] = "selected_schedule"
"""The id of the schedule to use for auto scheduling."""

# PV system parameters
PV_CONFIG_SECTION: Final[str] = "pv_options"
PV_NOMINAL_POWER_WP: Final[str] = "nominal_power_wp"
PV_ORIENTATION: Final[str] = "orientation"
PV_TILT: Final[str] = "tilt"
PV_ANNUAL_EFFICIENCY_DECREASE: Final[str] = "annual_efficiency_decrease"
PV_INSTALLATION_DATE: Final[str] = "pv_installation_date"

# DHW boiler parameters
DHW_BOILER_CONFIG_SECTION: Final[str] = "dhw_boiler_options"
DHW_BOILER_VOLUME: Final[str] = "dhw_boiler_volume"
DHW_BOILER_HEAT_LOSS_RATE: Final[str] = "dhw_heat_loss_rate"
DHW_BOILER_ENERGY_LABEL: Final[str] = "dhw_boiler_energy_label"

# Modbus connection types
CONNECTION_TCP: Final[str] = "tcp"
CONNECTION_UDP: Final[str] = "udp"
CONNECTION_RTU_OVER_TCP: Final[str] = "rtuovertcp"
CONNECTION_SERIAL: Final[str] = "serial"

# Modbus slave number
MODBUS_DEVICE_ADDRESS: Final[str] = "slave"

# Modbus serial configuration fields
MODBUS_SERIAL_BAUDRATE: Final[str] = "baudrate"
MODBUS_SERIAL_BYTESIZE: Final[str] = "bytesize"
MODBUS_SERIAL_METHOD: Final[str] = "method"
MODBUS_SERIAL_PARITY: Final[str] = "parity"
MODBUS_SERIAL_STOPBITS: Final[str] = "stopbits"

# Modbus serial method types
MODBUS_SERIAL_METHOD_RTU: Final[str] = "rtu"
MODBUS_SERIAL_METHOD_ASCII: Final[str] = "ascii"

# Modbus parity bytes
MODBUS_SERIAL_PARITY_EVEN: Final[str] = "E"
MODBUS_SERIAL_PARITY_ODD: Final[str] = "O"
MODBUS_SERIAL_PARITY_NONE: Final[str] = "N"

# Modbus common struct formats
MODBUS_UINT8: Final[str] = "=xB"
MODBUS_ENUM8: Final[str] = "=xB"
MODBUS_DEVICE_CATEGORY: Final[str] = "=BB"
MODBUS_UINT16_BYTES: Final[str] = "=BB"
MODBUS_TIME_PROGRAM: Final[str] = "=BHBHBHBHBHBHBx"

# The supported step size the setpoint can be increased or decreased
TEMPERATURE_STEP: float = 0.5

# The default presets that are available on all climate zones
REMEHA_PRESET_SCHEDULE_1: Final[str] = "schedule_1"
REMEHA_PRESET_SCHEDULE_2: Final[str] = "schedule_2"
REMEHA_PRESET_SCHEDULE_3: Final[str] = "schedule_3"
HA_PRESET_MANUAL: Final[str] = "manual"
HA_PRESET_ANTI_FROST: Final[str] = "anti_frost"
CLIMATE_DEFAULT_PRESETS: Final[list[str]] = [
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
]

# Additional presets available on DHW zones
CLIMATE_DHW_EXTRA_PRESETS: Final[list[str]] = [PRESET_COMFORT, PRESET_ECO, PRESET_NONE]

HA_SCHEDULE_TO_REMEHA_SCHEDULE: Final[dict[str, ClimateZoneScheduleId]] = {
    REMEHA_PRESET_SCHEDULE_1: ClimateZoneScheduleId.SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2: ClimateZoneScheduleId.SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3: ClimateZoneScheduleId.SCHEDULE_3,
}


class DataType(StrEnum):
    """Data types for GTW-08 modbus.

    #### Notes
    The HA modbus component also provides a `DataType` enum, but it has a deprecated
    `UINT8` variant, which is used extensively by the GTW-08 parameter list.
    Not providing an `UINT8` variant would require a more generic approach
    while reading/writing registers, that is more complex than adding a new
    variant and handling it specifically.
    """

    UINT8 = "uint8"
    """A single byte, read from a 2-byte register with struct format of `xB`.
    Also used for ENUM8"""

    INT16 = "int16"
    INT32 = "int32"
    INT64 = "int64"
    UINT16 = "uint16"
    UINT32 = "uint32"
    UINT64 = "uint64"
    FLOAT32 = "float32"
    FLOAT64 = "float64"
    STRING = "string"
    CIA_301_TIME_OF_DAY = "cia301_time_of_day"
    """A time of day, encoded as defined in the CAN301 par 9.1.6.4, 'Time of Day'."""

    TUPLE16 = "tuple16"
    """A `tuple[int, int]` read from a single register."""

    ZONE_TIME_PROGRAM = "zone_time_program"
    """A zone time program for a single day, encoded in bytes as defined in the GTW-08 parameter list."""


@dataclass(frozen=True)
class Limits(float, Enum):
    """Forced limits users must not exceed."""

    CH_MIN_TEMP = 6.0
    """Central heating minimum temperature."""

    CH_MAX_TEMP = 30.0
    """Central heating maximum temperature."""

    DHW_MIN_TEMP = 10.0
    """Domestic hot water minimum temperature."""

    DHW_MAX_TEMP = 65.0
    """Domestic hot water maximum temperature."""

    DHW_SCHEDULING_SETPOINT_OVERRIDE_DURATION = 2
    """The duration in hours of a temporary setpoint override in DHW scheduling."""

    HYSTERESIS_MIN_TEMP = 0.0
    """The minimum required hysteresis."""

    HYSTERESIS_MAX_TEMP = 40.0
    """The maximum allowed hysteresis."""


# Base register information for zones, device info, time schedules
REMEHA_ZONE_RESERVED_REGISTERS: Final[int] = 512
REMEHA_DEVICE_INSTANCE_RESERVED_REGISTERS: Final[int] = 6
REMEHA_TIME_PROGRAM_RESERVED_REGISTERS: Final[int] = 70
REMEHA_TIME_PROGRAM_BYTE_SIZE: Final[int] = 20
REMEHA_TIME_PROGRAM_SLOT_SIZE: Final[int] = 3
REMEHA_TIME_PROGRAM_TIME_STEP_MINUTES: Final[int] = 10

# Reference to Remeha modbus registers
type ModbusVariableRef = int


@dataclass(unsafe_hash=True)
class ModbusVariableDescription:
    """Modbus register description.

    Attributes:
        start_address (ModbusRegisterRef): The register index as specified in the GTW-08 parameter list.
        name (str): The name as shown in the 'Data' field in the GTW-08 parameter list.
        data_type (DataType): The data type of the variable.
        scale (float): Multiply the 'raw' variable value by this.
        count (int): The amount of registers to read/write. Required, and calculated for all types except `DataType.STRING`.
        friendly_name (str | None): The optional parameter name as shown in the Remeha installation manual of the appliance.

    """

    start_address: ModbusVariableRef
    name: str
    data_type: DataType
    scale: float | None = Field(default=None)
    count: int | None = Field(default=None)
    friendly_name: str | None = Field(default=None)

    @model_validator(mode="after")
    def ensure_mandatory_fields(self) -> Self:
        """Ensure the fields `count` and `struct_format` have a value when they are required.

        Additionally, if `count` has no value, it is calculated for data types other than `DataType.STRING`.

        * `count` is required if `data_type == DataType.STRING`
        * `scale` must be `None` if `data_type == DataType.TUPLE16`

        """

        def ensure_register_count() -> int:
            match self.data_type:
                case DataType.UINT8 | DataType.UINT16 | DataType.INT16 | DataType.TUPLE16:
                    return 1
                case DataType.UINT32 | DataType.INT32 | DataType.FLOAT32:
                    return 2
                case DataType.CIA_301_TIME_OF_DAY:
                    return 3
                case DataType.UINT64 | DataType.INT64 | DataType.FLOAT64:
                    return 4
                case DataType.ZONE_TIME_PROGRAM:
                    return 10
                case _:
                    # Raise an error if self.count cannot be calculated.
                    raise ValueError(
                        f"Cannot calculate amount of registers required for {self.data_type}"
                    )

        if self.data_type == DataType.STRING and self.count is None:
            raise ValueError(
                "Attribute self.count has no value, but it is required because data_type is DataType.STRING"
            )

        if self.data_type == DataType.TUPLE16 and self.scale is not None:
            raise ValueError(
                "self.scale has a value, but self.data_type is DataType.TUPLE16, which cannot be scaled."
            )

        self.count = ensure_register_count() if self.count is None else self.count


class MetaRegisters:
    """Register mappings for meta data."""

    NUMBER_OF_DEVICES: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=128,
        name="numberOfDevices",
        data_type=DataType.UINT8,
    )
    NUMBER_OF_ZONES: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=189, name="NumberOfZones", data_type=DataType.UINT8
    )

    OUTSIDE_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=384, name="varApTOutside", data_type=DataType.INT16, scale=0.01
    )

    SEASON_MODE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=385, name="varApSeasonMode", data_type=DataType.UINT8
    )

    CURRENT_ERROR: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=277, name="applianceCurrentError", data_type=DataType.UINT16
    )

    ERROR_PRIORITY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=278, name="applianceErrorPriority", data_type=DataType.INT16
    )

    APPLIANCE_STATUS_1: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=279, name="applilanceStatus1", data_type=DataType.UINT8
    )

    APPLIANCE_STATUS_2: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=280, name="applilanceStatus2", data_type=DataType.UINT8
    )

    FLOW_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=400, name="varApTFlow", data_type=DataType.INT16, scale=0.01
    )

    RETURN_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=401, name="varApTReturn", data_type=DataType.INT16, scale=0.01
    )

    HEAT_PUMP_FLOW_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=403, name="varHpHeatPumpTF", data_type=DataType.INT16, scale=0.01
    )

    HEAT_PUMP_RETURN_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=404, name="varHpHeatPumpTR", data_type=DataType.INT16, scale=0.01
    )

    WATER_PRESSURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=409, name="varApWaterPressure", data_type=DataType.UINT8, scale=0.1
    )

    FLOW_METER: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=410, name="varApFlowmeter", data_type=DataType.UINT16, scale=0.01
    )

    # This variable exists on the appliance level. In the Remeha Home app however, this variable
    # is configurable in two places: in the CH zone and at the system level. Change one, change
    # the other too.
    # In this integration, this value is shown in all CH climates and can be set as follows:
    # * To force cooling, set HVACMode to COOL
    # * To let the system decide to cool or heat, set HVACMode to HEAT_COOL
    COOLING_FORCED: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=503, name="parApCoolingForced", data_type=DataType.UINT8
    )


class DeviceInstanceRegisters:
    """The register mappings for device instances."""

    TYPE_BOARD: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=129,
        name="DeviceTypeBoard",
        data_type=DataType.TUPLE16,
    )
    SW_VERSION: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=130,
        name="sw_version",
        data_type=DataType.TUPLE16,
    )
    HW_VERSION: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=132,
        name="hw_version",
        data_type=DataType.TUPLE16,
    )
    ARTICLE_NUMBER: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=133, name="ArticleNumber", data_type=DataType.UINT32
    )


class ZoneRegisters:
    """The register mappings for a climate zone."""

    TYPE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=640,
        name="varZoneType",
        data_type=DataType.UINT8,
    )
    FUNCTION: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=641,
        name="parZoneFunction",
        data_type=DataType.UINT8,
        friendly_name="CP020",
    )
    SHORT_NAME: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=642,
        name="parZoneFriendlyNameShort",
        data_type=DataType.STRING,
        count=3,
    )
    OWNING_DEVICE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=646,
        name="instance",
        data_type=DataType.UINT8,
    )
    MODE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=649,
        name="parZoneMode",
        data_type=DataType.UINT8,
        friendly_name="CP320",
    )
    TEMPORARY_SETPOINT: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=663,
        name="parZoneTemporaryRoomSetpoint",
        data_type=DataType.UINT16,
        scale=0.1,
        friendly_name="CP510",
    )
    ROOM_MANUAL_SETPOINT: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=664,
        name="parZoneRoomManualSetpoint",
        data_type=DataType.UINT16,
        scale=0.1,
        friendly_name="CP200",
    )
    DHW_COMFORT_SETPOINT: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=665,
        name="parZoneDhwComfortSetpoint",
        data_type=DataType.UINT16,
        scale=0.01,
        friendly_name="CP350",
    )
    DHW_REDUCED_SETPOINT: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=666,
        name="parZoneDhwReducedSetpoint",
        data_type=DataType.UINT16,
        scale=0.01,
        friendly_name="CP360",
    )
    DHW_CALORIFIER_HYSTERESIS: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=686,
        # It's actually Hysteresis (with an e), but since the parameter list defines it
        # as Hysterisis, we'll conform to their naming.
        name="parZoneDhwCalorifierHysterisis",
        data_type=DataType.UINT16,
        scale=0.01,
        friendly_name="CP420",
    )
    SELECTED_TIME_PROGRAM: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=688,
        name="parZoneTimeProgramSelected",
        data_type=DataType.UINT8,
        friendly_name="CP570",
    )
    TIME_PROGRAM_MONDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=689,
        name="parZoneTimeProgramMonday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    TIME_PROGRAM_TUESDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=699,
        name="parZoneTimeProgramTuesday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    TIME_PROGRAM_WEDNESDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=709,
        name="parZoneTimeProgramWednesday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    TIME_PROGRAM_THURSDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=719,
        name="parZoneTimeProgramThursday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    TIME_PROGRAM_FRIDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=729,
        name="parZoneTimeProgramFriday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    TIME_PROGRAM_SATURDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=739,
        name="parZoneTimeProgramSaturday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    TIME_PROGRAM_SUNDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=749,
        name="parZoneTimeProgramSunday",
        data_type=DataType.ZONE_TIME_PROGRAM,
    )
    END_TIME_MODE_CHANGE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=978,
        name="parZoneEndTimeModeChange",
        data_type=DataType.CIA_301_TIME_OF_DAY,
    )
    CURRENT_ROOM_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=1104,
        name="varZoneTRoom",
        data_type=DataType.INT16,
        scale=0.1,
        friendly_name="CM030",
    )
    CURRENT_HEATING_MODE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=1109,
        name="varZoneCurrentHeatingMode",
        data_type=DataType.UINT8,
        friendly_name="CM200",
    )
    PUMP_RUNNING: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=1110,
        name="varZonePumpRunning",
        data_type=DataType.UINT8,
        friendly_name="CM050",
    )
    DHW_TANK_TEMPERATURE: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=1119,
        name="varDhwTankTemperature",
        data_type=DataType.INT16,
        scale=0.01,
        friendly_name="CM040",
    )


WEEKDAY_TO_MODBUS_VARIABLE: Final[dict[Weekday, ModbusVariableDescription]] = {
    Weekday.MONDAY: ZoneRegisters.TIME_PROGRAM_MONDAY,
    Weekday.TUESDAY: ZoneRegisters.TIME_PROGRAM_TUESDAY,
    Weekday.WEDNESDAY: ZoneRegisters.TIME_PROGRAM_WEDNESDAY,
    Weekday.THURSDAY: ZoneRegisters.TIME_PROGRAM_THURSDAY,
    Weekday.FRIDAY: ZoneRegisters.TIME_PROGRAM_FRIDAY,
    Weekday.SATURDAY: ZoneRegisters.TIME_PROGRAM_SATURDAY,
    Weekday.SUNDAY: ZoneRegisters.TIME_PROGRAM_SUNDAY,
}

REMEHA_SENSORS: Final[dict[ModbusVariableDescription, SensorEntityDescription]] = {
    MetaRegisters.CURRENT_ERROR: SensorEntityDescription(  # 277
        key=MetaRegisters.CURRENT_ERROR.name, name="current_error"
    ),
    MetaRegisters.ERROR_PRIORITY: SensorEntityDescription(  # 278
        key=MetaRegisters.ERROR_PRIORITY.name, name="error_priority"
    ),
    MetaRegisters.OUTSIDE_TEMPERATURE: SensorEntityDescription(  # 384
        key=MetaRegisters.OUTSIDE_TEMPERATURE.name,
        device_class=SensorDeviceClass.TEMPERATURE,
        name="outside_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.FLOW_TEMPERATURE: SensorEntityDescription(  # 400
        key=MetaRegisters.FLOW_TEMPERATURE.name,
        device_class=SensorDeviceClass.TEMPERATURE,
        name="flow_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.RETURN_TEMPERATURE: SensorEntityDescription(  # 401
        key=MetaRegisters.RETURN_TEMPERATURE.name,
        device_class=SensorDeviceClass.TEMPERATURE,
        name="return_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.HEAT_PUMP_FLOW_TEMPERATURE: SensorEntityDescription(  # 403
        key=MetaRegisters.HEAT_PUMP_FLOW_TEMPERATURE.name,
        device_class=SensorDeviceClass.TEMPERATURE,
        name="heat_pump_flow_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.HEAT_PUMP_RETURN_TEMPERATURE: SensorEntityDescription(  # 404
        key=MetaRegisters.HEAT_PUMP_RETURN_TEMPERATURE.name,
        device_class=SensorDeviceClass.TEMPERATURE,
        name="heat_pump_return_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.WATER_PRESSURE: SensorEntityDescription(  # 409
        key=MetaRegisters.WATER_PRESSURE.name,
        device_class=SensorDeviceClass.PRESSURE,
        name="water_pressure",
        native_unit_of_measurement="bar",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.FLOW_METER: SensorEntityDescription(  # 410
        key=MetaRegisters.FLOW_METER.name,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        name="flow_rate",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
