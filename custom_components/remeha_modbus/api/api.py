"""Implementation of the Remeha Modbus API."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, StrEnum, auto
from types import MappingProxyType
from typing import Any, Self

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from pymodbus import FramerType, ModbusException
from pymodbus import client as ModbusClient
from pymodbus.client import (
    AsyncModbusSerialClient,
    AsyncModbusTcpClient,
    AsyncModbusUdpClient,
    ModbusBaseClient,
)
from pymodbus.pdu import ModbusPDU

from custom_components.remeha_modbus.const import (
    MODBUS_DEVICE_ADDRESS,
    MODBUS_SERIAL_BAUDRATE,
    MODBUS_SERIAL_BYTESIZE,
    MODBUS_SERIAL_METHOD,
    MODBUS_SERIAL_PARITY,
    MODBUS_SERIAL_STOPBITS,
    REMEHA_DEVICE_INSTANCE_RESERVED_REGISTERS,
    REMEHA_ZONE_RESERVED_REGISTERS,
    DataType,
    DeviceInstanceRegisters,
    MetaRegisters,
    ModbusVariableDescription,
    ZoneRegisters,
)
from custom_components.remeha_modbus.helpers.gtw08 import TimeOfDay
from custom_components.remeha_modbus.helpers.modbus import from_registers, to_registers

from .appliance import Appliance, ApplianceErrorPriority, ApplianceStatus, SeasonalMode
from .climate_zone import (
    ClimateZone,
    ClimateZoneFunction,
    ClimateZoneHeatingMode,
    ClimateZoneMode,
    ClimateZoneScheduleId,
    ClimateZoneType,
)

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

    MK = int("14", 16)
    """Appliance control panel like eTwist"""

    SCB = int("19", 16)
    """Circuit control board"""

    EEC = int("1b", 16)
    """Motherboard for gas boilers like GAS 120 Ace"""

    GATEWAY = int("1e", 16)
    """A gateway, for example GTW-08 (modbus gateway)"""

    def is_mainboard(self) -> bool:
        """Return whether this value represents a mainboard, a.k.a. the main device."""

        return self in [
            DeviceBoardType.CU_GH,
            DeviceBoardType.CU_OH,
            DeviceBoardType.EHC,
            DeviceBoardType.EEC,
        ]


@dataclass(eq=False)
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

    def __eq__(self, other) -> bool:
        """Compare this `DeviceBoardCategory` to another for equality.

        Only `type` is used to determine equality, since the generation might change.

        Returns:
            `bool`: `True` if the objects are considered equal, `False` otherwise.

        """

        if isinstance(other, self.__class__):
            return self.type == other.type

        return False

    def __hash__(self):
        """Return a hash of this device board category."""

        return hash(self.type)


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

    def is_mainboard(self) -> bool:
        """Return whether this device is a mainboard."""

        return self.board_category.type.is_mainboard()

    def __eq__(self, other) -> bool:
        """Compare this `DeviceInstance` with another for equality.

        Only `id` and `board_category` are considered, to allow HA to update
        the device info after it gets a software upgrade for example.

        Returns:
            `bool`: `True` if the objects are considered equal, `False` otherwise.

        """
        if isinstance(other, self.__class__):
            return self.id == other.id and self.board_category == other.board_category

        return False

    def __hash__(self):
        """Return a hash of this device instance."""
        return hash((self.id, self.board_category))


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


#################################
###     remeha_modbus API     ###
#################################


class RemehaApi:
    """Use instances of this class to interact with the Remeha device through Modbus."""

    def __init__(
        self,
        name: str,
        connection_type: ConnectionType,
        client: ModbusClient.ModbusBaseClient,
        device_address: int = 1,
    ):
        """Create a new API instance."""
        self._client: ModbusClient.ModbusBaseClient = client

        self._name = name
        self._connection_type = connection_type
        self._device_address = device_address
        self._lock = asyncio.Lock()
        self._message_delay_seconds: int | None = 10 / 1000  # 10ms

    @classmethod
    def create(cls, name: str, config: MappingProxyType[str, Any]) -> Self:
        """Create a new `RemehaApi` instance.

        Args:
            name (str): The name of the modbus hub name.
            config (MappingProxyType[str, Any]): The dict containing the configuration of the related `ConfigEntry`.

        """
        connection_type: ConnectionType = config[CONF_TYPE]
        client: ModbusBaseClient
        match connection_type:
            case ConnectionType.SERIAL:
                client = AsyncModbusSerialClient(
                    port=config[CONF_PORT],
                    baudrate=config[MODBUS_SERIAL_BAUDRATE],
                    bytesize=config[MODBUS_SERIAL_BYTESIZE],
                    framer=config[MODBUS_SERIAL_METHOD],
                    parity=config[MODBUS_SERIAL_PARITY],
                    stopbits=config[MODBUS_SERIAL_STOPBITS],
                )
            case ConnectionType.TCP:
                client = AsyncModbusTcpClient(
                    host=config[CONF_HOST],
                    port=int(config[CONF_PORT]),
                    framer=FramerType.SOCKET,
                    timeout=5,
                )
            case ConnectionType.UDP:
                client = AsyncModbusUdpClient(
                    host=config[CONF_HOST],
                    port=int(config[CONF_PORT]),
                    framer=FramerType.SOCKET,
                    timeout=5,
                )
            case ConnectionType.RTU_OVER_TCP:
                client = AsyncModbusTcpClient(
                    host=config[CONF_HOST],
                    port=int(config[CONF_PORT]),
                    framer=FramerType.RTU,
                    timeout=5,
                )

        return RemehaApi(
            name=name,
            connection_type=connection_type,
            client=client,
            device_address=config[MODBUS_DEVICE_ADDRESS],
        )

    @property
    def name(self) -> str:
        """Return the modbus hub name."""
        return self._name

    @property
    def connection_type(self) -> ConnectionType:
        """Return the modbus connection type."""
        return self._connection_type

    @property
    async def async_is_connected(self) -> bool:
        """Return whether we're connected to the modbus device."""
        async with self._lock:
            return self._client.connected

    @property
    async def async_is_cooling_forced(self) -> bool:
        """Return whether the appliance is in forced cooling mode."""

        return from_registers(
            registers=await self._async_read_registers(variable=MetaRegisters.COOLING_FORCED),
            destination_variable=MetaRegisters.COOLING_FORCED,
        )

    async def async_connect(self) -> bool:
        """Connect to the configured modbus device."""

        async with self._lock:
            if not self._client.connected:
                return await self._client.connect()

            return True

    async def async_close(self) -> None:
        """Close the connection to the configured modbus device."""

        async with self._lock:
            if self._client.connected:
                try:
                    self._client.close()
                except ModbusException as ex:
                    _LOGGER.error("Error while closing modbus client", exc_info=ex)

                _LOGGER.info("Modbus connection closed.")

    async def _async_read_registers(
        self, variable: ModbusVariableDescription, offset: int = 0
    ) -> list[int]:
        """Read the registers representing the requested variable from the modbus device.

        The actual amount of registers to read is calculated based on `variable.data_type`.

        Args:
            variable (ModbusVariableDescription): The variable to retrieve.
            offset (int): The offset for `variable.start_address`, in registers. Used for zone and device info registers.

        Returns:
            list[int]: The requested registers.

        Raises:
            ModbusException: If the connection to the modbus device is lost or if the request fails.
            ValueError: If the required register count cannot be calculated.

        """

        async def _async_ensure_connected() -> None:
            """Ensure that we're connected or raise an exception."""
            if not self._client.connected and not await self._client.connect():
                raise ModbusException("Connection to modbus device lost.")

        if self._message_delay_seconds is not None:
            # Let the modbus device catch its breath.
            await asyncio.sleep(self._message_delay_seconds)

        await _async_ensure_connected()
        response: ModbusPDU = await self._client.read_holding_registers(
            address=variable.start_address + offset,
            count=variable.count,
            slave=self._device_address,
        )
        if response.isError():
            raise ModbusException(
                "Modbus device returned an error while reading holding registers."
            )

        return response.registers

    async def _async_write_registers(
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

        async def _async_ensure_connected() -> None:
            if not self._client.connected and not await self._client.connect():
                raise ModbusException("Connection to modbus device lost.")

        async with self._lock:
            await _async_ensure_connected()
            response: ModbusPDU = await self._client.write_registers(
                address=variable.start_address + offset,
                values=registers,
                slave=self._device_address,
            )
            if response.isError():
                raise ModbusException("Modbus device returned an error while writing registers.")

    def get_zone_register_offset(self, zone: ClimateZone | int) -> int:
        """Get the offset in registers for the given `ClimateZone | int`."""
        zone_id: int = zone.id if isinstance(zone, ClimateZone) else zone
        return (zone_id - 1) * REMEHA_ZONE_RESERVED_REGISTERS

    def get_device_register_offset(self, device: DeviceInstance | int) -> int:
        """Get the offset in registers for the given `DeviceInfo | int`."""

        device_id: int = device.id if isinstance(device, DeviceInstance) else device
        return device_id * REMEHA_DEVICE_INSTANCE_RESERVED_REGISTERS

    async def async_health_check(self) -> None:
        """Attempt to check the system health by reading a single register (128 - numberOfDevices).

        Raises
        ------
            `ModbusException` - if the health check is unsuccessful.

        """
        try:
            await self.async_read_number_of_device_instances()
        except ValueError as ex:
            raise ModbusException from ex

        _LOGGER.debug("Modbus health check successful")

    async def async_read_device_instances(self) -> list[DeviceInstance]:
        """Retrieve the available devices instances of the Remeha appliance.

        Returns
            `list[DeviceInstance]`: A list of all discovered device instances.

        Raises
            `ModbusException`: If the list of device instances cannot be obtained.

        """

        number_of_instances: int = await self.async_read_number_of_device_instances()
        return [
            instance
            for instance in [
                await self.async_read_device_instance(instance_id)
                for instance_id in range(number_of_instances)
            ]
            if instance is not None
        ]

    async def async_read_number_of_device_instances(self) -> int:
        """Retrieve the number of available  device instances in the appliance.

        Returns
            `int`: The number of instances.

        Raises
            `ModbusException`: If the number of instances cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be deserialized successfully.

        """

        return from_registers(
            registers=await self._async_read_registers(variable=MetaRegisters.NUMBER_OF_DEVICES),
            destination_variable=MetaRegisters.NUMBER_OF_DEVICES,
        )

    async def async_read_device_instance(self, id: int) -> DeviceInstance:
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
        board_category = from_registers(
            registers=await self._async_read_registers(
                variable=DeviceInstanceRegisters.TYPE_BOARD,
                offset=device_register_offset,
            ),
            destination_variable=DeviceInstanceRegisters.TYPE_BOARD,
        )
        sw_version = from_registers(
            registers=await self._async_read_registers(
                variable=DeviceInstanceRegisters.SW_VERSION,
                offset=device_register_offset,
            ),
            destination_variable=DeviceInstanceRegisters.SW_VERSION,
        )
        hw_version = from_registers(
            registers=await self._async_read_registers(
                variable=DeviceInstanceRegisters.HW_VERSION,
                offset=device_register_offset,
            ),
            destination_variable=DeviceInstanceRegisters.HW_VERSION,
        )
        article_number = from_registers(
            registers=await self._async_read_registers(
                variable=DeviceInstanceRegisters.ARTICLE_NUMBER,
                offset=device_register_offset,
            ),
            destination_variable=DeviceInstanceRegisters.ARTICLE_NUMBER,
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

    async def async_read_appliance(self) -> Appliance:
        """Read the appliance status registers.

        Returns:
            `Appliance`: The appliance with its status fields.

        Raises:
            `ModbusException`: If the appliance status fields cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be successfully deserialized.

        """

        current_error: int = from_registers(
            registers=await self._async_read_registers(variable=MetaRegisters.CURRENT_ERROR),
            destination_variable=MetaRegisters.CURRENT_ERROR,
        )

        raw_error_priority = from_registers(
            registers=await self._async_read_registers(variable=MetaRegisters.ERROR_PRIORITY),
            destination_variable=MetaRegisters.ERROR_PRIORITY,
        )

        error_priority: ApplianceErrorPriority = (
            ApplianceErrorPriority(raw_error_priority)
            if raw_error_priority
            else ApplianceErrorPriority.NO_ERROR
        )
        appliance_status: ApplianceStatus = ApplianceStatus(
            bits=(
                from_registers(
                    registers=await self._async_read_registers(
                        variable=MetaRegisters.APPLIANCE_STATUS_1
                    ),
                    destination_variable=MetaRegisters.APPLIANCE_STATUS_1,
                ),
                from_registers(
                    registers=await self._async_read_registers(
                        variable=MetaRegisters.APPLIANCE_STATUS_2
                    ),
                    destination_variable=MetaRegisters.APPLIANCE_STATUS_2,
                ),
            )
        )

        season_mode: SeasonalMode = SeasonalMode(
            from_registers(
                registers=await self._async_read_registers(variable=MetaRegisters.SEASON_MODE),
                destination_variable=MetaRegisters.SEASON_MODE,
            )
        )

        return Appliance(
            current_error=current_error,
            error_priority=error_priority,
            status=appliance_status,
            season_mode=season_mode,
        )

    async def async_read_sensor_values(
        self, descriptions: list[ModbusVariableDescription]
    ) -> dict[ModbusVariableDescription, Any]:
        """Read the values of the given list of variable descriptions.

        Args:
            descriptions (list[ModbusVariableDescription]): The list of modbus variables to retrieve.

        Returns:
            dict[ModbusVariableDescription, Any]: A mapping from modbus variables to their values.

        """

        return dict(
            zip(
                descriptions,
                [
                    from_registers(
                        registers=await self._async_read_registers(variable=d),
                        destination_variable=d,
                    )
                    for d in descriptions
                ],
                strict=True,
            )
        )

    async def async_read_zones(self) -> list[ClimateZone]:
        """Retrieve the available zones of the modbus device.

        This method returns the all zones having a supported `ClimateZoneFunction`.
        Whether a zone function is supported can be queried using `ClimateZoneFunction.is_supported()`

        Returns
            `list[ClimateZone]`: A list of all discovered zones.

        Raises
            `ModbusException`: If the list of zones cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be successfully deserialized.

        """

        number_of_zones: int = await self.async_read_number_of_zones()
        return [
            zone
            for zone in [
                await self.async_read_zone(zone_id) for zone_id in range(1, number_of_zones + 1)
            ]
            if zone is not None
        ]

    async def async_read_number_of_zones(self) -> int:
        """Retrieve the number of zones defined in the appliance.

        Returns
            `int`: The number of zones.

        Raises
            `ModbusException`: If the number of zones cannot be obtained.
            `ValueError`: If the retrieved modbus data cannot be deserialized successfully.

        """
        return from_registers(
            registers=await self._async_read_registers(variable=MetaRegisters.NUMBER_OF_ZONES),
            destination_variable=MetaRegisters.NUMBER_OF_ZONES,
        )

    async def async_read_zone(self, id: int) -> ClimateZone | None:
        """Read a single climate zone from the modbus interface.

        This reads the registers as described in the table below. Only the base zone registers
        are mentioned here; add `512 * id` to get the discrete register number of the zone.
        For details, refer to the Remeha GTW-08 parameter list.

        | Base address  | Variable name                     | Description                                           | Modbus type   | HA type                   |
        |---------------|-----------------------------------|-------------------------------------------------------|---------------|---------------------------|
        |       640     | `varZoneType`                     | Zone type.                                            |   `ENUM8`     | `ClimateZoneType`         |
        |       641     | `parZoneFunction`                 | Zone function.                                        |   `ENUM8`     | `ClimateZoneFunction`     |
        |       642     | `parZoneFriendlyNameShort`        | Zone short name.                                      |   `STRING`    | `str`                     |
        |       646     | `instance`                        | Device instance owning the zone.                      |   `UINT8`     | `int`                     |
        |       649     | `parZoneMode`                     | Mode zone working.                                    |   `ENUM8`     | `ClimateZoneMode`         |
        |       664     | `parZoneRoomManualSetpoint`       | Manually set wished room temperature of the zone.     |   `UINT16`    | `float`                   |
        |       665     | `parZoneDhwComfortSetpoint`       | Wished comfort domestic hot water temperature.        |   `UINT16`    | `float`                   |
        |       666     | `parZoneDhwReducedSetpoint`       | Wished reduced domestic hot water temperature.        |   `UINT16`    | `float`                   |
        |       686     | `parZoneDhwCalorifierHysteresis`  | Hysteresis to start DHW tank load                     |   `UINT16`    | `float`                   |
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

        zone_type = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.TYPE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.TYPE,
        )

        # Bail out if the zone is not present.
        if zone_type == ClimateZoneType.NOT_PRESENT.value:
            _LOGGER.info("Ignoring zone(zone_id=%d), because its type is NOT_PRESENT.", id)
            return None

        zone_function = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.FUNCTION, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.FUNCTION,
        )
        zone_short_name = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.SHORT_NAME, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.SHORT_NAME,
        )
        owning_device = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.OWNING_DEVICE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.OWNING_DEVICE,
        )
        zone_mode = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.MODE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.MODE,
        )
        temporary_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.TEMPORARY_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.TEMPORARY_SETPOINT,
        )
        room_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.ROOM_MANUAL_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.ROOM_MANUAL_SETPOINT,
        )
        dhw_comfort_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_COMFORT_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.DHW_COMFORT_SETPOINT,
        )
        dhw_reduced_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_REDUCED_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.DHW_REDUCED_SETPOINT,
        )
        dhw_calorifier_hysteresis = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_CALORIFIER_HYSTERESIS,
                offset=zone_register_offset,
            ),
            destination_variable=ZoneRegisters.DHW_CALORIFIER_HYSTERESIS,
        )
        end_time_temporary_override = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.END_TIME_MODE_CHANGE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.END_TIME_MODE_CHANGE,
        )
        selected_schedule = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
                offset=zone_register_offset,
            ),
            destination_variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
        )
        room_temperature = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
                offset=zone_register_offset,
            ),
            destination_variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
        )
        heating_mode = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.CURRENT_HEATING_MODE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.CURRENT_HEATING_MODE,
        )
        pump_running = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.PUMP_RUNNING, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.PUMP_RUNNING,
        )
        dhw_tank_temperature = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_TANK_TEMPERATURE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.DHW_TANK_TEMPERATURE,
        )

        return ClimateZone(
            id=id,
            type=ClimateZoneType(zone_type),
            function=ClimateZoneFunction(zone_function),
            short_name=zone_short_name,
            owning_device=None if owning_device is None else int(owning_device),
            mode=ClimateZoneMode(zone_mode),
            temporary_setpoint=temporary_setpoint,
            selected_schedule=(
                None if selected_schedule is None else ClimateZoneScheduleId(selected_schedule)
            ),
            heating_mode=(None if heating_mode is None else ClimateZoneHeatingMode(heating_mode)),
            room_setpoint=room_setpoint,
            dhw_comfort_setpoint=dhw_comfort_setpoint,
            dhw_reduced_setpoint=dhw_reduced_setpoint,
            dhw_calorifier_hysteresis=dhw_calorifier_hysteresis,
            temporary_setpoint_end_time=end_time_temporary_override,
            room_temperature=room_temperature,
            pump_running=bool(pump_running),
            dhw_tank_temperature=dhw_tank_temperature,
        )

    async def async_read_zone_update(self, zone: ClimateZone) -> ClimateZone:
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
        |       666     | `parZoneDhwReducedSetpoint`       | Wished reduced domestic hot water temperature.        |   `UINT16`    | `float`                   |
        |       686     | `parZoneDhwCalorifierHysteresis   | Hysteresis to start DHW tank load                     |   `UINT16`    | `float`                   |
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

        zone_mode = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.MODE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.MODE,
        )
        temporary_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.TEMPORARY_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.TEMPORARY_SETPOINT,
        )
        room_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.ROOM_MANUAL_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.ROOM_MANUAL_SETPOINT,
        )
        dhw_comfort_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_COMFORT_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.DHW_COMFORT_SETPOINT,
        )
        dhw_reduced_setpoint = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_REDUCED_SETPOINT, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.DHW_REDUCED_SETPOINT,
        )
        dhw_calorifier_hysteresis = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_CALORIFIER_HYSTERESIS,
                offset=zone_register_offset,
            ),
            destination_variable=ZoneRegisters.DHW_CALORIFIER_HYSTERESIS,
        )
        end_time_temporary_override = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.END_TIME_MODE_CHANGE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.END_TIME_MODE_CHANGE,
        )
        selected_schedule = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
                offset=zone_register_offset,
            ),
            destination_variable=ZoneRegisters.SELECTED_TIME_PROGRAM,
        )
        room_temperature = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
                offset=zone_register_offset,
            ),
            destination_variable=ZoneRegisters.CURRENT_ROOM_TEMPERATURE,
        )
        heating_mode = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.CURRENT_HEATING_MODE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.CURRENT_HEATING_MODE,
        )
        pump_running = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.PUMP_RUNNING, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.PUMP_RUNNING,
        )
        dhw_tank_temperature = from_registers(
            registers=await self._async_read_registers(
                variable=ZoneRegisters.DHW_TANK_TEMPERATURE, offset=zone_register_offset
            ),
            destination_variable=ZoneRegisters.DHW_TANK_TEMPERATURE,
        )

        # Merge old and new zone.
        return ClimateZone(
            id=zone.id,
            type=zone.type,
            function=zone.function,
            short_name=zone.short_name,
            owning_device=zone.owning_device,
            mode=ClimateZoneMode(zone_mode),
            temporary_setpoint=temporary_setpoint,
            selected_schedule=(
                None if selected_schedule is None else ClimateZoneScheduleId(selected_schedule)
            ),
            heating_mode=(None if heating_mode is None else ClimateZoneHeatingMode(heating_mode)),
            room_setpoint=room_setpoint,
            dhw_comfort_setpoint=dhw_comfort_setpoint,
            dhw_reduced_setpoint=dhw_reduced_setpoint,
            dhw_calorifier_hysteresis=dhw_calorifier_hysteresis,
            temporary_setpoint_end_time=end_time_temporary_override,
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
            value (Enum | None): The value to write. If `None`, the GTW-08 NULL value is written instead.
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
            await self.async_write_primitive(variable=variable, value=None, offset=offset)
        elif isinstance(value, Enum):
            await self.async_write_primitive(variable=variable, value=value.value, offset=offset)
        else:
            raise TypeError(f"Expect value to be an Enum or None, but got {type(value).__name__}")

    async def async_write_primitive(
        self,
        variable: ModbusVariableDescription,
        value: str | float | bool | tuple[int, int] | datetime | None,
        offset: int = 0,
    ) -> None:
        """Write a single primitive value to the modbus device.

        ### Notes:
            * If `value` is a tuple, the whole tuple must fit in a single register, contain exactly two elements that are both treated as unsigned bytes.
                Therefore the individual values cannot exceed 2^8.
            * Values of type `datatype` are only allowed when `variable.data_type == DataType.CIA_301_TIME_OF_DAY`.

        Args:
            variable (ModbusVariableDescription): The description of the variable to write.
            value (str|float|bool|tuple[int,int]|datetime|None): The value to write. If `None`, the GTW-08 NULL value is written instead.
            offset (int): The offset in registers of `variable.start_address`. Used for zone- and device objects.

        Raises:
            ModbusException: If the connection to the modbus device is lost or if the write request fails.
            ValueError:
                * If no conversion path exists between `variable.data_type` and `value`
                * If conversion to a numeric type fails.
                * If `value` is a `tuple` which does not contain exactly two elements.
                * If `value` is a `datetime` but `variable.data_type is not DataType.CIA_301_TIME_OF_DAY`.

        """

        if isinstance(value, datetime):
            if variable.data_type is not DataType.CIA_301_TIME_OF_DAY:
                raise ValueError(
                    f"No conversion path from {type(value).__qualname__} to modbus data type {variable.data_type.name}."
                )

            value = TimeOfDay.to_bytes(value)

        await self._async_write_registers(
            variable=variable,
            registers=to_registers(source_variable=variable, value=value),
            offset=offset,
        )
