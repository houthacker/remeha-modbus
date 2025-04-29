"""Constants for the Remeha Modbus integration."""

from enum import Enum, StrEnum
from typing import Final, Self

from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_NONE,
)
from pydantic import Field, model_validator
from pydantic.dataclasses import dataclass

DOMAIN: Final[str] = "remeha_modbus"

# Versioning for the config flow.
HA_CONFIG_VERSION = 1
HA_CONFIG_MINOR_VERSION = 0

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


@dataclass
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
        start_address=189,
        name="NumberOfZones",
        data_type=DataType.UINT8,
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
        data_type=DataType.STRING,
        count=10,
    )
    TIME_PROGRAM_TUESDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=699,
        name="parZoneTimeProgramTuesday",
        data_type=DataType.STRING,
        count=10,
    )
    TIME_PROGRAM_WEDNESDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=709,
        name="parZoneTimeProgramWednesday",
        data_type=DataType.STRING,
        count=10,
    )
    TIME_PROGRAM_THURSDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=719,
        name="parZoneTimeProgramThursday",
        data_type=DataType.STRING,
        count=10,
    )
    TIME_PROGRAM_FRIDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=729,
        name="parZoneTimeProgramFriday",
        data_type=DataType.STRING,
        count=10,
    )
    TIME_PROGRAM_SATURDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=739,
        name="parZoneTimeProgramSaturday",
        data_type=DataType.STRING,
        count=10,
    )
    TIME_PROGRAM_SUNDAY: Final[ModbusVariableDescription] = ModbusVariableDescription(
        start_address=749,
        name="parZoneTimeProgramSunday",
        data_type=DataType.STRING,
        count=10,
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
