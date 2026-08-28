"""Constants for the Remeha Modbus integration."""

from collections.abc import Callable
from datetime import date
from enum import Enum, StrEnum
from typing import Final, Literal, NamedTuple

import voluptuous as vol
from aio_remeha_modbus.api.const import (
    ClimateZoneMode,
    ClimateZoneScheduleId,
    HybridRegisters,
    MetaRegisters,
    ModbusVariableDescription,
    Weekday,
)
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
from homeassistant.core import Event, EventStateChangedData
from homeassistant.helpers import config_validation as cv
from pydantic.dataclasses import dataclass

from custom_components.remeha_modbus.helpers import validation as remeha_cv

DOMAIN: Final[str] = "remeha_modbus"
ISSUE_TRACKER_URL: Final[str] = "https://github.com/houthacker/remeha-modbus/issues"

# Versioning for the config flow.
HA_CONFIG_VERSION = 1
HA_CONFIG_MINOR_VERSION = 2

# Versioning for the json storage
STORAGE_MAJOR_VERSION = 1
STORAGE_MINOR_VERSION = 0
STORAGE_FILE_KEY = f"{DOMAIN}.storage"
STORAGE_RUNTIME_KEY = f"{DOMAIN}_storage"

type EntityEventCallback = Callable[[Event[EventStateChangedData]], None]

SWITCH_SCHEDULE_SYNC: Final[str] = "enable_schedule_sync"
"""Entity name of the switch that determines whether schedules are synchronized.

Enabling this requires the user to have installed the `scheduler-card` and `scheduler-component`
integrations.
"""

HEATPUMP_MANAGED_SCHEDULES: Final[str] = "heatpump_managed_schedules"
"""Entity name of the switch that determines whether time schedule execution is managed by the heat pump (True) or HA (False).

The recommended setting is 'on', as to have the heat pump manage time schedule execution.
"""

TIME_SILENT_MODE_START_TIME: Final[str] = "silent_mode_start_time"
"""Entity name of the time entity that configures when the appliance silent mode starts."""

TIME_SILENT_MODE_END_TIME: Final[str] = "silent_mode_end_time"
"""Entity name of the time entity that configures when the appliance silent mode ends."""

ISSUE_CONFIG_ENTRY_CONNECTION_TYPE: Final[str] = "config_entry_error_connection_type"

ISSUE_CONFIG_ENTRY_KEY_ERROR: Final[str] = "config_entry_key_error"

ISSUE_HEATPUMP_MANAGED_SCHEDULES_OFF: Final[str] = "heatpump_managed_schedules_off"

ISSUE_HEATPUMP_MANAGED_SCHEDULES_LEARN_MORE_URL: Final[str] = (
    "https://github.com/houthacker/remeha-modbus#heatpump-managed-schedules"
)

ISSUE_INVALID_ZONE_SCHEDULE: Final[str] = "invalid_zone_schedule"

ISSUE_DISCOVERY_TABLE_CORRUPTED: Final[str] = "modbus_discovery_table_corrupted"
ISSUE_DISCOVERY_TABLE_CORRUPTED_LEARN_MORE_URL: Final[str] = (
    "https://github.com/houthacker/remeha-modbus#modbus-discovery-table"
)

ISSUE_RESTART_REQUIRED_REDISCOVERY: Final[str] = "restart_required_force_system_rediscovery"

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

ATTR_ZONE_ID: Final[str] = "zone_id"
"""Attribute in `climate` entities containing the related `ClimateZone` id."""

ATTR_SCHEDULER_NAME: Final[str] = "name"
"""Attribute in `switch` entities in the `scheduler` component where their name is stored."""

ATTR_SCHEDULER_TAGS: Final[str] = "tags"
"""Attribute in `switch` entities in the `scheduler` component where tags are stored."""

type UnsubscribeCallback = Callable[[], None]
"""A type shorthand for a no-arg callable returning None."""


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

    def has_cooling_capability(self) -> bool:
        """Return whether this `ClimateZoneFunction` supports cooling."""
        return self in [
            ClimateZoneFunction.MIXING_CIRCUIT,
            ClimateZoneFunction.FAN_CONVECTOR,
        ]


class ClimateZoneHeatingMode(Enum):
    """The mode the zone is currently functioning in."""

    STANDBY = 0
    HEATING = 1
    COOLING = 2


class ZoneScheduleUID(NamedTuple):
    """A key class to uniquely identify a climate zone schedule."""

    zone_id: int

    schedule_id: ClimateZoneScheduleId

    weekday: Weekday

    def __str__(self):
        """Return a string representation of this object."""
        return f"{self.zone_id}.{self.schedule_id}.{self.weekday.name}"


WEEKDAY_TO_SHORT_DESC: Final[
    dict[Weekday, Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]
] = {
    Weekday.MONDAY: "mon",
    Weekday.TUESDAY: "tue",
    Weekday.WEDNESDAY: "wed",
    Weekday.THURSDAY: "thu",
    Weekday.FRIDAY: "fri",
    Weekday.SATURDAY: "sat",
    Weekday.SUNDAY: "sun",
}

SHORT_DESC_TO_WEEKDAY: Final[
    dict[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"], Weekday]
] = {WEEKDAY_TO_SHORT_DESC[day]: day for day in Weekday}

CONFIG_AUTO_SCHEDULE: Final[str] = "auto_schedule"

### Service names. Keep in sync with services.yaml service name. ###
SERVICE_BOOTSTRAP_BLENDERS: Final[str] = "bootstrap_blenders"
SERVICE_READ_REGISTERS: Final[str] = "read_registers"
SERVICE_AUTO_SCHEDULE: Final[str] = "dhw_auto_schedule"
SERVICE_FORCE_SYSTEM_REDISCOVERY: Final[str] = "force_system_rediscovery"

### Service fields
READ_REGISTERS_START_REGISTER: Final[str] = "start_register"
READ_REGISTERS_REGISTER_COUNT: Final[str] = "register_count"
READ_REGISTERS_STRUCT_FORMAT: Final[str] = "struct_format"

### Service schemes
READ_REGISTERS_SERVICE_SCHEMA: vol.Schema = vol.Schema(
    {
        vol.Required(READ_REGISTERS_START_REGISTER): cv.positive_int,
        vol.Required(READ_REGISTERS_REGISTER_COUNT, default=1): cv.positive_int,
        vol.Required(READ_REGISTERS_STRUCT_FORMAT, default="=H"): remeha_cv.struct_format,
    }
)


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
REMEHA_PRESET_SCHEDULE_4: Final[str] = "schedule_4"

HA_PRESET_MANUAL: Final[str] = "manual"
HA_PRESET_ANTI_FROST: Final[str] = "anti_frost"
CLIMATE_SCHEDULING_PRESETS: Final[list[str]] = [
    REMEHA_PRESET_SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3,
    REMEHA_PRESET_SCHEDULE_4,
]

# Additional presets available on DHW zones
CLIMATE_DHW_EXTRA_PRESETS: Final[list[str]] = [PRESET_COMFORT, PRESET_ECO, PRESET_NONE]

HA_SCHEDULE_TO_REMEHA_SCHEDULE: Final[dict[str, ClimateZoneScheduleId]] = {
    REMEHA_PRESET_SCHEDULE_1: ClimateZoneScheduleId.SCHEDULE_1,
    REMEHA_PRESET_SCHEDULE_2: ClimateZoneScheduleId.SCHEDULE_2,
    REMEHA_PRESET_SCHEDULE_3: ClimateZoneScheduleId.SCHEDULE_3,
    REMEHA_PRESET_SCHEDULE_4: ClimateZoneScheduleId.SCHEDULE_4,
}

HA_CLIMATE_PRESET_TO_REMEHA_ZONE_MODE: Final[dict[str, ClimateZoneMode]] = {
    HA_PRESET_ANTI_FROST: ClimateZoneMode.ANTI_FROST,
    HA_PRESET_MANUAL: ClimateZoneMode.MANUAL,
    PRESET_COMFORT: ClimateZoneMode.MANUAL,
    PRESET_ECO: ClimateZoneMode.ANTI_FROST,
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
REMEHA_TIME_STEP_MINUTES: Final[int] = 10

# Option keys for the ENUM status sensors. The human-readable values are provided
# as translations (see the `entity.sensor` section in the translation files).
SEASON_MODE_OPTIONS: Final[dict[int, str]] = {
    0: "winter",
    1: "frost_protection",
    2: "transition_season",
    3: "summer",
}

STATUS_OPTIONS: Final[dict[int, str]] = {
    0: "standby",
    1: "heat_demand",
    2: "generator_start",
    3: "generator_heating",
    4: "generator_dhw",
    5: "generator_stop",
    6: "pump_post_run",
    7: "cooling",
    8: "controlled_shutdown",
    9: "start_prevention",
    10: "locking_mode",
    11: "load_test_min",
    12: "load_test_heating_max",
    13: "load_test_dhw_max",
    15: "manual_heat_demand",
    16: "frost_protection",
    17: "venting",
    18: "control_unit_cooling",
    19: "resetting",
    20: "automatic_filling",
    21: "stopped",
    22: "calibration",
    23: "factory_test",
    24: "hydraulic_balancing",
    200: "device_mode",
    254: "unknown",
}

SUBSTATUS_OPTIONS: Final[dict[int, str]] = {
    0: "standby",
    1: "pause_time",
    2: "close_hydraulic_valve",
    3: "stop_pump",
    4: "wait_start_release",
    21: "generator_starting",
    30: "internal_setpoint",
    31: "limited_internal_setpoint",
    32: "power_controlled",
    60: "pump_post_run",
    61: "start_pump",
    63: "start_pause_time",
    65: "compressor_unloaded",
    66: "hp_tmax_backup_on",
    67: "outside_temp_limit_hp_off",
    68: "hp_stop_by_hybrid",
    69: "defrost_with_heat_pump",
    70: "defrost_with_backup",
    71: "defrost_hp_and_backup",
    73: "hp_flow_above_tmax",
    75: "hp_off_high_humidity",
    76: "hp_off_flow",
    79: "generator_unloaded",
    80: "hp_unloaded_cooling",
    81: "hp_stop_outside_temp",
    82: "hp_off_flow_tmax",
    88: "bl_backup_off",
    89: "bl_heat_pump_off",
    90: "bl_hp_and_backup_off",
    91: "low_tariff",
    92: "pv_with_heat_pump",
    93: "pv_hp_and_backup",
    94: "smart_grid",
    95: "wait_water_pressure",
    96: "no_generator_available",
    102: "free_cooling_pump_off",
    103: "free_cooling_pump_on",
    106: "blocking_active",
    107: "warming_up",
    108: "curative_defrost",
    109: "preventive_defrost",
    200: "init_completed",
    201: "init_csu",
    202: "init_identification",
    203: "init_blocking_parameters",
    204: "init_safety_unit",
    205: "init_blocking",
    254: "unknown",
    255: "safety_shutdown",
}

REMEHA_ENUM_SENSOR_OPTIONS: Final[dict[ModbusVariableDescription, dict[int, str]]] = {
    MetaRegisters.SEASON_MODE: SEASON_MODE_OPTIONS,
    MetaRegisters.STATUS: STATUS_OPTIONS,
    MetaRegisters.SUBSTATUS: SUBSTATUS_OPTIONS,
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
    MetaRegisters.SEASON_MODE: SensorEntityDescription(  # 385
        key=MetaRegisters.SEASON_MODE.name,
        name="season_mode",
        translation_key="season_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(SEASON_MODE_OPTIONS.values()),
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
    MetaRegisters.STATUS: SensorEntityDescription(  # 411
        key=MetaRegisters.STATUS.name,
        name="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_OPTIONS.values()),
    ),
    MetaRegisters.SUBSTATUS: SensorEntityDescription(  # 412
        key=MetaRegisters.SUBSTATUS.name,
        name="substatus",
        translation_key="substatus",
        device_class=SensorDeviceClass.ENUM,
        options=list(SUBSTATUS_OPTIONS.values()),
    ),
    MetaRegisters.POWER_ACTUAL: SensorEntityDescription(  # 413
        key=MetaRegisters.POWER_ACTUAL.name,
        name="actual_relative_power",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.GENERATOR_STARTS_TOTAL: SensorEntityDescription(  # 419
        key=MetaRegisters.GENERATOR_STARTS_TOTAL.name,
        name="generator_starts_total",
        native_unit_of_measurement="starts",
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.GENERATOR_HOURS_TOTAL: SensorEntityDescription(  # 421
        key=MetaRegisters.GENERATOR_HOURS_TOTAL.name,
        name="generator_hours_total",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.BACKUP1_STARTS: SensorEntityDescription(  # 423
        key=MetaRegisters.BACKUP1_STARTS.name,
        name="backup1_starts",
        native_unit_of_measurement="starts",
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.BACKUP1_HOURS: SensorEntityDescription(  # 425
        key=MetaRegisters.BACKUP1_HOURS.name,
        name="backup1_hours",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.BACKUP2_STARTS: SensorEntityDescription(  # 427
        key=MetaRegisters.BACKUP2_STARTS.name,
        name="backup2_starts",
        native_unit_of_measurement="starts",
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.BACKUP2_HOURS: SensorEntityDescription(  # 429
        key=MetaRegisters.BACKUP2_HOURS.name,
        name="backup2_hours",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.POWER_ON_HOURS: SensorEntityDescription(  # 431
        key=MetaRegisters.POWER_ON_HOURS.name,
        name="power_on_hours",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.CH_ENERGY_CONSUMPTION: SensorEntityDescription(  # 433
        key=MetaRegisters.CH_ENERGY_CONSUMPTION.name,
        name="ch_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.DHW_ENERGY_CONSUMPTION: SensorEntityDescription(  # 435
        key=MetaRegisters.DHW_ENERGY_CONSUMPTION.name,
        name="dhw_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.COOLING_ENERGY_CONSUMPTION: SensorEntityDescription(  # 437
        key=MetaRegisters.COOLING_ENERGY_CONSUMPTION.name,
        name="cooling_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.BACKUP_ENERGY_CONSUMPTION: SensorEntityDescription(  # 441
        key=MetaRegisters.BACKUP_ENERGY_CONSUMPTION.name,
        name="backup_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.TOTAL_ENERGY_CONSUMPTION: SensorEntityDescription(  # 439
        key=MetaRegisters.TOTAL_ENERGY_CONSUMPTION.name,
        name="total_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.TOTAL_ENERGY_DELIVERY: SensorEntityDescription(  # 443
        key=MetaRegisters.TOTAL_ENERGY_DELIVERY.name,
        name="total_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.CH_ENERGY_DELIVERY: SensorEntityDescription(  # 445
        key=MetaRegisters.CH_ENERGY_DELIVERY.name,
        name="ch_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.DHW_ENERGY_DELIVERY: SensorEntityDescription(  # 447
        key=MetaRegisters.DHW_ENERGY_DELIVERY.name,
        name="dhw_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.COOLING_ENERGY_DELIVERY: SensorEntityDescription(  # 449
        key=MetaRegisters.COOLING_ENERGY_DELIVERY.name,
        name="cooling_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.BACKUP_ENERGY_DELIVERY: SensorEntityDescription(  # 451
        key=MetaRegisters.BACKUP_ENERGY_DELIVERY.name,
        name="backup_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    MetaRegisters.PUMP_SPEED: SensorEntityDescription(  # 459
        key=MetaRegisters.PUMP_SPEED.name,
        name="pump_speed",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    MetaRegisters.ACTUAL_PRODUCED_POWER: SensorEntityDescription(  # 460
        key=MetaRegisters.ACTUAL_PRODUCED_POWER.name,
        name="actual_produced_power",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    HybridRegisters.COP_CALCULATED: SensorEntityDescription(  # 9230
        key=HybridRegisters.COP_CALCULATED.name,
        name="cop_calculated",
        native_unit_of_measurement="CoP",
        state_class=SensorStateClass.MEASUREMENT,
    ),
}
