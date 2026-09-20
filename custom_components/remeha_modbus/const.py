"""Constants for the Remeha Modbus integration."""

from collections.abc import Callable
from enum import StrEnum
from typing import Final, Literal, NamedTuple

import voluptuous as vol
from aio_remeha_modbus.api.climate_zone import ClimateZoneMode
from aio_remeha_modbus.api.const import (
    ClimateZoneScheduleId,
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

# Configuration fields not provided by libs
CONF_FRAMER = "framer"

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

# Modbus slave number
MODBUS_DEVICE_ADDRESS: Final[str] = "slave"

# Modbus serial configuration fields
MODBUS_SERIAL_METHOD: Final[str] = "method"
MODBUS_SERIAL_PARITY: Final[str] = "parity"

# Modbus serial method types
MODBUS_SERIAL_METHOD_RTU: Final[str] = "rtu"
MODBUS_SERIAL_METHOD_ASCII: Final[str] = "ascii"

# Modbus parity bytes
MODBUS_SERIAL_PARITY_EVEN: Final[str] = "E"
MODBUS_SERIAL_PARITY_ODD: Final[str] = "O"
MODBUS_SERIAL_PARITY_NONE: Final[str] = "N"

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

REMEHA_ENUM_SENSOR_OPTIONS: Final[dict[str, dict[int, str]]] = {
    "season_mode": SEASON_MODE_OPTIONS,
    "status": STATUS_OPTIONS,
    "substatus": SUBSTATUS_OPTIONS,
}

SENSOR_FIELD_OVERRIDES: Final[dict[str, str]] = {
    # Sensor values are looked up by entity name, which usually equals the name of the
    # `aio-remeha-modbus` field holding the value. Map the exceptions here, so the entity
    # names -- and with them the entity ids -- can stay as they are.
    "water_pressure": "actual_water_pressure",
}

REMEHA_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(  # 277
        key="applianceCurrentError", name="current_error"
    ),
    SensorEntityDescription(  # 278
        key="applianceErrorPriority", name="error_priority"
    ),
    SensorEntityDescription(  # 384
        key="varApTOutside",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="outside_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 385
        key="varApSeasonMode",
        name="season_mode",
        translation_key="season_mode",
        device_class=SensorDeviceClass.ENUM,
        options=list(SEASON_MODE_OPTIONS.values()),
    ),
    SensorEntityDescription(  # 400
        key="varApTFlow",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="flow_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 401
        key="varApTReturn",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="return_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 403
        key="varHpHeatPumpTF",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="heat_pump_flow_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 404
        key="varHpHeatPumpTR",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="heat_pump_return_temperature",
        native_unit_of_measurement="°C",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 409
        key="varApWaterPressure",
        device_class=SensorDeviceClass.PRESSURE,
        name="water_pressure",
        native_unit_of_measurement="bar",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 410
        key="varApFlowmeter",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        name="flow_rate",
        native_unit_of_measurement="L/min",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 411
        key="varApStatus",
        name="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_OPTIONS.values()),
    ),
    SensorEntityDescription(  # 412
        key="varApSubStatus",
        name="substatus",
        translation_key="substatus",
        device_class=SensorDeviceClass.ENUM,
        options=list(SUBSTATUS_OPTIONS.values()),
    ),
    SensorEntityDescription(  # 413
        key="varApPowerActual",
        name="actual_relative_power",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 419
        key="varApGeneratorStartsTotal",
        name="generator_starts_total",
        native_unit_of_measurement="starts",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 421
        key="varApGeneratorHoursTotal",
        name="generator_hours_total",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 423
        key="varApBackup1Starts",
        name="backup1_starts",
        native_unit_of_measurement="starts",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 425
        key="varApBackup1Hours",
        name="backup1_hours",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 427
        key="varApBackup2Starts",
        name="backup2_starts",
        native_unit_of_measurement="starts",
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 429
        key="varApBackup2Hours",
        name="backup2_hours",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 431
        key="varApPowerOnHours",
        name="power_on_hours",
        native_unit_of_measurement="h",
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 433
        key="varApChEnergyConsumption",
        name="ch_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 435
        key="varApDhwEnergyConsumption",
        name="dhw_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 437
        key="varApCoolingEnergyConsumption",
        name="cooling_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 441
        key="varApBackupEnergyConsumption",
        name="backup_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 439
        key="varApTotalEnergyConsumption",
        name="total_energy_consumption",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 443
        key="varApTotalEnergyDelivery",
        name="total_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 445
        key="varApChEnergyDelivery",
        name="ch_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 447
        key="varApDhwEnergyDelivery",
        name="dhw_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 449
        key="varApCoolingEnergyDelivery",
        name="cooling_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 451
        key="varApBackupEnergydelivery",
        name="backup_energy_delivery",
        native_unit_of_measurement="kWh",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(  # 459
        key="varApPumpSpeed",
        name="pump_speed",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 460
        key="varApActualProducedPower",
        name="actual_produced_power",
        native_unit_of_measurement="kW",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(  # 9230
        key="varHpCopCalculated",
        name="cop_calculated",
        native_unit_of_measurement="CoP",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)
