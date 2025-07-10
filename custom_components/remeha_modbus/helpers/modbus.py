"""Modbus helper functions."""

import logging
from typing import Final

from pymodbus.client.mixin import ModbusClientMixin

from custom_components.remeha_modbus.const import DataType, ModbusVariableDescription

_LOGGER = logging.getLogger(__name__)

NULL_VALUES: Final[dict[DataType, int | bytes]] = {
    DataType.UINT8: int.from_bytes(b"\xff"),
    DataType.UINT16: int.from_bytes(b"\x00\xff", byteorder="little"),
    DataType.UINT32: int.from_bytes(b"\x00\x00\xff\xff", byteorder="little"),
    DataType.INT16: int.from_bytes(b"\x80\x00", signed=True, byteorder="little"),
    DataType.INT32: int.from_bytes(b"\x80\x00\x00\x00", signed=True, byteorder="little"),
    DataType.CIA_301_TIME_OF_DAY: b"\xff\x00\xff\x00\xff\x00",
    DataType.ZONE_TIME_PROGRAM: b"\xff\x00\xff\x00\xff\x00\xff\x00\xff\x00\xff\x00\xff\x00\xff\x00\xff\x00\xff\x00",
}


HA_TO_PYMODBUS_TYPE: Final[dict[DataType, ModbusClientMixin.DATATYPE]] = {
    DataType.INT16: ModbusClientMixin.DATATYPE.INT16,
    DataType.INT32: ModbusClientMixin.DATATYPE.INT32,
    DataType.INT64: ModbusClientMixin.DATATYPE.INT64,
    DataType.UINT8: ModbusClientMixin.DATATYPE.UINT16,
    DataType.UINT16: ModbusClientMixin.DATATYPE.UINT16,
    DataType.UINT32: ModbusClientMixin.DATATYPE.UINT32,
    DataType.UINT64: ModbusClientMixin.DATATYPE.UINT64,
    DataType.FLOAT32: ModbusClientMixin.DATATYPE.FLOAT32,
    DataType.FLOAT64: ModbusClientMixin.DATATYPE.FLOAT64,
    DataType.STRING: ModbusClientMixin.DATATYPE.STRING,
    DataType.TUPLE16: ModbusClientMixin.DATATYPE.UINT16,
}


def _is_gtw08_null_value(variable: ModbusVariableDescription, val: int | bytes) -> bool:
    if variable.data_type in NULL_VALUES:
        return val == NULL_VALUES[variable.data_type]

    return val is None


def _to_gtw08_null_value(data_type: DataType) -> int | bytes:
    if data_type in NULL_VALUES:
        return NULL_VALUES[data_type]

    return None


def _from_registers(
    variable: ModbusVariableDescription, registers: list[int]
) -> str | int | float | tuple[int, int] | bytes | None:
    # If variable requires a bytes result, use our own conversion since the ModbusClientMixin doesn't support them.
    val = (
        bytes_from_registers(registers=registers)
        if variable.data_type in [DataType.CIA_301_TIME_OF_DAY, DataType.ZONE_TIME_PROGRAM]
        else ModbusClientMixin.convert_from_registers(
            registers=registers, data_type=HA_TO_PYMODBUS_TYPE[variable.data_type]
        )
    )

    # Post-process
    if _is_gtw08_null_value(variable=variable, val=val):
        return None
    if variable.data_type == DataType.TUPLE16:
        return tuple(int(val).to_bytes(2))
    if variable.data_type == DataType.UINT8:
        # Ignore the first byte to get a clean uint8
        val = val & int("00ff", 16)

    # Apply scale
    if variable.scale is not None:
        # Always round to 3 decimals when scaling.
        # HA frontend can always choose to show a less precise value.
        val = round(val * variable.scale, 3)

    return val


def _to_registers(
    source_variable: ModbusVariableDescription,
    value: str | float | bytes | None,
) -> list[int]:
    mixin_data_type: ModbusClientMixin.DATATYPE = HA_TO_PYMODBUS_TYPE.get(
        source_variable.data_type, None
    )

    if mixin_data_type is None and source_variable.data_type not in [
        DataType.CIA_301_TIME_OF_DAY,
        DataType.ZONE_TIME_PROGRAM,
    ]:
        raise ValueError(
            f"No conversion path from {source_variable.data_type.name} to a modbus data type."
        )

    # de-scale non-null values
    if value is not None and source_variable.scale is not None:
        # Do not round the value here, but let pymodbus do that if necessary.
        value: float = float(value) / source_variable.scale

        # Convert to int if integer value.
        if value.is_integer():
            value = int(value)

    # None-values might have to be GTW-08 null values.
    if value is None:
        value = _to_gtw08_null_value(source_variable.data_type)

    # bytes to registers does not go through the ModbusClientMixin, since it has no bytes support.
    if isinstance(value, bytes) and source_variable.data_type in [
        DataType.CIA_301_TIME_OF_DAY,
        DataType.ZONE_TIME_PROGRAM,
    ]:
        return [int.from_bytes(value[i : i + 2]) for i in range(0, len(value), 2)]

    return ModbusClientMixin.convert_to_registers(value=value, data_type=mixin_data_type)


def to_registers(
    source_variable: ModbusVariableDescription,
    value: str | float | tuple[int, int] | bytes | None,
) -> list[int]:
    """Serialize `value` to a list of modbus register values.

    ### Notes:
        * The type of `value` is assumed to equal or be convertible to `variable.data_type`.
        * If `value == None`, the appropriate GTW-08 `null` value is returned if the GTW-08 parameter list specifies it.
            If no `null`-value is defined for `variable.data_type`, `None` is returned.
        * If `value` is a tuple, the whole tuple must fit in a single register, contain exactly two elements that both have a
                value that fits in a single byte.
                Therefore the individual values cannot exceed 2^8.

    Args:
        source_variable (ModbusVariableDescription): The description of the variable to serialize.
        value (str|float|bool|tuple[int,int]|bytes|None))]): The value to serialize.

    Returns:
        `list[int]`: The list of modbus register values. `list[0]` corresponds to `variable.start_address`.

    Raises:
        ValueError:
            * If no conversion path exists between `variable.data_type` and `value`
            * If conversion to a numeric type fails.
            * If `value` is a `tuple` which does not contain exactly two elements.

    """

    # Convert the HA data type to a modbus data type.
    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError("tuple must exist of exactly two elements.")

        value = value[0] << 8 | value[1]

    return _to_registers(source_variable=source_variable, value=value)


def from_registers(
    registers: list[int],
    destination_variable: ModbusVariableDescription,
) -> str | int | float | tuple[int, int] | bytes | None:
    """Deserializes `response` into a value of type `data_type`.

    #### Scaling response values
        Response values can be scaled by providing `destination_variable.scale`.
        For example, reading the manual setpoint from register 664 (`parZoneRoomManualSetpoint`) returns
        the setpoint as an integer (the value has a scale of 0.1). So a setpoint of `21.5 'C` will be returned as `215`.
        In that case, set `scale` to the corresponding `0.1` to retrieve the scaled value.

    Args:
        registers (list[int]): The modbus registers (2 bytes per register). The modbus protocol describes a big-endian representation
            of addresses and data items. Therefore, this method assumes big-endian ordering of the registers and their values.
        destination_variable (ModbusVariableDescription): A computer readable description of the variable to deserialize into.

    Returns:
        The response, deserialized to the requested data type, or `None` if the response
        contains a GTW-08 null value.

    Raises:
        ValueError: If the response cannot be decoded as the requested data type or if `destination_variable.count` does
            not exactly match the register count.

    """

    # Ensure the required amount of registers.
    if len(registers) != destination_variable.count:
        raise ValueError(
            f"Got {len(registers)} registers, but deserializing to {destination_variable.data_type.name} requires {destination_variable.count}.",
        )

    return _from_registers(variable=destination_variable, registers=registers)


def bytes_from_registers(registers: list[int]) -> bytes:
    """Return the raw bytes from the given list of registers."""

    return b"".join([x.to_bytes(2) for x in registers])
