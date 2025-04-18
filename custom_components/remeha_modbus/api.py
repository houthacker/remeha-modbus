"""Implementation of the Remeha Modbus API."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, StrEnum, auto

from pymodbus import FramerType, ModbusException
from pymodbus import client as ModbusClient
from pymodbus.pdu import ModbusPDU

from .const import (
    REMEHA_DEVICE_INSTANCE_RESERVED_REGISTERS,
    REMEHA_ZONE_RESERVED_REGISTERS,
    DeviceInstanceRegisters,
    Limits,
    MetaRegisters,
    ModbusVariableDescription,
    ZoneRegisters,
)
from .helpers.modbus import deserialize, serialize

_LOGGER = logging.getLogger(__name__)

#################################
### Device class definitions  ###
#################################


class DeviceBoardType(Enum):
    """Defines the type of device located on the device instance."""

    CU_GH = 0
    """Motherboard for central heating boilers like Tzerra Ace"""

    CU_OH = 1
    """Motherboard for condensing oil boilers like Calora Tower Oil LS"""

    EHC = 2
    """Motherboard for (hybrid) heat pumps like Mercuria Ace"""

    MK = int("0x14", 0)
    """Appliance control panel like eTwist"""

    SCB = int("0x19", 0)
    """Circuit control board"""

    EEC = int("0x1b", 0)
    """Mainboard for gas boilers like GAS 120 Ace"""

    GATEWAY = int("0x1e", 0)
    """A gateway, for example GTW-08 (modbus gateway)"""


@dataclass
class DeviceBoardCategory:
    """The category of the device located on the appliance."""

    type: DeviceBoardType
    """The device type"""

    generation: int
    """The category generation"""

    def __str__(self):
        """Textual representation of this DeviceBoardCategory."""

        name: str = None
        match self.type:
            case DeviceBoardType.CU_GH:
                name = "CU-GH"
            case DeviceBoardType.CU_OH:
                name = "CU-OH"
            case DeviceBoardType.GATEWAY:
                name = "GTW"
            case _:
                name = self.type.name

        return f"{name}-{self.generation}"


@dataclass(eq=False)
class DeviceInstance:
    """A device (electronic board) somewhere on the Remeha appliance."""

    id: int
    """The device sequence id."""

    board_category: DeviceBoardCategory
    """The board category on this instance."""

    sw_version: tuple[int, int]
    """The software version as (major,minor)"""

    hw_version: tuple[int, int]
    """The hardware version as (major,minor)"""

    article_number: int
    """The article number of the device"""

    def __eq__(self, other) -> bool:
        """Compare this `DeviceInstance` with another for equality.

        For equality, only the property `id` is considered.

        Returns:
            `bool`: `True` if the objects are considered equal, `False` otherwise.

        """
        if isinstance(other, self.__class__):
            return self.id == other.id

        return False


#################################
### Climate class definitions ###
#################################


class ConnectionType(StrEnum):
    """Defines the type of modbus connection."""

    TCP = auto()
    """TCP/IP connection with socket framer, used with Ethernet enabled devices."""

    UDP = auto()
    """UDP connection with socker framer."""

    RTU_OVER_TCP = "rtuovertcp"
    """TCP/IP connection with RTU framer, used when connecting to modbus forwarders."""

    SERIAL = auto()
    """Serial connection with RTU framer, used with TTY port or USB rs485 converter."""


class SerialConnectionMethod(StrEnum):
    """Defines the serial connection method."""

    RTU = auto()
    """Binary data transmission preceded by slave it and followed by a crc. Standard."""

    ASCII = auto()
    """ASCII data transmission preceded by slave id and followed by a crc. Used for new devices."""


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

    ALthough this property is optional, it needn't be `None` if `mode != ClimateZoneMode.SCHEDULING`.
    """

    heating_mode: ClimateZoneHeatingMode
    """The current heating mode of the climate zone"""

    room_setpoint: float
    """The current room temperature setpoint"""

    dhw_comfort_setpoint: float
    """The setpoint for DHW in comfort mode"""

    dhw_calorifier_hysterisis: float | None
    """Hysterisis to start DHW tank load"""

    room_temperature: float
    """The current room temperature"""

    dhw_tank_temperature: float
    """The current DHW tank temperature"""

    pump_running: bool
    """Whether the zone pump is currently running"""

    dhw_tank_temperature: float
    """The current DHW tank temperature"""

    @property
    def current_setpoint(self) -> float:
        """Return the current setpoint of this zone.

        The actual returned setpoint field depends on the type of zone.
        """

        if self.is_central_heating():
            return self.room_setpoint

        if self.is_domestic_hot_water():
            return self.dhw_comfort_setpoint

        _LOGGER.warning(
            "Current setpoint not supported for climate zones of type %s", self.type
        )
        return -1

    @current_setpoint.setter
    def current_setpoint(self, value: float):
        """Set the current setpoint of this zone."""

        if self.is_central_heating():
            self.room_setpoint = value
        elif self.is_domestic_hot_water():
            self.dhw_comfort_setpoint = value
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

        _LOGGER.warning(
            "Current temperature not supported for climate zones of type %s", self.type
        )
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
                self.id == other.id
                and self.type == other.type
                and self.function == other.function
            )

        return False


#################################
###     remeha_modbus API     ###
#################################


class RemehaApi:
    """Use instances of this class to interact with the Remeha device through Modbus."""

    def __init__(
        self, name: str, connection_type: ConnectionType, device_address: int = 1
    ):
        """Create a new API instance."""
        self._client: ModbusClient.ModbusBaseClient = None

        self._name = name
        self._connection_type = connection_type
        self._device_address = device_address
        self._lock = asyncio.Lock()
        self._message_delay_seconds: int | None = 10 / 1000  # 10ms

    def name(self) -> str:
        """Return the modbus hub name."""
        return self._name

    def connection_type(self) -> ConnectionType:
        """Return the modbus connection type."""
        return self._connection_type

    @property
    async def connected(self) -> bool:
        """Return whether we're connected to the modbus device."""
        async with self._lock:
            return self._client.connected

    async def connect(self) -> bool:
        """Connect to the configured modbus device."""

        async with self._lock:
            if not self._client.connected:
                return await self._client.connect()

            return True

    async def close(self) -> None:
        """Close the connection to the configured modbus device."""

        async with self._lock:
            if self._client.connected:
                try:
                    await self._client.close()
                except ModbusException as ex:
                    _LOGGER.error("Error while closing modbus client", exc_info=ex)

                _LOGGER.info("Modbus connection closed.")

    async def _read_variable(
        self, variable: ModbusVariableDescription, offset: int = 0
    ) -> ModbusPDU:
        """Read the requested variable from the modbus device.

        The actual amount of registers to read is calculated based on `variable.data_type`.

        Args:
            variable (ModbusVariableDescription): The variable to retrieve.
            offset (int): The offset for `variable.start_address`, in registers. Used for zone and device info registers.

        Returns:
            ModbusPDU: The resulting PDU.

        Raises:
            ModbusException: If the connection to the modbus device is lost or if the request fails.
            ValueError: If the required register count cannot be calculated.

        """

        async def _ensure_connected() -> None:
            if not self._client.connected and not await self._client.connect():
                raise ModbusException("Connection to modbus device lost.")

        if self._message_delay_seconds is not None:
            # Let the modbus device catch its breath.
            await asyncio.sleep(self._message_delay_seconds)

        # After this, we're either we're connected or an exception is raised.
        await _ensure_connected()
        response: ModbusPDU = await self._client.read_holding_registers(
            address=variable.start_address + offset,
            count=variable.count,
            slave=self._device_address,
        )
        if response.isError():
            raise ModbusException(
                "Modbus device returned an error while reading holding registers."
            )

        return response

    async def _write_registers(
        self, variable: ModbusVariableDescription, registers: list[int], offset: int = 0
    ) -> None:
        """Write the `value` to the given modbus variable.

        The actual amount of registers to write is calculated based on `variable.data_type`.

        Args:
            variable (ModbusVariableDescription): The variable to write.
            registers (list[int]): The list of register values to write.
            offset (int): The offset for `variable.start_address`, in registers. Used for zone and device info registers.

        Raises:
            ModbusException: If the connection to the modbus device is lost or if the write request fails.

        """

        async def _ensure_connected() -> None:
            if not self._client.connected and not await self._client.connect():
                raise ModbusException("Connection to modbus device lost.")

        async with self._lock:
            await _ensure_connected()
            response: ModbusPDU = await self._client.write_registers(
                address=variable.start_address + offset,
                values=registers,
                slave=self._device_address,
            )
            if response.isError():
                raise ModbusException(
                    "Modbus device returned an error while writing registers."
                )

    def get_zone_register_offset(self, zone: ClimateZone | int) -> int:
        """Get the offset in registers for the given `ClimateZone | int`."""
        zone_id: int = zone.id if isinstance(zone, ClimateZone) else zone
        return (zone_id - 1) * REMEHA_ZONE_RESERVED_REGISTERS

    def get_device_register_offset(self, device: DeviceInstance | int) -> int:
        """Get the offset in registers for the given `DeviceInfo | int`."""

        device_id: int = device.id if isinstance(device, DeviceInstance) else device
        return (device_id - 1) * REMEHA_DEVICE_INSTANCE_RESERVED_REGISTERS

    async def health_check(self) -> None:
        """Attempt to check the system health by reading a single register (128 - numberOfDevices).

        Raises
        ------
            `ModbusException` - if the health check is unsuccessful.

        """
        try:
            await self.read_number_of_device_instances()
        except ValueError as ex:
            raise ModbusException from ex

        _LOGGER.debug("Modbus health check successful")

    async def read_device_instances(self) -> list[DeviceInstance]:
        """Retrieve the available devices instances of the Remeha appliance.

        Returns
            `list[DeviceInstance]`: A list of all discovered device instances.

        Raises
            `ModbusException`: If the list of device instances cannot be obtained.

        """

        number_of_instances: int = await self.read_number_of_device_instances()
        return [
            instance
            for instance in [
                await self.read_device_instance(instance_id)
                for instance_id in range(1, number_of_instances + 1)
            ]
            if instance is not None
        ]

    async def read_number_of_device_instances(self) -> int:
        """Retrieve the number of available  device instances in the appliance.

        Returns
            `int`: The number of instances.

        Raises
            `ModbusException`: If the number of instances cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be deserialized successfully.

        """

        return deserialize(
            response=await self._read_variable(
                variable=MetaRegisters.NUMBER_OF_DEVICES
            ),
            variable=MetaRegisters.NUMBER_OF_DEVICES,
        )

    async def read_device_instance(self, id: int) -> DeviceInstance:
        """Read a single device instance from the modbus interface.

        This reads the registers as described in the table below. Only the base zone registers
        are mentioned here; add `6 * id` to get the discrete register number of the zone.
        For details, refer to the Remeha GTW-08 parameter list.

        | Base address  | Variable name                 | Description                                           | Modbus type   | HA type                   |
        |---------------|-------------------------------|-------------------------------------------------------|---------------|---------------------------|
        |       129     | `DeviceTypeBoard`             | Type of the device located on the instance.           |   `UINT16`    | `DeviceBoardCategory`     |
        |       130     | `sw_version`                  | Software version (ex. 0x2001 = SW02.01)               |   `UINT16`    | `tuple[int, int]`         |
        |       132     | `hw_version`                  | Hardware version (ex. 0x2001 = HW02.01)               |   `UINT16`    | `tuple[int, int]`         |
        |       133     | `ArticleNumber`               | Article number of the device located on the instance. |   `UINT32`    | `int`                     |

        Args:
            id (int): The one-based instance id.

        Returns:
            `DeviceInst4ance`: The requested device instance

        Raises:
            `ModbusException`: If the instance registers cannot be read.
            `ValueException`: If deserializing the registers to a `DeviceInstance` fails.

        """
        device_register_offset: int = self.get_device_register_offset(id)
        board_category = deserialize(
            response=await self._read_variable(
                variable=DeviceInstanceRegisters.TYPE_BOARD,
                offset=device_register_offset,
            ),
            variable=DeviceInstanceRegisters.TYPE_BOARD,
        )
        sw_version = deserialize(
            response=await self._read_variable(
                variable=DeviceInstanceRegisters.SW_VERSION,
                offset=device_register_offset,
            ),
            variable=DeviceInstanceRegisters.SW_VERSION,
        )
        hw_version = deserialize(
            response=await self._read_variable(
                variable=DeviceInstanceRegisters.HW_VERSION,
                offset=device_register_offset,
            ),
            variable=DeviceInstanceRegisters.HW_VERSION,
        )
        article_number = deserialize(
            response=await self._read_variable(
                variable=DeviceInstanceRegisters.ARTICLE_NUMBER,
                offset=device_register_offset,
            ),
            variable=DeviceInstanceRegisters.ARTICLE_NUMBER,
        )

        return DeviceInstance(
            id=id,
            board_category=DeviceBoardCategory(
                type=DeviceBoardType(board_category[0]), generation=board_category[1]
            ),
            sw_version=sw_version,
            hw_version=hw_version,
            article_number=article_number,
        )

    async def read_zones(self) -> list[ClimateZone]:
        """Retrieve the available zones of the modbus device.

        This method returns the all zones having a supported `ClimateZoneFunction`.
        Whether a zone function is supported can be queried using `ClimateZoneFunction.is_supported()`

        Returns
            `list[ClimateZone]`: A list of all discovered zones.

        Raises
            `ModbusException`: If the list of zones cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be deserialized. successfully.

        """

        number_of_zones: int = await self.read_number_of_zones()
        return [
            zone
            for zone in [
                await self.read_zone(zone_id)
                for zone_id in range(1, number_of_zones + 1)
            ]
            if zone is not None
        ]

    async def read_number_of_zones(self) -> int:
        """Retrieve the number of zones defined in the appliance.

        Returns
            `int`: The number of zones.

        Raises
            `ModbusException`: If the number of zones cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be deserialized successfully.

        """
        return deserialize(
            response=await self._read_variable(variable=MetaRegisters.NUMBER_OF_ZONES),
            variable=MetaRegisters.NUMBER_OF_ZONES,
        )

    async def read_zone(self, id: int) -> ClimateZone | None:
        """Read a single climate zone from the modbus interface.

        This reads the registers as described in the table below. Only the base zone registers
        are mentioned here; add `512 * id` to get the discrete register number of the zone.
        For details, refer to the Remeha GTW-08 parameter list.

        | Base address  | Variable name                     | Description                                           | Modbus type   | HA type                   |
        |---------------|-----------------------------------|-------------------------------------------------------|---------------|---------------------------|
        |       640     | `varZoneType`                     | Zone type.                                            |   `ENUM8`     | `ClimateZoneType`         |
        |       641     | `parZoneFunction`                 | Zone function.                                        |   `ENUM8`     | `ClimateZoneFunction`     |
        |       642     | `parZoneFriendlyNameShort         | Zone short name.                                      |   `STRING`    | `str`                     |
        |       646     | `instance`                        | Device instance owning the zone.                      |   `UINT8`     | `int`                     |
        |       649     | `parZoneMode`                     | Mode zone working.                                    |   `ENUM8`     | `ClimateZoneMode`         |
        |       664     | `parZoneRoomManualSetpoint`       | Manually set wished room temperature of the zone.     |   `UINT16`    | `float`                   |
        |       665     | `parZoneDhwComfortSetpoint`       | Wished comfort domestic hot water temperature.        |   `UINT16`    | `float`                   |
        |       686     | `parZoneDhwCalorifierHysterisis   | Hysterisis to start DHW tank load                     |   `UINT16`    | `float`                   |
        |       688     | `parZoneTimeProgramSelected`      | Time program selected by the user.                    |   `ENUM8`     | `ClimateZoneScheduleId`   |
        |      1104     | `varZoneTRoom`                    | Current room temperature for zone.                    |   `INT16`     | `float`                   |
        |      1109     | `varZoneCurrentHeatingMode`       | Current mode the zone is functioning in.              |   `ENUM8`     | `ClimateZoneHeatingMode`  |
        |      1110     | `varZonePumpRunning`              | Whether the zone pump is ruinning.                    |   `ENUM8`     | `bool`                    |
        |      1119     | `varDhwTankTemperature`           | Tank temperature DHW tank (bottom or single sensor)   |   `INT16`     | `float`                   |

        Args:
            id (int): The one-based zone id.

        Returns:
            `ClimateZone`: The requested zone, or `None` if `zone.type == ClimateZoneType.NOT_PRESENT`.

        Raises:
            `ModbusException`: If the zone registers cannot be read.
            `ValueError`: If deserializing the registers to a `ClimateZone` fails.

        """

        zone_register_offset: int = self.get_zone_register_offset(id)

        zone_type = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.TYPE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.TYPE,
        )
        zone_function = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.FUNCTION, offset=zone_register_offset
            ),
            variable=ZoneRegisters.FUNCTION,
        )
        zone_short_name = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.SHORT_NAME, offset=zone_register_offset
            ),
            variable=ZoneRegisters.SHORT_NAME,
        )
        owning_device = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.OWNING_DEVICE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.OWNING_DEVICE,
        )
        zone_mode = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.MODE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.MODE,
        )
        room_setpoint = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.ROOM_MANUAL_SETPOINT, offset=zone_register_offset
            ),
            variable=ZoneRegisters.ROOM_MANUAL_SETPOINT,
        )
        dhw_comfort_setpoint = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.DHW_COMFORT_SETPOINT, offset=zone_register_offset
            ),
            variable=ZoneRegisters.DHW_COMFORT_SETPOINT,
        )
        dhw_calorifier_hysterisis = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.DHW_CALORIFIER_HYSTERISIS,
                offset=zone_register_offset,
            ),
            variable=ZoneRegisters.DHW_CALORIFIER_HYSTERISIS,
        )
        selected_schedule = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
                offset=zone_register_offset,
            ),
            variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
        )
        room_temperature = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
                offset=zone_register_offset,
            ),
            variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
        )
        heating_mode = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.CURRENT_HEATING_MODE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.CURRENT_HEATING_MODE,
        )
        pump_running = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.PUMP_RUNNING, offset=zone_register_offset
            ),
            variable=ZoneRegisters.PUMP_RUNNING,
        )
        dhw_tank_temperature = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.DHW_TANK_TEMPERATURE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.DHW_TANK_TEMPERATURE,
        )

        if zone_type == ClimateZoneType.NOT_PRESENT.value:
            _LOGGER.info(
                "Ignoring zone(zone_id=%d), because its type is NOT_PRESENT.", id
            )
            return None

        return ClimateZone(
            id=id,
            type=ClimateZoneType(zone_type),
            function=ClimateZoneFunction(zone_function),
            short_name=zone_short_name,
            owning_device=None if owning_device is None else int(owning_device),
            mode=ClimateZoneMode(zone_mode),
            selected_schedule=None
            if selected_schedule is None
            else ClimateZoneScheduleId(selected_schedule),
            heating_mode=None
            if heating_mode is None
            else ClimateZoneHeatingMode(heating_mode),
            room_setpoint=room_setpoint,
            dhw_comfort_setpoint=dhw_comfort_setpoint,
            dhw_calorifier_hysterisis=dhw_calorifier_hysterisis,
            room_temperature=room_temperature,
            pump_running=bool(pump_running),
            dhw_tank_temperature=dhw_tank_temperature,
        )

    async def read_zone_update(self, zone: ClimateZone) -> ClimateZone:
        """Retrieve updates for a single ClimateZone.

        In attempt to reduce the amount of calls over the network, this only reads updatable fields from modbus and
        merges `zone` with the updates in a new returned `ClimateZone`. Only the base zone registers are mentioned
        here; add `512 * id` to get the discrete register number of the zone.
        For details, refer to the Remeha GTW-08 parameter list.

        | Base address  | Variable name                     | Description                                           | Modbus type   | HA type                   |
        |---------------|-----------------------------------|-------------------------------------------------------|---------------|---------------------------|
        |       649     | `parZoneMode`                     | Mode zone working.                                    |   `ENUM8`     | `ClimateZoneMode`         |
        |       664     | `parZoneRoomManualSetpoint`       | Manually set wished room temperature of the zone.     |   `UINT16`    | `float`                   |
        |       665     | `parZoneDhwComfortSetpoint`       | Wished comfort domestic hot water temperature.        |   `UINT16`    | `float`                   |
        |       686     | `parZoneDhwCalorifierHysterisis   | Hysterisis to start DHW tank load                     |   `UINT16`    | `float`                   |
        |       688     | `parZoneTimeProgramSelected`      | Time program selected by the user.                    |   `ENUM8`     | `ClimateZoneScheduleId`   |
        |      1104     | `varZoneTRoom`                    | Current room temperature for zone.                    |   `INT16`     | `float`                   |
        |      1109     | `varZoneCurrentHeatingMode`       | Current mode the zone is functioning in.              |   `ENUM8`     | `ClimateZoneHeatingMode`  |
        |      1110     | `varZonePumpRunning`              | Whether the zone pump is ruinning.                    |   `ENUM8`     | `bool`                    |
        |      1119     | `varDhwTankTemperature`           | Tank temperature DHW tank (bottom or single sensor)   |   `INT16`     | `float`                   |


        Args:
            zone (ClimateZone): The zone to update.

        Returns:
            `ClimateZone`: The updated zone.

        Raises:
            `ModbusException`: If the zone update registers cannot be read.
            `ValueError`: If deserializing any register fails.

        """

        zone_register_offset: int = self.get_zone_register_offset(zone)

        zone_mode = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.MODE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.MODE,
        )
        room_setpoint = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.ROOM_MANUAL_SETPOINT, offset=zone_register_offset
            ),
            variable=ZoneRegisters.ROOM_MANUAL_SETPOINT,
        )
        dhw_comfort_setpoint = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.DHW_COMFORT_SETPOINT, offset=zone_register_offset
            ),
            variable=ZoneRegisters.DHW_COMFORT_SETPOINT,
        )
        dhw_calorifier_hysterisis = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.DHW_CALORIFIER_HYSTERISIS,
                offset=zone_register_offset,
            ),
            variable=ZoneRegisters.DHW_CALORIFIER_HYSTERISIS,
        )
        selected_schedule = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
                offset=zone_register_offset,
            ),
            variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
        )
        room_temperature = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
                offset=zone_register_offset,
            ),
            variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
        )
        heating_mode = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.CURRENT_HEATING_MODE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.CURRENT_HEATING_MODE,
        )
        pump_running = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.PUMP_RUNNING, offset=zone_register_offset
            ),
            variable=ZoneRegisters.PUMP_RUNNING,
        )
        dhw_tank_temperature = deserialize(
            response=await self._read_variable(
                variable=ZoneRegisters.DHW_TANK_TEMPERATURE, offset=zone_register_offset
            ),
            variable=ZoneRegisters.DHW_TANK_TEMPERATURE,
        )

        # Merge old and new zone.
        return ClimateZone(
            id=zone.id,
            type=zone.type,
            function=zone.function,
            short_name=zone.short_name,
            owning_device=zone.owning_device,
            mode=ClimateZoneMode(zone_mode),
            selected_schedule=None
            if selected_schedule is None
            else ClimateZoneScheduleId(selected_schedule),
            heating_mode=None
            if heating_mode is None
            else ClimateZoneHeatingMode(heating_mode),
            room_setpoint=room_setpoint,
            dhw_comfort_setpoint=dhw_comfort_setpoint,
            dhw_calorifier_hysterisis=dhw_calorifier_hysterisis,
            room_temperature=room_temperature,
            pump_running=bool(pump_running),
            dhw_tank_temperature=dhw_tank_temperature,
        )

    async def async_write_enum(
        self, variable: ModbusVariableDescription, value: Enum | None, offset: int = 0
    ) -> None:
        """Write the given enum value to the modbus device.

        Args:
            variable (ModbusVariableDescription): The description of the variable to write.
            value (Enum | None): The value to write. If `None`, the modbus NULL value is written instead, if the spec allows it.
            offset (int): The offset in registers of `variable.start_address`. Used for zone- and device objects.

        Raises:
            TypeError: If `value` is not an `Enum` or `None`.
            ModbusException: If the connection to the modbus device is lost or if the write request fails.
            ValueError:
                * If no conversion path exists between `variable.data_type` and `value`
                * If conversion to a numeric type fails.
                * If `value` is a `tuple` which does not contain exactly two elements.

        """
        if value is None:
            await self.async_write_primitive(
                variable=variable, value=None, offset=offset
            )
        elif isinstance(value, Enum):
            await self.async_write_primitive(
                variable=variable, value=value.value, offset=offset
            )
        else:
            raise TypeError(
                f"Expect value to be an Enum or None, but got {type(value).__name__}"
            )

    async def async_write_primitive(
        self,
        variable: ModbusVariableDescription,
        value: str
        | float
        | bool
        | tuple[int, int]
        | bytes
        | Callable[[], bytes]
        | None,
        offset: int = 0,
    ) -> None:
        """Write a single primitive value to the modbus device.

        ### Notes:
            * If `value` is a tuple, the whole tuple must fit in a single register, contain exactly two elements that are both treated as unsigned bytes.
                Therefore the individual values cannot exceed 2^8.

        Args:
            variable (ModbusVariableDescription): The description of the variable to write.
            value (str|float|bool|tuple[int,int]|bytes|(() -> bytes)|None): The value to write. If `None`, the modbus NULL value is written instead, if the spec allows it.
            offset (int): The offset in registers of `variable.start_address`. Used for zone- and device objects.

        Raises:
            ModbusException: If the connection to the modbus device is lost or if the write request fails.
            ValueError:
                * If no conversion path exists between `variable.data_type` and `value`
                * If conversion to a numeric type fails.
                * If `value` is a `tuple` which does not contain exactly two elements.

        """

        await self._write_registers(
            variable=variable,
            registers=serialize(variable=variable, value=value),
            offset=offset,
        )


class RemehaModbusSocketApi(RemehaApi):
    """Implementation of the Remeha modbus API that connects to the modbus device through a socket."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int = 502,
        connection_type: ConnectionType = ConnectionType.RTU_OVER_TCP,
        device_address: int = 100,
    ):
        """Create a new API with a socket connection to the modbus device."""

        super().__init__(
            name=name, connection_type=connection_type, device_address=device_address
        )

        if connection_type in [
            ConnectionType.TCP,
            ConnectionType.UDP,
            ConnectionType.RTU_OVER_TCP,
        ]:
            self._host: str = host
            self._port: int = port

            # Create the appropriate client type, but do not yet connect.
            match self._connection_type:
                case ConnectionType.TCP:
                    self._client = ModbusClient.AsyncModbusTcpClient(
                        host=self._host,
                        port=self._port,
                        framer=FramerType.SOCKET,
                        timeout=5,
                    )
                case ConnectionType.UDP:
                    self._client = ModbusClient.AsyncModbusUdpClient(
                        host=self._host,
                        port=self._port,
                        framer=FramerType.SOCKET,
                        timeout=5,
                    )
                case ConnectionType.RTU_OVER_TCP:
                    self._client = ModbusClient.AsyncModbusTcpClient(
                        host=self._host,
                        port=self._port,
                        framer=FramerType.RTU,
                        timeout=5,
                    )
        else:
            raise ModbusException(
                f"Connection type [{connection_type}] is unsupported within a socket-based API."
            )

    def host(self) -> str:
        """Return the hostname or IP address of the modbus device."""
        return self._host

    def port(self) -> int:
        """Return the port number at which the modbus device listens."""
        return self._port


class RemehaModbusSerialApi(RemehaApi):
    """Implementation of the Remeha modbus API that connects to the modbus device through a serial or USB port."""

    def __init__(
        self,
        name: str,
        port: str,
        baudrate: int = 19200,
        bytesize: int = 8,
        method: SerialConnectionMethod = SerialConnectionMethod.RTU,
        parity: str = "N",
        stopbits: int = 2,
        device_address: int = 1,
    ):
        """Create a new API with a serial connection to the modbus device."""

        super().__init__(
            name=name,
            connection_type=ConnectionType.SERIAL,
            device_address=device_address,
        )

        # Assume self._connection_type is SERIAL
        self._client = ModbusClient.AsyncModbusSerialClient(
            port=port,
            baudrate=baudrate,
            bytesize=bytesize,
            framer=method,
            parity=parity,
            stopbits=stopbits,
        )

        self._port: str = port
        self._baudrate: int = baudrate
        self._bytesize: int = bytesize
        self._method: SerialConnectionMethod = method
        self._parity: str = parity
        self._stopbits: int = stopbits

    def port(self) -> int:
        """Return the serial port or USB device where the modbus device is connected to the Home Assistant host."""
        return self._port

    def baudrate(self) -> int:
        """Return the speed of the serial connection."""
        return self._baudrate

    def bytesize(self) -> int:
        """Return the data size in bits of each byte."""
        return self._bytesize

    def method(self) -> SerialConnectionMethod:
        """Return the serial connection method."""
        return self._method

    def parity(self) -> str:
        """Return the parity of the data bytes."""
        return self._parity

    def stopbits(self) -> int:
        """Return the stopbits of the data bytes."""
        return self._stopbits
